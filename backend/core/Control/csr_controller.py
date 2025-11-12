# core/Control/csr_controllers.py
"""
CONTROLLER layer for CSR features.
Coordinates entities, shapes data for delivery (dicts), and enforces app-level rules.
"""

from __future__ import annotations
from typing import Dict, Any, List
from django.utils import timezone

from core.models import CSRRep, ClaimStatus, MatchQueue
from core.entity.csr_entity import (
    DashboardEntity, RequestEntity, ShortlistEntity, CommitEntity,
    MatchEntity, MatchProgressEntity, NotificationEntity, CompletedRequestsEntity,
)


class CSRDashboardController:
    @staticmethod
    def get_dashboard(csr: CSRRep) -> Dict[str, Any]:
        today = DashboardEntity.today_active_requests(csr)
        committed = DashboardEntity.committed_requests(csr)
        notes = DashboardEntity.recent_notifications(csr.user)

        return {
            "today_active": [
                {
                    "id": r.id,
                    "pin": r.pin.name,
                    "cv": r.cv.name if r.cv else None,
                    "service_type": r.service_type,
                    "appointment_time": r.appointment_time.isoformat(),
                }
                for r in today
            ],
            "committed": [
                {"id": r.id, "status": r.status, "pin": r.pin.name, "service_type": r.service_type}
                for r in committed
            ],
            "notifications": [
                {
                    "id": n.id,
                    "type": n.type,
                    "message": n.message,
                    "request_id": n.request_id,
                    "cv_id": n.cv_id,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notes
            ],
        }


class CSRRequestController:
    @staticmethod
    def list_pool() -> Dict[str, Any]:
        soon = RequestEntity.coming_soon()
        all_pending = RequestEntity.available_requests()
        return {
            "coming_soon": [
                {
                    "id": r.id,
                    "service_type": r.service_type,
                    "category": r.service_type,
                    "appointment_date": r.appointment_date.isoformat(),
                    "service_location": r.service_location,
                    "location": r.service_location,
                    "shortlist_count": getattr(r, "shortlist_count", 0),
                }
                for r in soon
            ],
            "all_requests": [
                {
                    "id": r.id,
                    "service_type": r.service_type,
                    "category": r.service_type,
                    "appointment_date": r.appointment_date.isoformat(),
                    "service_location": r.service_location,
                    "location": r.service_location,
                    "shortlist_count": getattr(r, "shortlist_count", 0),
                }
                for r in all_pending
            ],
        }

    @staticmethod
    def shortlist_add(csr: CSRRep, request_id: str) -> Dict[str, Any]:
        sl = RequestEntity.shortlist(csr, request_id)
        req = sl.request
        pin_name = req.pin.name if req and req.pin else ""
        appointment_date = req.appointment_date.isoformat() if req and req.appointment_date else ""
        service_location = req.service_location if req else ""
        service_type = req.service_type if req else ""
        return {
            "shortlisted": True,
            "id": sl.id,
            "request_id": sl.request_id,
            "pin": pin_name,
            "category": service_type,
            "service_type": service_type,
            "appointment_date": appointment_date,
            "service_location": service_location,
            "location": service_location,
        }

    @staticmethod
    def shortlist_remove(csr: CSRRep, request_id: str) -> Dict[str, Any]:
        RequestEntity.remove_shortlist(csr, request_id)
        return {"shortlisted": False, "request_id": request_id}

    @staticmethod
    def commit_request(csr: CSRRep, request_id: str) -> Dict[str, Any]:
        req = RequestEntity.commit(csr, request_id)
        # Once committed, remove from this CSR's shortlist so UI updates cleanly
        RequestEntity.remove_shortlist(csr, request_id)
        return {"id": req.id, "status": req.status}


class CSRShortlistController:
    @staticmethod
    def list(csr: CSRRep) -> Dict[str, Any]:
        rows = ShortlistEntity.list_shortlist(csr)
        return {
            "items": [
                {
                    "shortlist_id": s.id,
                    "request_id": s.request_id,
                    "pin": s.request.pin.name,
                    "service_type": s.request.service_type,
                    "category": s.request.service_type,
                    "appointment_date": s.request.appointment_date.isoformat(),
                    "service_location": s.request.service_location,
                    "location": s.request.service_location,
                }
                for s in rows
            ]
        }


class CSRCommitController:
    @staticmethod
    def list(csr: CSRRep) -> Dict[str, Any]:
        rows = CommitEntity.list_committed(csr)
        return {
            "items": [
                {"id": r.id, "pin": r.pin.name, "category": r.service_type, "status": r.status}
                for r in rows
            ]
        }


class CSRMatchController:
    @staticmethod
    def _serialize_cv(cv):
        if not cv:
            return None
        company = getattr(cv, "company", None)
        return {
            "id": cv.id,
            "name": cv.name,
            "company": company.companyname if company else None,
        }

    @staticmethod
    def _serialize_queue(mq: MatchQueue) -> Dict[str, Any]:
        mq = MatchQueue.objects.select_related(
            "cv1queue__company", "cv2queue__company", "cv3queue__company"
        ).get(pk=mq.pk)
        return {
            "request": mq.request_id,
            "status": mq.status,
            "current_index": mq.current_index,
            "sent_at": mq.sent_at.isoformat() if mq.sent_at else None,
            "deadline": mq.deadline.isoformat() if mq.deadline else None,
            "cv1queue": CSRMatchController._serialize_cv(mq.cv1queue),
            "cv2queue": CSRMatchController._serialize_cv(mq.cv2queue),
            "cv3queue": CSRMatchController._serialize_cv(mq.cv3queue),
        }

    @staticmethod
    def suggest(request_id: str) -> Dict[str, Any]:
        # Load request only once by Entity where necessary; here we use ORM directly for simplicity
        from core.models import Request as _Req
        req = _Req.objects.select_related("pin").get(pk=request_id)
        suggestions = MatchEntity.suggest_top(req)
        return {
            "suggestions": [
                {"cv_id": s.cv_id, "score": s.score, "reason": s.reason} for s in suggestions
            ]
        }

    @staticmethod
    def set_assignment_pool(request_id: str, cv_ids: List[str]) -> Dict[str, Any]:
        mq = MatchEntity.set_assignment_pool(request_id, cv_ids)
        return CSRMatchController._serialize_queue(mq)

    @staticmethod
    def get_assignment_pool(request_id: str) -> Dict[str, Any]:
        mq = MatchProgressEntity.ensure_current_queue(request_id)
        if not mq:
            mq = MatchEntity.get_assignment_pool(request_id)
        if not mq:
            return {
                "request": request_id,
                "status": None,
                "current_index": None,
                "sent_at": None,
                "deadline": None,
                "cv1queue": None,
                "cv2queue": None,
                "cv3queue": None,
            }
        return CSRMatchController._serialize_queue(mq)

    @staticmethod
    def send_offers(request_id: str, timeout_minutes: int = 30) -> Dict[str, Any]:
        mq = MatchEntity.send_offers(request_id, timeout_minutes)
        return CSRMatchController._serialize_queue(mq)

    @staticmethod
    def cv_decision(request_id: str, cv_id: str, accepted: bool) -> Dict[str, Any]:
        req = MatchProgressEntity.record_cv_decision(request_id, cv_id, accepted)
        return {"request_id": req.id, "status": req.status, "cv": req.cv_id}

    @staticmethod
    def sweep_dormant() -> Dict[str, Any]:
        n = MatchProgressEntity.auto_advance_dormant()
        return {"auto_advanced": n}


class CSRNotificationController:
    @staticmethod
    def list(user) -> Dict[str, Any]:
        qs = NotificationEntity.list_for_user(user)
        return {
            "items": [
                {
                    "id": n.id,
                    "type": n.type,
                    "message": n.message,
                    "request_id": n.request_id,
                    "cv_id": n.cv_id,
                    "created_at": n.created_at.isoformat(),
                }
                for n in qs
            ]
        }


class CSRCompletedController:
    @staticmethod
    def list(csr: CSRRep) -> Dict[str, Any]:
        qs = CompletedRequestsEntity.list_completed(csr)
        return {"items": [{"id": r.id, "pin": r.pin.name, "cv": r.cv.name if r.cv else None} for r in qs]}

    @staticmethod
    def claims(request_id: str) -> Dict[str, Any]:
        qs = CompletedRequestsEntity.claims_for_request(request_id)
        return {
            "claims": [
                {
                    "id": c.id,
                    "cv": c.cv.name,
                    "amount": str(c.amount),
                    "status": c.status,
                    "verified_by_pin": c.status == ClaimStatus.VERIFIED_BY_PIN,
                    "created_at": c.created_at.isoformat(),
                }
                for c in qs
            ]
        }

    @staticmethod
    def reimburse(claim_id: str) -> Dict[str, Any]:
        c = CompletedRequestsEntity.set_claim_status(claim_id, ClaimStatus.REIMBURSED_BY_CSR)
        return {"id": c.id, "status": c.status}

    @staticmethod
    def reject(claim_id: str) -> Dict[str, Any]:
        c = CompletedRequestsEntity.set_claim_status(claim_id, ClaimStatus.REJECTED_BY_CSR)
        return {"id": c.id, "status": c.status}
