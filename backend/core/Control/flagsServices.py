

from __future__ import annotations
from typing import Optional

from django.db import transaction

from core.models import FlaggedRequest, FlagType, Request, CSRRep


@transaction.atomic
def auto_flag_request(*, req: Request, reason: str = "") -> FlaggedRequest:
    clean_reason = (reason or "").strip() or "Auto moderation flagged this request."
    return FlaggedRequest.objects.create(
        request=req,
        flag_type=FlagType.AUTO,
        csr=None,
        reasonbycsr=clean_reason,
    )


@transaction.atomic
def manual_flag_request(*, req: Request, csr: CSRRep, reason: str) -> FlaggedRequest:

    clean_reason = (reason or "").strip() or "CSR manually flagged this request."
    return FlaggedRequest.objects.create(
        request=req,
        flag_type=FlagType.MANUAL,
        csr=csr,
        reasonbycsr=clean_reason,
    )


def list_flags_for_request(*, req: Request):
    return req.flags.select_related("csr", "resolved_by").order_by("-created_at")
