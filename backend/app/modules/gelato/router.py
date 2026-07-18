# ABOUTME: GELATO (Warehouse Management) API router — bins & directed putaway.
# ABOUTME: Minimal stub for Phase 12a task 1 so the gelato package imports
# ABOUTME: cleanly (mousse-style __init__ imports this router at package load).
# ABOUTME: The real RBAC-gated routes land in task 8, which replaces this stub.
"""
GELATO API router — stub (Phase 12a task 1).

Carries no routes yet: task 8 replaces this file with the real bin CRUD and
putaway endpoints. Present now only so app.modules.gelato imports cleanly.
"""
from fastapi import APIRouter

router = APIRouter()
