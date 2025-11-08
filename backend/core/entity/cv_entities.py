# core/entity/cv_entity.py
from __future__ import annotations
from django.db import transaction
from core.models import (
    CV, Request, RequestStatus,
    ClaimReport, ClaimStatus
)

class CvEntity:
    """
    DB-only for CV use-cases.
    """

    @staticmethod
    def list_requests(*, cv_id: str, status: str):
        return (
            Request.objects.filter(cv_id=cv_id, status=status)
            .order_by("-created_at")
        )

    @staticmethod
    @transaction.atomic
    def create_claim_report(*, request: Request, cv: CV, **data) -> ClaimReport:
        return ClaimReport.objects.create(request=request, cv=cv, **data)
