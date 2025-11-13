# core/entity/csr_entity.py
"""
ENTITY layer (aka repositories/services) for CSR features.
Only ORM/database logic lives here (no HTTP, no DRF objects).
Safe to unit test directly.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Dict, Any
from django.db import transaction
from django.db.models import Q, Count, F, QuerySet
from django.utils import timezone

from core.models import (
    Request, RequestStatus, ShortlistedRequest, CSRRep, CV, Notification,
    NotificationType, MatchQueue, MatchQueueStatus, ClaimReport, ClaimStatus,
    ServiceCategory, PersonInNeed,
)


# ---------- Dashboard / Listing ----------

class DashboardEntity:
    @staticmethod
    def today_active_requests(csr: CSRRep) -> QuerySet:
        """
        Active requests whose appointment date is today, belonging to CSR's company (if applicable).
        """
        today = timezone.localdate()
        qs = Request.objects.filter(
            status=RequestStatus.ACTIVE,
            appointment_date=today,
        ).select_related("pin", "cv")
        # If CSR should only see his company’s CV-assigned requests, filter by CV.company
        # return qs.filter(cv__company=csr.company) if needed
        return qs

    @staticmethod
    def committed_requests(csr: CSRRep) -> QuerySet:
        """
        All requests this CSR has committed to (any status).
        """
        return Request.objects.filter(
            committed_by_csr=csr
        ).select_related("pin", "cv")

    @staticmethod
    def recent_notifications(user, limit: int = 30) -> QuerySet:
        return Notification.objects.filter(
            recipient=user
        ).select_related("cv", "request")[:limit]


class RequestEntity:
    @staticmethod
    def get(request_id: str) -> Request:
        return Request.objects.select_related("pin", "cv", "committed_by_csr").get(pk=request_id)

    @staticmethod
    def available_requests() -> QuerySet:
        """
        Pool shown on Request Page (PENDING only).
        Includes shortlist count via annotation.
        """
        return (
            Request.objects.filter(status=RequestStatus.PENDING)
            .select_related("pin")
            .annotate(shortlist_count=Count("shortlisted_by"))
            .order_by("appointment_date", "appointment_time")
        )

    @staticmethod
    def coming_soon(days: int = 7) -> QuerySet:
        """
        PENDING requests with near appointment dates (next `days`).
        """
        today = timezone.localdate()
        return (
            Request.objects.filter(
                status=RequestStatus.PENDING,
                appointment_date__range=(today, today + timezone.timedelta(days=days)),
            )
            .select_related("pin")
            .annotate(shortlist_count=Count("shortlisted_by"))
            .order_by("appointment_date", "appointment_time")
        )

    @staticmethod
    @transaction.atomic
    def shortlist(csr: CSRRep, request_id: str) -> ShortlistedRequest:
        req = Request.objects.select_for_update().get(pk=request_id)
        sl, _ = ShortlistedRequest.objects.get_or_create(csr=csr, request=req)
        return sl

    @staticmethod
    @transaction.atomic
    def remove_shortlist(csr: CSRRep, request_id: str) -> None:
        ShortlistedRequest.objects.filter(
            csr=csr, request_id=request_id
        ).delete()

    @staticmethod
    @transaction.atomic
    def commit(csr: CSRRep, request_id: str) -> Request:
        """
        Commit = move from PENDING → COMMITTED and stamp committer/ts.
        Relies on model CheckConstraints to enforce integrity.
        """
        req = Request.objects.select_for_update().get(pk=request_id)
        if req.status != RequestStatus.PENDING:
            raise ValueError("Only PENDING requests can be committed.")
        req.status = RequestStatus.COMMITTED
        req.committed_by_csr = csr
        req.committed_at = timezone.now()
        req.save(update_fields=["status", "committed_by_csr", "committed_at", "updated_at"])
        return req


class ShortlistEntity:
    @staticmethod
    def list_shortlist(csr: CSRRep) -> QuerySet:
        return (
            ShortlistedRequest.objects.filter(
                csr=csr,
                request__status=RequestStatus.PENDING,
            )
            .select_related("request", "request__pin")
            .order_by("-created_at")
        )


class CommitEntity:
    @staticmethod
    def list_committed(csr: CSRRep) -> QuerySet:
        return Request.objects.filter(
            status=RequestStatus.COMMITTED, committed_by_csr=csr
        ).select_related("pin")


# ---------- Matching (Auto-suggest & Assignment Pool) ----------

@dataclass
class Suggestion:
    cv_id: str
    score: float
    reason: Dict[str, Any]


class MatchEntity:
    @staticmethod
    def _score_cv_for_request(req: Request, cv: CV) -> Tuple[float, Dict[str, Any]]:
        """
        Compute a simple match score using category + preferences (gender/language).
        Expand as needed (distance, historical performance, etc.).
        """
        score = 0.0
        reasons = {}

        # Category preference
        if cv.service_category_preference == req.service_type:
            score += 3.0
            reasons["category"] = True

        # PIN preferences
        pin: PersonInNeed = req.pin
        if pin.preferred_cv_gender and cv.gender == pin.preferred_cv_gender:
            score += 2.0
            reasons["gender"] = True
        if cv.main_language == pin.preferred_cv_language:
            score += 2.0
            reasons["language_main"] = True
        elif cv.second_language and cv.second_language == pin.preferred_cv_language:
            score += 1.0
            reasons["language_second"] = True

        # Sooner appointments = prioritise available CVs (placeholder +1)
        score += 1.0

        return score, reasons

    @staticmethod
    def suggest_top(req: Request, limit: int = 7) -> List[Suggestion]:
        cvs = CV.objects.select_related("company").all()
        scored: List[Suggestion] = []
        for cv in cvs:
            s, why = MatchEntity._score_cv_for_request(req, cv)
            if s > 0:
                scored.append(Suggestion(cv_id=cv.id, score=s, reason=why))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]

    @staticmethod
    @transaction.atomic
    def set_assignment_pool(request_id: str, cv_ids: List[str]) -> MatchQueue:
        """
        Select up to 3 CVs in order; create or update the MatchQueue.
        """
        if not (1 <= len(cv_ids) <= 3):
            raise ValueError("You must pick 1 to 3 CVs.")
        req = Request.objects.select_for_update().get(pk=request_id)
        cv_list = list(CV.objects.filter(id__in=cv_ids))
        # Preserve the order the CSR chose
        cv_map = {cv.id: cv for cv in cv_list}
        ordered = [cv_map[cid] for cid in cv_ids if cid in cv_map]
        if len(ordered) != len(cv_ids):
            raise ValueError("Some CVs not found.")

        qs = MatchQueue.objects.select_for_update()
        mq, created = qs.get_or_create(
            request=req,
            defaults={
                "cv1queue": ordered[0],
                "cv2queue": ordered[1] if len(ordered) > 1 else None,
                "cv3queue": ordered[2] if len(ordered) > 2 else None,
                "current_index": 1,
                "status": MatchQueueStatus.PENDING,
                "sent_at": None,
                "deadline": None,
            },
        )
        if not created:
            mq.cv1queue = ordered[0]
            mq.cv2queue = ordered[1] if len(ordered) > 1 else None
            mq.cv3queue = ordered[2] if len(ordered) > 2 else None
            mq.current_index = 1
            mq.status = MatchQueueStatus.PENDING
            mq.sent_at = None
            mq.deadline = None
            mq.save(update_fields=["cv1queue", "cv2queue", "cv3queue", "current_index", "status", "sent_at", "deadline"])
        else:
            mq.save()
        return mq


    @staticmethod
    def get_assignment_pool(request_id: str) -> Optional[MatchQueue]:
        try:
            return MatchQueue.objects.select_related(
                "cv1queue__company", "cv2queue__company", "cv3queue__company"
            ).get(request_id=request_id)
        except MatchQueue.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def send_offers(request_id: str, timeout_minutes: int = 30) -> MatchQueue:
        """
        Start the offer sequence — send to CV#1 (ACTIVE). Notifications recorded here.
        """
        req = Request.objects.select_for_update().get(pk=request_id)
        mq = MatchQueue.objects.select_for_update().get(request=req)

        # Move to ACTIVE and notify CV#1
        mq.status = MatchQueueStatus.ACTIVE
        mq.sent_at = timezone.now()
        mq.deadline = mq.sent_at + timezone.timedelta(minutes=timeout_minutes)
        mq.save(update_fields=["status", "sent_at", "deadline"])

        # Notify CSR user (recipient = CSRRep.user) and optionally the CV (if your app supports it)
        Notification.objects.create(
            recipient=req.committed_by_csr.user,  # CSR account user
            type=NotificationType.OFFER_SENT,
            message=f"Offer sent to CV #{mq.current_index} for {req.id}",
            request=req,
            cv=[mq.cv1queue, mq.cv2queue, mq.cv3queue][mq.current_index - 1] if mq.current_index <= 3 else None,
            meta={"rank": mq.current_index, "expires_at": mq.deadline.isoformat()},
        )
        return mq


class MatchProgressEntity:
    @staticmethod
    def _get_current_cv(mq: MatchQueue) -> Optional[CV]:
        if mq.current_index == 1:
            return mq.cv1queue
        if mq.current_index == 2:
            return mq.cv2queue
        if mq.current_index == 3:
            return mq.cv3queue
        return None

    @staticmethod
    @transaction.atomic
    def record_cv_decision(request_id: str, cv_id: str, accepted: bool) -> Request:
        """
        CV accepts or declines. On accept → match; on decline → advance.
        """
        
        req = Request.objects.select_for_update().get(pk=request_id)
        mq = MatchQueue.objects.select_for_update().get(request=req)

        current_cv = MatchProgressEntity._get_current_cv(mq)
        if not current_cv or current_cv.id != cv_id or mq.status != MatchQueueStatus.ACTIVE:
            raise ValueError("Invalid CV decision state.")

        if accepted:
            # Create the match
            req.cv = current_cv
            req.status = RequestStatus.ACTIVE
            req.save(update_fields=["cv", "status", "updated_at"])

            mq.status = MatchQueueStatus.FILLED
            mq.save(update_fields=["status"])

            Notification.objects.create(
                recipient=req.committed_by_csr.user,
                type=NotificationType.MATCH_ACCEPTED,
                message=f"{current_cv.name} accepted {req.id}.",
                request=req,
                cv=current_cv,
            )
            return req

        # Declined — advance
        Notification.objects.create(
            recipient=req.committed_by_csr.user,
            type=NotificationType.OFFER_DECLINED,
            message=f"{current_cv.name} declined {req.id}. Advancing.",
            request=req,
            cv=current_cv,
        )
        return MatchProgressEntity._advance_queue(req, mq)

    @staticmethod
    def _advance_queue(req: Request, mq: MatchQueue) -> Request:
        # Advance to next index or exhaust
        nxt = mq.current_index + 1
        next_cv = None
        if nxt == 2:
            next_cv = mq.cv2queue
        elif nxt == 3:
            next_cv = mq.cv3queue

        if next_cv:
            mq.current_index = nxt
            mq.sent_at = timezone.now()
            mq.deadline = mq.sent_at + timezone.timedelta(minutes=30)
            mq.status = MatchQueueStatus.ACTIVE
            mq.save(update_fields=["current_index", "sent_at", "deadline", "status"])

            Notification.objects.create(
                recipient=req.committed_by_csr.user,
                type=NotificationType.QUEUE_ADVANCED,
                message=f"Offer moved to CV #{mq.current_index} for {req.id}.",
                request=req,
                cv=next_cv,
                meta={"rank": mq.current_index, "expires_at": mq.deadline.isoformat()},
            )
        else:
            mq.status = MatchQueueStatus.EXHAUSTED
            mq.save(update_fields=["status"])
            Notification.objects.create(
                recipient=req.committed_by_csr.user,
                type=NotificationType.NO_MATCH_FOUND,
                message=f"No match found from queue for {req.id}.",
                request=req,
            )
            # Optionally: revert request to COMMITTED (still in CSR pool)
            req.status = RequestStatus.COMMITTED
            req.cv = None
            req.save(update_fields=["status", "cv", "updated_at"])

        return req

    @staticmethod
    @transaction.atomic
    def auto_advance_dormant(now=None) -> int:
        """
        Called by a periodic job. Moves expired ACTIVE queues to next CV.
        Returns number of advanced queues.
        """
        now = now or timezone.now()
        qs = MatchQueue.objects.select_for_update().filter(
            status=MatchQueueStatus.ACTIVE,
            deadline__isnull=False,
            deadline__lt=now,
        )
        count = 0
        for mq in qs:
            req = mq.request
            MatchProgressEntity._advance_queue(req, mq)
            Notification.objects.create(
                recipient=req.committed_by_csr.user,
                type=NotificationType.OFFER_EXPIRED,
                message=f"No response — auto-advanced for {req.id}.",
                request=req,
                cv=MatchProgressEntity._get_current_cv(mq),
            )
            count += 1
        return count

    @staticmethod
    @transaction.atomic
    def ensure_current_queue(request_id: str) -> Optional[MatchQueue]:
        try:
            req = Request.objects.select_for_update().get(pk=request_id)
        except Request.DoesNotExist:
            return None
        try:
            mq = MatchQueue.objects.select_for_update().get(request=req)
        except MatchQueue.DoesNotExist:
            return None
        if (
            mq.status == MatchQueueStatus.ACTIVE
            and mq.deadline
            and mq.deadline < timezone.now()
        ):
            MatchProgressEntity._advance_queue(req, mq)
            mq.refresh_from_db()
        return mq


# ---------- Notifications ----------

class NotificationEntity:
    @staticmethod
    def list_for_user(user) -> QuerySet:
        return Notification.objects.filter(recipient=user).select_related("request", "cv").order_by("-created_at")


# ---------- Completed & Claims ----------

class CompletedRequestsEntity:
    @staticmethod
    def list_completed(csr: CSRRep) -> QuerySet:
        """
        Completed requests (optionally scoped by company).
        """
        return Request.objects.filter(
            status=RequestStatus.COMPLETE,
            claims__isnull=False,
        ).select_related("pin", "cv").order_by("-completed_at").distinct()

    @staticmethod
    def claims_for_request(request_id: str) -> QuerySet:
        return (
            ClaimReport.objects.filter(request_id=request_id)
            .select_related("cv", "request")
            .order_by("-created_at")
        )

    @staticmethod
    @transaction.atomic
    def set_claim_status(claim_id: str, status: ClaimStatus) -> ClaimReport:
        cl = ClaimReport.objects.select_for_update().get(pk=claim_id)
        cl.status = status
        cl.save(update_fields=["status", "updated_at"])
        return cl
