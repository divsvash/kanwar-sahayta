"""
Aggregated v1 API router.

Includes all domain-specific routers for the Kanwar Sahayata API.
"""

from fastapi import APIRouter
from app.api.v1 import platform, pilgrims, groups, users, routes, checkpoints, journeys, presence, safety

router = APIRouter(prefix="/api/v1")

# Platform
router.include_router(platform.router, tags=["Platform"])

# Identity
router.include_router(pilgrims.router, tags=["Pilgrims"])
router.include_router(groups.router, tags=["Groups"])
router.include_router(users.router, tags=["Users"])

# Journey
router.include_router(routes.router, tags=["Routes"])
router.include_router(checkpoints.router, tags=["Checkpoints"])
router.include_router(journeys.router, tags=["Journeys"])
router.include_router(presence.router, tags=["Presence"])

# Safety (SOS emergencies, medical incidents)
router.include_router(safety.router, tags=["Safety"])