"""Deterministic Risk Assessment Engine.

Assesses the priority of a :class:`~app.models.complaint.Complaint` using
configuration read entirely from ``risk_rules.json``, served by
:class:`~app.knowledge.loader.KnowledgeLoader`. Risk assessment is
entirely Python-based and deterministic: it never calls an LLM and always
produces the same result for the same input, per 03_AI_DESIGN.md section 8
and 04_CODING_CONTRACT.md section 11.

Assessment proceeds in three deterministic steps:

1. Collect risk-factor "signals" implied by the complaint's type,
   category, and QA-reported severity (via ``type_signals``,
   ``category_signals``, and ``severity_signals`` in ``risk_rules.json``).
2. Walk the configured ``priority_order`` and assign the first priority
   level whose required signal flags (the existing ``Critical`` /
   ``High`` / ``Medium`` / ``Low`` sections of ``risk_rules.json``) are
   all present in the collected signals. If none match, the configured
   ``default_priority`` is assigned.
3. Resolve the score and recommended actions for the assigned priority
   from ``priority_scores`` and ``recommended_actions`` in
   ``risk_rules.json``.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.knowledge.loader import KnowledgeLoader, get_knowledge_loader
from app.models.complaint import Complaint
from app.models.risk import Risk

logger = logging.getLogger(__name__)

#: Fallback priority evaluation order, used only if ``risk_rules.json``
#: does not define a ``priority_order`` section.
_DEFAULT_PRIORITY_ORDER: tuple[str, ...] = ("Critical", "High", "Medium", "Low")

#: Fallback priority, used only if ``risk_rules.json`` does not define a
#: ``default_priority`` section.
_DEFAULT_PRIORITY: str = "Low"


def _utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        The current UTC time.
    """
    return datetime.now(timezone.utc)


