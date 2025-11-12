# core/management/commands/seed_main.py
from __future__ import annotations

import random
from typing import List, Optional
from datetime import date, time, timedelta, datetime

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Count
from django.core.files.base import ContentFile  # for dummy receipts

from faker import Faker  # type: ignore

from core.models import (
    Company, PersonInNeed, CV, CSRRep, PA,
    Request, RequestStatus, FlaggedRequest, FlagType,
    ServiceCategory, GenderChoices, LanguageChoices,
    ResolutionOutcome,
    ShortlistedRequest,
    EmailOTP, OtpPurpose,
    ClaimReport, ClaimStatus, ClaimDispute, DisputeReason, ClaimCategory, PaymentMethod,
    ChatRoom, ChatMessage,
    MatchQueue, Notification, NotificationType
)

# -----------------------
# CONFIGURABLE DEFAULTS
# -----------------------
DEFAULT_COMPANIES = 5
DEFAULT_PINS = 50
DEFAULT_CVS = 20
DEFAULT_CSRS = 9
DEFAULT_REQUESTS = 180

SG_PREFIXES = ["8", "9"]
USE_LLM_FOR_MESSAGES = False

fake = Faker("en_US")

def rand_phone():
    return random.choice(SG_PREFIXES) + "".join(str(random.randint(0, 9)) for _ in range(7))

def rand_gender() -> str:
    return random.choice([GenderChoices.MALE, GenderChoices.FEMALE]).value

def rand_language() -> str:
    return random.choice([LanguageChoices.EN, LanguageChoices.ZH, LanguageChoices.TA, LanguageChoices.MS]).value

def rand_service_category() -> str:
    return random.choice([c[0] for c in ServiceCategory.choices])

def rand_date_within(days_back=45, days_forward=45) -> date:
    base = timezone.now().date()
    delta = random.randint(-days_back, days_forward)
    return base + timedelta(days=delta)

def rand_time() -> time:
    h = random.choice(range(8, 21))
    m = random.choice([0, 15, 30, 45])
    return time(hour=h, minute=m)

def weighted_choice(items_with_weights):
    items, weights = zip(*items_with_weights)
    return random.choices(items, weights=weights, k=1)[0]

def set_created(obj, days_back=60):
    # best-effort backdate for nicer demo timelines
    if not hasattr(obj, "created_at"):
        return obj
    dt = timezone.now() - timedelta(days=random.randint(0, days_back), minutes=random.randint(0, 1440))
    type(obj).objects.filter(pk=obj.pk).update(created_at=dt)
    return obj

def aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

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

def pick_line(role: str) -> str:
    return random.choice(PIN_LINES if role == "pin" else CV_LINES)

def make_chat_script(n_pairs: int) -> List[tuple[str, str]]:
    script: List[tuple[str, str]] = []
    for _ in range(n_pairs):
        script.append(("pin", pick_line("pin")))
        script.append(("cv", pick_line("cv")))
    return script

