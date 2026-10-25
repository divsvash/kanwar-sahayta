"""
Platform domain Pydantic schemas.

Season lifecycle and health-check request/response models.
(The original repo shipped a byte-identical copy of the identity
schemas here; rewritten to match platform/service.py and
api/v1/platform.py.)
"""

from datetime import datetime, date
from uuid import UUID
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


class SeasonStatus(str, Enum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SeasonCreateRequest(BaseModel):
    """Create a new Yatra season (starts in PLANNING)."""
    name: str = Field(..., min_length=3, max_length=100)
    start_date: date
    end_date: date
    description: Optional[str] = Field(None, max_length=500)


class SeasonUpdateRequest(BaseModel):
    """Partial season metadata update."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=500)


class SeasonStatusUpdateRequest(BaseModel):
    """PLANNING -> ACTIVE -> ARCHIVED transitions only."""
    status: SeasonStatus


class SeasonResponse(BaseModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SeasonListResponse(BaseModel):
    items: List[SeasonResponse]
    total: int
    page: int
    page_size: int


class ActiveSeasonResponse(BaseModel):
    id: UUID
    name: str
    start_date: date
    end_date: date
    status: str
    days_remaining: int
