import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from core.models import (
    Company,
    PersonInNeed,
    CV,
    CSRRep,
    PA,
    Request,
    RequestStatus,
    LanguageChoices,
    GenderChoices,
    ServiceCategory,
    ClaimReport,
    ClaimCategory,
    PaymentMethod,
    ClaimStatus,
    DisputeReason,
    FlaggedRequest,
    FlagType,
    ResolutionOutcome,
    ShortlistedRequest,
    EmailOTP,
    MatchQueue,
    MatchQueueStatus,
    Notification,
    NotificationType,
    ChatRoom,
    OtpPurpose,
)
from core.Control.cv_controller import CvController
from core.Control.chat_controller import ChatController
from core.Control.pin_controller import PinController
from core.Control.admin_controllers import (
    AdminFlagController,
    AdminReportController,
    AdminMetricsController,
)
from core.Control.csr_controller import CSRMatchController
from core.entity.pin_entity import PinEntity

pytestmark = pytest.mark.django_db

def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

@pytest.fixture
def company():
    return Company.objects.create(company_id=_unique("COMP"), companyname="Helping Hands Ltd")

@pytest.fixture
def user_factory():
    user_model = get_user_model()

    def _create(username=None, email=None, password="Passw0rd!"):
        username = username or _unique("user")
        return user_model.objects.create_user(
            username=username,
            email=email or f"{username}@example.com",
            password=password,
        )

    return _create

@pytest.fixture
def pin_factory(user_factory):
    def _create(**overrides):
        user = overrides.pop("user", user_factory(overrides.pop("username", None)))
        return PersonInNeed.objects.create(
            user=user,
            name=overrides.pop("name", f"PIN {user.username}"),
            dob=overrides.pop("dob", date(1950, 1, 1)),
            phone=overrides.pop("phone", "11112222"),
            address=overrides.pop("address", "1 Helper Way"),
            preferred_cv_language=overrides.pop("preferred_cv_language", LanguageChoices.EN),
            preferred_cv_gender=overrides.pop("preferred_cv_gender", GenderChoices.FEMALE),
        )

    return _create

@pytest.fixture
def cv_factory(user_factory, company):
    def _create(**overrides):
        user = overrides.pop("user", user_factory(overrides.pop("username", None)))
        return CV.objects.create(
            user=user,
            name=overrides.pop("name", f"CV {user.username}"),
            dob=overrides.pop("dob", date(1990, 1, 1)),
            phone=overrides.pop("phone", "99998888"),
            address=overrides.pop("address", "2 Helper Way"),
            gender=overrides.pop("gender", GenderChoices.MALE),
            main_language=overrides.pop("main_language", LanguageChoices.EN),
            second_language=overrides.pop("second_language", LanguageChoices.ZH),
            service_category_preference=overrides.pop(
                "service_category_preference", ServiceCategory.HEALTHCARE
            ),
            company=overrides.pop("company", company),
        )

    return _create

@pytest.fixture
def csr_factory(user_factory, company):
    def _create(**overrides):
        user = overrides.pop("user", user_factory(overrides.pop("username", None)))
        return CSRRep.objects.create(
            user=user,
            name=overrides.pop("name", f"CSR {user.username}"),
            dob=overrides.pop("dob", date(1985, 1, 1)),
            phone=overrides.pop("phone", "33334444"),
            address=overrides.pop("address", "3 Helper Way"),
            gender=overrides.pop("gender", GenderChoices.FEMALE),
            company=overrides.pop("company", company),
        )

    return _create

@pytest.fixture
def pa_factory(user_factory):
    def _create(**overrides):
        user = overrides.pop("user", user_factory(overrides.pop("username", None)))
        return PA.objects.create(
            user=user,
            name=overrides.pop("name", f"PA {user.username}"),
            dob=overrides.pop("dob", date(1980, 1, 1)),
            phone=overrides.pop("phone", "77776666"),
            address=overrides.pop("address", "4 Admin Way"),
        )

    return _create

