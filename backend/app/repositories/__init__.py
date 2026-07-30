"""Repositories package.

Owns all persistence access to the database. Repositories translate
between ORM models (``app.db_models``) and plain data-transfer objects,
and are the only layer permitted to import SQLAlchemy session and ORM
types. Per the Phase 10 objective, repositories contain no business
logic: no validation, no risk calculation, no LLM calls, and no
workflow orchestration. Those responsibilities remain with the
Validator, RiskEngine, LLMService, and LangGraph workflow respectively.
"""
