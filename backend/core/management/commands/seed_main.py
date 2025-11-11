# core/management/commands/seed_main.py
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Optional
from datetime import date, time, timedelta, datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.db.models import Count

from faker import Faker  # type: ignore

from core.models import (
    ClaimCategory, Company, PersonInNeed, CV, CSRRep, PA,
    Request, RequestStatus, FlaggedRequest, FlagType,
    ServiceCategory, GenderChoices, LanguageChoices,
    ResolutionOutcome,
    ShortlistedRequest,
    EmailOTP, OtpPurpose,
    ClaimReport, ClaimStatus, ClaimDispute, DisputeReason,
    ChatRoom, ChatMessage,
)

# -----------------------
# CONFIGURABLE DEFAULTS
# -----------------------
DEFAULT_COMPANIES = 5
DEFAULT_PINS = 50
DEFAULT_CVS = 20
DEFAULT_CSRS = 9
DEFAULT_REQUESTS = 180

SG_PREFIXES = ["8", "9"]  # SG-like mobile numbers

# Use an LLM to generate chat lines? Totally optional.
USE_LLM_FOR_MESSAGES = False  # keep False unless you wire your own client


# -----------------------
# RANDOM HELPERS
# -----------------------
fake = Faker("en_US")

def rand_phone():
    """Generate a simple SG 8-digit phone, starting with 8/9."""
    return random.choice(SG_PREFIXES) + "".join(str(random.randint(0, 9)) for _ in range(7))

def rand_gender() -> str:
    return random.choice([GenderChoices.MALE, GenderChoices.FEMALE]).value

def rand_language() -> str:
    return random.choice([LanguageChoices.EN, LanguageChoices.ZH, LanguageChoices.TA, LanguageChoices.MS]).value

def rand_service_category() -> str:
    # Use the "value" side (first item of TextChoices tuples)
    return random.choice([c[0] for c in ServiceCategory.choices])

def rand_date_within(days_back=45, days_forward=45) -> date:
    base = timezone.now().date()
    delta = random.randint(-days_back, days_forward)
    return base + timedelta(days=delta)

def rand_time() -> time:
    h = random.choice(range(8, 21))   # 8 AM to 8 PM
    m = random.choice([0, 15, 30, 45])
    return time(hour=h, minute=m)

def weighted_choice(items_with_weights):
    """items_with_weights = [(item, weight), ...]"""
    items, weights = zip(*items_with_weights)
    return random.choices(items, weights=weights, k=1)[0]

def set_created(obj, days_back=60):
    """
    Randomize created_at into the past for nicer charts.
    Works on models that have a 'created_at' field.
    """
    if not hasattr(obj, "created_at"):
        return obj
    dt = timezone.now() - timedelta(days=random.randint(0, days_back), minutes=random.randint(0, 1440))
    type(obj).objects.filter(pk=obj.pk).update(created_at=dt)
    return obj

def aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


# -----------------------
# CHAT MESSAGE GENERATION
# -----------------------
PIN_LINES = [
    "Hi! Just confirming tomorrow's appointment.",
    "Could we meet at the lobby? I need wheelchair assistance.",
    "Thank you for helping today.",
    "I will be at the pick-up point 10 minutes earlier.",
    "Please note I have difficulty with stairs.",
]
CV_LINES = [
    "Got it! I will arrive 10 minutes earlier.",
    "Understood—I'll bring a foldable wheelchair.",
    "Please have your appointment card ready.",
    "No problem. See you at the lobby.",
    "Glad to help. Do you have any questions?",
]

def llm_chat_line(role: str, service_type: str) -> str:
    # Placeholder if you ever want to use an LLM — keep it simple/off by default.
    # You could swap in your Llama2 client here.
    # Return a safe fallback if no LLM is used.
    if role == "pin":
        return random.choice(PIN_LINES)
    return random.choice(CV_LINES)

def make_chat_script(n_pairs: int, use_llm: bool = False, service_type: str = "") -> List[tuple[str, str]]:
    """
    Returns a list of (role, text) alternating between PIN and CV.
    role in {"pin", "cv"}.
    """
    script: List[tuple[str, str]] = []
    for i in range(n_pairs):
        pin_line = llm_chat_line("pin", service_type) if use_llm else random.choice(PIN_LINES)
        cv_line  = llm_chat_line("cv",  service_type) if use_llm else random.choice(CV_LINES)
        script.append(("pin", pin_line))
        script.append(("cv", cv_line))
    return script