class RiskEngine:
    """Deterministic, rule-based risk assessment engine.

    The engine reads all rules, signal mappings, scores, and recommended
    actions from ``risk_rules.json`` via :class:`KnowledgeLoader`. It
    never guesses missing complaint information and never invokes an
    LLM.

    The engine is stateless beyond its ``knowledge_loader`` reference
    (which is itself thread-safe), so a single instance can safely be
    shared and called concurrently across threads.

    Attributes:
        knowledge_loader: Source of risk rules configuration.
    """

    def __init__(self, knowledge_loader: KnowledgeLoader | None = None) -> None:
        """Initialize the risk engine.

        Args:
            knowledge_loader: Loader used to read risk rules. Defaults to
                the shared process-wide loader.
        """
        self.knowledge_loader = knowledge_loader or get_knowledge_loader()

    def assess(self, complaint: Complaint) -> Risk:
        """Run deterministic risk assessment against a complaint.

        Args:
            complaint: The complaint data to assess.

        Returns:
            A populated :class:`~app.models.risk.Risk` result.
        """
        rules = self.knowledge_loader.load_risk_rules()

        signals = self._collect_signals(complaint, rules)
        priority, matched_flags = self._determine_priority(signals, rules)
        reasons = self._build_reasons(complaint, priority, matched_flags)
        score = self._resolve_score(priority, rules)
        recommended_actions = self._resolve_recommended_actions(priority, rules)

        logger.info(
            "Risk assessment completed: priority=%s, score=%s, signal_count=%d",
            priority,
            score,
            len(signals),
        )

        return Risk(
            priority=priority,
            score=score,
            risk_factors=sorted(signals),
            reasons=reasons,
            recommended_actions=recommended_actions,
            assessment_timestamp=_utc_now(),
        )

    def _collect_signals(self, complaint: Complaint, rules: dict[str, Any]) -> set[str]:
        """Collect risk-factor signals implied by the complaint.

        The complaint type takes precedence over the broader category
        when both are mapped, since it is the more specific signal
        source. QA-reported severity is always applied in addition, as
        an escalation input.

        Args:
            complaint: The complaint data to inspect.
            rules: The parsed contents of ``risk_rules.json``.

        Returns:
            The set of risk-factor signal names implied by the complaint.
        """
        signals: set[str] = set()

        type_signals: dict[str, list[str]] = rules.get("type_signals", {})
        category_signals: dict[str, list[str]] = rules.get("category_signals", {})
        severity_signals: dict[str, list[str]] = rules.get("severity_signals", {})

        if complaint.complaint_type and complaint.complaint_type in type_signals:
            signals.update(type_signals[complaint.complaint_type])
        elif complaint.complaint_category and complaint.complaint_category in category_signals:
            signals.update(category_signals[complaint.complaint_category])

        if complaint.severity and complaint.severity in severity_signals:
            signals.update(severity_signals[complaint.severity])

        return signals

    def _determine_priority(
        self, signals: set[str], rules: dict[str, Any]
    ) -> tuple[str, list[str]]:
        """Assign the first matching priority level for the given signals.

        Args:
            signals: Risk-factor signals collected for the complaint.
            rules: The parsed contents of ``risk_rules.json``.

        Returns:
            A tuple of ``(priority, matched_flag_names)``. ``matched_flag_names``
            is empty when no rule matched and the default priority was used.
        """
        priority_order: list[str] = rules.get("priority_order", list(_DEFAULT_PRIORITY_ORDER))

        for priority in priority_order:
            required_flags: dict[str, bool] = rules.get(priority, {})
            flag_names = [flag for flag, required in required_flags.items() if required]
            if flag_names and all(flag in signals for flag in flag_names):
                return priority, flag_names

        default_priority: str = rules.get("default_priority", _DEFAULT_PRIORITY)
        return default_priority, []

    def _build_reasons(
        self,
        complaint: Complaint,
        priority: str,
        matched_flags: list[str],
    ) -> list[str]:
        """Build human-readable reasons explaining the assigned priority."""

        reasons: list[str] = []

        # Product information
        if complaint.product_name:
            reasons.append(f"Product involved: {complaint.product_name}.")

        if getattr(complaint, "company_name", None):
            reasons.append(f"Manufacturer/Company: {complaint.company_name}.")

        # Complaint information
        if complaint.complaint_category:
            reasons.append(
                f"Complaint category identified as '{complaint.complaint_category}'."
            )

        if complaint.complaint_type:
            reasons.append(
                f"Complaint type identified as '{complaint.complaint_type}'."
            )

        if getattr(complaint, "defect_type", None):
            reasons.append(
                f"Observed defect: {complaint.defect_type}."
            )

        # Batch traceability
        if complaint.batch_number:
            reasons.append(
                "Batch number available for traceability."
            )

        # Patient information
        if getattr(complaint, "reported_event", None):
            reasons.append(
                f"Patient reported: {complaint.reported_event}."
            )

        if getattr(complaint, "reported_event", None):
            event = complaint.reported_event.rstrip(".")
            reasons.append(f"Patient reported: {event}.")

        # Severity
        if complaint.severity:
            reasons.append(
                f"Reported severity: {complaint.severity}."
            )

        # Rule explanation
        if matched_flags:
            reasons.append(
                "Risk rule triggered by: "
                + ", ".join(sorted(matched_flags))
                + "."
            )
        else:
            reasons.append(
                f"No high-risk rule matched; default priority '{priority}' assigned."
            )

        return reasons

    def _resolve_score(self, priority: str, rules: dict[str, Any]) -> int | None:
        """Resolve the numeric risk score configured for a priority level.

        Args:
            priority: The assigned priority level.
            rules: The parsed contents of ``risk_rules.json``.

        Returns:
            The configured score, or ``None`` if not configured.
        """
        priority_scores: dict[str, int] = rules.get("priority_scores", {})
        return priority_scores.get(priority)

    def _resolve_recommended_actions(
        self,
        priority: str,
        rules: dict[str, Any],
    ) -> list[str]:
        """Resolve recommended actions."""

        actions = list(
            rules.get("recommended_actions", {}).get(priority, [])
        )

        default_actions = {
            "Critical": [
                "Quarantine affected batch.",
                "Notify QA Manager immediately.",
                "Initiate product recall assessment.",
                "Begin laboratory investigation.",
            ],
            "High": [
                "Investigate affected batch.",
                "Review manufacturing records.",
                "Collect retained samples.",
            ],
            "Medium": [
                "Review complaint history.",
                "Monitor for similar complaints.",
            ],
            "Low": [
                "Document complaint.",
                "Continue routine monitoring.",
            ],
        }

        if not actions:
            actions = default_actions.get(priority, [])

        return actions