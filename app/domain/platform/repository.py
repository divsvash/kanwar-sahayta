"""
Platform domain repository.

Data access layer for Season and AuditEvent entities.
All queries are season-scoped where applicable.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from app.domain.platform.models import Season, AuditEvent


class SeasonRepository:
    """Data access for Season aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, season: Season) -> Season:
        """Persist a new season."""
        self.session.add(season)
        await self.session.flush()
        return season

    async def get_by_id(self, season_id: UUID) -> Optional[Season]:
        """Get season by ID."""
        result = await self.session.execute(
            select(Season).where(Season.id == season_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_active(self) -> Optional[Season]:
        """Get the currently active season (should be exactly one during Yatra)."""
        result = await self.session.execute(
            select(Season).where(Season.status == "ACTIVE")
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> Tuple[List[Season], int]:
        """List seasons with optional status filter."""
        query = select(Season)
        count_query = select(func.count(Season.id))

        if status:
            query = query.where(Season.status == status)
            count_query = count_query.where(Season.status == status)

        query = query.order_by(desc(Season.start_date))
        total = (await self.session.execute(count_query)).scalar()

        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def update(self, season: Season) -> Season:
        """Update an existing season."""
        await self.session.flush()
        return season

    async def get_season_for_date(self, check_date: datetime) -> Optional[Season]:
        """Find the season that contains a given date."""
        result = await self.session.execute(
            select(Season).where(
                and_(
                    Season.start_date <= check_date.date(),
                    Season.end_date >= check_date.date(),
                )
            )
        )
        return result.scalar_one_or_none()


class AuditEventRepository:
    """Append-only data access for AuditEvent ledger."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: AuditEvent) -> AuditEvent:
        """Append a new audit event (immutable)."""
        self.session.add(event)
        await self.session.flush()
        return event

    async def bulk_create(self, events: List[AuditEvent]) -> List[AuditEvent]:
        """Append multiple audit events in a single transaction."""
        self.session.add_all(events)
        await self.session.flush()
        return events

    async def get_by_aggregate(
        self,
        aggregate_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AuditEvent], int]:
        """Get all audit events for a specific entity."""
        query = (
            select(AuditEvent)
            .where(AuditEvent.aggregate_id == aggregate_id.bytes)
            .order_by(desc(AuditEvent.occurred_at))
        )
        count_query = (
            select(func.count(AuditEvent.id))
            .where(AuditEvent.aggregate_id == aggregate_id.bytes)
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def search(
        self,
        season_id: Optional[UUID] = None,
        aggregate_type: Optional[str] = None,
        aggregate_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        actor_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[AuditEvent], int]:
        """Search audit events with multiple filters."""
        query = select(AuditEvent)
        count_query = select(func.count(AuditEvent.id))
        conditions = []

        if season_id:
            conditions.append(AuditEvent.season_id == season_id.bytes)
        if aggregate_type:
            conditions.append(AuditEvent.aggregate_type == aggregate_type)
        if aggregate_id:
            conditions.append(AuditEvent.aggregate_id == aggregate_id.bytes)
        if event_type:
            conditions.append(AuditEvent.event_type == event_type)
        if actor_id:
            conditions.append(AuditEvent.actor_id == actor_id.bytes)
        if from_date:
            conditions.append(AuditEvent.occurred_at >= from_date)
        if to_date:
            conditions.append(AuditEvent.occurred_at <= to_date)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        query = query.order_by(desc(AuditEvent.occurred_at))
        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total