# -----------------------
# MANAGEMENT COMMAND
# -----------------------
class Command(BaseCommand):
    help = "Seed the database with sample data: companies, users, profiles, requests, shortlists, flags, claims, chats & messages, OTPs."

    def add_arguments(self, parser):
        parser.add_argument("--companies", type=int, default=DEFAULT_COMPANIES)
        parser.add_argument("--pins", type=int, default=DEFAULT_PINS)
        parser.add_argument("--cvs", type=int, default=DEFAULT_CVS)
        parser.add_argument("--csrs", type=int, default=DEFAULT_CSRS)
        parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
        parser.add_argument("--create_pa", action="store_true", help="Also create a PA admin user/profile")
        parser.add_argument("--clear", action="store_true", help="Drop existing data for a clean reseed")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()

        num_companies = opts["companies"]
        num_pins = opts["pins"]
        num_cvs = opts["cvs"]
        num_csrs = opts["csrs"]
        num_requests = opts["requests"]
        create_pa = opts["create_pa"]
        clear = opts["clear"]

        self.stdout.write(self.style.NOTICE("Seeding database..."))

        if clear:
            self._clear_all()
            self.stdout.write(self.style.WARNING("Cleared existing data."))

        # -----------------------
        # 1) Companies
        # -----------------------
        companies = []
        for i in range(num_companies):
            cid = f"CMP-{1000+i}"
            comp = Company.objects.create(
                company_id=cid,
                companyname=fake.company(),
            )
            set_created(comp)
            companies.append(comp)
        self.stdout.write(self.style.SUCCESS(f"Created {len(companies)} companies"))

        # -----------------------
        # 2) PA admin (optional)
        # -----------------------
        pa_profile = None
        if create_pa:
            if not User.objects.filter(username="pa_admin").exists():
                pa_user = User.objects.create_user(
                    username="pa_admin",
                    email="pa_admin@example.com",
                    password="Admin1234!",
                )
                pa_user.is_staff = True
                pa_user.is_superuser = True
                pa_user.save()
            else:
                pa_user = User.objects.get(username="pa_admin")

            pa_profile = PA.objects.create(
                user=pa_user,
                name="Platform Admin",
                dob=date(1990, 1, 1),
                phone=rand_phone(),
                address=fake.address(),
            )
            set_created(pa_profile)
            self.stdout.write(self.style.SUCCESS("Created PA admin user 'pa_admin' (password: Admin1234!)"))

        # -----------------------
        # 3) PINs
        # -----------------------
        pins: List[PersonInNeed] = []
        for i in range(num_pins):
            u = User.objects.create_user(
                username=f"pin{i+1}",
                email=f"ntucaudit@gmail.com",
                password="Test1234!",
            )
            p = PersonInNeed.objects.create(
                user=u,
                name=fake.name(),
                dob=fake.date_of_birth(minimum_age=18, maximum_age=90),
                phone=rand_phone(),
                address=fake.address(),
                preferred_cv_language=rand_language(),
                preferred_cv_gender=rand_gender(),
            )
            set_created(p)
            pins.append(p)
        self.stdout.write(self.style.SUCCESS(f"Created {len(pins)} PIN profiles"))

        # -----------------------
        # 4) CVs
        # -----------------------
        cvs: List[CV] = []
        for i in range(num_cvs):
            u = User.objects.create_user(
                username=f"cv{i+1}",
                email=f"cv{i+1}@example.com",
                password="Test1234!",
            )
            c = CV.objects.create(
                user=u,
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
            set_created(c)
            cvs.append(c)
        self.stdout.write(self.style.SUCCESS(f"Created {len(cvs)} CV profiles"))

        # -----------------------
        # 5) CSRs
        # -----------------------
        csrs: List[CSRRep] = []
        for i in range(num_csrs):
            u = User.objects.create_user(
                username=f"csr{i+1}",
                email=f"csr{i+1}@example.com",
                password="Test1234!",
            )
            c = CSRRep.objects.create(
                user=u,
                name=fake.name(),
                dob=fake.date_of_birth(minimum_age=21, maximum_age=75),
                phone=rand_phone(),
                address=fake.address(),
                gender=rand_gender(),
                company=random.choice(companies),
            )
            set_created(c)
            csrs.append(c)
        self.stdout.write(self.style.SUCCESS(f"Created {len(csrs)} CSR profiles"))

        # -----------------------
        # 6) Requests (+ Flags, Shortlists)
        # -----------------------
        status_weights = [
            (RequestStatus.REVIEW,   22),
            (RequestStatus.PENDING,  30),
            (RequestStatus.ACTIVE,   24),
            (RequestStatus.COMPLETE, 18),
            (RequestStatus.REJECTED, 6),
        ]

        requests: List[Request] = []
        for i in range(num_requests):
            pin = random.choice(pins)
            service = rand_service_category()
            appt_date = rand_date_within()
            appt_time = rand_time()
            status_choice = weighted_choice(status_weights)

            # Assign CV only if ACTIVE/COMPLETE
            cv = random.choice(cvs) if status_choice in (RequestStatus.ACTIVE, RequestStatus.COMPLETE) else None

            req = Request.objects.create(
                pin=pin,
                cv=cv,
                service_type=service,
                appointment_date=appt_date,
                appointment_time=appt_time,
                pickup_location=fake.street_address(),
                service_location=fake.company() + " Clinic",
                description=fake.sentence(nb_words=12),
                status=status_choice,
            )
            set_created(req)

            # If COMPLETE, ensure completed_at set to a realistic time (yesterday or earlier if appt in past)
            if req.status == RequestStatus.COMPLETE and not req.completed_at:
                # completed_at around appointment end, or fallback to yesterday
                approx = datetime.combine(
                    req.appointment_date, req.appointment_time
                ) + timedelta(hours=2)
                if approx > timezone.now():
                    approx = timezone.now() - timedelta(hours=random.randint(6, 30))
                req.completed_at = aware(approx)
                req.save(update_fields=["completed_at"])

            # Random flags for REVIEW/PENDING (some resolved, some not)
            if req.status in (RequestStatus.REVIEW, RequestStatus.PENDING) and random.random() < 0.25:
                ft = random.choice([FlagType.AUTO, FlagType.MANUAL])
                csr_for_flag = random.choice(csrs) if ft == FlagType.MANUAL else None
                flag = FlaggedRequest.objects.create(
                    request=req,
                    flag_type=ft,
                    csr=csr_for_flag,
                    reasonbycsr="Suspicious wording" if csr_for_flag else "Auto moderation triggered",
                )
                set_created(flag)
                # 50% chance it's resolved by PA
                if random.random() < 0.5 and 'pa_user' in locals() or True:
                    # If you created PA, mark some flags resolved by PA
                    if create_pa and pa_profile:
                        flag.resolved = True
                        flag.resolved_at = timezone.now() - timedelta(days=random.randint(0, 10))
                        flag.resolved_by = pa_profile
                        flag.resolution_notes = random.choice([
                            "Looks fine after review.",
                            "Reject: contains disallowed intent.",
                            "Approved with caution.",
                        ])
                        flag.resolution_outcome = random.choice([ResolutionOutcome.ACCEPTED, ResolutionOutcome.REJECTED])
                        flag.save()

            # Shortlists for PENDING requests (so shortlist_count > 0)
            if req.status == RequestStatus.PENDING:
                shortlisters = random.sample(csrs, k=random.randint(0, min(3, len(csrs))))
                for csr in shortlisters:
                    ShortlistedRequest.objects.get_or_create(csr=csr, request=req)

            requests.append(req)

        self.stdout.write(self.style.SUCCESS(f"Created {len(requests)} Requests"))

        # -----------------------
        # 7) Claims (+ Disputes) for COMPLETE requests
        # -----------------------
        complete_reqs = [r for r in requests if r.status == RequestStatus.COMPLETE and r.cv_id]
        claim_count = 0
        dispute_count = 0
        for r in complete_reqs:
            if random.random() < 0.75:  # 75% of completed have a claim
                amount = round(random.uniform(5, 60), 2)
                method = random.choice(["cash", "card", "paynow", "paylah"])
                claim = ClaimReport.objects.create(
                    request=r,
                    cv=r.cv,
                    category=random.choice([c[0] for c in ClaimCategory.choices]),
                    expense_date=r.appointment_date,
                    amount=amount,
                    payment_method=method,
                    description=fake.sentence(nb_words=10),
                    status=ClaimStatus.SUBMITTED,
                )
                set_created(claim)
                claim_count += 1

                # random resolution by PIN: verify or dispute
                roll = random.random()
                if roll < 0.5:
                    # verify
                    claim.status = ClaimStatus.VERIFIED_BY_PIN
                    claim.save(update_fields=["status"])
                elif roll < 0.8:
                    # dispute
                    reason = random.choice([r for r in DisputeReason.values])
                    ClaimDispute.objects.create(
                        claim=claim, pin=r.pin, reason=reason, comment=fake.sentence(nb_words=8)
                    )
                    claim.status = ClaimStatus.DISPUTED_BY_PIN
                    claim.save(update_fields=["status"])
                    dispute_count += 1
                else:
                    # left submitted
                    pass

        self.stdout.write(self.style.SUCCESS(f"Created {claim_count} Claims ({dispute_count} disputed)"))

        # -----------------------
        # 8) OTPs (profile update + password change)
        # -----------------------
        otp_count = 0
        for pin in random.sample(pins, k=min(len(pins), 12)):
            # valid profile update OTP
            EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PROFILE_UPDATE,
                expires_at=timezone.now() + timedelta(minutes=10),
                consumed=False,
            ); otp_count += 1

            # expired password-change OTP
            EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PASSWORD_CHANGE,
                expires_at=timezone.now() - timedelta(minutes=5),
                consumed=False,
            ); otp_count += 1

            # consumed OTP
            used = EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PROFILE_UPDATE,
                expires_at=timezone.now() - timedelta(minutes=1),
                consumed=True,
            ); otp_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {otp_count} OTP rows"))

        # -----------------------
        # 9) ChatRooms for ACTIVE + COMPLETE (and messages)
        # -----------------------
        # Rule you stated: chat is visible only for Active & Completed.
        chats_created = 0
        msgs_created = 0
        for r in requests:
            if r.status not in (RequestStatus.ACTIVE, RequestStatus.COMPLETE):
                continue
            # Create or get chat; your model's save() will default opens_at to the start of appointment day
            chat, _ = ChatRoom.objects.get_or_create(request=r)

            # If COMPLETE, set expires_at to completed_at + 24h
            if r.status == RequestStatus.COMPLETE and r.completed_at:
                chat.expires_at = r.completed_at + timedelta(hours=24)
                # Ensure opens_at at day start (if not already set)
                day_start = aware(datetime.combine(r.appointment_date, datetime.min.time()))
                chat.opens_at = chat.opens_at or day_start
                chat.save(update_fields=["opens_at", "expires_at"])
            else:
                # ACTIVE: open starting from day start, no explicit expiry (frontend will treat as open)
                day_start = aware(datetime.combine(r.appointment_date, datetime.min.time()))
                if not chat.opens_at:
                    chat.opens_at = day_start
                    chat.save(update_fields=["opens_at"])

            chats_created += 1

            # Seed 4–10 alternating messages between PIN and CV
            if r.cv_id:
                script = make_chat_script(
                    n_pairs=random.randint(2, 5),
                    use_llm=USE_LLM_FOR_MESSAGES,
                    service_type=r.service_type,
                )
                # Start messages near opens_at
                cursor = chat.opens_at or aware(datetime.combine(r.appointment_date, datetime.min.time()))
                for role, text in script:
                    sender_user = (r.pin.user if role == "pin" else r.cv.user)
                    msg = ChatMessage.objects.create(room=chat, sender=sender_user, body=text)
                    # push created_at forward a bit for realism
                    cursor += timedelta(minutes=random.randint(3, 20))
                    ChatMessage.objects.filter(pk=msg.pk).update(created_at=cursor)
                    msgs_created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {chats_created} ChatRooms and {msgs_created} ChatMessages"))

        # -----------------------
      
        # -----------------------
        # Not strictly necessary, but handy to verify counts > 0 exist:
        pending_with_counts = (
            Request.objects.filter(status=RequestStatus.PENDING)
            .annotate(shortlist_count=Count("shortlisted_by", distinct=True))
            .order_by("-created_at")[:5]
        )
        any_counts = [r.shortlist_count for r in pending_with_counts]
        self.stdout.write(self.style.NOTICE(f"Sample shortlist_count in PENDING: {any_counts}"))

        self.stdout.write(self.style.SUCCESS("Seeding complete."))
