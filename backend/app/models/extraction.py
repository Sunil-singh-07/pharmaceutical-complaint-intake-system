from pydantic import BaseModel, ConfigDict, Field


class ExtractedComplaintData(BaseModel):
    """Structured complaint fields extracted from raw complaint text."""

    model_config = ConfigDict(extra="forbid")

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
    manufacturing_date: str | None = None
    expiry_date: str | None = None

    # ==========================
    # Complaint Information
    # ==========================
    complaint_category: str | None = None
    complaint_type: str | None = None
    defect_type: str | None = None
    severity: str | None = None
    description: str | None = None

    # ==========================
    # Patient Information
    # ==========================
    reported_event: str | None = None
    symptoms: list[str] = Field(default_factory=list)

    # ==========================
    # Metadata
    # ==========================
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)