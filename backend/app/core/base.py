"""
Shared SQLAlchemy 2.0 DeclarativeBase for all module models.

Every module model must inherit from Base so that Base.metadata is
fully populated when Alembic's env.py calls autogenerate.

SQLAlchemy 2.0 style: class Base(DeclarativeBase) — NOT the legacy
declarative_base() function which loses Mapped[] annotation support.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
