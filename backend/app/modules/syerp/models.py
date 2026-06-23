"""
SYERP module models.

Phase 1: Module-marker stub only. No concrete tables are defined here.
Real Vendor, Customer, and GL tables are added in Phase 4 (SYERP Core Hub).

Every model added here MUST inherit from Base so that Base.metadata is
populated when app.core.models (the central aggregator) is imported by
Alembic's env.py.
"""
from app.core.base import Base  # noqa: F401

# Phase 4+ tables go here, e.g.:
#
# from sqlalchemy import String
# from sqlalchemy.orm import Mapped, mapped_column
#
# class Vendor(Base):
#     __tablename__ = "syerp_vendor"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     name: Mapped[str] = mapped_column(String(255), nullable=False)
#
# class Customer(Base):
#     __tablename__ = "syerp_customer"
#     id: Mapped[int] = mapped_column(primary_key=True)
#     name: Mapped[str] = mapped_column(String(255), nullable=False)
