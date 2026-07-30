"""ORM models package.

Contains SQLAlchemy declarative models that describe database tables
only. These are intentionally kept separate from the business Pydantic
models in ``app.models``: ORM models here describe *how data is stored*,
while ``app.models`` describes *what the data means* to the application.
Neither package imports the other.
"""
