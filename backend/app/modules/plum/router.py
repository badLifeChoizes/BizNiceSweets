"""
PLUM module router — placeholder.

This file is a minimal stub so that backend/app/modules/plum/__init__.py can
import the router and the package initializes cleanly before Plan 05-02
implements the full service + endpoints.

Plan 05-02 will replace this stub with the real PLUM API endpoints:
  GET  /plum/parts
  POST /plum/parts
  GET  /plum/parts/{id}
  PATCH /plum/parts/{id}
  POST /plum/parts/{id}/revisions
  POST /plum/parts/{id}/revisions/{rev_id}/advance
"""
from fastapi import APIRouter

router = APIRouter(prefix="/plum", tags=["plum"])
