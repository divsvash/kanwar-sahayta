"""
Journey API endpoints.

Read-only journey queries. Journeys are managed by the system
as projections from PresenceEvents.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_season
from app.domain.journey.service import JourneyService
from app.domain.journey.schemas import (
    JourneyResponse, JourneyDetailResponse, JourneyListResponse,
    JourneyGapAlertResponse,
)
from app.domain.journey.repository import JourneyRepository, PresenceEventRepository

router = APIRouter(prefix="/journeys", tags=["Journeys"])


@router.get("/pilgrim/{pilgrim_id}", response_model=JourneyResponse)
async def get_pilgrim_journey(
    pilgrim_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get the journey for a specific pilgrim."""
    service = JourneyService(db)
    journey = await service.get_pilgrim_journey(pilgrim_id)
    return _journey_to_response(journey)


@router.get("/{journey_id}", response_model=JourneyDetailResponse)
async def get_journey(
    journey_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get journey by ID with recent presence events."""
    service = JourneyService(db)
    journey = await service.get_journey(journey_id)
    presence_repo = PresenceEventRepository(db)
    events, _ = await presence_repo.get_by_pilgrim(
        UUID(bytes=journey.pilgrim_id), page=1, page_size=10
    )

    from app.domain.journey.schemas import PresenceEventResponse
    return JourneyDetailResponse(
        id=UUID(bytes=journey.id),
        pilgrim_id=UUID(bytes=journey.pilgrim_id),
        pilgrim_name=journey.pilgrim.full_name if journey.pilgrim else None,
        route_id=UUID(bytes=journey.route_id),
        route_name=journey.route.name if journey.route else None,
        status=journey.status,
        started_at=journey.started_at,
        completed_at=journey.completed_at,
        last_checkpoint_id=UUID(bytes=journey.last_checkpoint_id) if journey.last_checkpoint_id else None,
        last_checkpoint_name=journey.last_checkpoint.name if journey.last_checkpoint else None,
        last_observed_at=journey.last_observed_at,
        next_expected_checkpoint_id=UUID(bytes=journey.next_expected_checkpoint_id) if journey.next_expected_checkpoint_id else None,
        next_expected_checkpoint_name=journey.next_checkpoint.name if journey.next_checkpoint else None,
        next_expected_arrival_at=journey.next_expected_arrival_at,
        hours_since_last_seen=journey.hours_since_last_seen,
        expected_checkins_missed=journey.expected_checkins_missed,
        total_distance_covered_km=journey.total_distance_covered_km,
        total_checkins=journey.total_checkins,
        current_segment_index=journey.current_segment_index,
        created_at=journey.created_at,
        updated_at=journey.updated_at,
        recent_presence=[
            PresenceEventResponse(
                id=UUID(bytes=e.id),
                pilgrim_id=UUID(bytes=e.pilgrim_id),
                checkpoint_id=UUID(bytes=e.checkpoint_id),
                scanned_at=e.scanned_at,
                synced_at=e.synced_at,
                direction=e.direction,
                scan_result=e.scan_result,
                missing_person_match=e.missing_person_match,
                notes=e.notes,
            )
            for e in events
        ],
    )


@router.get("", response_model=JourneyListResponse)
async def list_journeys(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str = Query(None),
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """List journeys with filters."""
    repo = JourneyRepository(db)
    items, total = await repo.list_by_status(season_id, status, page, page_size)
    return JourneyListResponse(
        items=[_journey_to_response(j) for j in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/alerts/miss-risk", response_model=list[JourneyGapAlertResponse])
async def get_miss_risk_alerts(
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """Get all journeys with MISS_RISK status."""
    service = JourneyService(db)
    journeys = await service.list_miss_risk_journeys(season_id)
    return [
        JourneyGapAlertResponse(
            journey_id=UUID(bytes=j.id),
            pilgrim_id=UUID(bytes=j.pilgrim_id),
            pilgrim_name=j.pilgrim.full_name if j.pilgrim else "Unknown",
            last_seen_at=j.last_observed_at,
            last_seen_location=j.last_checkpoint.name if j.last_checkpoint else None,
            hours_missing=j.hours_since_last_seen or 0,
            expected_next_checkpoint=j.next_checkpoint.name if j.next_checkpoint else None,
            route_name=j.route.name if j.route else None,
        )
        for j in journeys
    ]


def _journey_to_response(journey) -> JourneyResponse:
    return JourneyResponse(
        id=UUID(bytes=journey.id),
        pilgrim_id=UUID(bytes=journey.pilgrim_id),
        pilgrim_name=journey.pilgrim.full_name if journey.pilgrim else None,
        route_id=UUID(bytes=journey.route_id),
        route_name=journey.route.name if journey.route else None,
        status=journey.status,
        started_at=journey.started_at,
        completed_at=journey.completed_at,
        last_checkpoint_id=UUID(bytes=journey.last_checkpoint_id) if journey.last_checkpoint_id else None,
        last_checkpoint_name=journey.last_checkpoint.name if journey.last_checkpoint else None,
        last_observed_at=journey.last_observed_at,
        next_expected_checkpoint_id=UUID(bytes=journey.next_expected_checkpoint_id) if journey.next_expected_checkpoint_id else None,
        next_expected_checkpoint_name=journey.next_checkpoint.name if journey.next_checkpoint else None,
        next_expected_arrival_at=journey.next_expected_arrival_at,
        hours_since_last_seen=journey.hours_since_last_seen,
        expected_checkins_missed=journey.expected_checkins_missed,
        total_distance_covered_km=journey.total_distance_covered_km,
        total_checkins=journey.total_checkins,
        current_segment_index=journey.current_segment_index,
        created_at=journey.created_at,
        updated_at=journey.updated_at,
    )