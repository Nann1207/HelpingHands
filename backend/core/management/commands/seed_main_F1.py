from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from typing import List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from faker import Faker  # type: ignore

from core.models import (
    Company,
    PersonInNeed,
    CV,
    CSRRep,
    PA,
    Request,
    RequestStatus,
    ServiceCategory,
    GenderChoices,
    LanguageChoices,
    EmailOTP,
    OtpPurpose,
    ChatRoom,
    ChatMessage,
    MatchQueue,
    Notification,
    ShortlistedRequest,
    FlaggedRequest,
    ClaimReport,
    ClaimDispute,
)

DEFAULT_COMPANIES = 2
DEFAULT_PINS = 60
DEFAULT_CVS = 30
DEFAULT_CSRS = 2
DEFAULT_COMPLETED_REQUESTS = 130

SG_PREFIXES = ["8", "9"]
PIN_EMAIL = "avaataraangbison@gmail.com"

fake = Faker("en_US")


# create random phone number using local SG prefixes
def rand_phone() -> str:
    return random.choice(SG_PREFIXES) + "".join(str(random.randint(0, 9)) for _ in range(7))


# create random gender
def rand_gender() -> str:
    return random.choice([GenderChoices.MALE, GenderChoices.FEMALE]).value


# create random language
def rand_language() -> str:
    return random.choice([LanguageChoices.EN, LanguageChoices.ZH, LanguageChoices.TA, LanguageChoices.MS]).value


# create random service category
def rand_service_category() -> str:
    return random.choice([c[0] for c in ServiceCategory.choices])


# create random appointment time (08:00–17:45)
def rand_time() -> time:
    hour = random.choice(range(8, 18))  # 08:00–17:45
    minute = random.choice([0, 15, 30, 45])
    return time(hour=hour, minute=minute)


# randomly shifts an object's created_at timestamp back up to `days_back` days (only if the field exists).
def set_created(obj, days_back: int = 60):
    """
    Randomly back-date created_at within the last `days_back` days, if model has created_at.
    """
    if not hasattr(obj, "created_at"):
        return obj
    dt = timezone.now() - timedelta(
        days=random.randint(0, days_back),
        minutes=random.randint(0, 1440),
    )
    type(obj).objects.filter(pk=obj.pk).update(created_at=dt)
    return obj


# ensures a datetime is timezone-aware by converting it if it's naive.
def aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


# chat history for PIN
PIN_LINES = [
    "Hi! Just confirming tomorrow's appointment.",
    "Could we meet at the lobby? I need wheelchair assistance.",
    "Thank you for helping today.",
    "I will be at the pick-up point 10 minutes earlier.",
    "Please note I have difficulty with stairs.",
]

# chat history for CV
CV_LINES = [
    "Got it! I will arrive 10 minutes earlier.",
    "Understood - I'll bring a foldable wheelchair.",
    "Please have your appointment card ready.",
    "No problem. See you at the lobby.",
    "Glad to help. Do you have any questions?",
]

# sample reasons used when seeding flagged requests for demo/testing
FLAG_REASONS = [
    "Inappropriate language in request description",
    "Suspicious or spam-like request",
    "Potential misuse of the service",
    "False or misleading information reported",
    "Safety concern raised by CSR",
]


# returns a random chat message line based on whether the sender is a PIN or a CV.
def pick_line(role: str) -> str:
    return random.choice(PIN_LINES if role == "pin" else CV_LINES)


# generates a simple PIN↔CV chat script with n message pairs (pin then cv)
def make_chat_script(n_pairs: int) -> List[tuple[str, str]]:
    """
    Simple back-and-forth between PIN and CV.
    Returns list of (role, text) pairs, where role is 'pin' or 'cv'.
    """
    script: List[tuple[str, str]] = []
    for _ in range(n_pairs):
        script.append(("pin", pick_line("pin")))
        script.append(("cv", pick_line("cv")))
    return script


