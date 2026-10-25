"""
Platform domain service layer.

Business logic for Season lifecycle management
and centralized audit event recording.
"""

from uuid import UUID, uuid4
from datetime import datetime, date
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.platform.models import Season, AuditEvent
from app.domain.platform.repository import SeasonRepository, AuditEventRepository
from app.domain.platform.schemas import (
    SeasonCreateRequest, SeasonUpdateRequest, SeasonStatusUpdateRequest,
)
from app.core.exceptions import (
    NotFoundError, ValidationError, ConflictError, SeasonNotActiveError,
)


class SeasonService:
    """
    Manages Season lifecycle.

    Only one season can be ACTIVE at a time.
    Status transitions: PLANNING -> ACTIVE -> ARCHIVED.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SeasonRepository(session)

    async def create_season(self, request: SeasonCreateRequest) -> Season:
        """Create a new Yatra season."""
        # Validate dates
        if request.end_date <= request.start_date:
            raise ValidationError(
                "end_date must be after start_date",
                error_code="INVALID_DATE_RANGE",
            )

        season = Season(
            id=uuid4().bytes,
            name=request.name,
            start_date=request.start_date,
            end_date=request.end_date,
            description=request.description,
            status="PLANNING",
        )
        return await self.repo.create(season)

    async def get_season(self, season_id: UUID) -> Season:
        """Get a season by ID."""
        season = await self.repo.get_by_id(season_id)
        if not season:
            raise NotFoundError(f"Season {season_id} not found")
        return season

    async def get_active_season(self) -> Season:
        """Get the currently active season. Raises if none active."""
        season = await self.repo.get_active()
        if not season:
            raise SeasonNotActiveError("No active season. Please activate a season first.")
        return season

    async def list_seasons(
        self, page: int = 1, page_size: int = 20, status: Optional[str] = None
    ) -> Tuple[List[Season], int]:
        """List all seasons with optional status filter."""
        return await self.repo.list_all(page, page_size, status)

    async def update_season(self, season_id: UUID, request: SeasonUpdateRequest) -> Season:
        """Update season metadata."""
        season = await self.get_season(season_id)

        if request.name is not None:
            season.name = request.name
        if request.start_date is not None:
            season.start_date = request.start_date
        if request.end_date is not None:
            season.end_date = request.end_date
        if request.description is not None:
            season.description = request.description

        # Re-validate dates
        if season.end_date <= season.start_date:
            raise ValidationError("end_date must be after start_date")

        season.updated_at = datetime.utcnow()
        return await self.repo.update(season)

    async def update_status(
        self, season_id: UUID, request: SeasonStatusUpdateRequest
    ) -> Season:
        """Change season status with validation."""
        season = await self.get_season(season_id)
        new_status = request.status.value

        # Validate transitions
        valid_transitions = {
            "PLANNING": ["ACTIVE", "ARCHIVED"],
            "ACTIVE": ["ARCHIVED"],
            "ARCHIVED": [],  # Terminal state
        }

        if new_status not in valid_transitions.get(season.status, []):
            raise ValidationError(
                f"Cannot transition from {season.status} to {new_status}",
                error_code="INVALID_STATUS_TRANSITION",
            )

        # If activating, ensure no other season is ACTIVE
        if new_status == "ACTIVE":
            current_active = await self.repo.get_active()
            if current_active and current_active.id != season.id:
                raise ConflictError(
                    f"Another season ({current_active.name}) is already ACTIVE. "
                    f"Archive it before activating this one.",
                    error_code="ANOTHER_SEASON_ACTIVE",
                )

        season.status = new_status
        season.updated_at = datetime.utcnow()
        return await self.repo.update(season)

    async def get_season_for_today(self) -> Optional[Season]:
        """Get the season that contains today's date."""
        return await self.repo.get_season_for_date(datetime.utcnow())


class AuditService:
    """
    Centralized audit logging service.

    Used by all other services to record state-changing operations.
    Provides an immutable compliance ledger for government audit.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AuditEventRepository(session)

    async def log_event(
        self,
        season_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[UUID] = None,
        actor_role: Optional[str] = None,
        source: str = "API",
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """
        Record an immutable audit event.

        Args:
            season_id: Season scope
            aggregate_type: Domain aggregate (pilgrim, journey, group, etc.)
            aggregate_id: Entity ID this event pertains to
            event_type: Specific event (PILGRIM_REGISTERED, SOS_RAISED, etc.)
            payload: Full event data as JSON
            actor_id: User who performed the action (None for system)
            actor_role: Role of the actor
            source: Source system (API, PORTAL, SYSTEM, BULK_IMPORT)
            ip_address: Client IP for security auditing
        """
        event = AuditEvent(
            id=uuid4().bytes,
            season_id=season_id.bytes,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id.bytes,
            event_type=event_type,
            actor_id=actor_id.bytes if actor_id else None,
            actor_role=actor_role,
            payload=payload,
            source=source,
            ip_address=ip_address,
            occurred_at=datetime.utcnow(),
        )
        return await self.repo.create(event)

    async def get_entity_audit_trail(
        self, aggregate_id: UUID, page: int = 1, page_size: int = 50
    ) -> Tuple[List[AuditEvent], int]:
        """Get the complete audit trail for an entity."""
        return await self.repo.get_by_aggregate(aggregate_id, page, page_size)

    async def search_audit_events(
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
        """Search audit events with filters."""
        return await self.repo.search(
            season_id=season_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            actor_id=actor_id,
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
        )