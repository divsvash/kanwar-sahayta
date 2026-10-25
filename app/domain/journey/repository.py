"""
Journey domain repository.

Data access layer for Route, Checkpoint, Journey, and PresenceEvent entities.
Handles spatial queries and high-throughput presence event recording.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.orm import selectinload
from app.domain.journey.models import (
    Route, Checkpoint, RouteSegment, Journey, PresenceEvent
)


class RouteRepository:
    """Data access for Route aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, route: Route) -> Route:
        self.session.add(route)
        await self.session.flush()
        return route

    async def get_by_id(self, route_id: UUID) -> Optional[Route]:
        result = await self.session.execute(
            select(Route)
            .options(selectinload(Route.segments))
            .where(Route.id == route_id.bytes)
        )
        return result.scalar_one_or_none()

    async def list_by_season(
        self, season_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Route], int]:
        query = (
            select(Route)
            .where(Route.season_id == season_id.bytes)
            .order_by(Route.name)
        )
        count_query = (
            select(func.count(Route.id))
            .where(Route.season_id == season_id.bytes)
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def update(self, route: Route) -> Route:
        await self.session.flush()
        return route


class CheckpointRepository:
    """Data access for Checkpoint aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, checkpoint: Checkpoint) -> Checkpoint:
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def get_by_id(self, checkpoint_id: UUID) -> Optional[Checkpoint]:
        result = await self.session.execute(
            select(Checkpoint).where(Checkpoint.id == checkpoint_id.bytes)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 50,
        checkpoint_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[Checkpoint], int]:
        query = select(Checkpoint)
        count_query = select(func.count(Checkpoint.id))
        conditions = []

        if checkpoint_type:
            conditions.append(Checkpoint.checkpoint_type == checkpoint_type)
        if status:
            conditions.append(Checkpoint.status == status)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def get_nearest_checkpoints(
        self, latitude: float, longitude: float, limit: int = 5
    ) -> List[Checkpoint]:
        """Find nearest checkpoints to a GPS location using spatial index."""
        point_wkt = f"POINT({longitude} {latitude})"
        result = await self.session.execute(
            select(Checkpoint)
            .where(Checkpoint.status == "ACTIVE")
            .order_by(
                func.ST_Distance(
                    Checkpoint.location,
                    func.ST_GeomFromText(point_wkt, 4326)
                )
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def update(self, checkpoint: Checkpoint) -> Checkpoint:
        await self.session.flush()
        return checkpoint


class RouteSegmentRepository:
    """Data access for RouteSegment entity."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, segment: RouteSegment) -> RouteSegment:
        self.session.add(segment)
        await self.session.flush()
        return segment

    async def get_by_route(self, route_id: UUID) -> List[RouteSegment]:
        result = await self.session.execute(
            select(RouteSegment)
            .options(
                selectinload(RouteSegment.start_checkpoint),
                selectinload(RouteSegment.end_checkpoint),
            )
            .where(RouteSegment.route_id == route_id.bytes)
            .order_by(RouteSegment.sequence_order)
        )
        return result.scalars().all()

    async def get_by_id(self, segment_id: UUID) -> Optional[RouteSegment]:
        result = await self.session.execute(
            select(RouteSegment).where(RouteSegment.id == segment_id.bytes)
        )
        return result.scalar_one_or_none()


class JourneyRepository:
    """Data access for Journey projection."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, journey: Journey) -> Journey:
        self.session.add(journey)
        await self.session.flush()
        return journey

    async def get_by_pilgrim(self, pilgrim_id: UUID) -> Optional[Journey]:
        result = await self.session.execute(
            select(Journey)
            .options(
                selectinload(Journey.route),
                selectinload(Journey.last_checkpoint),
                selectinload(Journey.next_checkpoint),
            )
            .where(Journey.pilgrim_id == pilgrim_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, journey_id: UUID) -> Optional[Journey]:
        result = await self.session.execute(
            select(Journey)
            .options(
                selectinload(Journey.pilgrim),
                selectinload(Journey.route),
                selectinload(Journey.last_checkpoint),
            )
            .where(Journey.id == journey_id.bytes)
        )
        return result.scalar_one_or_none()

    async def list_by_status(
        self,
        season_id: UUID,
        status: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Journey], int]:
        query = (
            select(Journey)
            .options(selectinload(Journey.pilgrim))
            .where(
                and_(
                    Journey.pilgrim.has(season_id=season_id.bytes),
                    Journey.status == status,
                )
            )
            .order_by(Journey.last_observed_at.asc().nullsfirst())
        )
        count_query = (
            select(func.count(Journey.id))
            .where(
                and_(
                    Journey.pilgrim.has(season_id=season_id.bytes),
                    Journey.status == status,
                )
            )
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def get_miss_risk_journeys(
        self, season_id: UUID, hours_threshold: float = 36.0
    ) -> List[Journey]:
        """Get journeys with MISS_RISK status for gap detection."""
        result = await self.session.execute(
            select(Journey)
            .options(selectinload(Journey.pilgrim))
            .where(
                and_(
                    Journey.pilgrim.has(season_id=season_id.bytes),
                    Journey.status == "MISS_RISK",
                    Journey.hours_since_last_seen >= hours_threshold,
                )
            )
        )
        return result.scalars().all()

    async def update(self, journey: Journey) -> Journey:
        await self.session.flush()
        return journey


class PresenceEventRepository:
    """
    Data access for immutable PresenceEvent ledger.

    All operations are append-only. No update or delete methods.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: PresenceEvent) -> PresenceEvent:
        """Append a single presence event (immutable)."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def bulk_create(self, events: List[PresenceEvent]) -> List[PresenceEvent]:
        """Append multiple presence events (offline batch sync)."""
        self.session.add_all(events)
        await self.session.flush()
        return events

    async def get_by_id(self, event_id: UUID) -> Optional[PresenceEvent]:
        result = await self.session.execute(
            select(PresenceEvent).where(PresenceEvent.id == event_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_pilgrim(
        self, pilgrim_id: UUID, page: int = 1, page_size: int = 50
    ) -> Tuple[List[PresenceEvent], int]:
        """Get presence history for a pilgrim (most recent first)."""
        query = (
            select(PresenceEvent)
            .where(PresenceEvent.pilgrim_id == pilgrim_id.bytes)
            .order_by(desc(PresenceEvent.scanned_at))
        )
        count_query = (
            select(func.count(PresenceEvent.id))
            .where(PresenceEvent.pilgrim_id == pilgrim_id.bytes)
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def get_latest_for_pilgrim(
        self, pilgrim_id: UUID
    ) -> Optional[PresenceEvent]:
        """Get the most recent presence event for a pilgrim."""
        result = await self.session.execute(
            select(PresenceEvent)
            .where(PresenceEvent.pilgrim_id == pilgrim_id.bytes)
            .order_by(desc(PresenceEvent.scanned_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_offline_mutation_id(
        self, mutation_id: UUID
    ) -> Optional[PresenceEvent]:
        """Check if an offline event was already synced (idempotency)."""
        result = await self.session.execute(
            select(PresenceEvent).where(
                PresenceEvent.offline_mutation_id == mutation_id.bytes
            )
        )
        return result.scalar_one_or_none()

    async def count_by_checkpoint(
        self, checkpoint_id: UUID, since: Optional[datetime] = None
    ) -> int:
        """Count presence events at a checkpoint (for occupancy)."""
        query = select(func.count(PresenceEvent.id)).where(
            and_(
                PresenceEvent.checkpoint_id == checkpoint_id.bytes,
                PresenceEvent.direction == "CHECKIN",
            )
        )
        if since:
            query = query.where(PresenceEvent.scanned_at >= since)

        return (await self.session.execute(query)).scalar()

    async def get_by_checkpoint(
        self,
        checkpoint_id: UUID,
        page: int = 1,
        page_size: int = 50,
        since: Optional[datetime] = None,
    ) -> Tuple[List[PresenceEvent], int]:
        """Get recent presence events at a checkpoint."""
        query = (
            select(PresenceEvent)
            .where(PresenceEvent.checkpoint_id == checkpoint_id.bytes)
            .order_by(desc(PresenceEvent.scanned_at))
        )
        count_query = select(func.count(PresenceEvent.id)).where(
            PresenceEvent.checkpoint_id == checkpoint_id.bytes
        )

        if since:
            query = query.where(PresenceEvent.scanned_at >= since)
            count_query = count_query.where(PresenceEvent.scanned_at >= since)

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total