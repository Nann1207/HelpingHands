from __future__ import annotations
import json
import logging
from datetime import date
from typing import Dict, Any


from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError

try:
    import requests
except ImportError: 
    requests = None


logger = logging.getLogger(__name__)

from core.models import Request, RequestStatus, CV, MatchQueueStatus
from core.entity.cv_entities import CvEntity
from core.Control.chat_controller import ChatController  # reuse
from core.Control.csr_controller import CSRMatchController  # reuse 

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

    @staticmethod
    def _has_pending_offer(req: Request, cv_id: str) -> bool:
        mq = getattr(req, "match_queue", None)
        if not mq or mq.status != MatchQueueStatus.ACTIVE:
            return False
        return (
            (mq.current_index == 1 and mq.cv1queue_id == cv_id)
            or (mq.current_index == 2 and mq.cv2queue_id == cv_id)
            or (mq.current_index == 3 and mq.cv3queue_id == cv_id)
        )

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
        req = get_object_or_404(Request.objects.select_related("pin", "cv", "match_queue"), pk=req_id)
        if req.cv_id != cv.id and not CvController._has_pending_offer(req, cv.id):
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
        req = get_object_or_404(Request.objects.select_related("pin", "match_queue"), pk=req_id)
        if req.cv_id != cv.id and not CvController._has_pending_offer(req, cv.id):
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
        endpoint = getattr(settings, "SEA_LION_LLAMA_ENDPOINT", "https://api.sea-lion.ai/v1/chat/completions")
        model = getattr(settings, "SEA_LION_LLAMA_MODEL", "aisingapore/Gemma-SEA-LION-v4-27B-IT")

        # Try remote if configured; fallback to rules if not or on failure
        if api_key and requests:
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a safety coach for a volunteer transport platform. "
                                "Return ONLY a JSON array (no text) of 3-6 concise safety tips."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(prompt),
                        },
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7,
                    "top_p": 0.9,
                }
                resp = requests.post(
                    endpoint.rstrip("/"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10,
                )
                resp.raise_for_status()
                parsed = CvController._parse_llm_tips(resp.json())
                if parsed:
                    logger.info("Sea Lion safety tips generated for request %s via %s", req.id, endpoint)
                    return {"request_id": req.id, "tips": parsed}
            except (requests.RequestException, ValueError, KeyError) as exc:
                logger.warning("Sea Lion safety tips fetch failed for request %s: %s", req.id, exc)
        elif api_key and not requests:
            logger.warning("Sea Lion API key configured but 'requests' not installed; using fallback tips.")
        else:
            logger.info("Sea Lion API not configured; using fallback tips.")

        tips = CvController._fallback_tips(req=req, age=age, pin=pin)
        logger.info("Fallback safety tips returned for request %s", req.id)
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

    # ---------- helpers ----------

    @staticmethod
    def _parse_llm_tips(payload):
        if not isinstance(payload, dict):
            return None
        choices = payload.get("choices")
        if not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = (message or {}).get("content") if isinstance(message, dict) else None
        if not content or not isinstance(content, str):
            return None
        content = content.strip()
        if not content:
            return None
        tips = None
        try:
            tips = json.loads(content)
            if isinstance(tips, dict):
                tips = tips.get("tips")
        except ValueError:
            tips = None
        if tips is None:
            tips = [
                part.strip(" -•\t")
                for part in content.splitlines()
                if part.strip()
            ]
        if isinstance(tips, str):
            tips = [tips]
        if isinstance(tips, list):
            cleaned = [t.strip() for t in tips if isinstance(t, str) and t.strip()]
            return cleaned or None
        return None

    @staticmethod
    def _fallback_tips(*, req, age, pin):
        tips = [
            "Verify the rider's identity at pickup and confirm the appointment details.",
            "Keep communication inside the Helping Hands channels; avoid sharing personal numbers.",
            "Share your live status with the platform if travelling to an unfamiliar location.",
        ]
        service = (req.service_type or "").lower()
        if service.startswith("vaccination") or "medical" in service:
            tips.append("Double-check that medical documents and medications are packed securely.")
        if service.startswith("legal") or "court" in service:
            tips.append("Plan extra time for security checkpoints and document checks.")
        if age and age >= 65:
            tips.append("Allow additional time for mobility support and ensure safe entry/exit of vehicles.")
        if pin and getattr(pin, "preferred_cv_gender", "") == "female":
            tips.append("Prioritize well-lit, public meeting points when possible.")
        return tips


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
