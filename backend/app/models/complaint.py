"""Complaint sub-model of ComplaintState."""

from datetime import date

from pydantic import BaseModel, Field


class Complaint(BaseModel):
    """Structured complaint information captured during intake."""

    # ==========================
    # Company Information
    # ==========================
    company_name: str | None = None
    manufacturer: str | None = None

    # ==========================
    # Product Information
    # ==========================
    product_name: str | None = None
    generic_name: str | None = None
    strength: str | None = None
    dosage_form: str | None = None
    pack_size: str | None = None
    quantity: str | None = None

    # ==========================
    # Batch Information
    # ==========================
    batch_number: str | None = None
    manufacturing_date: date | None = None
    expiry_date: date | None = None

    # ==========================
    # Complaint Information
    # ==========================
    complaint_description: str | None = None
    complaint_category: str | None = None
    complaint_type: str | None = None
    defect_type: str | None = None
    severity: str | None = None

    # ==========================
    # Patient Information
    # ==========================
    reported_event: str | None = None
    symptoms: list[str] = Field(default_factory=list)