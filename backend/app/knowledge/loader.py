"""Knowledge base loader.

Loads and caches structured domain knowledge (complaint taxonomy and risk
rules) from the JSON configuration files bundled in this package. The
loader is strictly read-only: knowledge lives in configuration, not
hardcoded logic, per 02_ARCHITECTURE.md section 7.
"""

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KNOWLEDGE_DIR = Path(__file__).resolve().parent
_TAXONOMY_FILENAME = "complaint_taxonomy.json"
_RISK_RULES_FILENAME = "risk_rules.json"


class KnowledgeFileNotFoundError(Exception):
    """Raised when a required knowledge base file cannot be found.

    Attributes:
        path: Path that was expected to contain the knowledge base file.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the exception with the missing file's path.

        Args:
            path: Path that was expected to contain the knowledge base
                file.
        """
        self.path = path
        super().__init__(f"Knowledge base file not found: {path}")


class KnowledgeParseError(Exception):
    """Raised when a knowledge base file contains invalid JSON.

    Attributes:
        path: Path of the file that failed to parse.
        reason: Description of the underlying JSON decoding error.
    """

    def __init__(self, path: Path, reason: str) -> None:
        """Initialize the exception with the failing file and reason.

        Args:
            path: Path of the file that failed to parse.
            reason: Description of the underlying JSON decoding error.
        """
        self.path = path
        self.reason = reason
        super().__init__(f"Failed to parse knowledge base file '{path}': {reason}")


class InvalidCategoryError(Exception):
    """Raised when a complaint category is not present in the taxonomy.

    Attributes:
        category: The unrecognized category name.
    """

    def __init__(self, category: str) -> None:
        """Initialize the exception with the unrecognized category name.

        Args:
            category: The unrecognized category name.
        """
        self.category = category
        super().__init__(f"Unknown complaint category: '{category}'")


class KnowledgeLoader:
    """Loads and caches the complaint taxonomy and risk rules.

    Data is read from JSON files and cached in memory after the first
    successful load per instance. All public methods are read-only.
    Loading and caching are protected by a lock so a shared instance is
    safe to use across threads.

    Attributes:
        taxonomy_path: Path to the complaint taxonomy JSON file.
        risk_rules_path: Path to the risk rules JSON file.
    """

    def __init__(
        self,
        taxonomy_path: Path | None = None,
        risk_rules_path: Path | None = None,
    ) -> None:
        """Initialize the loader with paths to its knowledge base files.

        Args:
            taxonomy_path: Path to the complaint taxonomy JSON file.
                Defaults to ``complaint_taxonomy.json`` bundled in this
                package.
            risk_rules_path: Path to the risk rules JSON file. Defaults
                to ``risk_rules.json`` bundled in this package.
        """
        self.taxonomy_path: Path = taxonomy_path or (_KNOWLEDGE_DIR / _TAXONOMY_FILENAME)
        self.risk_rules_path: Path = risk_rules_path or (_KNOWLEDGE_DIR / _RISK_RULES_FILENAME)
        self._lock = threading.Lock()
        self._taxonomy: dict[str, Any] | None = None
        self._risk_rules: dict[str, Any] | None = None

    def load_taxonomy(self) -> dict[str, Any]:
        """Load and cache the complaint taxonomy.

        Returns:
            The parsed complaint taxonomy, containing ``categories`` and
            ``risk_factors``. The same cached object is returned on
            subsequent calls.

        Raises:
            KnowledgeFileNotFoundError: If the taxonomy file is missing.
            KnowledgeParseError: If the taxonomy file contains invalid
                JSON.
        """
        with self._lock:
            if self._taxonomy is None:
                self._taxonomy = self._read_json(self.taxonomy_path)
                logger.info("Loaded complaint taxonomy from %s", self.taxonomy_path)
            return self._taxonomy

    def load_risk_rules(self) -> dict[str, Any]:
        """Load and cache the risk rules.

        Returns:
            The parsed risk rules, keyed by priority level. The same
            cached object is returned on subsequent calls.

        Raises:
            KnowledgeFileNotFoundError: If the risk rules file is missing.
            KnowledgeParseError: If the risk rules file contains invalid
                JSON.
        """
        with self._lock:
            if self._risk_rules is None:
                self._risk_rules = self._read_json(self.risk_rules_path)
                logger.info("Loaded risk rules from %s", self.risk_rules_path)
            return self._risk_rules

    def get_categories(self) -> list[str]:
        """Return all complaint category names.

        Returns:
            A list of complaint category names defined in the taxonomy.

        Raises:
            KnowledgeFileNotFoundError: If the taxonomy file is missing.
            KnowledgeParseError: If the taxonomy file contains invalid
                JSON.
        """
        taxonomy = self.load_taxonomy()
        return list(taxonomy.get("categories", {}).keys())

    def get_types(self, category: str) -> list[str]:
        """Return the complaint types defined for a category.

        Args:
            category: Name of the complaint category.

        Returns:
            A list of complaint types belonging to ``category``.

        Raises:
            InvalidCategoryError: If ``category`` is not defined in the
                taxonomy.
            KnowledgeFileNotFoundError: If the taxonomy file is missing.
            KnowledgeParseError: If the taxonomy file contains invalid
                JSON.
        """
        taxonomy = self.load_taxonomy()
        categories: dict[str, Any] = taxonomy.get("categories", {})
        if category not in categories:
            raise InvalidCategoryError(category)
        return list(categories[category])

    def get_risk_factors(self) -> list[str]:
        """Return all known risk factors.

        Returns:
            A list of risk factor names defined in the taxonomy.

        Raises:
            KnowledgeFileNotFoundError: If the taxonomy file is missing.
            KnowledgeParseError: If the taxonomy file contains invalid
                JSON.
        """
        taxonomy = self.load_taxonomy()
        return list(taxonomy.get("risk_factors", []))

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        """Read and parse a JSON file.

        Args:
            path: Path to the JSON file to read.

        Returns:
            The parsed JSON content.

        Raises:
            KnowledgeFileNotFoundError: If ``path`` does not exist.
            KnowledgeParseError: If ``path`` contains invalid JSON.
        """
        if not path.is_file():
            raise KnowledgeFileNotFoundError(path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise KnowledgeParseError(path, str(exc)) from exc


@lru_cache
def get_knowledge_loader() -> KnowledgeLoader:
    """Return the process-wide singleton ``KnowledgeLoader`` instance.

    Using ``lru_cache`` ensures every caller shares one loader (and thus
    one cache) within a process, mirroring the pattern used by
    ``app.config.settings.get_settings`` and
    ``app.services.session_store.get_session_store``.

    Returns:
        The shared ``KnowledgeLoader`` instance.
    """
    return KnowledgeLoader()
