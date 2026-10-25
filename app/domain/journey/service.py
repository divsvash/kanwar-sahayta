from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from app.domain.journey.models import PresenceEvent, Journey, Checkpoint
from app.domain.journey.schemas import PresenceEventCreateRequest as PresenceEventCreate
from app.core.exceptions import NotFoundError, ValidationError

class PresenceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_checkin(self, request: PresenceEventCreate, season_id: UUID) -> PresenceEvent:
        """Record a single check-in event. Immutable append-only."""
        # Validate checkpoint exists
        checkpoint = await self.session.execute(
            select(Checkpoint).where(Checkpoint.id == request.checkpoint_id.bytes)
        )
        if not checkpoint.scalar_one_or_none():
            raise NotFoundError(f"Checkpoint {request.checkpoint_id} not found")

        event = PresenceEvent(
            id=uuid4().bytes,
            season_id=season_id.bytes,
            pilgrim_id=request.pilgrim_id.bytes,
            checkpoint_id=request.checkpoint_id.bytes,
            device_id=request.device_id.bytes if request.device_id else None,
            operator_user_id=request.operator_user_id.bytes,
            scanned_at=datetime.utcnow(),
            synced_at=datetime.utcnow(),
            offline_mutation_id=uuid4().bytes,
            direction=request.direction.value,
            scan_result=request.scan_result,
            notes=request.notes
        )
        self.session.add(event)
        await self.session.flush()

        # Update journey projection
        await self._update_journey_projection(event)

        return event

    async def _update_journey_projection(self, event: PresenceEvent):
        """Update journey read-model after presence event."""
        journey_result = await self.session.execute(
            select(Journey).where(Journey.pilgrim_id == event.pilgrim_id)
        )
        journey = journey_result.scalar_one_or_none()

        if journey:
            journey.last_presence_event_id = event.id
            journey.last_checkpoint_id = event.checkpoint_id
            journey.last_known_location = (
                select(Checkpoint.location)
                .where(Checkpoint.id == event.checkpoint_id)
                .scalar_subquery()
            )
            if journey.status == "PLANNED":
                journey.status = "IN_PROGRESS"
                journey.started_at = event.scanned_at
            journey.updated_at = datetime.utcnow()

        await self.session.flush()

    async def get_pilgrim_presence_history(
        self, pilgrim_id: UUID, limit: int = 50
    ) -> List[PresenceEvent]:
        result = await self.session.execute(
            select(PresenceEvent)
            .where(PresenceEvent.pilgrim_id == pilgrim_id.bytes)
            .order_by(desc(PresenceEvent.scanned_at))
            .limit(limit)
        )
        return result.scalars().all()

# ──────────────────────────────────────────────
# Route, Checkpoint, Journey services
# (missing from the original repo; written to match
#  api/v1/routes.py, checkpoints.py, journeys.py)
# ──────────────────────────────────────────────

import math
from app.domain.journey.models import Route, RouteSegment
from app.domain.journey.repository import (
    RouteRepository, CheckpointRepository, RouteSegmentRepository, JourneyRepository,
)
from app.domain.journey.schemas import (
    RouteCreateRequest, RouteUpdateRequest, RouteSegmentCreateRequest,
    CheckpointCreateRequest, CheckpointUpdateRequest,
)
from app.core.exceptions import NotFoundError


class RouteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RouteRepository(session)
        self.segment_repo = RouteSegmentRepository(session)

    async def create_route(self, request: RouteCreateRequest) -> Route:
        route = Route(
            id=uuid4().bytes,
            season_id=request.season_id.bytes,
            name=request.name,
            description=request.description,
            status="ACTIVE",
        )
        return await self.repo.create(route)

    async def get_route(self, route_id: UUID) -> Route:
        route = await self.repo.get_by_id(route_id)
        if not route:
            raise NotFoundError(f"Route {route_id} not found")
        return route

    async def list_routes(self, season_id: UUID, page: int = 1, page_size: int = 20):
        return await self.repo.list_by_season(season_id, page, page_size)

    async def update_route(self, route_id: UUID, request: RouteUpdateRequest) -> Route:
        route = await self.get_route(route_id)
        for field in ("name", "description", "status", "total_distance_km", "estimated_hours"):
            value = getattr(request, field, None)
            if value is not None:
                setattr(route, field, value.value if hasattr(value, "value") else value)
        route.updated_at = datetime.utcnow()
        return await self.repo.update(route)

    async def add_segment(self, request: RouteSegmentCreateRequest) -> RouteSegment:
        segment = RouteSegment(
            id=uuid4().bytes,
            season_id=request.season_id.bytes,
            route_id=request.route_id.bytes,
            sequence_order=request.sequence_order,
            start_checkpoint_id=request.start_checkpoint_id.bytes,
            end_checkpoint_id=request.end_checkpoint_id.bytes,
            distance_km=request.distance_km,
            nominal_walking_hours=request.nominal_walking_hours,
            difficulty=request.difficulty.value if hasattr(request.difficulty, "value") else request.difficulty,
        )
        return await self.segment_repo.create(segment)


