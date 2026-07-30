"""Knowledge base package.

Contains structured domain knowledge as configuration, not code, per
02_ARCHITECTURE.md section 7:

- ``complaint_taxonomy.json``: complaint categories, types, and risk
  factors.
- ``risk_rules.json``: deterministic priority rules, consumed by the
  Risk Engine service in a later development phase.
- ``loader.py``: read-only, cached access to the files above via
  :class:`~app.knowledge.loader.KnowledgeLoader`.
"""
