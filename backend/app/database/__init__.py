"""Database package.

Provides the SQLAlchemy engine (``connection.py``), declarative base
(``base.py``), and session lifecycle management (``session.py``) used by
the persistence layer. Contains no business logic, validation, risk
calculation, or workflow orchestration; see ``app.repositories`` for the
persistence-only repository layer built on top of this package.
"""
