# core/Control/csr_controller.py
from __future__ import annotations
from typing import Sequence

from django.core.exceptions import PermissionDenied

from core.models import Request, CSRRep, CV, MatchQueue
from core.entity.csr_entity import CSRRepository


class CSRController:
    # ---------- Gate ----------
    @staticmethod
    def _as_csr(user) -> CSRRep:
        try:
            return user.csrrep
        except Exception:
            raise PermissionDenied("Current user is not a CSR representative.")

    # ---------- Read ----------
    @staticmethod
    def list_pending(user):
        csr = CSRController._as_csr(user)
        return CSRRepository.pending_requests_visible_to_csr(csr)

    @staticmethod
    def list_shortlisted(user):
        csr = CSRController._as_csr(user)
        return CSRRepository.shortlisted_requests(csr)

    # ---------- Actions ----------
    @staticmethod
    def shortlist(user, req_id: str):
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        CSRRepository.add_shortlist(csr, req)
        return req

    @staticmethod
    def unshortlist(user, req_id: str):
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        CSRRepository.remove_shortlist(csr, req)
        return req

    @staticmethod
    def flag_request(user, req_id: str, reason: str = ""):
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        return CSRRepository.create_manual_flag(csr, req, reason)

    # ---------- Suggestions + Queue ----------
    @staticmethod
    def get_suggestions(user, req_id: str):
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        return CSRRepository.score_candidates(req, csr, limit=7)

    @staticmethod
    def create_queue(user, req_id: str, selected_cv_ids: Sequence[str]) -> MatchQueue:
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        return CSRRepository.create_queue_for_request(csr, req, selected_cv_ids)

    @staticmethod
    def start_queue(user, req_id: str, hours_to_respond: int = 1) -> CV:
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        mq = req.match_queue
        return CSRRepository.start_queue(mq, hours_to_respond=hours_to_respond)

    @staticmethod
    def advance_queue(user, req_id: str, hours_to_respond: int = 1):
        csr = CSRController._as_csr(user)
        req = Request.objects.get(pk=req_id)
        return CSRRepository.cv_decline_or_timeout(req, hours_to_respond=hours_to_respond)
