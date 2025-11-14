# core/entity/admin_entities.py


#THIS IS THE ADMIN ENTITY LAYER

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from io import StringIO
from typing import Optional, Dict, Any, Tuple, Iterable
import csv 
from datetime import datetime, date


from django.db import transaction
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
    FlaggedRequest, FlagType, ResolutionOutcome,
)

#HELPER FUNCTIONS 

def _parse_date_or_none(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None #It basically converts string dates to date objects

def truncator(granularity: str):
    g = (granularity or "day").lower()
    if g == "year":
        return TruncYear, "%Y" #Group by year, its to cute the full date to just year
    if g == "month":
        return TruncMonth, "%Y-%m" #Group by month 
    if g == "week" and HAS_TRUNCWEEK:
        return TruncWeek, "%G-W%V" #Group by week
    return TruncDate, "%Y-%m-%d" #Group by the calendar day



@dataclass(frozen=True) #once datarange objecct is created, it cannot be modified 
class DateRange: #A class to store 2 dates: start and end
    start: date
    end: date

    @classmethod
    def from_strings(cls, date_from: Optional[str], date_to: Optional[str]): #a class method, it belongs to the class. Takes in 2 optional date strings
        end = _parse_date_or_none(date_to) or timezone.now().date() #The end date is either today's date or the provided one.

        earliest = Request.objects.order_by("created_at").values_list("created_at", flat=True).first() #Looks at the Request database table, finds the earliest request created by sorting all requests by their creation date (created_at) from oldest to newest and then taking the first one
        earliest_date = earliest.date() if earliest else end #If earliest request exist, it takes that if not it just takes the end date

        start = _parse_date_or_none(date_from) or earliest_date #This converts the date_from, start date into a date object

        return cls(start=start, end=end)  #Returns a new DateRange object with the start and end dates set or if no dates were provided, it covers the entire range of available data, from the first request to today.



class RequestEntity:

    @staticmethod
    def by_created_range(dr: DateRange) -> QuerySet[Request]: #Returns all requests created between these two dates.
        return Request.objects.filter(
            created_at__date__gte=dr.start, 
            created_at__date__lte=dr.end
        )

    @staticmethod
    def count_by_status() -> Dict[str, int]: #This method counts how many requests are in each status category
        return {
            "review":   Request.objects.filter(status=RequestStatus.REVIEW).count(),
            "rejected": Request.objects.filter(status=RequestStatus.REJECTED).count(),
            "pending":  Request.objects.filter(status=RequestStatus.PENDING).count(),
            "active":   Request.objects.filter(status=RequestStatus.ACTIVE).count(),
            "complete": Request.objects.filter(status=RequestStatus.COMPLETE).count(),
        }


    @staticmethod
    @transaction.atomic #Ensures that the  databases changes are safe
    def update_status_after_pa_action(flag: FlaggedRequest, action: str) -> None:
        req = flag.request #Each FlaggedRequest is connected to a Request through a foreign key
        if not req:
            return

        update_fields = ["status"]

        if action == "reject":
            req.status = RequestStatus.REJECTED #If the action is "reject", it sets the request's status to REJECTED
        elif action == "accept":
            req.status = RequestStatus.PENDING #If the action is "resolve", it sets the request's status to PENDING
            # Pending requests must not keep any commit metadata to satisfy DB constraint
            req.committed_by_csr = None
            req.committed_at = None
            update_fields.extend(["committed_by_csr", "committed_at"])

        req.save(update_fields=update_fields) #Saves the updated status back to the database
    

    #Export the requests to CSV
    @staticmethod
    def export_csv(date_from: Optional[str], date_to: Optional[str]) -> Tuple[str, bytes]: #If no filter dates are given, it exports all requests

        qs = Request.objects.select_related("pin", "cv") #It is to fetch related objects immediately
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        buf = StringIO()
        writer = csv.writer(buf) #Allows us to write rows into that in-memory CSV.

        #Column headers
        writer.writerow([
            "request_id", "status", "service_type",
            "appointment_date", "appointment_time",
            "pin_id", "pin_name", "cv_id", "cv_name",
            "created_at",
        ])

        #This will be for the data rows
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


        #Statistics at the end 
        total = qs.count()
        status_counts = {     ##Filter the queryset with status and count them
            "Pending": qs.filter(status=RequestStatus.PENDING).count(), 
            "Review": qs.filter(status=RequestStatus.REVIEW).count(),
            "Active": qs.filter(status=RequestStatus.ACTIVE).count(),
            "Completed": qs.filter(status=RequestStatus.COMPLETE).count(),
            "Rejected": qs.filter(status=RequestStatus.REJECTED).count(),
            }

        writer.writerow([]) #This is an empty row for spacing
        writer.writerow(["SUMMARY:"])
        writer.writerow(["Total Requests", total])
        for status, count in status_counts.items():
                writer.writerow([status, count])

        return "requestsExport.csv", buf.getvalue().encode("utf-8-sig")




#Total counts of different user types
class ProfileEntity:
    @staticmethod
    def totals() -> Dict[str, int]:
        return {
            "total_pins": PersonInNeed.objects.count(),
            "total_cvs":  CV.objects.count(),
            "total_csrs": CSRRep.objects.count(),
        }


    @staticmethod
    def new_by_bucket(Model, dr: DateRange, trunc_fn): #This filter only records that were created within the date range

        return (Model.objects            #gte is greater than or equal to start date and lte is less than or equal to end date
                .filter(created_at__date__gte=dr.start, created_at__date__lte=dr.end) 
                .annotate(bucket=trunc_fn("created_at")) #Add a new column to each record called bucket, truncate the time part and parts of the date
                .values("bucket") #Group by bucket
                .annotate(cnt=Count("id")) #Count how many records are in each bucket
                .order_by("bucket")) 





class FlagEntity:

    @staticmethod
    def countsFlaggedRequest() -> Dict[str, int]:
        return {
            "open":     FlaggedRequest.objects.filter(resolved=False).count(), #How many flags are still open
            "resolved": FlaggedRequest.objects.filter(resolved=True).count(), #How many flags have been resolved
        }



    @staticmethod 
    def filtered(*, resolved: Optional[bool], flag_type: Optional[str],
                date_from: Optional[str], date_to: Optional[str]):
        qs = FlaggedRequest.objects.select_related("request", "csr", "resolved_by")

        if resolved is not None:
            qs = qs.filter(resolved=resolved) #This is to filter by whether the flag is resolved or not

        if flag_type in (FlagType.AUTO, FlagType.MANUAL):
            qs = qs.filter(flag_type=flag_type) #This filters by the type of flag

        
        def _parse_date(s: Optional[str]) -> Optional[date]: #Parse a string into a date object
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError: 
                return None  
            

        start = _parse_date(date_from)
        end = _parse_date(date_to)

        if start:
            qs = qs.filter(created_at__date__gte=start) #filter requests created on or after that date.
        if end:
            qs = qs.filter(created_at__date__lte=end) # filter requests created on or before that date.


        return qs.order_by("-created_at") #sort the results by creation date in descending ordder




    #This function basiaclly marks a flag as closed and sets the outcome to accepted
    @staticmethod
    @transaction.atomic
    def accept_flag(*, flag_id: int, pa_user, notes: str = "") -> FlaggedRequest:
        pa_profile = pa_user.pa 
        flag = FlaggedRequest.objects.select_related("request", "resolved_by").get(pk=flag_id) 

        flag.resolved = True #Resolve the flag
        flag.resolved_at = timezone.now() #Set the resolved time to now
        flag.resolved_by = pa_profile #Platform admin
        flag.resolution_outcome = ResolutionOutcome.ACCEPTED 
        if notes:
            flag.resolution_notes = (flag.resolution_notes + "\n" + notes).strip() if flag.resolution_notes else notes
        flag.save()

        RequestEntity.update_status_after_pa_action(flag, action="accept")  #Calls the method to update the request status to review to pending
        return flag
    


    @staticmethod
    @transaction.atomic #This is to reject a flag and set the outcome to rejected 
    def reject_flag(*, flag_id: int, pa_user, notes: str = "") -> FlaggedRequest:
        pa_profile = pa_user.pa
        flag = FlaggedRequest.objects.select_related("request", "resolved_by").get(pk=flag_id)

        flag.resolved = True
        flag.resolved_at = timezone.now()
        flag.resolved_by = pa_profile
        flag.resolution_outcome = ResolutionOutcome.REJECTED
        add = "Rejected by PA." if not notes else f"Rejected by PA: {notes}" #Check if PA got say anything, if not just say rejected by PA
        flag.resolution_notes = (flag.resolution_notes + "\n" + add).strip() if flag.resolution_notes else add #Combine existing note with new note by PA
        flag.save() #Save the changes to the database, update one object

        RequestEntity.update_status_after_pa_action(flag, action="reject")  #Calls the method to update the request status to review to reject
        return flag 



    #Get counts of open and resolved flags
    @staticmethod
    def counts() -> Dict[str, int]:
        return {
            "open":     FlaggedRequest.objects.filter(resolved=False).count(),
            "resolved": FlaggedRequest.objects.filter(resolved=True).count(),
        }


