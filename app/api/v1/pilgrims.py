"""
Pilgrim API endpoints.

Multi-step registration, profile queries, status management, and QR lifecycle.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_season, require_permissions
from app.domain.identity.service import PilgrimService
from app.domain.identity.schemas import (
    PilgrimInitiateRequest, PilgrimInitiateResponse,
    PilgrimProfileRequest, PilgrimMedicalRequest,
    PilgrimRouteSelectionRequest, PilgrimCompleteRegistrationRequest,
    PilgrimResponse, PilgrimSummaryResponse, PilgrimListResponse,
    PilgrimSearchRequest, PilgrimStatusUpdateRequest,
    PilgrimQRRevokeRequest, PilgrimBulkRegisterRequest,
    PilgrimBulkRegisterResponse,
)

router = APIRouter(prefix="/pilgrims", tags=["Pilgrims"])


# ──────────────────────────────────────────────
# Multi-Step Self Registration
# ──────────────────────────────────────────────

@router.post("/initiate", response_model=PilgrimInitiateResponse, status_code=201)
async def initiate_registration(
    request: PilgrimInitiateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Step 1: Initiate registration with phone number."""
    service = PilgrimService(db)
    pilgrim = await service.initiate_registration(request)
    return PilgrimInitiateResponse(
        pilgrim_id=UUID(bytes=pilgrim.id),
        message="OTP sent to phone number",
    )


@router.put("/{pilgrim_id}/profile", response_model=PilgrimResponse)
async def complete_profile(
    pilgrim_id: UUID,
    request: PilgrimProfileRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Step 2: Add personal and emergency contact details."""
    service = PilgrimService(db)
    pilgrim = await service.complete_profile(pilgrim_id, request)
    return _pilgrim_to_response(pilgrim)


@router.put("/{pilgrim_id}/medical", response_model=PilgrimResponse)
async def complete_medical(
    pilgrim_id: UUID,
    request: PilgrimMedicalRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Step 3: Add medical information."""
    service = PilgrimService(db)
    pilgrim = await service.complete_medical(pilgrim_id, request)
    return _pilgrim_to_response(pilgrim)


@router.put("/{pilgrim_id}/route", response_model=PilgrimResponse)
async def select_route(
    pilgrim_id: UUID,
    request: PilgrimRouteSelectionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Step 4: Select journey route and activate pilgrim."""
    service = PilgrimService(db)
    pilgrim = await service.select_route(pilgrim_id, request)
    return _pilgrim_to_response(pilgrim)


# ──────────────────────────────────────────────
# Single-Step Counter Registration
# ──────────────────────────────────────────────

@router.post("/register", response_model=PilgrimResponse, status_code=201)
async def complete_registration(
    request: PilgrimCompleteRegistrationRequest,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Single-step registration for counter-assisted flow."""
    service = PilgrimService(db)
    pilgrim = await service.complete_registration(request, season_id)
    return _pilgrim_to_response(pilgrim)


# ──────────────────────────────────────────────
# Bulk Registration
# ──────────────────────────────────────────────

@router.post("/bulk-register", response_model=PilgrimBulkRegisterResponse, status_code=201, dependencies=[Depends(require_permissions("pilgrim:write"))])
async def bulk_register(
    request: PilgrimBulkRegisterRequest,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Register multiple pilgrims at once (max 100)."""
    service = PilgrimService(db)
    results = PilgrimBulkRegisterResponse(success_count=0, failure_count=0, errors=[], pilgrim_ids=[])

    for pilgrim_data in request.pilgrims:
        try:
            pilgrim = await service.complete_registration(pilgrim_data, season_id)
            results.success_count += 1
            results.pilgrim_ids.append(UUID(bytes=pilgrim.id))
        except Exception as e:
            results.failure_count += 1
            results.errors.append({
                "phone": pilgrim_data.phone,
                "error": str(e),
            })

    return results


# ──────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────

@router.get("/{pilgrim_id}", response_model=PilgrimResponse)
async def get_pilgrim(
    pilgrim_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get pilgrim by ID."""
    service = PilgrimService(db)
    pilgrim = await service.get_pilgrim(pilgrim_id)
    return _pilgrim_to_response(pilgrim)


@router.get("", response_model=PilgrimListResponse, dependencies=[Depends(require_permissions("pilgrim:read"))])
async def list_pilgrims(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    group_id: Optional[UUID] = None,
    route_id: Optional[UUID] = None,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """List pilgrims with filters and pagination."""
    service = PilgrimService(db)
    items, total = await service.list_pilgrims(
        season_id, page, page_size, status, group_id, route_id
    )
    return PilgrimListResponse(
        items=[_pilgrim_to_response(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/search/by-name", response_model=PilgrimListResponse, dependencies=[Depends(require_permissions("pilgrim:read"))])
async def search_pilgrims_by_name(
    name: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Search pilgrims by name (fuzzy match)."""
    service = PilgrimService(db)
    items = await service.search_pilgrims_by_name(season_id, name, limit)
    return PilgrimListResponse(
        items=[_pilgrim_to_response(p) for p in items],
        total=len(items),
        page=1,
        page_size=len(items),
    )


# ──────────────────────────────────────────────
# Status Management
# ──────────────────────────────────────────────

@router.put("/{pilgrim_id}/status", response_model=PilgrimResponse, dependencies=[Depends(require_permissions("pilgrim:write"))])
async def update_pilgrim_status(
    pilgrim_id: UUID,
    request: PilgrimStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Update pilgrim status."""
    service = PilgrimService(db)
    pilgrim = await service.update_status(pilgrim_id, request)
    return _pilgrim_to_response(pilgrim)


@router.put("/{pilgrim_id}/revoke-qr", response_model=PilgrimResponse, dependencies=[Depends(require_permissions("pilgrim:write"))])
async def revoke_qr(
    pilgrim_id: UUID,
    request: PilgrimQRRevokeRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke pilgrim's QR code."""
    service = PilgrimService(db)
    pilgrim = await service.revoke_qr(pilgrim_id, request)
    return _pilgrim_to_response(pilgrim)


# ──────────────────────────────────────────────
# Response Builder
# ──────────────────────────────────────────────

def _pilgrim_to_response(pilgrim) -> PilgrimResponse:
    """Convert Pilgrim model to response schema."""
    return PilgrimResponse(
        id=UUID(bytes=pilgrim.id),
        season_id=UUID(bytes=pilgrim.season_id) if pilgrim.season_id else None,
        full_name=pilgrim.full_name,
        phone=pilgrim.phone,
        age=pilgrim.age,
        gender=pilgrim.gender,
        blood_group=pilgrim.blood_group,
        medical_flags=pilgrim.medical_flags,
        allergies=pilgrim.allergies,
        current_medications=pilgrim.current_medications,
        emergency_contact_name=pilgrim.emergency_contact_name,
        emergency_contact_phone=pilgrim.emergency_contact_phone,
        emergency_contact_relation=pilgrim.emergency_contact_relation,
        photo_url=pilgrim.photo_url,
        status=pilgrim.status,
        route_id=UUID(bytes=pilgrim.route_id) if pilgrim.route_id else None,
        group_id=UUID(bytes=pilgrim.group_id) if pilgrim.group_id else None,
        registration_channel=pilgrim.registration_channel,
        qr_version=pilgrim.qr_version,
        qr_issued_at=pilgrim.qr_issued_at,
        qr_expires_at=pilgrim.qr_expires_at,
        created_at=pilgrim.created_at,
        updated_at=pilgrim.updated_at,
    )