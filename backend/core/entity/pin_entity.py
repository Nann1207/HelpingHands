# core/entity/pin_entity.py
from __future__ import annotations
from typing import Optional, Iterable
from django.db import transaction
from django.utils import timezone

from core.models import (
    PersonInNeed, Request, RequestStatus,
    EmailOTP, OtpPurpose,
    ClaimReport, ClaimStatus, ClaimDispute, DisputeReason
)

class PinEntity:
    """
    DB-only for PIN use-cases. No permissions, no business orchestration here.
    """

    # --- Requests ---
    @staticmethod
    @transaction.atomic
    def create_request(*, pin: PersonInNeed, **data) -> Request:
        # Caller decides status before calling (Pending vs Review)
        req = Request.objects.create(pin=pin, **data)
        return req

    @staticmethod
    def list_requests(*, pin_id: str, status: Optional[str] = None):
        qs = Request.objects.filter(pin_id=pin_id)
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-created_at")

    # --- Profile / OTP ---
    @staticmethod
    def create_email_otp(*, email: str, code: str, purpose: str, expires_at) -> EmailOTP:
        return EmailOTP.objects.create(
            email=email, code=code, purpose=purpose, expires_at=expires_at, consumed=False
        )

    @staticmethod
    def get_valid_email_otp(*, email: str, code: str, purpose: str) -> Optional[EmailOTP]:
        now = timezone.now()
        try:
            return EmailOTP.objects.get(
                email=email, code=code, purpose=purpose, consumed=False, expires_at__gte=now
            )
        except EmailOTP.DoesNotExist:
            return None

    @staticmethod
    def consume_email_otp(otp: EmailOTP):
        otp.consumed = True
        otp.save(update_fields=["consumed"])

    @staticmethod
    @transaction.atomic
    def update_profile_fields(*, pin: PersonInNeed, **fields) -> PersonInNeed:
        # fields like address, phone etc.
        for k, v in fields.items():
            setattr(pin, k, v)
        pin.save(update_fields=list(fields.keys()))
        return pin

    # --- Claims (view & PIN actions) ---
    @staticmethod
    def list_completed_with_claims(*, pin_id: str):
        # Requests that are completed, include claims
        return (
            Request.objects.filter(pin_id=pin_id, status=RequestStatus.COMPLETE)
            .prefetch_related("claims", "claims__disputes")
            .order_by("-completed_at", "-created_at")
        )

    @staticmethod
    @transaction.atomic
    def verify_claim(*, claim: ClaimReport) -> ClaimReport:
        claim.status = ClaimStatus.VERIFIED_BY_PIN
        claim.save(update_fields=["status"])
        return claim

    @staticmethod
    @transaction.atomic
    def dispute_claim(*, claim: ClaimReport, pin: PersonInNeed, reason: str, comment: str = "") -> ClaimDispute:
        # create dispute, set status
        dispute = ClaimDispute.objects.create(
            claim=claim, pin=pin, reason=reason, comment=comment
        )
        claim.status = ClaimStatus.DISPUTED_BY_PIN
        claim.save(update_fields=["status"])
        return dispute
