from django.utils import timezone
from datetime import datetime, timedelta
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.conf import settings



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


class ResolutionOutcome(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"   # PA accepted the flag, Request continues
    REJECTED = "rejected", "Rejected"   # PA rejected, Request rejected


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
        on_delete=models.SET_NULL,   #if CV leaves the system, keep the request history
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
    completed_at = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # If status is COMPLETE and we haven't recorded the time yet, set it now
        if self.status == RequestStatus.COMPLETE and self.completed_at is None:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"] #newest requests first
        indexes = [
            models.Index(fields=["status"]),    #filter by status
            models.Index(fields=["appointment_date", "appointment_time"]), #filter by appointment datetime
            models.Index(fields=["pin"]),   #filter by PIN
        ]

    def __str__(self):
        return f"{self.id} [{self.status}] {self.service_type} for {self.pin.name}" #display object
    

class ShortlistedRequest(models.Model):

    id = models.BigAutoField(primary_key=True)

    csr = models.ForeignKey(
        CSRRep,
        on_delete=models.CASCADE,
        related_name="shortlists",
    )
    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="shortlisted_by",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["csr", "request"],
                name="uq_shortlist_csr_request"
            )
        ]
        indexes = [
            models.Index(fields=["csr"]),
            models.Index(fields=["request"]),
            models.Index(fields=["-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Shortlist(csr={self.csr_id}, req={self.request_id})"





#THIS IS FOR PA
class FlagType(models.TextChoices):
    AUTO = "auto", "Auto-Flagged" #System will raise this
    MANUAL = "manual", "Manually Flagged by CSR" #CSR will raise this


#Stores both auto and manual flags for a Request
class FlaggedRequest(models.Model):

    request = models.ForeignKey( #Links to the Request being flagged
        Request,
        on_delete=models.CASCADE,
        related_name="flags"
    )

    flag_type = models.CharField(
        max_length=10,
        choices=FlagType.choices
    ) #Either auto or manual flag

    csr = models.ForeignKey(
        CSRRep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True, #auto-flags does not have a CSR
        related_name="flags_made",
    )

    reasonbycsr = models.TextField(
        blank=True,
        help_text="Why this was flagged (auto reason or CSR comment)."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    
    resolved = models.BooleanField(default=False) #This is to get all the open flags easily and an indicator if resolved or not, True is done, False still open
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        PA, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="flags_resolved"
    )
    resolution_notes = models.TextField(blank=True)

   
    resolution_outcome = models.CharField(
        max_length=10,
        choices=ResolutionOutcome.choices,
        null=True, blank=True,
        help_text="Whether PA accepted or rejected this flag." #Basically the outcome.
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["flag_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        who = self.csr.name if self.csr else "system" #If auto it will show system.
        
        return f"Flag {self.flag_type} on {self.request.id} by {who}"


#THIS PART IS FOR CV AND PIN 

#2 reasons why OTP is sent: profile update and password change
class OtpPurpose(models.TextChoices):
    PROFILE_UPDATE = "profile_update", "Profile Update"
    PASSWORD_CHANGE = "password_change", "Password Change"



#Each OTP sent to email is stored here
class EmailOTP(models.Model):
    email = models.EmailField() #The email the OTP is sent to
    code = models.CharField(max_length=6) #The OTP code itself
    purpose = models.CharField(max_length=30, choices=OtpPurpose.choices) #The purpose of the OTP
    expires_at = models.DateTimeField() #When the OTP becomes invalid
    consumed = models.BooleanField(default=False) #Marks if the OTP was already used (True = used, False = still valid).
    created_at = models.DateTimeField(auto_now_add=True) #auto store time, when the OTP was created 

    class Meta:
        indexes = [models.Index(fields=["email", "purpose", "expires_at", "consumed"])] #Adds an index for faster lookup


# --- Claim reporting by CV, with PIN dispute ---
class ClaimCategory(models.TextChoices):
    TRANSPORT = "transport", "Transportation"
    FOOD = "food", "Food"
    MEDS = "meds", "Medication"
    APPOINTMENT = "appointment", "Appointment"
    OTHER = "other", "Other"

class PaymentMethod(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    PAYNOW = "paynow", "Bank Paynow"
    PAYLAH = "paylah", "DBS PayLah"

class ClaimStatus(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    VERIFIED_BY_PIN = "verified_by_pin", "Verified by PIN"
    DISPUTED_BY_PIN = "disputed_by_pin", "Disputed by PIN"
    REJECTED_BY_CSR = "rejected_by_csr", "Rejected by CSR"  
    REIMBURSED_BY_CSR = "reimbursed_by_csr", "Reimbursed by CSR"  


def claimid():
    return "CLM" + uuid.uuid4().hex[:8].upper() #Claim ID which is primary key

class ClaimReport(models.Model):
    id = models.CharField(max_length=11, 
                          primary_key=True, 
                          editable=False, 
                          default=claimid, 
                          unique=True)
    
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="claims") #Request being claimed for
    cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name="claims") #CV making the claim

    category = models.CharField(max_length=20, choices=ClaimCategory.choices) #Category of claim
    expense_date = models.DateField() #Date of expense
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]) #Amount claimed
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)    #Payment method used
    description = models.CharField(max_length=600, blank=True) #Description of claim
    receipt = models.FileField(upload_to="receipts/", blank=False, null=False) #Receipt upload 
    
    status = models.CharField(max_length=20, choices=ClaimStatus.choices, default=ClaimStatus.SUBMITTED) #default is submitted
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


 
 #Category of dispute raised by PIN
class DisputeReason(models.TextChoices):
    INCORRECT_AMOUNT = "incorrect_amount", "Incorrect amount"
    NEVER_HAPPENED = "never_happened", "Never happened"
    INCORRECT_ITEM = "incorrect_item", "Incorrect item"
    DESCRIPTION_ERROR = "description_error", "Description error"

class ClaimDispute(models.Model):
    claim = models.ForeignKey(ClaimReport, on_delete=models.CASCADE, related_name="disputes") #Each of the dispute is linked to a claim
    pin = models.ForeignKey(PersonInNeed, on_delete=models.CASCADE, related_name="claim_disputes") #PIN raising the dispute
    reason = models.CharField(max_length=50, choices=DisputeReason.choices) #Reason for dispute
    comment = models.CharField(max_length=600, blank=True) #Additional comments by PIN
    created_at = models.DateTimeField(auto_now_add=True) 



#THIS SECTION IS FOR CHAT BETWEEN CV AND PIN



#a reusable helper filter that helps us get “open” or “closed” chat rooms easily
class ChatRoomQuerySet(models.QuerySet):
    def open(self):
        now = timezone.now()
        return self.filter(
            opens_at__lte=now
        ).filter(
            models.Q(expires_at__gte=now) | models.Q(expires_at__isnull=True)
        )

    def closed(self):
        now = timezone.now()
        return self.filter(
            models.Q(expires_at__lt=now) | models.Q(opens_at__gt=now)
        )



#Custom manager to use the above queryset methods
class ChatRoomManager(models.Manager):
    def get_queryset(self):
        return ChatRoomQuerySet(self.model, using=self._db) #returns the custom queryset
    def open(self):
        return self.get_queryset().open() #uses the open() method from the custom queryset
    def closed(self):
        return self.get_queryset().closed() #uses the closed() method from the custom queryset
    



def chatid():
    return "CHAT" + uuid.uuid4().hex[:8].upper() #UNIQUE CHAT ID

class ChatRoom(models.Model): #every chat room is only a PIN and CV
    id = models.CharField(max_length=12, 
                          primary_key=True, 
                          editable=False, 
                          default=chatid, 
                          unique=True) #Chat Room ID
    
    request = models.OneToOneField(Request, 
                                   on_delete=models.CASCADE, 
                                   related_name="chat") #Each request has one chat room
    

    
    opens_at = models.DateTimeField(blank=True, null=True)   #when chat opens (start of the appointment day)
    expires_at = models.DateTimeField(blank=True, null=True) #when the chat should stop accepting messages.
    created_at = models.DateTimeField(auto_now_add=True) #timestamp when the chat row was created.

    # Attach the custom manager
    objects = ChatRoomManager()

    #Indexes to speed up query
    class Meta:
        indexes = [
            models.Index(fields=["opens_at"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["created_at"]),
        ]


    @property
    def is_open(self):
        now = timezone.now()
        if not self.opens_at:
            return False
        #Open if now >= opens_at, and either no expiry yet (Active) OR not past expires_at
        if self.expires_at is None:
            return now >= self.opens_at
        return self.opens_at <= now <= self.expires_at



    def save(self, *args, **kwargs):

        #If opens_at is not set default to start of the appointment day
        if not self.opens_at and self.request:
            day_start = datetime.combine(self.request.appointment_date, datetime.min.time())

            self.opens_at = timezone.make_aware(day_start) if timezone.is_naive(day_start) else day_start

        #Savesss 
        super().save(*args, **kwargs)


    def __str__(self):
        return f"ChatRoom {self.id} for Request {self.request_id}"
    
    @property
    def cv(self):
        return self.request.cv

    @property
    def pin(self):
        return self.request.pin

    

#Each record is one message
class ChatMessage(models.Model):

    #Each message belongs to one ChatRoom.
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages") #Which chat room this message belongs to
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) #Who sent the message either PIN or CV
    body = models.TextField() #Message content
    created_at = models.DateTimeField(auto_now_add=True) #when it was sent

    class Meta:
        ordering = ["created_at"]
