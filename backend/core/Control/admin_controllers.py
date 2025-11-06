# core/control/admin_controllers.py
"""
CONTROL layer — class-based “controllers” for Platform Admin use-cases.
- No HTTP/DRF imports here.
- Pure business logic + ORM via repositories/helpers.
- Composition over inheritance (do NOT subclass Django models).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta, date
from io import StringIO
from typing import Optional, Dict, Any, Tuple, Iterable

import csv
from django.db.models import Count, QuerySet
from django.db.models.functions import TruncDate, TruncMonth, TruncYear
from django.utils import timezone

try:
    from django.db.models.functions import TruncWeek
    HAS_TRUNCWEEK = True
except Exception:
    HAS_TRUNCWEEK = False

from core.models import (
    PersonInNeed, CV, CSRRep, PA,
    Request, RequestStatus,
    FlaggedRequest, FlagType,
)

# ---------- Helpers / Repositories ----------

def _parse_date_or_none(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None

def _truncator(granularity: str):
    g = (granularity or "day").lower()
    if g == "year":
        return TruncYear, "%Y"
    if g == "month":
        return TruncMonth, "%Y-%m"
    if g == "week" and HAS_TRUNCWEEK:
        return TruncWeek, "%G-W%V"
    return TruncDate, "%Y-%m-%d"

@dataclass(frozen=True)
class DateRange:
    start: date
    end: date

    @classmethod
    def from_strings(cls, date_from: Optional[str], date_to: Optional[str], default_days=14):
        end = _parse_date_or_none(date_to) or timezone.now().date()
        start = _parse_date_or_none(date_from) or (end - timedelta(days=default_days))
        return cls(start=start, end=end)

class RequestRepository:
    """All Request-related reads."""
    @staticmethod
    def by_created_range(dr: DateRange) -> QuerySet[Request]:
        return Request.objects.filter(
            created_at__date__gte=dr.start,
            created_at__date__lte=dr.end
        )

class ProfileRepository:
    """Aggregates across the three profile tables; per-model helpers below."""
    @staticmethod
    def new_by_bucket(Model, dr: DateRange, trunc_fn):
        # All profiles have created_at now (from BaseProfile).
        return (Model.objects
                .filter(created_at__date__gte=dr.start, created_at__date__lte=dr.end)
                .annotate(bucket=trunc_fn("created_at"))
                .values("bucket")
                .annotate(cnt=Count("id"))
                .order_by("bucket"))

class FlagRepository:
    @staticmethod
    def filtered(*, resolved: Optional[bool], flag_type: Optional[str],
                 date_from: Optional[str], date_to: Optional[str]):
        qs = FlaggedRequest.objects.select_related("request", "csr", "resolved_by")
        if resolved is not None:
            qs = qs.filter(resolved=resolved)
        if flag_type in (FlagType.AUTO, FlagType.MANUAL):
            qs = qs.filter(flag_type=flag_type)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs.order_by("-created_at")

# ---------- Controllers (3-class format) ----------

class AdminMetricsController:
    """KPI cards + time-series for Platform Admin dashboard."""
    @staticmethod
    def get_metrics(*, granularity: str = "day",
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> Dict[str, Any]:

        trunc_fn, fmt = _truncator(granularity)
        dr = DateRange.from_strings(date_from, date_to)

        # KPI cards
        totals = {
            "total_pins": PersonInNeed.objects.count(),
            "total_cvs":  CV.objects.count(),
            "total_csrs": CSRRep.objects.count(),
        }
        req_counts = {
            "review":   Request.objects.filter(status=RequestStatus.REVIEW).count(),
            "pending":  Request.objects.filter(status=RequestStatus.PENDING).count(),
            "active":   Request.objects.filter(status=RequestStatus.ACTIVE).count(),
            "complete": Request.objects.filter(status=RequestStatus.COMPLETE).count(),
        }
        flag_counts = {
            "open":     FlaggedRequest.objects.filter(resolved=False).count(),
            "resolved": FlaggedRequest.objects.filter(resolved=True).count(),
        }

        # Requests by status (bucketed)
        req_buckets: Dict[str, Dict[str, int]] = {}
        for row in (RequestRepository.by_created_range(dr)
                    .annotate(bucket=trunc_fn("created_at"))
                    .values("bucket", "status")
                    .annotate(cnt=Count("id"))
                    .order_by("bucket")):
            key = row["bucket"].strftime(fmt) if hasattr(row["bucket"], "strftime") else str(row["bucket"])
            if key not in req_buckets:
                req_buckets[key] = {"date": key, "review": 0, "pending": 0, "active": 0, "complete": 0}
            req_buckets[key][row["status"]] += row["cnt"]
        requests_by_status = list(req_buckets.values())

        # New users per bucket
        users_map: Dict[str, Dict[str, int]] = {}
        for label, Model in (("pins", PersonInNeed), ("cvs", CV), ("csrs", CSRRep)):
            for row in ProfileRepository.new_by_bucket(Model, dr, trunc_fn):
                key = row["bucket"].strftime(fmt) if hasattr(row["bucket"], "strftime") else str(row["bucket"])
                if key not in users_map:
                    users_map[key] = {"date": key, "pins": 0, "cvs": 0, "csrs": 0}
                users_map[key][label] += row["cnt"]
        new_users_series = list(users_map.values())

        return {
            "cards": {**totals, "requests": req_counts, "flags": flag_counts},
            "charts": {
                "granularity": granularity,
                "range": {"from": dr.start.isoformat(), "to": dr.end.isoformat()},
                "requests_by_status": requests_by_status,
                "new_users": new_users_series,
            },
        }

class AdminFlagController:
    """Flag lifecycle (list, resolve)."""
    @staticmethod
    def list_flags(*, resolved: Optional[bool], flag_type: Optional[str],
                   date_from: Optional[str], date_to: Optional[str]):
        return FlagRepository.filtered(
            resolved=resolved, flag_type=flag_type, date_from=date_from, date_to=date_to
        )

    @staticmethod
    def resolve_flag(*, flag_id: int, pa_user, notes: str = "") -> FlaggedRequest:
        flag = FlaggedRequest.objects.select_related("resolved_by").get(pk=flag_id)
        # Ensure resolver has a PA profile
        try:
            pa_profile = pa_user.pa
        except PA.DoesNotExist:
            raise PermissionError("Current user is not a Platform Admin (PA profile missing).")

        from django.utils import timezone as _tz
        flag.resolved = True
        flag.resolved_at = _tz.now()
        flag.resolved_by = pa_profile
        if notes:
            flag.resolution_notes = (flag.resolution_notes + "\n" + notes).strip() if flag.resolution_notes else notes
        flag.save()
        return flag

class AdminReportController:
    @staticmethod
    def export_requests_csv(*, date_from: Optional[str] = None,
                            date_to: Optional[str] = None) -> Tuple[str, bytes]:
        qs = Request.objects.select_related("pin", "cv").all()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "request_id", "status", "service_type",
            "appointment_date", "appointment_time",
            "pin_id", "pin_name", "cv_id", "cv_name",
            "created_at",
        ])
        for r in qs.order_by("-created_at"):
            writer.writerow([
                r.id,
                r.status,
                r.service_type,
                r.appointment_date.isoformat(),
                r.appointment_time.isoformat(),
                getattr(r.pin, "id", ""),
                getattr(r.pin, "name", "") if r.pin else "",
                getattr(r.cv, "id", ""),
                getattr(r.cv, "name", "") if r.cv else "",
                r.created_at.isoformat(),
            ])
        return "requests_export.csv", buf.getvalue().encode("utf-8-sig")