@pytest.fixture
def request_factory(pin_factory):
    def _create(**overrides):
        pin = overrides.pop("pin", pin_factory())
        appointment_dt = timezone.now() + timedelta(hours=1)
        defaults = {
            "service_type": overrides.pop("service_type", ServiceCategory.HEALTHCARE),
            "appointment_date": overrides.pop("appointment_date", appointment_dt.date()),
            "appointment_time": overrides.pop(
                "appointment_time", appointment_dt.time().replace(microsecond=0)
            ),
            "pickup_location": overrides.pop("pickup_location", "Pickup Point"),
            "service_location": overrides.pop("service_location", "Service Point"),
            "description": overrides.pop("description", "Need transport help"),
            "status": overrides.pop("status", RequestStatus.PENDING),
            "cv": overrides.pop("cv", None),
            "committed_by_csr": overrides.pop("committed_by_csr", None),
            "committed_at": overrides.pop("committed_at", None),
        }
        defaults.update(overrides)
        return Request.objects.create(pin=pin, **defaults)

    return _create

# User Story 1 (C06): CV submits an expense claim with receipt proof for CSR review.
def test_user_story_1_c06_cv_submits_claim_with_proof(
    cv_factory, pin_factory, request_factory, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    cv = cv_factory()
    pin = pin_factory()
    req = request_factory(pin=pin, status=RequestStatus.ACTIVE, cv=cv)

    claim = CvController.report_claim(
        user=cv.user,
        req_id=req.id,
        category=ClaimCategory.TRANSPORT,
        expense_date=date.today(),
        amount=Decimal("23.45"),
        payment_method=PaymentMethod.CASH,
        description="Taxi from clinic",
        receipt=SimpleUploadedFile("receipt.jpg", b"fake receipt data"),
    )

    assert ClaimReport.objects.filter(id=claim.id, request=req, cv=cv).exists()
    assert claim.status == ClaimStatus.SUBMITTED
    assert claim.receipt.name
    print("user story 1 pass")

# User Story 2 (C10): CV sees personalised safety tips generated for an assignment.
def test_user_story_2_c10_safety_tips_are_personalised(
    cv_factory, pin_factory, request_factory, settings
):
    settings.SEA_LION_LLAMA_API_KEY = ""
    settings.SEA_LION_LLAMA_ENDPOINT = ""
    pin = pin_factory(
        dob=date(1940, 1, 1),
        preferred_cv_gender=GenderChoices.FEMALE,
        preferred_cv_language=LanguageChoices.EN,
    )
    cv = cv_factory()
    req = request_factory(
        pin=pin,
        cv=cv,
        status=RequestStatus.ACTIVE,
        service_type=ServiceCategory.VACCINATION_CHECKUP,
        description="Medical escort for vaccination",
        pickup_location="Clinic A",
        service_location="Hospital B",
    )

    data = CvController.safety_tips(user=cv.user, req_id=req.id)
    tips = data["tips"]

    assert any("medical" in tip.lower() or "documents" in tip.lower() for tip in tips)
    assert any("well-lit" in tip.lower() for tip in tips)
    print("user story 2 pass")

# User Story 3 (C17): Chat access closes 24 hours after completion for secure messaging.
def test_user_story_3_c17_chat_expires_after_completion(
    cv_factory, pin_factory, request_factory
):
    cv = cv_factory()
    pin = pin_factory()
    req = request_factory(pin=pin, cv=cv, status=RequestStatus.ACTIVE)

    ChatController.complete_request(user=cv.user, req_id=req.id)
    req.refresh_from_db()
    chat = ChatRoom.objects.get(request=req)

    assert req.status == RequestStatus.COMPLETE
    assert chat.expires_at - req.completed_at == timedelta(hours=24)
    print("user story 3 pass")

# User Story 4 (PA03): Platform admin reviews flagged requests for safety.
def test_user_story_4_pa03_admin_reviews_flagged_requests(pa_factory, request_factory):
    pa = pa_factory()
    req = request_factory(status=RequestStatus.REVIEW)
    flag = FlaggedRequest.objects.create(
        request=req,
        flag_type=FlagType.AUTO,
        reasonbycsr="Auto moderation trigger",
    )

    AdminFlagController.accept_flag(flag_id=flag.id, pa_user=pa.user, notes="Safe to proceed")
    flag.refresh_from_db()
    req.refresh_from_db()

    assert flag.resolved and flag.resolution_outcome == ResolutionOutcome.ACCEPTED
    assert flag.resolved_by == pa
    assert req.status == RequestStatus.PENDING
    print("user story 4 pass")

# User Story 5 (PA05): Platform admin exports a detailed request report with stats.
def test_user_story_5_pa05_admin_can_export_request_report(request_factory, cv_factory):
    pending = request_factory(status=RequestStatus.PENDING)
    review = request_factory(status=RequestStatus.REVIEW)
    completed = request_factory(status=RequestStatus.COMPLETE, cv=cv_factory())

    filename, payload = AdminReportController.export_requests_csv()
    text = payload.decode("utf-8-sig")

    assert filename == "requestsExport.csv"
    assert pending.id in text and review.id in text and completed.id in text
    assert "SUMMARY:" in text
    assert "Pending,1" in text
    assert "Review,1" in text
    assert "Completed,1" in text
    print("user story 5 pass")

# User Story 6 (PA06): Platform admin views platform-wide dashboard metrics.
def test_user_story_6_pa06_admin_dashboard_metrics(
    pin_factory, cv_factory, csr_factory, pa_factory, request_factory
):
    pin_one = pin_factory()
    pin_two = pin_factory()
    cv_one = cv_factory()
    cv_two = cv_factory()
    csr_one = csr_factory()
    csr_factory()

    req_review = request_factory(pin=pin_one, status=RequestStatus.REVIEW)
    req_pending = request_factory(pin=pin_two, status=RequestStatus.PENDING)
    request_factory(status=RequestStatus.REJECTED)
    request_factory(status=RequestStatus.ACTIVE, cv=cv_one)
    request_factory(status=RequestStatus.COMPLETE, cv=cv_two)

    pa = pa_factory()
    FlaggedRequest.objects.create(
        request=req_review,
        flag_type=FlagType.AUTO,
        reasonbycsr="auto",
    )
    FlaggedRequest.objects.create(
        request=req_pending,
        flag_type=FlagType.MANUAL,
        csr=csr_one,
        reasonbycsr="manual",
        resolved=True,
        resolved_by=pa,
        resolution_outcome=ResolutionOutcome.ACCEPTED,
    )

    metrics = AdminMetricsController.get_metrics()
    cards = metrics["cards"]

    assert cards["Review"] == 1
    assert cards["Pending"] == 1
    assert cards["Rejected"] == 1
    assert cards["Active"] == 1
    assert cards["Completed"] == 1
    assert cards["Open Flags"] == 1
    assert cards["Resolved Flags"] == 1
    assert cards["Number of PIN"] == PersonInNeed.objects.count()
    assert cards["Number of CV"] == CV.objects.count()
    assert cards["Number of CSR"] == CSRRep.objects.count()
    assert metrics["charts"]["requests_by_status"]
    assert any(row["review"] >= 1 for row in metrics["charts"]["requests_by_status"])
    print("user story 6 pass")

# User Story 7 (P04): PIN views shortlist counts on each request.
def test_user_story_7_p04_pin_views_shortlist_counts(
    pin_factory, csr_factory, request_factory
):
    pin = pin_factory()
    req = request_factory(pin=pin, status=RequestStatus.PENDING)
    ShortlistedRequest.objects.create(csr=csr_factory(), request=req)
    ShortlistedRequest.objects.create(csr=csr_factory(), request=req)

    entries = list(PinEntity.list_requests(pin_id=pin.id))
    assert entries and getattr(entries[0], "shortlist_count", 0) == 2
    print("user story 7 pass")

# User Story 8 (P09): PIN disputes an incorrect claim for CSR review.
def test_user_story_8_p09_pin_disputes_incorrect_claim(
    pin_factory, cv_factory, request_factory, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    pin = pin_factory()
    cv = cv_factory()
    req = request_factory(pin=pin, cv=cv, status=RequestStatus.COMPLETE)
    claim = ClaimReport.objects.create(
        request=req,
        cv=cv,
        category=ClaimCategory.MEDS,
        expense_date=date.today(),
        amount=Decimal("12.00"),
        payment_method=PaymentMethod.CARD,
        description="Medication fee",
        receipt=SimpleUploadedFile("proof.png", b"proof"),
    )

    PinController.dispute_claim(
        user=pin.user,
        claim_id=claim.id,
        reason=DisputeReason.INCORRECT_AMOUNT,
        comment="Amount mismatch",
    )
    claim.refresh_from_db()

    assert claim.status == ClaimStatus.DISPUTED_BY_PIN
    assert claim.disputes.count() == 1
    print("user story 8 pass")

# User Story 9 (P14): PIN verifies password change via email OTP.
def test_user_story_9_p14_pin_confirms_password_change_via_otp(pin_factory, monkeypatch):
    pin = pin_factory()
    sent = {}

    def fake_send_mail(*args, **kwargs):
        sent["called"] = True
        return 1

    monkeypatch.setattr("django.core.mail.send_mail", fake_send_mail)
    monkeypatch.setattr("core.Control.pin_controller.random.randint", lambda *_: 123456)

    PinController.start_password_change_otp(user=pin.user)
    otp = EmailOTP.objects.get(email=pin.user.email, purpose=OtpPurpose.PASSWORD_CHANGE)

    PinController.change_password_with_otp(user=pin.user, code="123456", new_password="S3curePwd!")
    pin.user.refresh_from_db()
    otp.refresh_from_db()

    assert pin.user.check_password("S3curePwd!")
    assert otp.consumed
    assert sent.get("called")
    print("user story 9 pass")

# User Story 10 (CSR9): Dormant requests auto-reassign to next CV.
def test_user_story_10_csr9_auto_reassigns_dormant_requests(
    cv_factory, csr_factory, request_factory
):
    csr = csr_factory()
    cv_one = cv_factory()
    cv_two = cv_factory()
    req = request_factory(
        status=RequestStatus.COMMITTED,
        committed_by_csr=csr,
        committed_at=timezone.now() - timedelta(days=1),
    )
    MatchQueue.objects.create(
        request=req,
        cv1queue=cv_one,
        cv2queue=cv_two,
        cv3queue=None,
        current_index=1,
        status=MatchQueueStatus.ACTIVE,
        sent_at=timezone.now() - timedelta(hours=2),
        deadline=timezone.now() - timedelta(hours=1),
    )

    result = CSRMatchController.sweep_dormant()
    mq = MatchQueue.objects.get(request=req)

    assert result["auto_advanced"] == 1
    assert mq.current_index == 2
    assert mq.deadline > timezone.now() - timedelta(minutes=5)
    assert Notification.objects.filter(
        type=NotificationType.OFFER_EXPIRED, request=req
    ).count() == 1
    print("user story 10 pass")

# User Story 11 (CSR16): CSR sees automated suggestions for best-fit CVs.
def test_user_story_11_csr16_auto_suggests_high_fit_volunteers(
    pin_factory, cv_factory, request_factory
):
    pin = pin_factory(
        preferred_cv_language=LanguageChoices.ZH,
        preferred_cv_gender=GenderChoices.FEMALE,
    )
    best_cv = cv_factory(
        gender=GenderChoices.FEMALE,
        main_language=LanguageChoices.ZH,
        service_category_preference=ServiceCategory.HEALTHCARE,
    )
    backup_cv = cv_factory(
        gender=GenderChoices.FEMALE,
        main_language=LanguageChoices.EN,
        second_language=LanguageChoices.ZH,
        service_category_preference=ServiceCategory.HEALTHCARE,
    )
    cv_factory(
        gender=GenderChoices.MALE,
        main_language=LanguageChoices.EN,
        service_category_preference=ServiceCategory.COMMUNITY_EVENT,
    )
    req = request_factory(pin=pin, service_type=ServiceCategory.HEALTHCARE)

    suggestions = CSRMatchController.suggest(request_id=req.id)["suggestions"]

    assert len(suggestions) >= 2
    assert suggestions[0]["cv_id"] == best_cv.id
    assert "category" in suggestions[0]["reason"]
    assert suggestions[0]["score"] >= suggestions[1]["score"] >= suggestions[-1]["score"]
    assert backup_cv.id in {s["cv_id"] for s in suggestions}
    print("user story 11 pass")
