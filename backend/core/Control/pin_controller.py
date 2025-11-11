# core/Control/pin_controller.py
from __future__ import annotations
from datetime import timedelta
import random
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.hashers import make_password

from core.models import (
    PersonInNeed, Request, 
    ClaimReport, DisputeReason, OtpPurpose, RequestStatus, FlagType
)
from core.entity.pin_entity import PinEntity

#Moderation service for checking request descriptions
class ModerationService:

    #Categories of bad terms
    VIOLENCE = ["kill", "murder", "bomb", "gun", "fight", "assault"]
    ABUSE = ["abuse", "harass", "rape", "molest", "bully"]
    DISCRIMINATION = ["racist", "sexist", "hate", "terrorist"]
    SELF_HARM = ["suicide", "self-harm", "cutting", "die", "depress"]
    EXPLICIT = ["nude", "porn", "sex", "drugs", "alcohol"]

    #check text for any bad terms
    @staticmethod
    def check(text: str) -> tuple[bool, str]:
        text = (text or "").lower()

        for word in ModerationService.VIOLENCE:
            if word in text:
                return True, "violence"

        for word in ModerationService.ABUSE:
            if word in text:
                return True, "abuse"

        for word in ModerationService.DISCRIMINATION:
            if word in text:
                return True, "discrimination"

        for word in ModerationService.SELF_HARM:
            if word in text:
                return True, "self_harm"

        for word in ModerationService.EXPLICIT:
            if word in text:
                return True, "explicit"

        #no bad terms found
        return False, ""


class PinController:

    #Ensure user its PIN
    @staticmethod
    def _ensure_is_pin(user) -> PersonInNeed:
        if not hasattr(user, "personinneed"):
            raise PermissionDenied("Not a PIN user.")
        return user.personinneed

    #Ensure user is PIN, runs moderation on description, creates request
    @staticmethod
    def submit_request(*, user, **payload) -> Request:
        pin = PinController._ensure_is_pin(user)

        description = payload.get("description", "")
        flagged, reason = ModerationService.check(description)
 
        #Set request status
        payload["status"] = RequestStatus.REVIEW if flagged else RequestStatus.PENDING

        #Create the request through Entity
        req = PinEntity.create_request(pin=pin, **payload)

        # If auto-flagged: create corresponding FlaggedRequest via Entity
        if flagged:
            PinEntity.create_flagged_request(
                request=req,
                flag_type=FlagType.AUTO,
                moderation_reason=reason,
                resolved=False,
            )

        return req



    #Ensures PIN user and lists their requests, filtered by status
    @staticmethod
    def list_my_requests(*, user, status: str | None = None):
        pin = PinController._ensure_is_pin(user)
        return PinEntity.list_requests(pin_id=pin.id, status=status)



    #OTP needed to update profile info 
    @staticmethod
    def start_profile_update_otp(*, user) -> dict:
        from django.core.mail import send_mail #Backend email service
        pin = PinController._ensure_is_pin(user)

        code = f"{random.randint(100000, 999999)}" #Generated 6-digit OTP
        expires_at = timezone.now() + timedelta(minutes=5) #OTP valid for 5 min
        PinEntity.create_email_otp( #Saves OTP to DB
            email=pin.user.email, code=code, purpose=OtpPurpose.PROFILE_UPDATE, expires_at=expires_at
        )
        

        send_mail( #Built in Django email function
            subject="Your Helping Hands OTP Code",
            message=f"Your OTP is {code}. It will expire in 10 minutes.",
            from_email=None,  # uses default email
            recipient_list=[pin.user.email],
        )
        return {"sent": True, "expires_at": expires_at} #Indicates OTP email sent


    @staticmethod
    def confirm_profile_update(*, user, code: str, **fields):
        pin = PinController._ensure_is_pin(user)
        otp = PinEntity.get_valid_email_otp( #checks OTP validity
            email=pin.user.email, code=code, purpose=OtpPurpose.PROFILE_UPDATE
        )
        if not otp:
            raise ValidationError("Invalid or expired OTP.")
        PinEntity.update_profile_fields(pin=pin, **fields) #updates profile fields
        PinEntity.consume_email_otp(otp) #marks OTP as used
        return pin
    
    def start_password_change_otp(*, user) -> dict:
        from django.core.mail import send_mail
        pin = PinController._ensure_is_pin(user)

        code = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=10)
        PinEntity.create_email_otp(
            email=pin.user.email,
            code=code,
            purpose=OtpPurpose.PASSWORD_CHANGE,   # <<< key difference
            expires_at=expires_at,
        )
        send_mail(
            subject="Your Helping Hands Password OTP",
            message=f"Your OTP is {code}. It will expire in 10 minutes.",
            from_email=None,
            recipient_list=[pin.user.email],
        )
        return {"sent": True, "expires_at": expires_at}

   
    @staticmethod
    def change_password_with_otp(*, user, code: str, new_password: str):
        pin = PinController._ensure_is_pin(user)
        otp = PinEntity.get_valid_email_otp( #Checks if the OTP they entered exists, matches their email and is still valid.
            email=pin.user.email, code=code, purpose=OtpPurpose.PASSWORD_CHANGE
        )
        if not otp:
            raise ValidationError("Invalid or expired OTP.") #If OTP invalid, raise error
        pin.user.password = make_password(new_password) #Hashes and sets new password
        pin.user.save(update_fields=["password"]) #Saves new password to DB
        PinEntity.consume_email_otp(otp) #Marks OTP as used
        return {"ok": True}



    #it get all the completed requests with any related claims and disputes
    @staticmethod
    def list_completed_with_claims(*, user):
        pin = PinController._ensure_is_pin(user)
        return PinEntity.list_completed_with_claims(pin_id=pin.id)


    #Verify a claim made by the cv
    @staticmethod
    def verify_claim(*, user, claim_id: str):
        pin = PinController._ensure_is_pin(user)
        claim = ClaimReport.objects.select_related("request").get(pk=claim_id)
        if claim.request.pin_id != pin.id: 
            raise PermissionDenied("Not your claim.")
        return PinEntity.verify_claim(claim=claim) 


    
    @staticmethod
    def dispute_claim(*, user, claim_id: str, reason: str, comment: str = ""):
        pin = PinController._ensure_is_pin(user)  #Ensure user is PIN
        if reason not in DisputeReason.values: #ensure the reason is one of the options
            raise ValidationError("Invalid dispute reason.")
        claim = ClaimReport.objects.select_related("request").get(pk=claim_id) #Get the claim
        if claim.request.pin_id != pin.id:
            raise PermissionDenied("Not your claim.")
        return PinEntity.dispute_claim(claim=claim, pin=pin, reason=reason, comment=comment) #Mark the claim as disputed 

    def list_claims_for_pin(*, user):
        if not hasattr(user, "personinneed"):
            raise PermissionDenied("Not allowed.")
        pin = user.personinneed
        return ClaimReport.objects.filter(request__pin=pin).select_related("request", "cv")