# core/Control/cv_controller.py
from __future__ import annotations
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Request, RequestStatus, CV, ClaimStatus
from core.entity.cv_entities import CvEntity
from core.entity.cv_entities import CvEntity
from core.Control.chat_controller import ChatController  # reuse complete flow

class CvController:
    """
    Business rules for Corporate Volunteers:
    - List Active/Completed requests
    - Complete a request (reuses ChatController.complete_request)
    - Safety tips (basic rules engine placeholder)
    - Submit claim report
    """

    @staticmethod
    def _ensure_is_cv(user) -> CV:
        if not hasattr(user, "cv"):
            raise PermissionDenied("Not a CV user.")
        return user.cv

    @staticmethod
    def list_requests(*, user, status: str):
        cv = CvController._ensure_is_cv(user)
        if status not in (RequestStatus.ACTIVE, RequestStatus.COMPLETE):
            raise ValidationError("Invalid status for CV list.")
        return CvEntity.list_requests(cv_id=cv.id, status=status)

    @staticmethod
    def complete_request(*, user, req_id: str):
        # delegate to chat controller so it sets expiry etc.
        return ChatController.complete_request(user=user, req_id=req_id)

    @staticmethod
    def safety_tips(*, user, req_id: str) -> dict:
        cv = CvController._ensure_is_cv(user)
        req = get_object_or_404(Request, pk=req_id)
        if req.cv_id != cv.id:
            raise PermissionDenied("Not your request.")

        # Simple tips engine placeholder
        pin = req.pin
        age = None
        if pin.dob:
            from datetime import date
            today = date.today()
            age = today.year - pin.dob.year - ((today.month, today.day) < (pin.dob.month, pin.dob.day))

        tips = [
            "Verify identity at pickup location.",
            "Keep communication in-app; avoid sharing personal numbers.",
        ]
        if req.service_type.lower().startswith("vaccination"):
            tips.append("Ensure medical documents are brought and stored safely.")
        if age and age >= 65:
            tips.append("Be mindful of mobility and allow extra time for transitions.")
        if pin and pin.preferred_cv_gender == "female":
            tips.append("If appropriate, keep interactions in public or well-lit areas.")

        return {"request_id": req.id, "tips": tips}

    @staticmethod
    def report_claim(*, user, req_id: str, **payload):
        cv = CvController._ensure_is_cv(user)
        req = get_object_or_404(Request, pk=req_id)
        if req.cv_id != cv.id:
            raise PermissionDenied("Not your request.")
        # basic validation can live in serializer; here assume clean
        claim = CvEntity.create_claim_report(request=req, cv=cv, **payload)
        # notify CSR + PIN later (out of scope)
        return claim


class CvClaimController:
    @staticmethod
    def create_claim(*, user, req_id, data, files):
        req = get_object_or_404(Request, pk=req_id)
        # ensure user is the assigned CV
        if not hasattr(user, "cv") or user.cv.id != (req.cv_id or ""):
            raise PermissionDenied("Not allowed.")
        receipt = files.get("receipt")
        if not receipt:
            raise ValueError("Receipt file is required.")

        # Normalized payload
        payload = {
            "request": req,
            "cv": user.cv,
            "category": data.get("category"),
            "expense_date": data.get("expense_date"),
            "amount": data.get("amount"),
            "payment_method": data.get("payment_method"),
            "description": data.get("description", ""),
            "receipt": receipt,
        }
        return CvEntity.create_claim(**payload)