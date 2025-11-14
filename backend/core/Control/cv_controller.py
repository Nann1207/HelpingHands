from __future__ import annotations
import json
from typing import Dict, Any


from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied, ValidationError

try:
    import requests
except ImportError: 
    requests = None


from core.models import Request, RequestStatus, CV, MatchQueueStatus
from core.entity.cv_entities import CvEntity
from core.Control.chat_controller import ChatController  
from core.Control.csr_controller import CSRMatchController  

class CvController:
    """
    - Dashboard sections (Pending offers / Active / Completed)
    - Accept / Decline offer
    - List Active/Completed requests
    - Request details (click-through)
    - Complete a request (delegates to ChatController)
    - Safety tips (Sea Lion Llama API with  fallback)
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
        try:
            payload = CvEntity.build_safety_prompt_payload(req_id=req_id)
        except Request.DoesNotExist:
            raise Http404("Request not found.")
        req = payload["request"]
        pin = payload["pin"]
        age = payload["age"]
        prompt = payload["prompt"]
        if req.cv_id != cv.id and not CvController._has_pending_offer(req, cv.id):
            raise PermissionDenied("Not your request.")

        api_key = getattr(settings, "SEA_LION_LLAMA_API_KEY", None)
        endpoint = getattr(settings, "SEA_LION_LLAMA_ENDPOINT", "https://api.sea-lion.ai/v1/chat/completions")
        model = getattr(settings, "SEA_LION_LLAMA_MODEL", "aisingapore/Gemma-SEA-LION-v4-27B-IT")

        
        if api_key and requests:
            try:
                advisor_prompt = (
                    "You provide safety tips for volunteer escorts who accompany persons-in-need to healthcare or community appointments.\n"
                    "Use the JSON payload to tailor 5-6 concise, practical tips that reflect the person's age, gender preference, service category, and appointment details.\n"
                    "Refer to the assisted individual as the person-in-need (PIN) at all times; never use rider, client, or patient labels.\n"
                    "Focus on on-site support and personal safety; do not mention driving or vehicle operations.\n"
                    "Service categories:\n"
                    "- Healthcare Escort: General medical consultations (GP visits, outpatient check-ups, hospital follow-ups).\n"
                    "- Therapy Escort: Physiotherapy, occupational therapy, counseling, or mental health sessions.\n"
                    "- Dialysis Escort: Recurring hemo/peritoneal dialysis appointments.\n"
                    "- Vaccination / Check-up: Short visits for vaccinations, tests, or screenings.\n"
                    "- Mobility Assistance: Wheelchair navigation, transfers, or wayfinding for persons with reduced mobility.\n"
                    "- Community Event: Social, cultural, or community activities such as support groups or library visits.\n"
                    "Return ONLY a JSON array (no prose) where each entry is a short safety tip string."
                )
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "advisor",
                            "content": advisor_prompt,
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
                    return {"request_id": req.id, "tips": parsed}
            except (requests.RequestException, ValueError, KeyError):
                pass

        tips = CvController._fallback_tips(req=req, age=age, pin=pin)
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

    # helper
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
            "Verify the person-in-need's identity at pickup and confirm the appointment details.",
            "Keep communication inside the Helping Hands channels; avoid sharing personal numbers.",
            "Share your live status with your loved ones if travelling to an unfamiliar location.",
        ]
        service = (req.service_type or "").lower()
        if service.startswith("vaccination") or "medical" in service:
            tips.append("Double-check that medical documents and medications are packed securely.")
        if service.startswith("legal") or "court" in service:
            tips.append("Plan extra time for security checkpoints and document checks.")
        if age and age >= 65:
            tips.append("Allow additional time for mobility support and ensure safe entry/exit when assisting the person-in-need.")
        if pin and getattr(pin, "preferred_cv_gender", "") == "female":
            tips.append("Prioritize well-lit, public meeting points for the person-in-need when possible.")
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
