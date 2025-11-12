from __future__ import annotations
import json
from datetime import date
from typing import Dict, Any

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError

from core.models import Request, RequestStatus, CV
from core.entity.cv_entities import CvEntity
from core.Control.chat_controller import ChatController  # reuse completion + chat handling
from core.Control.csr_controller import CSRMatchController  # reuse CV decision flow

class CvController:
    """
    Business rules for Corporate Volunteers:
    - Dashboard sections (Pending offers / Active / Completed)
    - Accept / Decline offer
    - List Active/Completed requests
    - Request details (click-through)
    - Complete a request (delegates to ChatController)
    - Safety tips (Sea Lion Llama API with graceful fallback)
    - Submit & list claims
    """

    # ---------- guards ----------

    @staticmethod
    def _ensure_is_cv(user) -> CV:
        if not hasattr(user, "cv"):
            raise PermissionDenied("Not a CV user.")
        return user.cv

    # ---------- dashboard ----------

    @staticmethod
    def dashboard(*, user) -> Dict[str, Any]:
        cv = CvController._ensure_is_cv(user)
        pending = CvEntity.list_pending_offers(cv_id=cv.id)
        active = CvEntity.list_active_sorted(cv_id=cv.id)
        completed = CvEntity.list_completed(cv_id=cv.id)
        return {"pending": pending, "active": active, "completed": completed}

    # ---------- lists & detail ----------

    @staticmethod
    def list_requests(*, user, status: str):
        cv = CvController._ensure_is_cv(user)
        if status not in (RequestStatus.ACTIVE, RequestStatus.COMPLETE):
            raise ValidationError("Invalid status for CV list.")
        if status == RequestStatus.ACTIVE:
            return CvEntity.list_active_sorted(cv_id=cv.id)
        return CvEntity.list_requests(cv_id=cv.id, status=status)

    @staticmethod
    def request_detail(*, user, req_id: str) -> Request:
        cv = CvController._ensure_is_cv(user)
        req = get_object_or_404(Request.objects.select_related("pin", "cv"), pk=req_id)
        if req.cv_id != cv.id:
            raise PermissionDenied("Not your request.")
        return req

    # ---------- offer decisions ----------

    @staticmethod
    def decide_offer(*, user, req_id: str, accepted: bool):
        cv = CvController._ensure_is_cv(user)
        # Reuse CSRMatchController entrypoint which writes notifications & transitions
        data = CSRMatchController.cv_decision(request_id=req_id, cv_id=cv.id, accepted=accepted)
        return data

    # ---------- completion ----------

    @staticmethod
    def complete_request(*, user, req_id: str):
        return ChatController.complete_request(user=user, req_id=req_id)

    # ---------- safety tips ----------

    @staticmethod
    def safety_tips(*, user, req_id: str) -> dict:
        cv = CvController._ensure_is_cv(user)
        req = get_object_or_404(Request.objects.select_related("pin"), pk=req_id)
        if req.cv_id != cv.id:
            raise PermissionDenied("Not your request.")

        # Prepare input
        pin = req.pin
        age = None
        if pin.dob:
            today = date.today()
            age = today.year - pin.dob.year - ((today.month, today.day) < (pin.dob.month, pin.dob.day))

        prompt = {
            "task": "risk_safety_guidance",
            "inputs": {
                "age": age,
                "gender": pin.preferred_cv_gender,
                "category": req.service_type,
                "description": req.description,
                "locations": {
                    "pickup": req.pickup_location,
                    "service": req.service_location
                }
            },
            "constraints": {
                "tone": "calm, practical, concise",
                "max_items": 6
            }
        }

        api_key = getattr(settings, "SEA_LION_LLAMA_API_KEY", None)
        endpoint = getattr(settings, "SEA_LION_LLAMA_ENDPOINT", None)

        # Try remote if configured; fallback to rules if not or on failure
        if api_key and endpoint:
            try:
                resp = requests.post(
                    endpoint.rstrip("/") + "/v1/tips",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    data=json.dumps(prompt),
                    timeout=6,
                )
                if resp.ok:
                    payload = resp.json()
                    tips = payload.get("tips") or payload.get("data") or []
                    if isinstance(tips, list) and tips:
                        return {"request_id": req.id, "tips": tips}
            except Exception:
                pass

        # Fallback heuristic
        tips = [
            "Verify identity at pickup; match name and address.",
            "Keep communication in-app; avoid sharing personal numbers.",
            "Share trip details with the platform if travelling alone.",
        ]
        if req.service_type.lower().startswith("vaccination"):
            tips.append("Ensure medical documents are brought and stored safely.")
        if age and age >= 65:
            tips.append("Plan for mobility support; allow extra time for transitions.")
        if pin and pin.preferred_cv_gender == "female":
            tips.append("Prefer public, well-lit places for handoffs when appropriate.")
        return {"request_id": req.id, "tips": tips}

    # ---------- claims ----------

    @staticmethod
    def report_claim(*, user, req_id: str, **payload):
        cv = CvController._ensure_is_cv(user)
        req = get_object_or_404(Request, pk=req_id)
        if req.cv_id != cv.id:
            raise PermissionDenied("Not your request.")
        claim = CvEntity.create_claim_report(request=req, cv=cv, **payload)
        return claim

    @staticmethod
    def list_claims(*, user):
        cv = CvController._ensure_is_cv(user)
        return CvEntity.list_my_claims(cv_id=cv.id)


class CvClaimController:
    @staticmethod
    def create_claim(*, user, req_id, data, files):
        req = get_object_or_404(Request, pk=req_id)
        if not hasattr(user, "cv") or user.cv.id != (req.cv_id or ""):
            raise PermissionDenied("Not allowed.")
        receipt = files.get("receipt")
        if not receipt:
            raise ValidationError("Receipt file is required.")
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
