# core/entity/pin_entity.py
from __future__ import annotations
from typing import Optional, Iterable
from django.db import transaction
from django.utils import timezone
from django.db.models import Count

from core.models import (
    PersonInNeed, Request, RequestStatus,
    EmailOTP, 
    ClaimReport, ClaimStatus, ClaimDispute, FlaggedRequest, FlagType
)

class PinEntity:

    #Creates a new service request for PIN users
    @staticmethod
    @transaction.atomic
    def create_request(*, pin: PersonInNeed, **data) -> Request:
        req = Request.objects.create(pin=pin, **data)
        return req

    #Fetches service requests for a specific PIN user, optionally can be used to filter by status
    @staticmethod
    def list_requests(*, pin_id: str, status: Optional[str] = None):
        qs = Request.objects.filter(pin_id=pin_id)
        if status:
            qs = qs.filter(status=status)

        qs = qs.annotate(shortlist_count=Count("shortlisted_by", distinct=True))   
        return qs.order_by("-created_at")


    #This is to create and store an email OTP for profile updates or password changes
    @staticmethod
    def create_email_otp(*, email: str, code: str, purpose: str, expires_at) -> EmailOTP:
        return EmailOTP.objects.create(
            email=email, code=code, purpose=purpose, expires_at=expires_at, consumed=False
        )

    #Validates an email OTP based on email, code, purpose, and checks if it's not consumed or expired
    @staticmethod
    def get_valid_email_otp(*, email: str, code: str, purpose: str) -> Optional[EmailOTP]:
        now = timezone.now()
        try:
            return EmailOTP.objects.get(
                email=email, code=code, purpose=purpose, consumed=False, expires_at__gte=now 
            )
        except EmailOTP.DoesNotExist:
            return None


    #Marks the OTP as used, so it can’t be reused
    @staticmethod
    def consume_email_otp(otp: EmailOTP):
        otp.consumed = True
        otp.save(update_fields=["consumed"]) #Mark the OTP as used


    #Updates profile information for a PIN
    @staticmethod
    @transaction.atomic
    def update_profile_fields(*, pin: PersonInNeed, **fields) -> PersonInNeed:

        for k, v in fields.items():
            setattr(pin, k, v)
        pin.save(update_fields=list(fields.keys()))
        return pin

    #Finds all claims for the PIN's completed requests.
    @staticmethod
    def list_completed_with_claims(*, pin_id: str):
        return (
            ClaimReport.objects.filter(
                request__pin_id=pin_id,
                request__status=RequestStatus.COMPLETE
            )
            .select_related("request", "cv")
            .prefetch_related("disputes")
            .order_by("-created_at")
        )

    #Marks a claim as verified, PIN agrees with the claim and saves status
    @staticmethod
    @transaction.atomic
    def verify_claim(*, claim: ClaimReport) -> ClaimReport:
        claim.status = ClaimStatus.VERIFIED_BY_PIN
        claim.save(update_fields=["status"])
        return claim


    #Creates a new dispute record for the claim
    @staticmethod
    @transaction.atomic
    def dispute_claim(*, claim: ClaimReport, pin: PersonInNeed, reason: str, comment: str = "") -> ClaimDispute:


        dispute = ClaimDispute.objects.create(
            claim=claim, pin=pin, reason=reason, comment=comment
        )
        claim.status = ClaimStatus.DISPUTED_BY_PIN
        claim.save(update_fields=["status"])
        return dispute
    
    @staticmethod
    def create_flagged_request(*, request, flag_type: str, moderation_reason: str = "", resolved: bool = False):
        flag = FlaggedRequest.objects.create(
            request=request,
            flag_type=flag_type or FlagType.AUTO,
            csr=None, 
            reasonbycsr=(f"Auto moderation: {moderation_reason}".strip() if moderation_reason else "Auto moderation"),
            resolved=resolved,
        )
        return flag