class Command(BaseCommand):
    help = "Seed the database with sample data: companies, users, profiles, requests, shortlists, flags, claims, chats, OTPs, queues & notifications."

    def add_arguments(self, parser):
        parser.add_argument("--companies", type=int, default=DEFAULT_COMPANIES)
        parser.add_argument("--pins", type=int, default=DEFAULT_PINS)
        parser.add_argument("--cvs", type=int, default=DEFAULT_CVS)
        parser.add_argument("--csrs", type=int, default=DEFAULT_CSRS)
        parser.add_argument("--requests", type=int, default=DEFAULT_REQUESTS)
        parser.add_argument("--create_pa", action="store_true")
        parser.add_argument("--clear", action="store_true")

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

        # 1) Companies
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

        # 2) PA admin (optional)
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

        # 3) PINs
        pins: List[PersonInNeed] = []
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

        # 4) CVs
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

        # 5) CSRs
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

        # 6) Requests (+ Flags, Shortlists)
        # Include COMMITTED in distribution and respect constraints.
        status_weights = [
            (RequestStatus.REVIEW,   20),
            (RequestStatus.PENDING,  28),
            (RequestStatus.COMMITTED, 8),
            (RequestStatus.ACTIVE,   24),
            (RequestStatus.COMPLETE, 14),
            (RequestStatus.REJECTED, 6),
        ]

        requests: List[Request] = []
        for i in range(num_requests):
            pin = random.choice(pins)
            service = rand_service_category()
            appt_date = rand_date_within()
            appt_time = rand_time()
            status_choice = weighted_choice(status_weights)

            # cv only for ACTIVE/COMPLETE; nullable otherwise
            cv_val: Optional[CV] = random.choice(cvs) if status_choice in (RequestStatus.ACTIVE, RequestStatus.COMPLETE) else None

            req_kwargs = dict(
                pin=pin,
                cv=cv_val,
                service_type=service,
                appointment_date=appt_date,
                appointment_time=appt_time,
                pickup_location=fake.street_address(),
                service_location=f"{fake.company()} Clinic",
                description=fake.sentence(nb_words=12),
                status=status_choice,
            )

            # If COMMITTED, we must have committed_by_csr & committed_at (DB constraint)
            if status_choice == RequestStatus.COMMITTED:
                csr_committer = random.choice(csrs)
                req_kwargs["committed_by_csr"] = csr_committer
                req_kwargs["committed_at"] = timezone.now() - timedelta(minutes=random.randint(10, 180))

            req = Request.objects.create(**req_kwargs)
            set_created(req)

            # If COMPLETE: ensure completed_at
            if req.status == RequestStatus.COMPLETE and not req.completed_at:
                approx = datetime.combine(req.appointment_date, req.appointment_time) + timedelta(hours=2)
                if approx > timezone.now():
                    approx = timezone.now() - timedelta(hours=random.randint(6, 30))
                req.completed_at = aware(approx)
                req.save(update_fields=["completed_at"])

            # Flags on REVIEW/PENDING occasionally
            if req.status in (RequestStatus.REVIEW, RequestStatus.PENDING) and random.random() < 0.30:
                ft = random.choice([FlagType.AUTO, FlagType.MANUAL])
                csr_for_flag = random.choice(csrs) if ft == FlagType.MANUAL else None
                flag = FlaggedRequest.objects.create(
                    request=req,
                    flag_type=ft,
                    csr=csr_for_flag,
                    reasonbycsr=("Suspicious wording" if csr_for_flag else "Auto moderation triggered"),
                )
                set_created(flag)

                # ~50% resolved by PA if present
                if create_pa and pa_profile and random.random() < 0.5:
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

            # Shortlists for PENDING
            if req.status == RequestStatus.PENDING:
                shortlisters = random.sample(csrs, k=random.randint(0, min(3, len(csrs))))
                for csr in shortlisters:
                    ShortlistedRequest.objects.get_or_create(csr=csr, request=req)

            requests.append(req)

        self.stdout.write(self.style.SUCCESS(f"Created {len(requests)} Requests"))

        # 7) Claims (COMPLETE) with dummy receipts + Disputes
        complete_reqs = [r for r in requests if r.status == RequestStatus.COMPLETE and r.cv_id]
        claim_count = 0
        dispute_count = 0
        for r in complete_reqs:
            if random.random() < 0.75:  # 75% have a claim
                amount = round(random.uniform(5, 60), 2)
                method = random.choice([m[0] for m in PaymentMethod.choices])
                claim = ClaimReport(
                    request=r,
                    cv=r.cv,
                    category=random.choice([c[0] for c in ClaimCategory.choices]),
                    expense_date=r.appointment_date,
                    amount=amount,
                    payment_method=method,
                    description=fake.sentence(nb_words=10),
                    status=ClaimStatus.SUBMITTED,
                )
                # Attach a tiny dummy "receipt"
                claim.receipt.save(
                    f"receipt_{r.id}.txt",
                    ContentFile(f"Receipt for request {r.id}\nAmount: ${amount}\n"),
                    save=True,
                )
                set_created(claim)
                claim_count += 1

                # PIN verifies or disputes
                roll = random.random()
                if roll < 0.5:
                    claim.status = ClaimStatus.VERIFIED_BY_PIN
                    claim.save(update_fields=["status"])
                elif roll < 0.8:
                    reason = random.choice([c[0] for c in DisputeReason.choices])
                    ClaimDispute.objects.create(
                        claim=claim, pin=r.pin, reason=reason, comment=fake.sentence(nb_words=8)
                    )
                    claim.status = ClaimStatus.DISPUTED_BY_PIN
                    claim.save(update_fields=["status"])
                    dispute_count += 1
                # else: remain SUBMITTED

        self.stdout.write(self.style.SUCCESS(f"Created {claim_count} Claims ({dispute_count} disputed)"))

        # 8) OTPs
        otp_count = 0
        for pin in random.sample(pins, k=min(len(pins), 12)):
            EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PROFILE_UPDATE,
                expires_at=timezone.now() + timedelta(minutes=10),
                consumed=False,
            ); otp_count += 1

            EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PASSWORD_CHANGE,
                expires_at=timezone.now() - timedelta(minutes=5),
                consumed=False,
            ); otp_count += 1

            used = EmailOTP.objects.create(
                email=pin.user.email,
                code=str(random.randint(100000, 999999)),
                purpose=OtpPurpose.PROFILE_UPDATE,
                expires_at=timezone.now() - timedelta(minutes=1),
                consumed=True,
            ); otp_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {otp_count} OTP rows"))

        # 9) ChatRooms for ACTIVE + COMPLETE
        chats_created = 0
        msgs_created = 0
        for r in requests:
            if r.status not in (RequestStatus.ACTIVE, RequestStatus.COMPLETE):
                continue
            chat, _ = ChatRoom.objects.get_or_create(request=r)

            if r.status == RequestStatus.COMPLETE and r.completed_at:
                chat.expires_at = r.completed_at + timedelta(hours=24)
                day_start = aware(datetime.combine(r.appointment_date, datetime.min.time()))
                chat.opens_at = chat.opens_at or day_start
                chat.save(update_fields=["opens_at", "expires_at"])
            else:
                day_start = aware(datetime.combine(r.appointment_date, datetime.min.time()))
                if not chat.opens_at:
                    chat.opens_at = day_start
                    chat.save(update_fields=["opens_at"])

            chats_created += 1

            if r.cv_id:
                script = make_chat_script(n_pairs=random.randint(2, 5))
                cursor = chat.opens_at or aware(datetime.combine(r.appointment_date, datetime.min.time()))
                for role, text in script:
                    sender_user = (r.pin.user if role == "pin" else r.cv.user)
                    msg = ChatMessage.objects.create(room=chat, sender=sender_user, body=text)
                    cursor += timedelta(minutes=random.randint(3, 20))
                    ChatMessage.objects.filter(pk=msg.pk).update(created_at=cursor)
                    msgs_created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {chats_created} ChatRooms and {msgs_created} ChatMessages"))

        # 10) Commit & matching queues + CSR notifications
        # Choose some PENDING or COMMITTED requests to simulate assignment flow
        candidates = [r for r in requests if r.status in (RequestStatus.PENDING, RequestStatus.COMMITTED)]
        random.shuffle(candidates)
        sampled = candidates[:min(len(candidates), 15)]  # up to 15 queues

        notif_created = 0
        queues_created = 0

        for req in sampled:
            # Ensure it is committed (constraint requires committer & timestamp)
            if not req.committed_by_csr_id:
                csr = random.choice(csrs)
                req.committed_by_csr = csr
                req.committed_at = timezone.now() - timedelta(minutes=random.randint(5, 60))
                req.status = RequestStatus.COMMITTED  # IMPORTANT: satisfy your check-constraints
                req.save(update_fields=["committed_by_csr", "committed_at", "status"])
            else:
                csr = req.committed_by_csr

            # Pick up to 3 CVs (prefer same company, else any)
            company_cvs = [cv for cv in cvs if cv.company_id == csr.company_id]
            pick_from = company_cvs if len(company_cvs) >= 3 else cvs
            picks = random.sample(pick_from, k=min(3, len(pick_from)))
            if not picks:
                continue

            # Create/replace queue rows (use actual field names: cv1queue/cv2queue/cv3queue)
            mq, _ = MatchQueue.objects.update_or_create(
                request=req,
                defaults={
                    "cv1queue": picks[0],
                    "cv2queue": picks[1] if len(picks) > 1 else None,
                    "cv3queue": picks[2] if len(picks) > 2 else None,
                    "current_index": 1,
                    "status": "active",  # MatchQueueStatus.ACTIVE.value
                    "sent_at": timezone.now(),
                    "deadline": timezone.now() + timedelta(minutes=30),
                },
            )
            queues_created += 1

            # Notify OFFER_SENT (rank 1)
            Notification.objects.create(
                recipient=csr.user,
                type=NotificationType.OFFER_SENT,
                message=f"Offer sent to {picks[0].name} ({picks[0].id}) for {req.id}",
                request=req, cv=picks[0],
                meta={"rank": 1, "deadline": mq.deadline.isoformat() if mq.deadline else None}
            ); notif_created += 1

            # Randomly simulate: expired+advance, declined, or accepted
            roll = random.random()
            # helper: map current_index -> current CV obj
            def current_cv_of(mq_obj: MatchQueue):
                if mq_obj.current_index == 1:
                    return mq_obj.cv1queue
                if mq_obj.current_index == 2:
                    return mq_obj.cv2queue
                if mq_obj.current_index == 3:
                    return mq_obj.cv3queue
                return None

            if roll < 0.33:
                # EXPIRED: advance to next (if any)
                Notification.objects.create(
                    recipient=csr.user,
                    type=NotificationType.OFFER_EXPIRED,
                    message=f"{picks[0].name} did not respond in time.",
                    request=req, cv=picks[0],
                    meta={"rank": 1}
                ); notif_created += 1

                if len(picks) >= 2:
                    # advance to #2
                    MatchQueue.objects.filter(pk=mq.pk).update(
                        current_index=2,
                        sent_at=timezone.now(),
                        deadline=timezone.now() + timedelta(minutes=30),
                    )
                    mq.refresh_from_db()
                    cv2 = current_cv_of(mq)
                    Notification.objects.create(
                        recipient=csr.user,
                        type=NotificationType.QUEUE_ADVANCED,
                        message=f"Reassigned to next CV ({cv2.id}) for {req.id}",
                        request=req, cv=cv2,
                        meta={"current_index": mq.current_index}
                    ); notif_created += 1

            elif roll < 0.66:
                # DECLINED by current CV
                cur_cv = current_cv_of(mq)
                Notification.objects.create(
                    recipient=csr.user,
                    type=NotificationType.OFFER_DECLINED,
                    message=f"{cur_cv.name} ({cur_cv.id}) declined offer for {req.id}",
                    request=req, cv=cur_cv,
                    meta={"rank": mq.current_index}
                ); notif_created += 1

                # advance if possible
                if mq.current_index < 3 and ((mq.current_index == 1 and mq.cv2queue_id) or (mq.current_index == 2 and mq.cv3queue_id)):
                    MatchQueue.objects.filter(pk=mq.pk).update(
                        current_index=mq.current_index + 1,
                        sent_at=timezone.now(),
                        deadline=timezone.now() + timedelta(minutes=30),
                    )
                    mq.refresh_from_db()
                    nxt = current_cv_of(mq)
                    Notification.objects.create(
                        recipient=csr.user,
                        type=NotificationType.QUEUE_ADVANCED,
                        message=f"Reassigned to next CV ({nxt.id}) for {req.id}",
                        request=req, cv=nxt,
                        meta={"current_index": mq.current_index}
                    ); notif_created += 1

            else:
                # ACCEPTED by current CV -> mark Request ACTIVE and set cv
                cur_cv = current_cv_of(mq)
                req.cv = cur_cv
                req.status = RequestStatus.ACTIVE
                req.save(update_fields=["cv", "status"])

                Notification.objects.create(
                    recipient=csr.user,
                    type=NotificationType.MATCH_ACCEPTED,
                    message=f"{cur_cv.name} accepted. Request {req.id} is ACTIVE.",
                    request=req, cv=cur_cv
                ); notif_created += 1

                # queue considered filled (we’ll just mark status and clear deadline)
                MatchQueue.objects.filter(pk=mq.pk).update(
                    status="filled",
                    deadline=None
                )

                # Ensure a chat exists once ACTIVE
                ChatRoom.objects.get_or_create(request=req)

        self.stdout.write(self.style.SUCCESS(f"Created {queues_created} MatchQueues & {notif_created} Notifications"))

        # Sanity print
        pending_with_counts = (
            Request.objects.filter(status=RequestStatus.PENDING)
            .annotate(shortlist_count=Count("shortlisted_by", distinct=True))
            .order_by("-created_at")[:5]
        )
        any_counts = [r.shortlist_count for r in pending_with_counts]
        self.stdout.write(self.style.NOTICE(f"Sample shortlist_count in PENDING: {any_counts}"))
        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _clear_all(self):
        # Delete in dependency order
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
        # keep superusers; clean the rest
        get_user_model().objects.exclude(is_superuser=True).delete()
