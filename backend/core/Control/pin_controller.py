# core/Control/pin_controller.py
from __future__ import annotations
from datetime import timedelta
import random
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.hashers import make_password

from core.models import (
    PersonInNeed, Request, RequestStatus,
    ClaimReport, DisputeReason, OtpPurpose
)
from core.entity.pin_entity import PinEntity

# Very simple moderation stub – replace with your real checker
class ModerationService:
    @staticmethod
    def check(text: str) -> tuple[bool, str]:
        # return (is_flagged, reason)
        if any(bad in (text or "").lower() for bad in ["abuse", "bomb", "kill"]):
            return True, "unsafe_content"
        return False, ""

class PinController:
    """
    Business rules for PIN:
    - Submit request (moderation decides status)
    - Dashboard lists
    - Profile update via OTP
    - Verify/Dispute claims
    """

    @staticmethod
    def _ensure_is_pin(user) -> PersonInNeed:
        if not hasattr(user, "personinneed"):
            raise PermissionDenied("Not a PIN user.")
        return user.personinneed

    # --- Request creation flow ---
    @staticmethod
    def submit_request(*, user, **payload) -> Request:
        pin = PinController._ensure_is_pin(user)

        description = payload.get("description", "")
        flagged, reason = ModerationService.check(description)
        # Set status per rules
        payload["status"] = RequestStatus.REVIEW if flagged else RequestStatus.PENDING

        req = PinEntity.create_request(pin=pin, **payload)
        # (optional) store moderation note somewhere if needed
        return req

    # --- Request dashboard ---
    @staticmethod
    def list_my_requests(*, user, status: str | None = None):
        pin = PinController._ensure_is_pin(user)
        return PinEntity.list_requests(pin_id=pin.id, status=status)

    # --- Profile & OTP (using Django email backend) ---
    @staticmethod
    def start_profile_update_otp(*, user) -> dict:
        from django.core.mail import send_mail
        pin = PinController._ensure_is_pin(user)

        code = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=10)
        PinEntity.create_email_otp(
            email=pin.user.email, code=code, purpose=OtpPurpose.PROFILE_UPDATE, expires_at=expires_at
        )
        # Send email (Django email backend must be configured)
        send_mail(
            subject="Your AskVox OTP Code",
            message=f"Your OTP is {code}. It will expire in 10 minutes.",
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[pin.user.email],
        )
        return {"sent": True, "expires_at": expires_at}

    @staticmethod
    def confirm_profile_update(*, user, code: str, **fields):
        pin = PinController._ensure_is_pin(user)
        otp = PinEntity.get_valid_email_otp(
            email=pin.user.email, code=code, purpose=OtpPurpose.PROFILE_UPDATE
        )
        if not otp:
            raise ValidationError("Invalid or expired OTP.")
        PinEntity.update_profile_fields(pin=pin, **fields)
        PinEntity.consume_email_otp(otp)
        return pin

    # optional: change password with OTP
    @staticmethod
    def change_password_with_otp(*, user, code: str, new_password: str):
        pin = PinController._ensure_is_pin(user)
        otp = PinEntity.get_valid_email_otp(
            email=pin.user.email, code=code, purpose=OtpPurpose.PASSWORD_CHANGE
        )
        if not otp:
            raise ValidationError("Invalid or expired OTP.")
        pin.user.password = make_password(new_password)
        pin.user.save(update_fields=["password"])
        PinEntity.consume_email_otp(otp)
        return {"ok": True}

    # --- Claims: verify / dispute ---
    @staticmethod
    def list_completed_with_claims(*, user):
        pin = PinController._ensure_is_pin(user)
        return PinEntity.list_completed_with_claims(pin_id=pin.id)

    @staticmethod
    def verify_claim(*, user, claim_id: str):
        pin = PinController._ensure_is_pin(user)
        claim = ClaimReport.objects.select_related("request").get(pk=claim_id)
        if claim.request.pin_id != pin.id:
            raise PermissionDenied("Not your claim.")
        return PinEntity.verify_claim(claim=claim)

    @staticmethod
    def dispute_claim(*, user, claim_id: str, reason: str, comment: str = ""):
        pin = PinController._ensure_is_pin(user)
        if reason not in DisputeReason.values:
            raise ValidationError("Invalid dispute reason.")
        claim = ClaimReport.objects.select_related("request").get(pk=claim_id)
        if claim.request.pin_id != pin.id:
            raise PermissionDenied("Not your claim.")
        return PinEntity.dispute_claim(claim=claim, pin=pin, reason=reason, comment=comment)
