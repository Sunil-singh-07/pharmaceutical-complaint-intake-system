"""Tests for the deterministic Validation Engine (Validator service)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.complaint import Complaint
from app.services.validator import Validator

# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------


def _today() -> date:
    """Return today's date derived from UTC, avoiding naive date.today().

    Returns:
        Today's date in UTC.
    """
    return datetime.now(timezone.utc).date()


def _valid_complaint(**overrides: object) -> Complaint:
    """Build a Complaint that passes every validation rule by default.

    Args:
        **overrides: Field overrides applied on top of the valid baseline.

    Returns:
        A Complaint instance.
    """
    base = {
        "company_name": "Acme Pharma",
        "product_name": "Painex 500mg",
        "batch_number": "B12345",
        "manufacturing_date": _today() - timedelta(days=30),
        "expiry_date": _today() + timedelta(days=365),
        "complaint_description": "Tablet arrived broken.",
        "complaint_category": "Physical Defect",
        "complaint_type": "Broken Tablet",
        "quantity": "2",
        "severity": "Medium",
    }
    base.update(overrides)
    return Complaint(**base)


@pytest.fixture
def validator() -> Validator:
    """Return a Validator backed by the real bundled knowledge base.

    Returns:
        A Validator instance.
    """
    return Validator()


# --------------------------------------------------------------------------
# Valid complaint
# --------------------------------------------------------------------------


def test_valid_complaint_passes_validation(validator: Validator) -> None:
    """A fully valid complaint should validate cleanly."""
    result = validator.validate(_valid_complaint())

    assert result.is_valid is True
    assert result.errors == []
    assert result.missing_fields == []
    assert result.validation_timestamp is not None


def test_valid_complaint_allows_optional_fields_absent(validator: Validator) -> None:
    """Validation should succeed even when optional fields are omitted."""
    complaint = _valid_complaint(
        batch_number=None,
        quantity=None,
        severity=None,
        manufacturing_date=None,
        expiry_date=None,
    )

    result = validator.validate(complaint)

    assert result.is_valid is True
    assert result.errors == []


# --------------------------------------------------------------------------
# Missing required fields
# --------------------------------------------------------------------------


def test_missing_required_fields_are_reported(validator: Validator) -> None:
    """Every unset required field should appear in missing_fields."""
    complaint = Complaint()

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert set(result.missing_fields) == {
        "product_name",
        "complaint_description",
        "complaint_category",
        "complaint_type",
    }
    error_fields = {error.field for error in result.errors}
    assert error_fields == set(result.missing_fields)


def test_validate_required_fields_returns_structured_errors(validator: Validator) -> None:
    """validate_required_fields should return structured field/message errors."""
    complaint = Complaint(product_name="Painex")

    errors, missing = validator.validate_required_fields(complaint)

    assert "product_name" not in missing
    assert "complaint_description" in missing
    assert all(hasattr(error, "field") and hasattr(error, "message") for error in errors)


# --------------------------------------------------------------------------
# Invalid category
# --------------------------------------------------------------------------


def test_invalid_category_is_rejected(validator: Validator) -> None:
    """An unknown complaint category should produce a structured error."""
    complaint = _valid_complaint(complaint_category="Not A Real Category")

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "complaint_category" for error in result.errors)


def test_validate_category_accepts_known_category(validator: Validator) -> None:
    """validate_category should return no errors for a known category."""
    complaint = _valid_complaint()

    errors = validator.validate_category(complaint)

    assert errors == []


# --------------------------------------------------------------------------
# Invalid complaint type
# --------------------------------------------------------------------------


def test_type_not_in_category_is_rejected(validator: Validator) -> None:
    """A type that exists but belongs to a different category is rejected."""
    complaint = _valid_complaint(
        complaint_category="Packaging Defect",
        complaint_type="Broken Tablet",
    )

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "complaint_type" for error in result.errors)


def test_validate_type_accepts_type_within_category(validator: Validator) -> None:
    """validate_type should accept a type that belongs to its category."""
    complaint = _valid_complaint(
        complaint_category="Packaging Defect",
        complaint_type="Damaged Seal",
    )

    errors = validator.validate_type(complaint)

    assert errors == []


def test_validate_type_skips_when_category_already_invalid(validator: Validator) -> None:
    """validate_type should not duplicate an already-invalid-category error."""
    complaint = _valid_complaint(
        complaint_category="Not A Real Category",
        complaint_type="Broken Tablet",
    )

    errors = validator.validate_type(complaint)

    assert errors == []


def test_validate_type_skips_when_category_is_absent(validator: Validator) -> None:
    """validate_type should return no errors when category is not supplied."""
    complaint = _valid_complaint(complaint_category=None, complaint_type="Broken Tablet")

    errors = validator.validate_type(complaint)

    assert errors == []


# --------------------------------------------------------------------------
# Invalid quantity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad_quantity", ["0", "-5", "abc", "5 boxes", "5.5"])
def test_invalid_quantity_is_rejected(validator: Validator, bad_quantity: str) -> None:
    """Non-positive or non-integer quantities should be rejected."""
    complaint = _valid_complaint(quantity=bad_quantity)

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "quantity" for error in result.errors)


@pytest.mark.parametrize("good_quantity", ["1", "42", "  7  "])
def test_valid_quantity_is_accepted(validator: Validator, good_quantity: str) -> None:
    """Positive integer quantities, with or without surrounding whitespace, pass."""
    complaint = _valid_complaint(quantity=good_quantity)

    errors = validator.validate_quantity(complaint)

    assert errors == []


# --------------------------------------------------------------------------
# Invalid / future dates
# --------------------------------------------------------------------------


def test_future_manufacturing_date_is_rejected(validator: Validator) -> None:
    """A manufacturing date in the future should be rejected."""
    complaint = _valid_complaint(manufacturing_date=_today() + timedelta(days=1))

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "manufacturing_date" for error in result.errors)


def test_expiry_before_manufacturing_date_is_rejected(validator: Validator) -> None:
    """An expiry date not after the manufacturing date should be rejected."""
    complaint = _valid_complaint(
        manufacturing_date=_today() - timedelta(days=10),
        expiry_date=_today() - timedelta(days=20),
    )

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "expiry_date" for error in result.errors)


def test_future_expiry_date_alone_is_accepted(validator: Validator) -> None:
    """A future expiry date is valid on its own (product not yet expired)."""
    complaint = _valid_complaint(
        manufacturing_date=_today() - timedelta(days=10),
        expiry_date=_today() + timedelta(days=700),
    )

    errors = validator.validate_date(complaint)

    assert errors == []


# --------------------------------------------------------------------------
# Empty description
# --------------------------------------------------------------------------


def test_blank_description_is_treated_as_missing(validator: Validator) -> None:
    """A whitespace-only description should be treated as missing."""
    complaint = _valid_complaint(complaint_description="    ")

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert "complaint_description" in result.missing_fields


# --------------------------------------------------------------------------
# Invalid severity
# --------------------------------------------------------------------------


def test_invalid_severity_is_rejected(validator: Validator) -> None:
    """A severity outside the allowed set should be rejected."""
    complaint = _valid_complaint(severity="Extreme")

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "severity" for error in result.errors)


@pytest.mark.parametrize("severity", ["Low", "Medium", "High", "Critical"])
def test_valid_severity_values_are_accepted(validator: Validator, severity: str) -> None:
    """Each of the four allowed severity values should pass."""
    complaint = _valid_complaint(severity=severity)

    result = validator.validate(complaint)

    assert result.is_valid is True


# --------------------------------------------------------------------------
# Batch number
# --------------------------------------------------------------------------


def test_blank_batch_number_is_rejected_when_supplied(validator: Validator) -> None:
    """An explicitly blank batch number should be rejected."""
    complaint = _valid_complaint(batch_number="   ")

    result = validator.validate(complaint)

    assert result.is_valid is False
    assert any(error.field == "batch_number" for error in result.errors)


def test_absent_batch_number_is_allowed(validator: Validator) -> None:
    """An omitted batch number (None) should not be treated as an error."""
    complaint = _valid_complaint(batch_number=None)

    result = validator.validate(complaint)

    assert result.is_valid is True


# --------------------------------------------------------------------------
# Multiple simultaneous validation errors
# --------------------------------------------------------------------------


def test_multiple_simultaneous_errors_are_all_reported(validator: Validator) -> None:
    """Several independent rule violations should all surface together."""
    complaint = Complaint(
        product_name="Painex",
        complaint_description="Broken on arrival",
        complaint_category="Packaging Defect",
        complaint_type="Broken Tablet",  # wrong category for this type
        quantity="-3",
        severity="Extreme",
        batch_number="   ",
        manufacturing_date=_today() + timedelta(days=5),
    )

    result = validator.validate(complaint)

    assert result.is_valid is False
    error_fields = {error.field for error in result.errors}
    assert error_fields == {
        "complaint_type",
        "quantity",
        "severity",
        "batch_number",
        "manufacturing_date",
    }


# --------------------------------------------------------------------------
# Validator is deterministic
# --------------------------------------------------------------------------


def test_validate_is_deterministic(validator: Validator) -> None:
    """Validating the same complaint twice should yield identical outcomes."""
    complaint = _valid_complaint()

    first = validator.validate(complaint)
    second = validator.validate(complaint)

    assert first.is_valid == second.is_valid
    assert first.errors == second.errors
    assert first.missing_fields == second.missing_fields
