# core/control/admin_controllers.py
from __future__ import annotations
from django.db.models import Count  

from typing import Optional, Dict, Any, Tuple

from core.entity.admin_entities import (

    DateRange, truncator,
    RequestEntity, ProfileEntity, FlagEntity
)


from typing import Optional, Dict, Any, Tuple
from django.db.models import Count

from core.entity.admin_entities import (
    DateRange, truncator,
    RequestEntity, ProfileEntity, FlagEntity
)


class AdminMetricsController:

    #To get the metrics for the dashboard
    @staticmethod
    def get_metrics(*, granularity: str = "day",
                    date_from: Optional[str] = None,
                    date_to: Optional[str] = None) -> Dict[str, Any]:

        trunc_fn, fmt = truncator(granularity) #Get the truncation function and format based on granularity (year, month, day)
        dr = DateRange.from_strings(date_from, date_to) #Create a date range object from the provided date strings

        #Uses all 3 entities
        totals_profiles = ProfileEntity.totals()                      
        req_counts      = RequestEntity.count_by_status()             
        flag_counts     = FlagEntity.counts()                        

        cards = {
            #Requests by status
            "Review":   req_counts.get("review", 0),
            "Pending":  req_counts.get("pending", 0),
            "Rejected": req_counts.get("rejected", 0),
            "Active":   req_counts.get("active", 0),
            "Completed":req_counts.get("complete", 0),

            #Flags
            "Open Flags":     flag_counts.get("open", 0),
            "Resolved Flags": flag_counts.get("resolved", 0),

            #User Profiles
            "Number of PIN": totals_profiles.get("total_pins", 0),
            "Number of CV":  totals_profiles.get("total_cvs", 0),
            "Number of CSR": totals_profiles.get("total_csrs", 0),
        }

        #Charts
        #Requests by status
        buckets: Dict[str, Dict[str, int]] = {} #This will hold one entry per date, bucket. Each date will have a nested dictionary counting requests by status


        qs = (RequestEntity.by_created_range(dr) #Get all requests in the date range
              .annotate(bucket=trunc_fn("created_at")) #Group them into buckets
              .values("bucket", "status") # only need bucket and status column for counting
              .annotate(cnt=Count("id")) #Count
              .order_by("bucket")) #Order by bucket

        for row in qs:
            key = row["bucket"].strftime(fmt) if hasattr(row["bucket"], "strftime") else str(row["bucket"])
            if key not in buckets: #If the bucket (date) does not exist, create it and intialise all status to be 0.
                buckets[key] = {
                    "date": key,
                    "review": 0, "pending": 0, "rejected": 0, "active": 0, "complete": 0,
                }
            buckets[key][row["status"]] += row["cnt"] #It adds the count of requests row["cnt"] to the correct status like pending or review" inside that date’s bucket

        requests_by_status = list(buckets.values()) #Covert to list


        return {
            "cards": cards,
            "charts": {
                "granularity": granularity,
                "range": {"from": dr.start.isoformat(), "to": dr.end.isoformat()},
                "requests_by_status": requests_by_status,           
            },
        } #returns the results in a dictionary




class AdminFlagController:
    @staticmethod
    def list_flags(*, resolved=None, flag_type=None, date_from=None, date_to=None):
        return FlagEntity.filtered(resolved=resolved, flag_type=flag_type, date_from=date_from, date_to=date_to) 

    @staticmethod
    def accept_flag(*, flag_id: int, pa_user, notes: str = ""):
        return FlagEntity.accept_flag(flag_id=flag_id, pa_user=pa_user, notes=notes) #Mark the flag as accept and move it on to pending

    @staticmethod
    def reject_flag(*, flag_id: int, pa_user, notes: str = ""): #Mark a flag as rejected.
        return FlagEntity.reject_flag(flag_id=flag_id, pa_user=pa_user, notes=notes)




class AdminReportController:
    @staticmethod
    def export_requests_csv(*, date_from: Optional[str] = None, #Export stats into a csv file
                            date_to: Optional[str] = None) -> Tuple[str, bytes]:
        return RequestEntity.export_csv(date_from, date_to)
