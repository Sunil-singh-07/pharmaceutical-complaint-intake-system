"""Tests for the deterministic Risk Assessment Engine (RiskEngine service)."""

import json
from pathlib import Path

import pytest

from app.knowledge.loader import KnowledgeLoader
from app.models.complaint import Complaint
from app.services.risk_engine import RiskEngine

# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------


def _complaint(**overrides: object) -> Complaint:
    """Build a minimal Complaint with the given field overrides.

    Args:
        **overrides: Field values to set on the complaint.

    Returns:
        A Complaint instance.
    """
    return Complaint(**overrides)


@pytest.fixture
def risk_engine() -> RiskEngine:
    """Return a RiskEngine backed by the real bundled knowledge base.

    Returns:
        A RiskEngine instance.
    """
    return RiskEngine()


# --------------------------------------------------------------------------
# Priority assignment via complaint type
# --------------------------------------------------------------------------


def test_foreign_particle_is_assessed_as_critical(risk_engine: RiskEngine) -> None:
    """Foreign Particle complaints should trigger patient_safety -> Critical."""
    complaint = _complaint(
        complaint_category="Contamination",
        complaint_type="Foreign Particle",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Critical"
    assert "patient_safety" in result.risk_factors
    assert "contamination" in result.risk_factors


def test_damaged_seal_is_assessed_as_medium(risk_engine: RiskEngine) -> None:
    """Damaged Seal complaints should trigger packaging_defect -> Medium."""
    complaint = _complaint(
        complaint_category="Packaging Defect",
        complaint_type="Damaged Seal",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Medium"
    assert "packaging_defect" in result.risk_factors


def test_leaking_bottle_is_assessed_as_medium(risk_engine: RiskEngine) -> None:
    """Leaking Bottle complaints should trigger packaging_defect -> Medium."""
    complaint = _complaint(
        complaint_category="Packaging Defect",
        complaint_type="Leaking Bottle",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Medium"


def test_wrong_label_is_assessed_as_low(risk_engine: RiskEngine) -> None:
    """Wrong Label complaints should trigger labeling_only -> Low."""
    complaint = _complaint(
        complaint_category="Labeling Defect",
        complaint_type="Wrong Label",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Low"
    assert "labeling_only" in result.risk_factors


def test_missing_label_is_assessed_as_low(risk_engine: RiskEngine) -> None:
    """Missing Label complaints should trigger labeling_only -> Low."""
    complaint = _complaint(
        complaint_category="Labeling Defect",
        complaint_type="Missing Label",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Low"


def test_broken_tablet_without_severity_defaults_to_low(risk_engine: RiskEngine) -> None:
    """Physical Defect types map only to product_quality, which no priority
    rule requires, so assessment should fall back to the default priority."""
    complaint = _complaint(
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Low"
    assert "product_quality" in result.risk_factors
    assert result.reasons[-1].startswith("No elevated risk factors")


# --------------------------------------------------------------------------
# Priority assignment via category fallback (no complaint_type mapped)
# --------------------------------------------------------------------------


def test_category_fallback_used_when_type_not_mapped(risk_engine: RiskEngine) -> None:
    """Category signals should be used when the complaint type is unmapped."""
    complaint = _complaint(
        complaint_category="Contamination",
        complaint_type="Some Unmapped Type",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Critical"
    assert "patient_safety" in result.risk_factors


def test_no_category_or_type_defaults_to_low(risk_engine: RiskEngine) -> None:
    """A complaint with no category or type should default to Low priority."""
    complaint = _complaint()

    result = risk_engine.assess(complaint)

    assert result.priority == "Low"
    assert result.risk_factors == []


# --------------------------------------------------------------------------
# Severity escalation
# --------------------------------------------------------------------------


def test_critical_severity_escalates_priority_to_critical(risk_engine: RiskEngine) -> None:
    """A Critical severity report should escalate priority via patient_safety."""
    complaint = _complaint(
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
        severity="Critical",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Critical"
    assert "patient_safety" in result.risk_factors


def test_high_severity_escalates_priority_to_high(risk_engine: RiskEngine) -> None:
    """A High severity report should escalate priority via contamination."""
    complaint = _complaint(
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
        severity="High",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "High"


def test_low_severity_does_not_override_higher_category_signal(
    risk_engine: RiskEngine,
) -> None:
    """A Low severity report should not downgrade an inherently critical type."""
    complaint = _complaint(
        complaint_category="Contamination",
        complaint_type="Foreign Particle",
        severity="Low",
    )

    result = risk_engine.assess(complaint)

    assert result.priority == "Critical"


# --------------------------------------------------------------------------
# Score and recommended actions
# --------------------------------------------------------------------------


def test_critical_priority_has_expected_score_and_actions(risk_engine: RiskEngine) -> None:
    """Critical priority should carry the configured score and actions."""
    complaint = _complaint(complaint_type="Foreign Particle")

    result = risk_engine.assess(complaint)

    assert result.score == 90
    assert len(result.recommended_actions) > 0
    assert all(isinstance(action, str) for action in result.recommended_actions)


def test_low_priority_has_expected_score_and_actions(risk_engine: RiskEngine) -> None:
    """Low priority should carry the configured score and actions."""
    complaint = _complaint()

    result = risk_engine.assess(complaint)

    assert result.score == 15
    assert len(result.recommended_actions) > 0


def test_all_four_priority_levels_have_distinct_scores(risk_engine: RiskEngine) -> None:
    """Each priority level should resolve to a distinct numeric score."""
    scores = {
        risk_engine.assess(_complaint(complaint_type="Foreign Particle")).score,
        risk_engine.assess(
            _complaint(complaint_category="Physical Defect", severity="High")
        ).score,
        risk_engine.assess(_complaint(complaint_type="Damaged Seal")).score,
        risk_engine.assess(_complaint(complaint_type="Wrong Label")).score,
    }

    assert scores == {90, 65, 40, 15}


# --------------------------------------------------------------------------
# Reasons
# --------------------------------------------------------------------------


def test_reasons_mention_complaint_type_and_category(risk_engine: RiskEngine) -> None:
    """Reasons should reference the complaint's type and category."""
    complaint = _complaint(
        complaint_category="Packaging Defect",
        complaint_type="Damaged Seal",
    )

    result = risk_engine.assess(complaint)

    assert any("Damaged Seal" in reason for reason in result.reasons)
    assert any("Packaging Defect" in reason for reason in result.reasons)


def test_reasons_mention_severity_when_reported(risk_engine: RiskEngine) -> None:
    """Reasons should reference QA-reported severity when present."""
    complaint = _complaint(
        complaint_category="Physical Defect",
        complaint_type="Broken Tablet",
        severity="High",
    )

    result = risk_engine.assess(complaint)

    assert any("High" in reason for reason in result.reasons)


def test_reasons_are_non_empty_for_every_assessment(risk_engine: RiskEngine) -> None:
    """Every assessment should produce at least one human-readable reason."""
    result = risk_engine.assess(_complaint())

    assert len(result.reasons) > 0


# --------------------------------------------------------------------------
# Output completeness / determinism
# --------------------------------------------------------------------------


def test_assessment_timestamp_is_set(risk_engine: RiskEngine) -> None:
    """assessment_timestamp should always be populated after assessment."""
    result = risk_engine.assess(_complaint(complaint_type="Foreign Particle"))

    assert result.assessment_timestamp is not None


def test_assessment_is_deterministic_for_identical_input(risk_engine: RiskEngine) -> None:
    """Assessing the same complaint twice should yield identical results,
    other than the assessment timestamp."""
    complaint = _complaint(
        complaint_category="Packaging Defect",
        complaint_type="Damaged Seal",
        severity="Medium",
    )

    first = risk_engine.assess(complaint)
    second = risk_engine.assess(complaint)

    assert first.priority == second.priority
    assert first.score == second.score
    assert first.risk_factors == second.risk_factors
    assert first.reasons == second.reasons
    assert first.recommended_actions == second.recommended_actions


def test_risk_factors_are_sorted(risk_engine: RiskEngine) -> None:
    """risk_factors should be returned in sorted order for stable output."""
    result = risk_engine.assess(_complaint(complaint_type="Foreign Particle"))

    assert result.risk_factors == sorted(result.risk_factors)


# --------------------------------------------------------------------------
# Custom knowledge loader / configuration-driven behavior
# --------------------------------------------------------------------------


def test_engine_uses_injected_knowledge_loader(tmp_path: Path) -> None:
    """The engine should read rules from a custom KnowledgeLoader, not
    hardcoded Python logic."""
    risk_rules_path = tmp_path / "risk_rules.json"
    risk_rules_path.write_text(
        json.dumps(
            {
                "Critical": {"custom_flag": True},
                "High": {},
                "Medium": {},
                "Low": {},
                "priority_order": ["Critical", "High", "Medium", "Low"],
                "default_priority": "Low",
                "type_signals": {"Custom Type": ["custom_flag"]},
                "category_signals": {},
                "severity_signals": {},
                "priority_scores": {"Critical": 99, "Low": 1},
                "recommended_actions": {
                    "Critical": ["Do the custom thing."],
                    "Low": [],
                },
            }
        ),
        encoding="utf-8",
    )
    loader = KnowledgeLoader(risk_rules_path=risk_rules_path)
    engine = RiskEngine(knowledge_loader=loader)

    result = engine.assess(_complaint(complaint_type="Custom Type"))

    assert result.priority == "Critical"
    assert result.score == 99
    assert result.recommended_actions == ["Do the custom thing."]


def test_engine_falls_back_to_default_priority_order_when_absent(
    tmp_path: Path,
) -> None:
    """When priority_order is missing from risk_rules.json, the engine
    should fall back to its built-in evaluation order."""
    risk_rules_path = tmp_path / "risk_rules.json"
    risk_rules_path.write_text(
        json.dumps(
            {
                "Critical": {"patient_safety": True},
                "High": {},
                "Medium": {},
                "Low": {},
                "type_signals": {"Foreign Particle": ["patient_safety"]},
            }
        ),
        encoding="utf-8",
    )
    loader = KnowledgeLoader(risk_rules_path=risk_rules_path)
    engine = RiskEngine(knowledge_loader=loader)

    complaint = _complaint(complaint_category="Contamination", complaint_type="Foreign Particle")
    result = engine.assess(complaint)

    assert result.priority == "Critical"


def test_engine_falls_back_to_default_priority_string_when_absent(
    tmp_path: Path,
) -> None:
    """When default_priority is missing, the engine should fall back to
    its built-in default of 'Low'."""
    risk_rules_path = tmp_path / "risk_rules.json"
    risk_rules_path.write_text(json.dumps({}), encoding="utf-8")
    loader = KnowledgeLoader(risk_rules_path=risk_rules_path)
    engine = RiskEngine(knowledge_loader=loader)

    result = engine.assess(_complaint())

    assert result.priority == "Low"
    assert result.score is None
    assert result.recommended_actions == []


def test_engine_propagates_missing_risk_rules_file(tmp_path: Path) -> None:
    """A missing risk_rules.json should surface as KnowledgeFileNotFoundError."""
    from app.knowledge.loader import KnowledgeFileNotFoundError

    missing_path = tmp_path / "does_not_exist.json"
    loader = KnowledgeLoader(risk_rules_path=missing_path)
    engine = RiskEngine(knowledge_loader=loader)

    with pytest.raises(KnowledgeFileNotFoundError):
        engine.assess(_complaint())


# --------------------------------------------------------------------------
# Default construction
# --------------------------------------------------------------------------


def test_risk_engine_defaults_to_shared_knowledge_loader() -> None:
    """RiskEngine() with no arguments should use the shared KnowledgeLoader."""
    from app.knowledge.loader import get_knowledge_loader

    engine = RiskEngine()

    assert engine.knowledge_loader is get_knowledge_loader()