# generates the complete F1 dataset: users, requests, chats, flags, OTPs, and relationships for demo/testing.
class Command(BaseCommand):
    # seeds the database with the full F1 demo scenario (companies, PA, PINs, CVs, CSRs, requests, chats, flags, OTPs).
    help = (
        "Seed the database with the focused F1 scenario: "
        "2 companies, 1 PA, 60 PINs (shared email), 30 CVs, 2 CSRs, "
        "130 completed requests with closed chats, plus 60 pending and 60 active "
        "requests such that each PIN has at least 1 pending and 1 active request. "
        "Active requests always have CV + CSR assigned, and chats open only on "
        "the appointment date/time. Also includes 5 rejected requests and "
        "30 flagged requests attached to completed ones."
    )

    # defines command-line arguments allowing custom counts and options for the seeding command.
    def add_arguments(self, parser):
        parser.add_argument("--companies", type=int, default=DEFAULT_COMPANIES)
        parser.add_argument("--pins", type=int, default=DEFAULT_PINS)
        parser.add_argument("--cvs", type=int, default=DEFAULT_CVS)
        parser.add_argument("--csrs", type=int, default=DEFAULT_CSRS)
        # Treat this as the number of COMPLETED requests to generate
        parser.add_argument("--requests", type=int, default=DEFAULT_COMPLETED_REQUESTS)
        parser.add_argument("--skip-pa", action="store_true", help="Do not create the PA admin profile")
        parser.add_argument("--clear", action="store_true", help="Remove existing demo data before seeding")

    # main command handler that seeds all F1 demo data (companies, users, requests, chats, flags, and OTPs) in one atomic transaction.
    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()

        num_companies = opts["companies"]
        num_pins = opts["pins"]
        num_cvs = opts["cvs"]
        num_csrs = opts["csrs"]
        num_completed_requests = opts["requests"]
        skip_pa = opts["skip_pa"]
        clear = opts["clear"]

        self.stdout.write(self.style.NOTICE("Seeding F1 scenario data..."))

        if clear:
            self._clear_all()
            self.stdout.write(self.style.WARNING("Cleared existing data."))

        # -------------------------------------------------------------------
        # Companies
        # -------------------------------------------------------------------
        companies = []
        for idx in range(num_companies):
            comp = Company.objects.create(
                company_id=f"F1-CMP-{1000 + idx}",
                companyname=fake.company(),
            )
            set_created(comp)
            companies.append(comp)
        self.stdout.write(self.style.SUCCESS(f"Created {len(companies)} companies"))

        # -------------------------------------------------------------------
        # Platform Admin (PA)  (username: pa_admin)
        # -------------------------------------------------------------------
        pa_profile = None
        if not skip_pa:
            pa_user, _ = User.objects.get_or_create(
                username="pa_admin",
                defaults={
                    "email": "pa_admin@example.com",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            pa_user.set_password("Admin1234!")
            pa_user.save()

            pa_profile, created = PA.objects.get_or_create(
                user=pa_user,
                defaults={
                    "name": "Platform Admin F1",
                    "dob": date(1990, 1, 1),
                    "phone": rand_phone(),
                    "address": fake.address(),
                },
            )
            set_created(pa_profile)
            if created:
                self.stdout.write(self.style.SUCCESS("Created PA profile 'pa_admin' (password: Admin1234!)"))
            else:
                self.stdout.write(self.style.WARNING("Reused existing PA profile for 'pa_admin'"))

        # -------------------------------------------------------------------
        # PINs (usernames: pin1..pin60)
        # -------------------------------------------------------------------
        pins: List[PersonInNeed] = []
        for idx in range(num_pins):
            user = User.objects.create_user(
                username=f"pin{idx+1}",
                email=PIN_EMAIL,  # ALL PINs share the same email as requested
                password="Test1234!",
            )
            pin = PersonInNeed.objects.create(
                user=user,
                name=fake.name(),
                dob=fake.date_of_birth(minimum_age=18, maximum_age=90),
                phone=rand_phone(),
                address=fake.address(),
                preferred_cv_language=rand_language(),
                preferred_cv_gender=rand_gender(),
            )
            set_created(pin)
            pins.append(pin)
        self.stdout.write(self.style.SUCCESS(f"Created {len(pins)} PIN profiles"))

        # -------------------------------------------------------------------
        # CVs (usernames: cv1..cv30)
        # -------------------------------------------------------------------
        cvs: List[CV] = []
        for idx in range(num_cvs):
            user = User.objects.create_user(
                username=f"cv{idx+1}",
                email=f"cv{idx+1}@example.com",
                password="Test1234!",
            )
            cv = CV.objects.create(
                user=user,
                name=fake.name(),
                dob=fake.date_of_birth(minimum_age=18, maximum_age=75),
                phone=rand_phone(),
                address=fake.address(),
                gender=rand_gender(),
                main_language=rand_language(),
                second_language=rand_language(),
                service_category_preference=rand_service_category(),
                company=random.choice(companies),
            )
            set_created(cv)
            cvs.append(cv)
        self.stdout.write(self.style.SUCCESS(f"Created {len(cvs)} CV profiles"))

        # -------------------------------------------------------------------
        # CSRs (usernames: csr1..csr2)
        # -------------------------------------------------------------------
        csrs: List[CSRRep] = []
        for idx in range(num_csrs):
            user = User.objects.create_user(
                username=f"csr{idx+1}",
                email=f"csr{idx+1}@example.com",
                password="Test1234!",
            )
            csr = CSRRep.objects.create(
                user=user,
                name=fake.name(),
                dob=fake.date_of_birth(minimum_age=21, maximum_age=75),
                phone=rand_phone(),
                address=fake.address(),
                gender=rand_gender(),
                company=random.choice(companies),
            )
            set_created(csr)
            csrs.append(csr)
        self.stdout.write(self.style.SUCCESS(f"Created {len(csrs)} CSR profiles"))

        # -------------------------------------------------------------------
        # REQUESTS
        # We will create:
        # - num_completed_requests COMPLETED
        # - 1 PENDING per PIN (60 total)
        # - 1 ACTIVE per PIN (60 total)
        # - 5 REJECTED requests (extra)
        # ensuring each PIN has >=1 pending + >=1 active, and all ACTIVE have CV+CSR.
        # -------------------------------------------------------------------
        completed_requests: List[Request] = []
        pending_requests: List[Request] = []
        active_requests: List[Request] = []
        rejected_requests: List[Request] = []

        # 1) COMPLETED requests (historic, with closed chat later)
        for idx in range(num_completed_requests):
            pin = random.choice(pins)
            cv = random.choice(cvs)
            csr = random.choice(csrs)
            service_type = rand_service_category()

            # Appointment 7–40 days in the past
            appointment_date = timezone.now().date() - timedelta(days=random.randint(7, 40))
            appointment_time = rand_time()
            appointment_dt = aware(datetime.combine(appointment_date, appointment_time))

            committed_at = appointment_dt - timedelta(
                days=1,
                minutes=random.randint(5, 120),
            )
            completed_at = appointment_dt + timedelta(hours=2)

            req = Request.objects.create(
                pin=pin,
                cv=cv,
                service_type=service_type,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                pickup_location=fake.street_address(),
                service_location=f"{fake.company()} Clinic",
                description=fake.sentence(nb_words=12),
                status=RequestStatus.COMPLETE,
                committed_by_csr=csr,
                committed_at=committed_at,
                completed_at=completed_at,
            )
            set_created(req)
            completed_requests.append(req)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(completed_requests)} COMPLETED requests (no flags/review)")
        )

        # 2) PENDING requests – exactly 1 per PIN
        #    IMPORTANT: due to DB CHECK constraint req_pending_not_committed,
        #    PENDING requests must NOT have committed_by_csr / committed_at set.
        #    We also leave cv/CSR NULL so they are truly “not yet matched/committed”.
        for pin in pins:
            service_type = rand_service_category()

            # Appointment in the near future: 3–30 days ahead
            appointment_date = timezone.now().date() + timedelta(days=random.randint(3, 30))
            appointment_time = rand_time()

            req = Request.objects.create(
                pin=pin,
                # cv=None by default (no CV yet)
                service_type=service_type,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                pickup_location=fake.street_address(),
                service_location=f"{fake.company()} Clinic",
                description=fake.sentence(nb_words=10),
                status=RequestStatus.PENDING,
                # committed_by_csr=None,
                # committed_at=None,
                # completed_at=None,
            )
            set_created(req)
            pending_requests.append(req)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(pending_requests)} PENDING requests (1 per PIN)")
        )

        # 3) ACTIVE requests – exactly 1 per PIN, all with CV + CSR assigned
        #    These are current “in-flight” or imminent appointments.
        for pin in pins:
            cv = random.choice(cvs)
            csr = random.choice(csrs)
            service_type = rand_service_category()

            # Appointment between yesterday and 7 days ahead
            day_offset = random.randint(-1, 7)
            appointment_date = timezone.now().date() + timedelta(days=day_offset)
            appointment_time = rand_time()
            appointment_dt = aware(datetime.combine(appointment_date, appointment_time))

            committed_at = appointment_dt - timedelta(hours=4)

            req = Request.objects.create(
                pin=pin,
                cv=cv,
                service_type=service_type,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                pickup_location=fake.street_address(),
                service_location=f"{fake.company()} Clinic",
                description=fake.sentence(nb_words=10),
                status=RequestStatus.ACTIVE,  # ACTIVE must be committed
                committed_by_csr=csr,
                committed_at=committed_at,
                # completed_at is still NULL
            )
            set_created(req)
            active_requests.append(req)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(active_requests)} ACTIVE requests (1 per PIN, all with CV + CSR assigned)"
            )
        )

        # 4) REJECTED requests – 5 extra requests (do not affect the 1 pending/active per PIN rule)
        for _ in range(5):
            pin = random.choice(pins)
            service_type = rand_service_category()

            # Rejected a few days ago, not committed, no CV/CSR
            appointment_date = timezone.now().date() - timedelta(days=random.randint(1, 14))
            appointment_time = rand_time()

            req = Request.objects.create(
                pin=pin,
                service_type=service_type,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                pickup_location=fake.street_address(),
                service_location=f"{fake.company()} Clinic",
                description="[DEMO] Request rejected by admin/CSR",
                status=RequestStatus.REJECTED,
                # cv=None, committed_by_csr=None, committed_at=None, completed_at=None
            )
            set_created(req)
            rejected_requests.append(req)

        self.stdout.write(
            self.style.SUCCESS(f"Created {len(rejected_requests)} REJECTED requests")
        )

        # -------------------------------------------------------------------
        # EMAIL OTPs – one per PIN (all share the same email), all expired+consumed
        # -------------------------------------------------------------------
        otp_count = 0
        for pin in pins:
            EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PROFILE_UPDATE,
                expires_at=timezone.now() - timedelta(minutes=random.randint(5, 90)),
                consumed=True,
            )
            otp_count += 1
        self.stdout.write(self.style.SUCCESS(f"Created {otp_count} OTP rows"))

        # -------------------------------------------------------------------
        # CHATS
        #
        # COMPLETED requests → closed chats (opens_at on appointment date, expires 24h after completed_at)
        # ACTIVE requests → chats that open only on appointment date/time and expire 24h after.
        # PENDING & REJECTED requests → no chats.
        # -------------------------------------------------------------------
        chats_created = 0
        msgs_created = 0

        # 3.1 Chats for COMPLETED requests (closed)
        for req in completed_requests:
            chat, _ = ChatRoom.objects.get_or_create(request=req)

            # Open on the appointment date (midnight). This is in the past.
            opens_at = aware(datetime.combine(req.appointment_date, datetime.min.time()))
            chat.opens_at = chat.opens_at or opens_at

            # Expire 24h after completion
            if req.completed_at:
                chat.expires_at = req.completed_at + timedelta(hours=24)
            chat.save(update_fields=["opens_at", "expires_at"])
            chats_created += 1

            # Populate some historical conversation
            script = make_chat_script(n_pairs=random.randint(2, 4))
            cursor = chat.opens_at
            for role, text in script:
                sender = req.pin.user if role == "pin" else req.cv.user
                msg = ChatMessage.objects.create(room=chat, sender=sender, body=text)
                cursor += timedelta(minutes=random.randint(2, 8))
                ChatMessage.objects.filter(pk=msg.pk).update(created_at=cursor)
                msgs_created += 1

        # 3.2 Chats for ACTIVE requests (open/soon-to-open)
        for req in active_requests:
            chat, _ = ChatRoom.objects.get_or_create(request=req)

            # IMPORTANT: chat opens ONLY on the appointment datetime
            if req.appointment_date and req.appointment_time:
                opens_at = aware(datetime.combine(req.appointment_date, req.appointment_time))
            else:
                # Fallback to appointment date midnight if time missing
                opens_at = aware(datetime.combine(req.appointment_date, datetime.min.time()))

            chat.opens_at = chat.opens_at or opens_at
            chat.expires_at = opens_at + timedelta(hours=24)
            chat.save(update_fields=["opens_at", "expires_at"])
            chats_created += 1

            # Optionally, seed a short pre-appointment conversation
            script = make_chat_script(n_pairs=1)
            cursor = chat.opens_at - timedelta(minutes=30)
            for role, text in script:
                sender = req.pin.user if role == "pin" else req.cv.user
                msg = ChatMessage.objects.create(room=chat, sender=sender, body=text)
                cursor += timedelta(minutes=5)
                ChatMessage.objects.filter(pk=msg.pk).update(created_at=cursor)
                msgs_created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created/updated {chats_created} ChatRooms and {msgs_created} ChatMessages")
        )

        # -------------------------------------------------------------------
        # FLAGS – 30 flags on completed requests, each with a demo reason
        #
        # We only rely on fields that actually exist on the model:
        # we try common names like `reason`, `flag_reason`, or `notes`.
        # -------------------------------------------------------------------
        resolved_flags_created = 0
        if completed_requests:
            flagged_sample = random.sample(
                completed_requests,
                k=min(30, len(completed_requests)),
            )
            for req in flagged_sample:
                # Create the basic flag row linked to the request
                flag = FlaggedRequest.objects.create(
                    request=req,
                )

                # Pick a demo reason
                reason_text = random.choice(FLAG_REASONS)

                # Try to attach the reason to a suitable text field
                updated = False
                if hasattr(flag, "reason"):
                    flag.reason = reason_text
                    updated = True
                if hasattr(flag, "flag_reason"):
                    flag.flag_reason = reason_text
                    updated = True
                if hasattr(flag, "notes") and not updated:
                    flag.notes = reason_text
                    updated = True

                # Save if we changed anything
                if updated:
                    flag.save()

                set_created(flag)
                resolved_flags_created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Created {resolved_flags_created} FlaggedRequest rows")
        )

        # -------------------------------------------------------------------
        # CLAIMS (Reimbursed + Disputed) – TEMPLATE / TODO
        #
        # You requested:
        #  - Some reimbursed claims for completed requests
        #  - Some disputed claims for completed requests
        #
        # The exact fields on ClaimReport / ClaimDispute aren't visible here,
        # so below is a TEMPLATE for you to adapt. Uncomment and adjust fields
        # according to your models.
        # -------------------------------------------------------------------
        """
        reimbursed_subset = random.sample(
            completed_requests,
            k=min(20, len(completed_requests))  # for example: 20 reimbursed claims
        )
        disputed_subset = random.sample(
            [r for r in completed_requests if r not in reimbursed_subset],
            k=min(10, len(completed_requests))  # e.g., 10 disputed claims
        )

        for req in reimbursed_subset:
            ClaimReport.objects.create(
                request=req,
                # TODO: fill in required fields, e.g.:
                # submitted_by=req.cv,
                # amount=Decimal("25.00"),
                # status="REIMBURSED",
                # reimbursed_at=timezone.now() - timedelta(days=1),
                # ...
            )

        for req in disputed_subset:
            report = ClaimReport.objects.create(
                request=req,
                # TODO: required fields for a claim that is under dispute
            )
            ClaimDispute.objects.create(
                claim=report,
                # TODO: fill in required fields, e.g.:
                # raised_by=req.pin,
                # reason="Incorrect distance claimed",
                # status="OPEN",
                # ...
            )
        """

        self.stdout.write(self.style.SUCCESS("F1 scenario seeding complete."))

    # completely wipes all demo-related data from the database before reseeding (except superusers).
    # so no need to run `python manage.py flush --noinput` all the time while editing seeding.
    def _clear_all(self):
        Notification.objects.all().delete()
        ChatMessage.objects.all().delete()
        ChatRoom.objects.all().delete()
        ClaimDispute.objects.all().delete()
        ClaimReport.objects.all().delete()
        EmailOTP.objects.all().delete()
        ShortlistedRequest.objects.all().delete()
        FlaggedRequest.objects.all().delete()
        MatchQueue.objects.all().delete()
        Request.objects.all().delete()
        CSRRep.objects.all().delete()
        CV.objects.all().delete()
        PersonInNeed.objects.all().delete()
        PA.objects.all().delete()
        Company.objects.all().delete()
        get_user_model().objects.exclude(is_superuser=True).delete()
