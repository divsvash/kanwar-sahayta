"""
Route API endpoints.

Route CRUD and segment management.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_season, require_permissions
from app.domain.journey.service import RouteService
from app.domain.journey.repository import RouteSegmentRepository
from app.domain.journey.schemas import (
    RouteCreateRequest, RouteUpdateRequest,
    RouteResponse, RouteDetailResponse, RouteListResponse,
    RouteSegmentCreateRequest, RouteSegmentResponse,
)

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.post("", response_model=RouteResponse, status_code=201, dependencies=[Depends(require_permissions("route:write"))])
async def create_route(
    request: RouteCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new pilgrimage route."""
    service = RouteService(db)
    route = await service.create_route(request)
    return _route_to_response(route, 0)


@router.get("/{route_id}", response_model=RouteDetailResponse)
async def get_route(
    route_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get route with segments."""
    service = RouteService(db)
    route = await service.get_route(route_id)
    segments = await RouteSegmentRepository(db).get_by_route(route_id)
    return RouteDetailResponse(
        id=UUID(bytes=route.id),
        season_id=UUID(bytes=route.season_id),
        name=route.name,
        description=route.description,
        status=route.status,
        total_distance_km=route.total_distance_km,
        estimated_hours=route.estimated_hours,
        segment_count=len(segments),
        created_at=route.created_at,
        updated_at=route.updated_at,
        segments=[
            RouteSegmentResponse(
                id=UUID(bytes=s.id),
                route_id=UUID(bytes=s.route_id),
                sequence_order=s.sequence_order,
                start_checkpoint_id=UUID(bytes=s.start_checkpoint_id),
                start_checkpoint_name=s.start_checkpoint.name if s.start_checkpoint else None,
                end_checkpoint_id=UUID(bytes=s.end_checkpoint_id),
                end_checkpoint_name=s.end_checkpoint.name if s.end_checkpoint else None,
                distance_km=s.distance_km,
                nominal_walking_hours=s.nominal_walking_hours,
                difficulty=s.difficulty,
                created_at=s.created_at,
            )
            for s in segments
        ],
    )


@router.get("", response_model=RouteListResponse)
async def list_routes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """List routes for the active season."""
    service = RouteService(db)
    items, total = await service.list_routes(season_id, page, page_size)
    return RouteListResponse(
        items=[_route_to_response(r, 0) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{route_id}", response_model=RouteResponse, dependencies=[Depends(require_permissions("route:write"))])
async def update_route(
    route_id: UUID,
    request: RouteUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Update route details."""
    service = RouteService(db)
    route = await service.update_route(route_id, request)
    return _route_to_response(route, 0)


@router.post("/{route_id}/segments", response_model=RouteSegmentResponse, status_code=201, dependencies=[Depends(require_permissions("route:write"))])
async def add_segment(
    route_id: UUID,
    request: RouteSegmentCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Add a segment to a route."""
    request.route_id = route_id
    service = RouteService(db)
    segment = await service.add_segment(request)
    return RouteSegmentResponse(
        id=UUID(bytes=segment.id),
        route_id=UUID(bytes=segment.route_id),
        sequence_order=segment.sequence_order,
        start_checkpoint_id=UUID(bytes=segment.start_checkpoint_id),
        end_checkpoint_id=UUID(bytes=segment.end_checkpoint_id),
        distance_km=segment.distance_km,
        nominal_walking_hours=segment.nominal_walking_hours,
        difficulty=segment.difficulty,
        created_at=segment.created_at,
    )


def _route_to_response(route, segment_count: int) -> RouteResponse:
    return RouteResponse(
        id=UUID(bytes=route.id),
        season_id=UUID(bytes=route.season_id),
        name=route.name,
        description=route.description,
        status=route.status,
        total_distance_km=route.total_distance_km,
        estimated_hours=route.estimated_hours,
        segment_count=segment_count,
        created_at=route.created_at,
        updated_at=route.updated_at,
    )