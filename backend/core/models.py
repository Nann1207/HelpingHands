import uuid
from django.db import models
from django.contrib.auth import get_user_model



#THIS SECTION IS FOR USER PROFILES


User = get_user_model() #Where the user's username, password and email are stored 


# Generates unique IDs for the different profiles
def pinid():
    return "PIN" + uuid.uuid4().hex[:8].upper()

def cvid():
    return "CV" + uuid.uuid4().hex[:8].upper()

def csrid():
    return "CSR" + uuid.uuid4().hex[:8].upper()

def pa_id():
    return "PA" + uuid.uuid4().hex[:8].upper()

def reqid():
    return "REQ" + uuid.uuid4().hex[:8].upper()


#Company details
class Company(models.Model):
    company_id = models.CharField(max_length=50, unique=True) 
    companyname = models.CharField(max_length=200)
    JoinedDate = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.companyname} (ID: {self.company_id})"


#Service Category Choices
class ServiceCategory(models.TextChoices):
    HEALTHCARE = "Healthcare", "Healthcare"
    THERAPY = "Therapy", "Therapy"
    DIALYSIS = "Dialysis", "Dialysis"
    VACCINATION_CHECKUP = "Vaccination / Check-up", "Vaccination / Check-up"
    MOBILITY_ASSISTANCE = "Mobility Assistance", "Mobility Assistance"
    COMMUNITY_EVENT = "Community Event", "Community Event"


#Gender Choices: stored as 'male', shown as 'Male'
class GenderChoices(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"


#Language Choices 
class LanguageChoices(models.TextChoices):
    EN = "en", "English"
    ZH = "zh", "Chinese"
    TA = "ta", "Tamil"
    MS = "ms", "Malay"


#Base profile, necessary info needed for all profiles
class BaseProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE, #If the user is deleted, their profile is also deleted
        related_name="%(class)s",
    )
    name = models.CharField(max_length=150)
    dob = models.DateField(blank=False)  
    phone = models.CharField(max_length=8)
    address = models.CharField(max_length=255)
       
    created_at = models.DateTimeField(auto_now_add=True)  # set on insert
    updated_at = models.DateTimeField(auto_now=True)      # set on every save

    class Meta:
        abstract = True #no table created for BaseProfile, meant for the subclass to inherit them


#PIN profile
class PersonInNeed(BaseProfile):
    id = models.CharField(
        max_length=11, #3 letters for "PIN" and 8 characters for uuid
        primary_key=True,
        unique=True,
        editable=False,
        default=pinid, #This is to automatically call the pinid() function to generate the ID
    )
    preferred_cv_language = models.CharField( #means there are only a few languages to choose from,  defined earlier
        max_length=20, choices=LanguageChoices.choices
    )
    preferred_cv_gender = models.CharField( #means there are only a few languages to choose from,  defined earlier
        max_length=20, choices=GenderChoices.choices, blank=True
    )

    def __str__(self):
        return f"PIN: {self.id}, Name: {self.name} (user={self.user.username})"


#CV Profile
class CV(BaseProfile):
    id = models.CharField(
        max_length=10,  #2 letters "CV" and 8 random characeters
        primary_key=True,
        unique=True,
        editable=False,
        default=cvid,
    )
    gender = models.CharField(max_length=20, choices=GenderChoices.choices)
    main_language = models.CharField(max_length=20, choices=LanguageChoices.choices)
    second_language = models.CharField(max_length=20, choices=LanguageChoices.choices, blank=True)

    service_category_preference = models.CharField(
        max_length=50, choices=ServiceCategory.choices
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,  # if company is deleted, remove CV profile
        related_name="volunteers",
    )

    def __str__(self):
        return f"CV: {self.id}, {self.name}, Company: {self.company.companyname}"


