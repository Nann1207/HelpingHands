

from __future__ import annotations
from typing import Optional, Dict, Any

from django.db import transaction

from core.models import (
    Request, RequestStatus,
    PersonInNeed, CV,
    ServiceCategory,
)


# ---------- helpers ----------

def _ensure_category(value: str) -> str:
    """
    Validate service_type is one of ServiceCategory values.
    Raises ValueError if invalid.
    """
    valid = [c[0] for c in ServiceCategory.choices]
    if value not in valid:
        raise ValueError(f"Invalid service_type '{value}'. Valid: {valid}")
    return value


def _assert_status(req: Request, expected: RequestStatus | str):
    """Raise ValueError if request is not in the expected status."""
    exp = expected if isinstance(expected, str) else expected.value
    if req.status != exp:
        raise ValueError(f"Invalid status transition. Expected '{exp}', got '{req.status}'.")


# ---------- use-cases ----------

@transaction.atomic
def create_request(*,
                   pin: PersonInNeed,
                   service_type: str,
                   appointment_date,
                   appointment_time,
                   pickup_location: str,
                   service_location: str,
                   description: str) -> Request:
    """
    PIN raises a new request. New requests always start in REVIEW.
    Boundary should enforce 'pin' is the current user’s PIN profile.
    """
    _ensure_category(service_type)
    req = Request.objects.create(
        pin=pin,
        service_type=service_type,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        pickup_location=pickup_location,
        service_location=service_location,
        description=description,
        status=RequestStatus.REVIEW,   # start in review
    )
    return req


@transaction.atomic
def moderation_pass(*, req: Request) -> Request:
    """
    Auto moderation passed → REVIEW → PENDING.
    """
    _assert_status(req, RequestStatus.REVIEW)
    req.status = RequestStatus.PENDING
    req.save(update_fields=["status", "updated_at"])
    return req


@transaction.atomic
def moderation_reject(*, req: Request) -> Request:
    """
    Moderation reject → REVIEW → REJECTED.
    (You added REJECTED in RequestStatus; PAs can later ask PIN to edit and resubmit.)
    """
    _assert_status(req, RequestStatus.REVIEW)
    req.status = RequestStatus.REJECTED
    req.save(update_fields=["status", "updated_at"])
    return req


@transaction.atomic
def assign_cv(*, req: Request, cv: CV) -> Request:
    """
    CSR/PA matches a CV to the request.
    Allowed only when req is PENDING.
    Transition: PENDING → ACTIVE (cv set).
    """
    _assert_status(req, RequestStatus.PENDING)
    req.cv = cv
    req.status = RequestStatus.ACTIVE
    req.save(update_fields=["cv", "status", "updated_at"])
    return req


@transaction.atomic
def unassign_cv(*, req: Request) -> Request:
    """
    Optional helper: remove CV from an ACTIVE request and demote back to PENDING.
    Useful if match fell through.
    """
    _assert_status(req, RequestStatus.ACTIVE)
    req.cv = None
    req.status = RequestStatus.PENDING
    req.save(update_fields=["cv", "status", "updated_at"])
    return req


@transaction.atomic
def complete_request(*, req: Request) -> Request:
    """
    Service done → ACTIVE → COMPLETE.
    CV stays attached for traceability.
    """
    _assert_status(req, RequestStatus.ACTIVE)
    req.status = RequestStatus.COMPLETE
    req.save(update_fields=["status", "updated_at"])
    return req


def list_requests(*,
                  status: Optional[str] = None,
                  service_type: Optional[str] = None,
                  date_from: Optional[str] = None,
                  date_to: Optional[str] = None):
    """
    Generic listing helper for dashboards.
    Boundary serializes the queryset or maps it into cards/tables.
    """
    qs = Request.objects.select_related("pin", "cv").all()
    if status:
        qs = qs.filter(status=status)
    if service_type:
        qs = qs.filter(service_type=service_type)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs.order_by("-created_at")



