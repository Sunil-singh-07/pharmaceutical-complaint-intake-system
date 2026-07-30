"""Deterministic Validation Engine.

Validates a :class:`~app.models.complaint.Complaint` against required-field
rules and against the complaint taxonomy served by
:class:`~app.knowledge.loader.KnowledgeLoader`. Validation is entirely
Python-based and deterministic: it never calls an LLM and never guesses,
per 03_AI_DESIGN.md section 9 and 04_CODING_CONTRACT.md section 11.
"""

import logging
import re
from datetime import datetime, timezone,date

from app.knowledge.loader import (
    InvalidCategoryError,
    KnowledgeLoader,
    get_knowledge_loader,
)
from app.models.complaint import Complaint
from app.models.validation import Validation, ValidationError

logger = logging.getLogger(__name__)

#: Complaint fields that must be present and non-blank before a complaint
#: can be saved.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "product_name",
    "complaint_description",
    "complaint_category",
    "complaint_type",
)

#: The only severity values the Validation Engine accepts.
_ALLOWED_SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


class Validator:
    """Deterministic, rule-based validator for complaint data.

    The validator checks a :class:`~app.models.complaint.Complaint`
    against required-field rules and against the complaint taxonomy
    served by :class:`~app.knowledge.loader.KnowledgeLoader`. It never
    writes to :class:`~app.models.complaint.Complaint`; it only reads it
    and reports what is present, missing, or invalid.

    The validator is stateless beyond its ``knowledge_loader`` reference
    (which is itself thread-safe, see 04_KnowledgeLoader), so a single
    instance can safely be shared and called concurrently across threads.

    Attributes:
        knowledge_loader: Source of complaint taxonomy data.
    """

    def __init__(self, knowledge_loader: KnowledgeLoader | None = None) -> None:
        """Initialize the validator.

        Args:
            knowledge_loader: Loader used to read the complaint taxonomy.
                Defaults to the shared process-wide loader.
        """
        self.knowledge_loader = knowledge_loader or get_knowledge_loader()

    def validate(self, complaint: Complaint) -> Validation:
        """Run every validation rule against a complaint.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A populated :class:`~app.models.validation.Validation` result.
        """
        errors: list[ValidationError] = []

        required_errors, missing_fields = self.validate_required_fields(complaint)
        errors.extend(required_errors)
        errors.extend(self.validate_category(complaint))
        errors.extend(self.validate_type(complaint))
        errors.extend(self.validate_quantity(complaint))
        errors.extend(self.validate_date(complaint))
        errors.extend(self._validate_batch_number(complaint))
        errors.extend(self._validate_severity(complaint))

        is_valid = not errors

        logger.info(
            "Validation completed: is_valid=%s, error_count=%d, "
            "missing_field_count=%d",
            is_valid,
            len(errors),
            len(missing_fields),
        )

        return Validation(
            is_valid=is_valid,
            errors=errors,
            warnings=[],
            missing_fields=missing_fields,
            validation_timestamp=_utc_now(),
        )

    def validate_required_fields(
        self, complaint: Complaint
    ) -> tuple[list[ValidationError], list[str]]:
        """Validate that all required fields are present and non-blank."""

        errors: list[ValidationError] = []
        missing: list[str] = []

        for field_name in _REQUIRED_FIELDS:
            value = getattr(complaint, field_name)

            if value is None:
                missing.append(field_name)
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"'{field_name}' is required and cannot be blank.",
                    )
                )
                continue

            if isinstance(value, str) and not value.strip():
                missing.append(field_name)
                errors.append(
                    ValidationError(
                        field=field_name,
                        message=f"'{field_name}' is required and cannot be blank.",
                    )
                )

        return errors, missing


    def validate_category(self, complaint: Complaint) -> list[ValidationError]:
        """Validate that the complaint category exists in the taxonomy.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A list of structured validation errors. Empty if the category
            is valid, or if no category was supplied (that is reported
            separately by :meth:`validate_required_fields`).
        """
        category = complaint.complaint_category
        if category is None or not category.strip():
            return []

        known_categories = self.knowledge_loader.get_categories()
        if category not in known_categories:
            return [
                ValidationError(
                    field="complaint_category",
                    message=f"Unknown complaint category: '{category}'.",
                )
            ]
        return []

    def validate_type(self, complaint: Complaint) -> list[ValidationError]:
        """Validate that the complaint type belongs to the selected category.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A list of structured validation errors. Empty if the type is
            valid, if no type was supplied, or if the category itself is
            invalid (that is reported separately by
            :meth:`validate_category`, to avoid duplicate error noise).
        """
        category = complaint.complaint_category
        complaint_type = complaint.complaint_type

        if complaint_type is None or not complaint_type.strip():
            return []
        if category is None or not category.strip():
            return []

        try:
            allowed_types = self.knowledge_loader.get_types(category)
        except InvalidCategoryError:
            return []

        if complaint_type not in allowed_types:
            return [
                ValidationError(
                    field="complaint_type",
                    message=(
                        f"Complaint type '{complaint_type}' does not belong "
                        f"to category '{category}'."
                    ),
                )
            ]
        return []

    def validate_quantity(self, complaint: Complaint) -> list[ValidationError]:
        """Validate that quantity contains a positive number."""

        quantity = complaint.quantity

        if quantity is None or not quantity.strip():
            return []

        match = re.search(r"\d+", quantity)

        if not match:
            return [
                ValidationError(
                    field="quantity",
                    message="Quantity must contain a positive number.",
                )
            ]

        if int(match.group()) <= 0:
            return [
                ValidationError(
                    field="quantity",
                    message="Quantity must be greater than zero.",
                )
            ]

        return []

    def validate_date(self, complaint: Complaint) -> list[ValidationError]:
        """Validate the complaint's manufacturing and expiry dates.

        Calendar-impossible dates (e.g. February 30) are already rejected
        by Pydantic when the ``Complaint`` model is constructed, so this
        method focuses on business-level impossibilities:

        - A manufacturing date in the future is rejected, since a batch
          cannot be manufactured after today.
        - An expiry date that is not strictly after the manufacturing
          date is rejected, when both are supplied.

        An expiry date in the future is intentionally accepted: most
        complaints concern products that have not yet expired.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A list of structured validation errors.
        """
        errors: list[ValidationError] = []
        manufacturing_date = complaint.manufacturing_date
        expiry_date = complaint.expiry_date

        if isinstance(manufacturing_date, str):
            try:
                manufacturing_date = datetime.strptime(
                    manufacturing_date,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                manufacturing_date = None

        if isinstance(expiry_date, str):
            try:
                expiry_date = datetime.strptime(
                    expiry_date,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                expiry_date = None

        today = date.today()
        if manufacturing_date is not None and manufacturing_date > today:
            errors.append(
                ValidationError(
                    field="manufacturing_date",
                    message="Manufacturing date cannot be in the future.",
                )
            )

        if (
            manufacturing_date is not None
            and expiry_date is not None
            and expiry_date <= manufacturing_date
        ):
            errors.append(
                ValidationError(
                    field="expiry_date",
                    message="Expiry date must be after the manufacturing date.",
                )
            )

        return errors


    def _validate_batch_number(self, complaint: Complaint) -> list[ValidationError]:
        """Validate that batch number, if supplied, is not blank.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A list of structured validation errors.
        """
        batch_number = complaint.batch_number
        if batch_number is not None and not batch_number.strip():
            return [
                ValidationError(
                    field="batch_number",
                    message="Batch number cannot be blank if supplied.",
                )
            ]
        return []

    def _validate_severity(self, complaint: Complaint) -> list[ValidationError]:
        """Validate that severity, if supplied, is one of the allowed values.

        Args:
            complaint: The complaint data to validate.

        Returns:
            A list of structured validation errors.
        """
        severity = complaint.severity
        if severity is None or not severity.strip():
            return []

        if severity not in _ALLOWED_SEVERITIES:
            return [
                ValidationError(
                    field="severity",
                    message=(
                        f"Severity '{severity}' is invalid. Allowed values: "
                        f"{', '.join(_ALLOWED_SEVERITIES)}."
                    ),
                )
            ]
        return []