#CSR Rep Profile
class CSRRep(BaseProfile):
    id = models.CharField(
        max_length=11,  #3 letters "CSR" and 8 random characeters
        primary_key=True,
        unique=True,
        editable=False,
        default=csrid,
    )
    gender = models.CharField(
        max_length=20, choices=GenderChoices.choices, blank=True
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,  # if company is deleted, remove CV profile
        related_name="csr_representatives",
    )
    def __str__(self):
        return f"CSR: {self.id}, {self.name}, Company: {self.company.companyname}"


#Admin profile
class PA(BaseProfile):
    id = models.CharField(
        max_length=10,  # 2 letters "PA" and 8 random characeters
        primary_key=True,
        unique=True,
        editable=False,
        default=pa_id,
    )

    def __str__(self):
        return f"PA: {self.id} {self.name}"



#THIS SECTION IS FOR PIN REQUESTS

class RequestStatus(models.TextChoices):
    REVIEW = "review", "Review"           #will go thru moderation/abuse check
    REJECTED = "rejected", "Rejected"     #denied by PA
    PENDING = "pending", "Pending"        #passed review; visible to CSR
    ACTIVE = "active", "Active"           #matched with cv
    COMPLETE = "complete", "Complete"     #Request finished


#A service request made by a PIN
class Request(models.Model):

    id = models.CharField(
        max_length=11, #RequestID 
        primary_key=True,
        editable=False,
        unique=True,
        default=reqid,
    )

    # Need to trace it back
    pin = models.ForeignKey(
        PersonInNeed,
        on_delete=models.CASCADE,    #if PIN leaves the system, keep the request history
        related_name="requests",
    )

    #when matched, store the CV (nullable until ACTIVE/COMPLETE)
    cv = models.ForeignKey(
        CV,
        on_delete=models.SET_NULL,   # if CV leaves the system, keep the request history
        null=True,
        blank=True,
        related_name="assigned_requests",
        help_text="Matched CV"
    )


    #Service type request
    service_type = models.CharField(
        max_length=50,
        choices=ServiceCategory.choices,
        help_text="Type of service requested."
    )


    # Appointment date/time
    appointment_date = models.DateField(help_text="Date of appointment.")
    appointment_time = models.TimeField(help_text="Time of appointment.")


    #Locations and description
    pickup_location = models.CharField(max_length=255)
    service_location = models.CharField(max_length=255)
    description = models.CharField(max_length=700)


    #Status of the request
    status = models.CharField(
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.REVIEW,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)   #set on create
    updated_at = models.DateTimeField(auto_now=True)       #set on every save

    class Meta:
        ordering = ["-created_at"] #newest requests first
        indexes = [
            models.Index(fields=["status"]),    #filter by status
            models.Index(fields=["appointment_date", "appointment_time"]), #filter by appointment datetime
            models.Index(fields=["pin"]),   #filter by PIN
        ]

    def __str__(self):
        return f"{self.id} [{self.status}] {self.service_type} for {self.pin.name}" #display object


#THIS IS FOR PA
class FlagType(models.TextChoices):
    AUTO = "auto", "Auto-Flagged"
    MANUAL = "manual", "Manually Flagged by CSR"


#Stores both auto and manual flags for a Request
class FlaggedRequest(models.Model):

    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="flags"
    )

    flag_type = models.CharField(
        max_length=10,
        choices=FlagType.choices
    )

    csr = models.ForeignKey(
        CSRRep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, #auto-flags does not have a CSR
        related_name="flags_made",
    )

    reason = models.TextField(
        blank=True,
        help_text="Why this was flagged (auto reason or CSR comment)."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    
    resolved = models.BooleanField(default=False) #Whether the flag has been resolved
    resolved_at = models.DateTimeField(null=True, blank=True)  
    resolved_by = models.ForeignKey(
        PA,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flags_resolved",
        help_text="PA who resolved the flag."
    )
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["flag_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        who = self.csr.name if self.csr else "system" #If auto it will show system
        return f"Flag {self.flag_type} on {self.request_id} by {who}"


