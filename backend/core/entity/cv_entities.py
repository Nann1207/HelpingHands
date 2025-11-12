from __future__ import annotations
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from core.models import (
    CV, Request, RequestStatus,
    ClaimReport, ClaimStatus, MatchQueue, MatchQueueStatus, ChatRoom
)

class CvEntity:
    """
    DB-only for CV use-cases.
    """

    # ---------- DASHBOARD LISTS ----------

    @staticmethod
    def list_pending_offers(*, cv_id: str):
        """
        Offers that are currently ACTIVE for this CV from the match queue.
        Auto-removal happens naturally when MatchQueue advances/expires;
        this list only shows offers where this CV is the current slot.
        """
        now = timezone.now()
        return (
            Request.objects
            .filter(
                Q(match_queue__status=MatchQueueStatus.ACTIVE),
                Q(match_queue__deadline__gte=now) | Q(match_queue__deadline__isnull=True),
                Q(match_queue__current_index=1, match_queue__cv1queue_id=cv_id)
                | Q(match_queue__current_index=2, match_queue__cv2queue_id=cv_id)
                | Q(match_queue__current_index=3, match_queue__cv3queue_id=cv_id),
            )
            .select_related("pin", "cv", "match_queue")
            .order_by("match_queue__deadline", "appointment_date", "appointment_time")
        )

    @staticmethod
    def list_active_sorted(*, cv_id: str):
        """
        Accepted requests (ACTIVE), sorted by upcoming appointment first.
        """
        return (
            Request.objects.filter(cv_id=cv_id, status=RequestStatus.ACTIVE)
            .select_related("pin", "cv")
            .order_by("appointment_date", "appointment_time", "created_at")
        )

    @staticmethod
    def list_completed(*, cv_id: str):
        return (
            Request.objects.filter(cv_id=cv_id, status=RequestStatus.COMPLETE)
            .select_related("pin", "cv")
            .order_by("-completed_at", "-updated_at")
        )

    @staticmethod
    def list_requests(*, cv_id: str, status: str):
        return (
            Request.objects.filter(cv_id=cv_id, status=status)
            .order_by("-created_at")
        )

    # ---------- CLAIMS ----------

    @staticmethod
    @transaction.atomic
    def create_claim_report(*, request: Request, cv: CV, **data) -> ClaimReport:
        return ClaimReport.objects.create(request=request, cv=cv, **data)

    @staticmethod
    def create_claim(**kwargs) -> ClaimReport:
        return ClaimReport.objects.create(**kwargs)

    @staticmethod
    def list_my_claims(*, cv_id: str):
        return (
            ClaimReport.objects
            .filter(cv_id=cv_id)
            .select_related("request", "cv")
            .order_by("-created_at")
        )
