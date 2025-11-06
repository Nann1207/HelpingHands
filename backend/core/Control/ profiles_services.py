
from __future__ import annotations
from typing import Optional
from django.contrib.auth import get_user_model
from django.db import transaction

from core.models import AbstractUser, Company, PersonInNeed, CV, CSRRep, PA, ServiceCategory

User = get_user_model()


@transaction.atomic
def create_company(*, company_id: str, companyname: str) -> Company:
    return Company.objects.create(company_id=company_id, companyname=companyname)


@transaction.atomic
def create_pin(*, user: AbstractUser, name: str, dob, phone: str, address: str,
               preferred_cv_language: str, preferred_cv_gender: str = "") -> PersonInNeed:
    return PersonInNeed.objects.create(
        user=user, name=name, dob=dob, phone=phone, address=address,
        preferred_cv_language=preferred_cv_language,
        preferred_cv_gender=preferred_cv_gender or "",
    )


@transaction.atomic
def create_cv(*, user: AbstractUser, company: Company, name: str, dob, phone: str, address: str,
              gender: str, main_language: str, second_language: str = "",
              service_category_preference: str = "Healthcare") -> CV:
    
    
    valid = [c[0] for c in ServiceCategory.choices]
    if service_category_preference not in valid:
        raise ValueError(f"Invalid service_category_preference; choose from: {valid}")
    return CV.objects.create(
        user=user, company=company, name=name, dob=dob, phone=phone, address=address,
        gender=gender, main_language=main_language, second_language=second_language or "",
        service_category_preference=service_category_preference,
    )


@transaction.atomic
def create_csr(*, user: AbstractUser, company: Company, name: str, dob, phone: str, address: str,
               gender: str = "") -> CSRRep:
    return CSRRep.objects.create(
        user=user, company=company, name=name, dob=dob, phone=phone, address=address,
        gender=gender or "",
    )


@transaction.atomic
def create_pa(*, user: AbstractUser, name: str, dob, phone: str, address: str) -> PA:
    return PA.objects.create(
        user=user, name=name, dob=dob, phone=phone, address=address
    )
