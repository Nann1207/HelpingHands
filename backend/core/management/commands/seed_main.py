# core/management/commands/seed_demo.py
from __future__ import annotations

import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from faker import Faker  # type: ignore

from core.models import (
    Company, PersonInNeed, CV, CSRRep, PA,
    Request, RequestStatus, FlaggedRequest, FlagType,
    ServiceCategory, GenderChoices, LanguageChoices,
    ResolutionOutcome,
)

# -----------------------
# CONFIGURABLE DEFAULTS
# -----------------------
DEFAULT_COMPANIES = 5
DEFAULT_PINS = 40
DEFAULT_CVS = 25
DEFAULT_CSRS = 8
DEFAULT_REQUESTS = 120

SG_PREFIXES = ["8", "9"]  # simple SG-like mobile numbers


# -----------------------
# RANDOM HELPERS
# -----------------------
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


class Command(BaseCommand):
    help = "Seed the database with sample Companies, Users, Profiles, Requests, and Flags for the PA dashboard."

    def add_arguments(self, parser):
        parser.add_argument("--companies", type=int, default=DEFAULT_COMPANIES)
        parser.add_argument("--pins", type=int, default=DEFAULT_PINS)
        parser.add_argument("--cvs", type=int, default=DEFAULT_CVS)
        parser.add_argument("--csrs", type=int, default=DEFAULT_CSRS)
        parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
        parser.add_argument("--create_pa", action="store_true", help="Also create a PA admin user/profile")

    @transaction.atomic
    def handle(self, *args, **opts):
        fake = Faker("en_US")
        User = get_user_model()

        num_companies = opts["companies"]
        num_pins = opts["pins"]
        num_cvs = opts["cvs"]
        num_csrs = opts["csrs"]
        num_requests = opts["requests"]
        create_pa = opts["create_pa"]

        self.stdout.write(self.style.NOTICE("Seeding database..."))

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
        pins = []
        for i in range(num_pins):
            u = User.objects.create_user(
                username=f"pin{i+1}",
                email=f"pin{i+1}@example.com",
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
        cvs = []
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
        csrs = []
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
        # 6) Requests
        # -----------------------
        # Include REJECTED in the mix so your dashboard always shows some rejected items.
        status_weights = [
            (RequestStatus.REVIEW,   24),
            (RequestStatus.PENDING,  28),
            (RequestStatus.ACTIVE,   20),
            (RequestStatus.COMPLETE, 18),
            (RequestStatus.REJECTED, 10),
        ]

        requests = []
        for i in range(num_requests):
            pin = random.choice(pins)
            svc = rand_service_category()
            appt_date = rand_date_within(30, 30)
            appt_time = rand_time()

            req = Request.objects.create(
                pin=pin,
                service_type=svc,
                appointment_date=appt_date,
                appointment_time=appt_time,
                pickup_location=fake.street_address(),
                service_location=fake.company() + " Clinic",
                description=fake.sentence(nb_words=12),
                status=weighted_choice(status_weights),
            )
            set_created(req)

            if req.status in (RequestStatus.ACTIVE, RequestStatus.COMPLETE) and cvs:
                cvs_match = [c for c in cvs if c.service_category_preference == svc]
                req.cv = random.choice(cvs_match) if cvs_match else random.choice(cvs)
                req.save(update_fields=["cv"])

            requests.append(req)

        self.stdout.write(self.style.SUCCESS(f"Created {len(requests)} Requests"))

        # -----------------------
        # 7) Flags
        # -----------------------
        # Create flags for ~1/3 of requests (skewed to REVIEW/PENDING)
        candidate_requests = [r for r in requests if r.status in (RequestStatus.REVIEW, RequestStatus.PENDING)]
        others = [r for r in requests if r.status not in (RequestStatus.REVIEW, RequestStatus.PENDING)]
        chosen = set(random.sample(candidate_requests, k=min(len(candidate_requests), max(1, len(requests)//3))))
        # sprinkle a few more from others
        if others:
            chosen.update(random.sample(others, k=min(len(others)//10, 5)))

        flag_count = 0
        for req in chosen:
            is_manual = random.choice([True, False])
            if is_manual and csrs:
                csr = random.choice(csrs)
                flag = FlaggedRequest.objects.create(
                    request=req,
                    flag_type=FlagType.MANUAL,
                    csr=csr,
                    reasonbycsr=random.choice([
                        "Manual review: wording needs redaction.",
                        "Manual review: unclear appointment details.",
                        "Manual review: mismatch with service category.",
                    ]),
                )
            else:
                flag = FlaggedRequest.objects.create(
                    request=req,
                    flag_type=FlagType.AUTO,
                    csr=None,
                    reasonbycsr=random.choice([
                        "Auto moderation: sensitive term detected.",
                        "Auto moderation: potential PII found.",
                        "Auto moderation: policy keyword matched.",
                    ]),
                )
            set_created(flag)

            # Randomly resolve some flags (only if PA exists)
            if pa_profile and random.choice([True, False]):
                flag.resolved = True
                flag.resolved_by = pa_profile
                # resolve 1–48 hours after created_at
                resolved_at = flag.created_at + timedelta(hours=random.randint(1, 48))
                flag.resolved_at = resolved_at

                # Random outcome: Accept or Reject
                outcome = random.choice([ResolutionOutcome.ACCEPTED, ResolutionOutcome.REJECTED])
                flag.resolution_outcome = outcome
                if outcome == ResolutionOutcome.ACCEPTED:
                    flag.resolution_notes = "Accepted by PA: valid flag; proceed."
                    # typical flow: REVIEW → PENDING if accepted
                    if req.status == RequestStatus.REVIEW:
                        req.status = RequestStatus.PENDING
                        req.save(update_fields=["status"])
                else:
                    flag.resolution_notes = "Rejected by PA: invalid flag; request rejected."
                    req.status = RequestStatus.REJECTED
                    req.save(update_fields=["status"])

                flag.save(update_fields=[
                    "resolved", "resolved_by", "resolved_at",
                    "resolution_outcome", "resolution_notes"
                ])

            flag_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {flag_count} FlaggedRequest records"))
        self.stdout.write(self.style.SUCCESS("Seeding complete!"))

        if create_pa:
            self.stdout.write(self.style.WARNING("Login as PA:  username=pa_admin  password=Admin1234!"))
