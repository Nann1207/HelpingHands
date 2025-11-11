# core/entity/csr_entity.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, List, Optional, Sequence, Dict, Any

from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Q, IntegerField, Value, Case, When, F

from core.models import (
    Request, RequestStatus, CSRRep, ShortlistedRequest, FlaggedRequest, FlagType,
    CV, MatchQueue, Notification, NotificationType, ChatRoom
)

OFFER_TIMEOUT_HOURS = 1  # each CV has 1 hour to respond by default


@dataclass
class VolunteerScore:
    cv_id: str
    score: int


class NotificationEntity:
    """Small helper to keep Notification writes tidy (no separate file)."""

    @staticmethod
    def create(
        *,
        recipient,
        ntype: NotificationType,
        message: str,
        request: Optional[Request] = None,
        cv: Optional[CV] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        return Notification.objects.create(
            recipient=recipient,
            type=ntype,
            message=message[:300],
            request=request,
            cv=cv,
            meta=meta or {},
        )

    @staticmethod
    def unread_for(user):
        return Notification.objects.filter(recipient=user, is_read=False).order_by("-created_at")

    @staticmethod
    def mark_all_read(user):
        Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)


class CSRRepository:
    # -------- Requests (read) --------
    @staticmethod
    def pending_requests_visible_to_csr(csr: CSRRep):
        # If you need to limit by company/domain later, filter here.
        return Request.objects.filter(status=RequestStatus.PENDING).order_by("-created_at")

    @staticmethod
    def shortlisted_requests(csr: CSRRep):
        return Request.objects.filter(shortlisted_by__csr=csr).order_by("-created_at")

    # -------- Shortlist (write) --------
    @staticmethod
    def add_shortlist(csr: CSRRep, req: Request):
        ShortlistedRequest.objects.get_or_create(csr=csr, request=req)

    @staticmethod
    def remove_shortlist(csr: CSRRep, req: Request):
        ShortlistedRequest.objects.filter(csr=csr, request=req).delete()

    # -------- Flags --------
    @staticmethod
    def create_manual_flag(csr: CSRRep, req: Request, reason: str = "") -> FlaggedRequest:
        return FlaggedRequest.objects.create(
            request=req,
            flag_type=FlagType.MANUAL,
            csr=csr,
            reasonbycsr=reason or "Manual flag by CSR.",
        )

    # -------- Suggestions (rank 7) --------
    @staticmethod
    def candidate_cvs_for_request(req: Request, csr: CSRRep, limit: int = 7) -> List[CV]:
        """
        CVs under this CSR's company ranked by:
          1) service category match (desc)
          2) completed assignments count (desc)
          3) active load (asc)
          4) id asc (tie-break)
        """
        qs = CV.objects.filter(company=csr.company)

        svc_match = Case(
            When(service_category_preference=req.service_type, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )

        qs = (
            qs.annotate(
                svc_match=svc_match,
                active_load=Count(
                    "assigned_requests",
                    filter=Q(assigned_requests__status__in=[RequestStatus.ACTIVE]),
                ),
                completed_count=Count(
                    "assigned_requests",
                    filter=Q(assigned_requests__status=RequestStatus.COMPLETE),
                ),
            )
            .order_by(
                F("svc_match").desc(),
                F("completed_count").desc(),
                F("active_load").asc(),
                "id",
            )
        )
        return list(qs[:limit])

    @staticmethod
    def score_candidates(req: Request, csr: CSRRep, limit: int = 7) -> List[Dict[str, Any]]:
        cvs = CSRRepository.candidate_cvs_for_request(req, csr, limit=limit)
        return [
            {
                "id": cv.id,
                "name": cv.name,
                "gender": cv.gender,
                "main_language": cv.main_language,
                "second_language": cv.second_language,
                "service_category_preference": cv.service_category_preference,
                "svc_match": getattr(cv, "svc_match", 0),
                "completed_count": getattr(cv, "completed_count", 0),
                "active_load": getattr(cv, "active_load", 0),
            }
            for cv in cvs
        ]

    # -------- Matching Queue (1..3) --------
    @staticmethod
    @transaction.atomic
    def create_queue_for_request(csr: CSRRep, req: Request, selected_cv_ids: Sequence[str]) -> MatchQueue:
        """
        selected_cv_ids: length 1..3 (ordered).
        Enforces PENDING request and confines to CSR's company.
        """
        if req.status != RequestStatus.PENDING:
            raise ValueError("Request must be PENDING to start matching.")

        cvs = list(CV.objects.filter(id__in=selected_cv_ids, company=csr.company))
        cv_map = {cv.id: cv for cv in cvs}
        ordered = [cv_map.get(i) for i in selected_cv_ids if cv_map.get(i)]

        if not ordered:
            raise ValueError("No valid CVs selected.")
        if len(ordered) > 3:
            raise ValueError("Select at most 3 CVs.")

        mq, _ = MatchQueue.objects.update_or_create(
            request=req,
            defaults={
                "cv1": ordered[0],
                "cv2": ordered[1] if len(ordered) >= 2 else None,
                "cv3": ordered[2] if len(ordered) >= 3 else None,
                "current_index": 1,
            },
        )

        # mark CSR commit
        now = timezone.now()
        req.committed_by_csr = csr
        req.committed_at = now
        req.save(update_fields=["committed_by_csr", "committed_at"])

        # 🔔 notify CSR: queue prepared
        NotificationEntity.create(
            recipient=csr.user,
            ntype=NotificationType.QUEUE_STARTED,
            message=f"Queue prepared for {req.id} with {len(ordered)} CV(s).",
            request=req,
            meta={"cv_ids": [c.id for c in ordered]},
        )
        return mq

    @staticmethod
    @transaction.atomic
    def start_queue(mq: MatchQueue, hours_to_respond: int = OFFER_TIMEOUT_HOURS):
        mq.start(hours_to_respond=hours_to_respond)
        current_cv = mq._get_current_cv()

        # 🔔 notify CSR: offer sent to current CV
        csr_user = mq.request.committed_by_csr.user if mq.request.committed_by_csr else None
        if csr_user and current_cv:
            NotificationEntity.create(
                recipient=csr_user,
                ntype=NotificationType.OFFER_SENT,
                message=f"Offer sent to {current_cv.name} for {mq.request.id}.",
                request=mq.request,
                cv=current_cv,
                meta={"rank": mq.current_index, "deadline": mq.deadline.isoformat() if mq.deadline else None},
            )
        return current_cv

    @staticmethod
    @transaction.atomic
    def cv_accept(req: Request, cv: CV):
        """CV accepts → lock match, assign cv, open chat, set ACTIVE, notify."""
        mq = req.match_queue
        current = mq._get_current_cv()
        if current != cv:
            raise ValueError("This CV is not the current candidate.")

        req.cv = cv
        req.status = RequestStatus.ACTIVE
        req.save(update_fields=["cv", "status"])

        ChatRoom.objects.get_or_create(request=req)

        mq.mark_filled()

        # 🔔 notify CSR: accepted + filled
        if req.committed_by_csr:
            NotificationEntity.create(
                recipient=req.committed_by_csr.user,
                ntype=NotificationType.MATCH_ACCEPTED,
                message=f"{cv.name} accepted. Request {req.id} is now ACTIVE.",
                request=req,
                cv=cv,
            )
            NotificationEntity.create(
                recipient=req.committed_by_csr.user,
                ntype=NotificationType.MATCH_FILLED,
                message=f"Queue filled for {req.id}.",
                request=req,
                cv=cv,
            )
        return req

    @staticmethod
    @transaction.atomic
    def cv_decline_or_timeout(req: Request, hours_to_respond: int = OFFER_TIMEOUT_HOURS):
        """
        Current CV declined/timed out → advance to next CV if available.
        Notifies CSR about expiry and reassignment (or exhaustion).
        Returns next CV or None if exhausted.
        """
        mq = req.match_queue
        prev_cv = mq._get_current_cv()
        advanced = mq.advance(hours_to_respond=hours_to_respond)
        csr_user = req.committed_by_csr.user if req.committed_by_csr else None

        # 🔔 notify CSR: previous expired/declined
        if csr_user and prev_cv:
            NotificationEntity.create(
                recipient=csr_user,
                ntype=NotificationType.OFFER_EXPIRED,
                message=f"{prev_cv.name} did not accept in time for {req.id}.",
                request=req,
                cv=prev_cv,
            )

        if advanced:
            next_cv = mq._get_current_cv()
            if csr_user and next_cv:
                NotificationEntity.create(
                    recipient=csr_user,
                    ntype=NotificationType.QUEUE_ADVANCED,
                    message=f"Reassigned {req.id} to {next_cv.name}.",
                    request=req,
                    cv=next_cv,
                    meta={"rank": mq.current_index, "deadline": mq.deadline.isoformat() if mq.deadline else None},
                )
                NotificationEntity.create(
                    recipient=csr_user,
                    ntype=NotificationType.OFFER_SENT,
                    message=f"Offer sent to {next_cv.name} for {req.id}.",
                    request=req,
                    cv=next_cv,
                    meta={"rank": mq.current_index, "deadline": mq.deadline.isoformat() if mq.deadline else None},
                )
            return next_cv

        # exhausted
        if csr_user:
            NotificationEntity.create(
                recipient=csr_user,
                ntype=NotificationType.QUEUE_ADVANCED,
                message=f"No more candidates left for {req.id} (queue exhausted).",
                request=req,
            )
        return None
