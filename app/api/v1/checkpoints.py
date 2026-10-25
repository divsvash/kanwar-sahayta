"""
Checkpoint API endpoints.

Checkpoint CRUD with spatial location support.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.domain.journey.service import CheckpointService
from app.domain.journey.schemas import (
    CheckpointCreateRequest, CheckpointUpdateRequest,
    CheckpointResponse, CheckpointListResponse,
)

router = APIRouter(prefix="/checkpoints", tags=["Checkpoints"])


@router.post("", response_model=CheckpointResponse, status_code=201, dependencies=[Depends(require_permissions("route:write"))])
async def create_checkpoint(
    request: CheckpointCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new checkpoint."""
    service = CheckpointService(db)
    checkpoint = await service.create_checkpoint(request)
    return _checkpoint_to_response(checkpoint)


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint(
    checkpoint_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get checkpoint by ID."""
    service = CheckpointService(db)
    checkpoint = await service.get_checkpoint(checkpoint_id)
    return _checkpoint_to_response(checkpoint)


@router.get("", response_model=CheckpointListResponse)
async def list_checkpoints(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    checkpoint_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List checkpoints with filters."""
    service = CheckpointService(db)
    items, total = await service.list_checkpoints(page, page_size, checkpoint_type, status)
    return CheckpointListResponse(
        items=[_checkpoint_to_response(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{checkpoint_id}", response_model=CheckpointResponse, dependencies=[Depends(require_permissions("route:write"))])
async def update_checkpoint(
    checkpoint_id: UUID,
    request: CheckpointUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Update checkpoint details."""
    service = CheckpointService(db)
    checkpoint = await service.update_checkpoint(checkpoint_id, request)
    return _checkpoint_to_response(checkpoint)


@router.get("/nearest", response_model=list[CheckpointResponse])
async def find_nearest_checkpoints(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db_session),
):
    """Find nearest checkpoints to a GPS location."""
    service = CheckpointService(db)
    checkpoints = await service.find_nearest(latitude, longitude, limit)
    return [_checkpoint_to_response(c) for c in checkpoints]


def _checkpoint_to_response(checkpoint) -> CheckpointResponse:
    """Extract lat/lng from POINT WKT."""
    latitude = None
    longitude = None
    if checkpoint.location:
        try:
            wkt = str(checkpoint.location)
            coords = wkt.replace("POINT(", "").replace(")", "").split()
            longitude = float(coords[0])
            latitude = float(coords[1])
        except (IndexError, ValueError):
            pass

    return CheckpointResponse(
        id=UUID(bytes=checkpoint.id),
        camp_id=UUID(bytes=checkpoint.camp_id) if checkpoint.camp_id else None,
        name=checkpoint.name,
        latitude=latitude,
        longitude=longitude,
        direction=checkpoint.direction,
        checkpoint_type=checkpoint.checkpoint_type,
        status=checkpoint.status,
        district=checkpoint.district,
        created_at=checkpoint.created_at,
        updated_at=checkpoint.updated_at,
    )