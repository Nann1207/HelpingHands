# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import FlaggedRequest, Request, RequestStatus

@receiver(post_save, sender=FlaggedRequest)
def move_request_to_review_on_open_flag(sender, instance: FlaggedRequest, created, **kwargs):

    if not instance.resolved:
        req_id = instance.request_id
        # Update directly to avoid extra selects; only change if not already REVIEW
        Request.objects.filter(pk=req_id).exclude(status=RequestStatus.REVIEW).update(status=RequestStatus.REVIEW)
