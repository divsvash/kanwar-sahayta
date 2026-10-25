"""
Platform API endpoints.

Season CRUD and system health check.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_active_user
from app.domain.platform.service import SeasonService
from app.domain.platform.schemas import (
    SeasonCreateRequest, SeasonUpdateRequest, SeasonStatusUpdateRequest,
    SeasonResponse, SeasonListResponse, ActiveSeasonResponse,
)
from app.core.exceptions import NotFoundError

router = APIRouter()


# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "Kanwar Sahayata",
        "version": "1.0.0",
    }


# ──────────────────────────────────────────────
# Season Endpoints
# ──────────────────────────────────────────────

@router.post("/seasons", response_model=SeasonResponse, status_code=201)
async def create_season(
    request: SeasonCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new Yatra season."""
    service = SeasonService(db)
    season = await service.create_season(request)
    return SeasonResponse(
        id=UUID(bytes=season.id),
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        status=season.status,
        description=season.description,
        created_at=season.created_at,
        updated_at=season.updated_at,
    )


@router.get("/seasons/active", response_model=ActiveSeasonResponse)
async def get_active_season(
    db: AsyncSession = Depends(get_db_session),
):
    """Get the currently active season."""
    from datetime import date
    service = SeasonService(db)
    try:
        season = await service.get_active_season()
        days_remaining = (season.end_date - date.today()).days
        return ActiveSeasonResponse(
            id=UUID(bytes=season.id),
            name=season.name,
            start_date=season.start_date,
            end_date=season.end_date,
            status=season.status,
            days_remaining=max(0, days_remaining),
        )
    except Exception:
        return ActiveSeasonResponse(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            name="No active season",
            start_date=date.today(),
            end_date=date.today(),
            status="NONE",
            days_remaining=0,
        )


@router.get("/seasons", response_model=SeasonListResponse)
async def list_seasons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List all seasons with pagination."""
    service = SeasonService(db)
    items, total = await service.list_seasons(page, page_size, status)
    return SeasonListResponse(
        items=[
            SeasonResponse(
                id=UUID(bytes=s.id),
                name=s.name,
                start_date=s.start_date,
                end_date=s.end_date,
                status=s.status,
                description=s.description,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/seasons/{season_id}", response_model=SeasonResponse)
async def get_season(
    season_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get a season by ID."""
    service = SeasonService(db)
    season = await service.get_season(season_id)
    return SeasonResponse(
        id=UUID(bytes=season.id),
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        status=season.status,
        description=season.description,
        created_at=season.created_at,
        updated_at=season.updated_at,
    )


@router.put("/seasons/{season_id}", response_model=SeasonResponse)
async def update_season(
    season_id: UUID,
    request: SeasonUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Update season metadata."""
    service = SeasonService(db)
    season = await service.update_season(season_id, request)
    return SeasonResponse(
        id=UUID(bytes=season.id),
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        status=season.status,
        description=season.description,
        created_at=season.created_at,
        updated_at=season.updated_at,
    )


@router.put("/seasons/{season_id}/status", response_model=SeasonResponse)
async def update_season_status(
    season_id: UUID,
    request: SeasonStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Activate or archive a season."""
    service = SeasonService(db)
    season = await service.update_status(season_id, request)
    return SeasonResponse(
        id=UUID(bytes=season.id),
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        status=season.status,
        description=season.description,
        created_at=season.created_at,
        updated_at=season.updated_at,
    )