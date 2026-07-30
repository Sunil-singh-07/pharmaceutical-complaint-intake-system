"""Tests for the KnowledgeLoader."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.knowledge.loader import (
    InvalidCategoryError,
    KnowledgeFileNotFoundError,
    KnowledgeLoader,
    KnowledgeParseError,
    get_knowledge_loader,
)

# --------------------------------------------------------------------------
# Successful loading
# --------------------------------------------------------------------------


def test_load_taxonomy_returns_expected_structure() -> None:
    """load_taxonomy should return the bundled taxonomy with expected keys."""
    loader = KnowledgeLoader()

    taxonomy = loader.load_taxonomy()

    assert "categories" in taxonomy
    assert "risk_factors" in taxonomy
    assert "Physical Defect" in taxonomy["categories"]


def test_load_risk_rules_returns_expected_structure() -> None:
    """load_risk_rules should return the bundled risk rules."""
    loader = KnowledgeLoader()

    risk_rules = loader.load_risk_rules()

    assert risk_rules["Critical"] == {"patient_safety": True}
    assert risk_rules["High"] == {"contamination": True}
    assert risk_rules["Medium"] == {"packaging_defect": True}
    assert risk_rules["Low"] == {"labeling_only": True}


def test_get_categories_returns_all_category_names() -> None:
    """get_categories should list every category defined in the taxonomy."""
    loader = KnowledgeLoader()

    categories = loader.get_categories()

    assert set(categories) == {
        "Physical Defect",
        "Packaging Defect",
        "Labeling Defect",
        "Contamination",
        "Product Quality",
    }


def test_get_types_returns_types_for_valid_category() -> None:
    """get_types should return the complaint types for a known category."""
    loader = KnowledgeLoader()

    types_ = loader.get_types("Physical Defect")

    assert "Broken Tablet" in types_
    assert "Discoloration" in types_


def test_get_risk_factors_returns_expected_factors() -> None:
    """get_risk_factors should list every risk factor in the taxonomy."""
    loader = KnowledgeLoader()

    risk_factors = loader.get_risk_factors()

    assert set(risk_factors) == {
        "patient_safety",
        "product_quality",
        "packaging_integrity",
        "regulatory_impact",
    }


# --------------------------------------------------------------------------
# Invalid category
# --------------------------------------------------------------------------


def test_get_types_raises_for_invalid_category() -> None:
    """get_types should raise InvalidCategoryError for an unknown category."""
    loader = KnowledgeLoader()

    with pytest.raises(InvalidCategoryError):
        loader.get_types("Nonexistent Category")


def test_invalid_category_error_carries_category_name() -> None:
    """InvalidCategoryError should expose the offending category name."""
    loader = KnowledgeLoader()

    with pytest.raises(InvalidCategoryError) as exc_info:
        loader.get_types("Nonexistent Category")

    assert exc_info.value.category == "Nonexistent Category"


# --------------------------------------------------------------------------
# Missing file
# --------------------------------------------------------------------------


def test_load_taxonomy_raises_for_missing_file(tmp_path: Path) -> None:
    """load_taxonomy should raise KnowledgeFileNotFoundError if absent."""
    missing_path = tmp_path / "does_not_exist.json"
    loader = KnowledgeLoader(taxonomy_path=missing_path)

    with pytest.raises(KnowledgeFileNotFoundError):
        loader.load_taxonomy()


def test_load_risk_rules_raises_for_missing_file(tmp_path: Path) -> None:
    """load_risk_rules should raise KnowledgeFileNotFoundError if absent."""
    missing_path = tmp_path / "does_not_exist.json"
    loader = KnowledgeLoader(risk_rules_path=missing_path)

    with pytest.raises(KnowledgeFileNotFoundError):
        loader.load_risk_rules()


# --------------------------------------------------------------------------
# Malformed JSON
# --------------------------------------------------------------------------


def test_load_taxonomy_raises_for_malformed_json(tmp_path: Path) -> None:
    """load_taxonomy should raise KnowledgeParseError for invalid JSON."""
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{ not valid json ", encoding="utf-8")
    loader = KnowledgeLoader(taxonomy_path=malformed_path)

    with pytest.raises(KnowledgeParseError):
        loader.load_taxonomy()


def test_load_risk_rules_raises_for_malformed_json(tmp_path: Path) -> None:
    """load_risk_rules should raise KnowledgeParseError for invalid JSON."""
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{ not valid json ", encoding="utf-8")
    loader = KnowledgeLoader(risk_rules_path=malformed_path)

    with pytest.raises(KnowledgeParseError):
        loader.load_risk_rules()


# --------------------------------------------------------------------------
# Caching behavior
# --------------------------------------------------------------------------


def test_load_taxonomy_is_cached_after_first_load(tmp_path: Path) -> None:
    """Repeated calls to load_taxonomy should return the same cached object."""
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(
        json.dumps({"categories": {"A": ["x"]}, "risk_factors": ["f1"]}),
        encoding="utf-8",
    )
    loader = KnowledgeLoader(taxonomy_path=taxonomy_path)

    first = loader.load_taxonomy()
    second = loader.load_taxonomy()

    assert first is second


def test_load_taxonomy_does_not_reread_file_after_caching(tmp_path: Path) -> None:
    """Once cached, taxonomy data should not reflect later file changes."""
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(
        json.dumps({"categories": {"A": ["x"]}, "risk_factors": ["f1"]}),
        encoding="utf-8",
    )
    loader = KnowledgeLoader(taxonomy_path=taxonomy_path)
    loader.load_taxonomy()

    taxonomy_path.write_text(
        json.dumps({"categories": {"B": ["y"]}, "risk_factors": ["f2"]}),
        encoding="utf-8",
    )
    cached = loader.load_taxonomy()

    assert "A" in cached["categories"]
    assert "B" not in cached["categories"]


def test_load_risk_rules_is_cached_after_first_load(tmp_path: Path) -> None:
    """Repeated calls to load_risk_rules should return the same cached object."""
    risk_rules_path = tmp_path / "risk_rules.json"
    risk_rules_path.write_text(json.dumps({"Low": {"x": True}}), encoding="utf-8")
    loader = KnowledgeLoader(risk_rules_path=risk_rules_path)

    first = loader.load_risk_rules()
    second = loader.load_risk_rules()

    assert first is second


def test_concurrent_load_taxonomy_is_thread_safe() -> None:
    """Concurrent loads should all resolve to the same cached instance."""
    loader = KnowledgeLoader()

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: loader.load_taxonomy(), range(50)))

    assert all(result is results[0] for result in results)


def test_get_knowledge_loader_returns_singleton() -> None:
    """get_knowledge_loader should return the same instance on every call."""
    first = get_knowledge_loader()
    second = get_knowledge_loader()

    assert first is second