def _parse_wkt_point(wkt: str):
    coords = str(wkt).replace("POINT(", "").replace(")", "").split()
    return float(coords[0]), float(coords[1])  # lon, lat


class CheckpointService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CheckpointRepository(session)

    async def create_checkpoint(self, request: CheckpointCreateRequest) -> Checkpoint:
        checkpoint = Checkpoint(
            id=uuid4().bytes,
            camp_id=request.camp_id.bytes if request.camp_id else None,
            name=request.name,
            location=f"POINT({request.longitude} {request.latitude})",
            direction=request.direction.value if hasattr(request.direction, "value") else request.direction,
            checkpoint_type=request.checkpoint_type.value if hasattr(request.checkpoint_type, "value") else request.checkpoint_type,
            status="ACTIVE",
            district=request.district,
        )
        return await self.repo.create(checkpoint)

    async def get_checkpoint(self, checkpoint_id: UUID) -> Checkpoint:
        checkpoint = await self.repo.get_by_id(checkpoint_id)
        if not checkpoint:
            raise NotFoundError(f"Checkpoint {checkpoint_id} not found")
        return checkpoint

    async def list_checkpoints(self, page: int = 1, page_size: int = 50,
                               checkpoint_type: Optional[str] = None,
                               status: Optional[str] = None):
        return await self.repo.list_all(page, page_size, checkpoint_type, status)

    async def update_checkpoint(self, checkpoint_id: UUID, request: CheckpointUpdateRequest) -> Checkpoint:
        checkpoint = await self.get_checkpoint(checkpoint_id)
        for field in ("name", "direction", "checkpoint_type", "status", "district"):
            value = getattr(request, field, None)
            if value is not None:
                setattr(checkpoint, field, value.value if hasattr(value, "value") else value)
        lat = getattr(request, "latitude", None)
        lon = getattr(request, "longitude", None)
        if lat is not None and lon is not None:
            checkpoint.location = f"POINT({lon} {lat})"
        checkpoint.updated_at = datetime.utcnow()
        return await self.repo.update(checkpoint)

    async def find_nearest(self, latitude: float, longitude: float, limit: int = 5):
        """
        Nearest checkpoints. MySQL uses ST_Distance; the SQLite demo
        computes haversine distance in Python instead.
        """
        from app.core.database import IS_SQLITE
        if not IS_SQLITE:
            return await self.repo.get_nearest_checkpoints(latitude, longitude, limit)

        from sqlalchemy import select as _select
        result = await self.session.execute(
            _select(Checkpoint).where(Checkpoint.status == "ACTIVE")
        )
        all_checkpoints = result.scalars().all()

        def haversine_km(cp):
            try:
                lon2, lat2 = _parse_wkt_point(cp.location)
            except (IndexError, ValueError, TypeError):
                return float("inf")
            r = 6371.0
            p1, p2 = math.radians(latitude), math.radians(lat2)
            dp = math.radians(lat2 - latitude)
            dl = math.radians(lon2 - longitude)
            a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            return 2 * r * math.asin(math.sqrt(a))

        return sorted(all_checkpoints, key=haversine_km)[:limit]


class JourneyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JourneyRepository(session)

    async def get_pilgrim_journey(self, pilgrim_id: UUID) -> Journey:
        journey = await self.repo.get_by_pilgrim(pilgrim_id)
        if not journey:
            raise NotFoundError(f"No journey for pilgrim {pilgrim_id}")
        return journey

    async def get_journey(self, journey_id: UUID) -> Journey:
        journey = await self.repo.get_by_id(journey_id)
        if not journey:
            raise NotFoundError(f"Journey {journey_id} not found")
        return journey

    async def list_miss_risk_journeys(self, season_id: UUID):
        return await self.repo.get_miss_risk_journeys(season_id)
