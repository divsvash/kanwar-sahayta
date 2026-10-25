"""
Presence Event API endpoints.

Live check-in recording and offline sync batch processing.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_season, require_permissions
from app.domain.journey.service import PresenceService
from app.domain.journey.schemas import (
    PresenceEventCreateRequest, PresenceEventResponse,
    PresenceEventListResponse, PilgrimPresenceHistoryResponse,
    OfflineSyncBatchRequest, OfflineSyncBatchResponse,
)

router = APIRouter(prefix="/presence", tags=["Presence"])


# ──────────────────────────────────────────────
# Online Check-In
# ──────────────────────────────────────────────

@router.post("", response_model=PresenceEventResponse, status_code=201, dependencies=[Depends(require_permissions("presence:write"))])
async def record_checkin(
    request: PresenceEventCreateRequest,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Record a live check-in or check-out event."""
    service = PresenceService(db)
    event = await service.record_checkin(request, season_id)
    return _presence_to_response(event)


# ──────────────────────────────────────────────
# Offline Sync
# ──────────────────────────────────────────────

@router.post("/sync", response_model=OfflineSyncBatchResponse, status_code=201)
async def sync_offline_batch(
    request: OfflineSyncBatchRequest,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Process a batch of offline presence events from a camp device."""
    service = PresenceService(db)
    results = await service.process_offline_batch(request, season_id)
    return OfflineSyncBatchResponse(
        batch_ref=UUID(results["batch_ref"]),
        status=results["status"],
        total_events=results["total_events"],
        processed_count=results["processed_count"],
        failed_count=results["failed_count"],
        failed_events=results["failed_events"],
        message=f"Processed {results['processed_count']}/{results['total_events']} events",
    )


# ──────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────

@router.get("/pilgrim/{pilgrim_id}", response_model=PilgrimPresenceHistoryResponse)
async def get_pilgrim_presence_history(
    pilgrim_id: UUID = Path(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    """Get presence event history for a pilgrim."""
    service = PresenceService(db)
    events, total = await service.get_pilgrim_history(pilgrim_id, page, page_size)
    return PilgrimPresenceHistoryResponse(
        pilgrim_id=pilgrim_id,
        pilgrim_name="",
        events=[_presence_to_response(e) for e in events],
        total_events=total,
    )


@router.get("/pilgrim/{pilgrim_id}/latest", response_model=PresenceEventResponse)
async def get_latest_presence(
    pilgrim_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the most recent presence event for a pilgrim."""
    service = PresenceService(db)
    event = await service.get_latest_presence(pilgrim_id)
    if not event:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"No presence events found for pilgrim {pilgrim_id}")
    return _presence_to_response(event)


# ──────────────────────────────────────────────
# Response Builder
# ──────────────────────────────────────────────

def _presence_to_response(event) -> PresenceEventResponse:
    """Convert PresenceEvent model to response schema."""
    return PresenceEventResponse(
        id=UUID(bytes=event.id),
        pilgrim_id=UUID(bytes=event.pilgrim_id),
        checkpoint_id=UUID(bytes=event.checkpoint_id),
        device_id=UUID(bytes=event.device_id) if event.device_id else None,
        operator_user_id=UUID(bytes=event.operator_user_id) if event.operator_user_id else None,
        scanned_at=event.scanned_at,
        synced_at=event.synced_at,
        direction=event.direction,
        scan_result=event.scan_result,
        missing_person_match=event.missing_person_match,
        notes=event.notes,
    )