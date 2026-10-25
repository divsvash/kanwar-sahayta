"""
Journey domain Pydantic schemas.

Request/response validation for Route, Checkpoint, Journey,
and PresenceEvent operations.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class JourneyStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    MISS_RISK = "MISS_RISK"
    COMPLETED = "COMPLETED"


class PresenceDirection(str, Enum):
    CHECKIN = "CHECKIN"
    CHECKOUT = "CHECKOUT"
    AUTO_CHECKOUT = "AUTO_CHECKOUT"


class CheckpointDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"
    EN_ROUTE = "EN_ROUTE"


class CheckpointType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    REST_CAMP = "REST_CAMP"
    MEDICAL_CAMP = "MEDICAL_CAMP"
    TRANSIT_CAMP = "TRANSIT_CAMP"
    MILESTONE = "MILESTONE"
    POLICE_POST = "POLICE_POST"


class CheckpointStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    CLOSED = "CLOSED"


class RouteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SegmentDifficulty(str, Enum):
    EASY = "EASY"
    MODERATE = "MODERATE"
    DIFFICULT = "DIFFICULT"


class ScanResult(str, Enum):
    STANDARD_SUCCESS = "STANDARD_SUCCESS"
    MEDICAL_FLAG = "MEDICAL_FLAG"
    MISSING_PERSON_MATCH = "MISSING_PERSON_MATCH"
    REVOKED_QR = "REVOKED_QR"
    DUPLICATE_SCAN = "DUPLICATE_SCAN"
    UNKNOWN_QR = "UNKNOWN_QR"
    CAMP_FULL_WARNING = "CAMP_FULL_WARNING"


# ──────────────────────────────────────────────
# Checkpoint Schemas
# ──────────────────────────────────────────────

class CheckpointCreateRequest(BaseModel):
    """Create a new checkpoint."""
    camp_id: Optional[UUID] = Field(None, description="Associated camp ID")
    name: str = Field(..., min_length=2, max_length=150, description="Checkpoint name")
    latitude: float = Field(..., ge=-90, le=90, description="GPS latitude")
    longitude: float = Field(..., ge=-180, le=180, description="GPS longitude")
    direction: CheckpointDirection = Field(..., description="IN, OUT, or EN_ROUTE")
    checkpoint_type: CheckpointType = Field(..., description="Type of facility")
    district: Optional[str] = Field(None, max_length=100, description="Administrative district")


class CheckpointUpdateRequest(BaseModel):
    """Update an existing checkpoint."""
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    direction: Optional[CheckpointDirection] = None
    checkpoint_type: Optional[CheckpointType] = None
    status: Optional[CheckpointStatus] = None
    district: Optional[str] = Field(None, max_length=100)


class CheckpointResponse(BaseModel):
    """Checkpoint details."""
    id: UUID
    camp_id: Optional[UUID] = None
    name: str
    latitude: float
    longitude: float
    direction: str
    checkpoint_type: str
    status: str
    district: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CheckpointListResponse(BaseModel):
    """Paginated list of checkpoints."""
    items: List[CheckpointResponse]
    total: int
    page: int
    page_size: int


# ──────────────────────────────────────────────
# Route Schemas
# ──────────────────────────────────────────────

class RouteCreateRequest(BaseModel):
    """Create a new route."""
    season_id: UUID
    name: str = Field(..., min_length=3, max_length=150)
    description: Optional[str] = Field(None, max_length=500)


class RouteUpdateRequest(BaseModel):
    """Update an existing route."""
    name: Optional[str] = Field(None, min_length=3, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[RouteStatus] = None


class RouteResponse(BaseModel):
    """Route details."""
    id: UUID
    season_id: UUID
    name: str
    description: Optional[str] = None
    status: str
    total_distance_km: Optional[float] = None
    estimated_hours: Optional[float] = None
    segment_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RouteDetailResponse(RouteResponse):
    """Route with segments."""
    segments: List["RouteSegmentResponse"] = []


class RouteListResponse(BaseModel):
    """Paginated list of routes."""
    items: List[RouteResponse]
    total: int
    page: int
    page_size: int


# ──────────────────────────────────────────────
# Route Segment Schemas
# ──────────────────────────────────────────────

class RouteSegmentCreateRequest(BaseModel):
    """Create a new route segment."""
    route_id: UUID
    season_id: UUID
    sequence_order: int = Field(..., ge=0, description="Order within route (0-based)")
    start_checkpoint_id: UUID
    end_checkpoint_id: UUID
    distance_km: float = Field(..., gt=0, description="Distance in kilometers")
    nominal_walking_hours: float = Field(..., gt=0, description="Estimated walking hours")
    difficulty: SegmentDifficulty = SegmentDifficulty.MODERATE

    @validator("end_checkpoint_id")
    def checkpoints_must_differ(cls, v: UUID, values: dict) -> UUID:
        start_id = values.get("start_checkpoint_id")
        if start_id and v == start_id:
            raise ValueError("start_checkpoint_id and end_checkpoint_id must be different")
        return v


class RouteSegmentResponse(BaseModel):
    """Route segment details."""
    id: UUID
    route_id: UUID
    sequence_order: int
    start_checkpoint_id: UUID
    start_checkpoint_name: Optional[str] = None
    end_checkpoint_id: UUID
    end_checkpoint_name: Optional[str] = None
    distance_km: float
    nominal_walking_hours: float
    difficulty: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Journey Schemas
# ──────────────────────────────────────────────

class JourneyCreateRequest(BaseModel):
    """Initialize a journey for a pilgrim."""
    pilgrim_id: UUID
    route_id: UUID


class JourneyResponse(BaseModel):
    """Journey status and details."""
    id: UUID
    pilgrim_id: UUID
    pilgrim_name: Optional[str] = None
    route_id: UUID
    route_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_checkpoint_id: Optional[UUID] = None
    last_checkpoint_name: Optional[str] = None
    last_observed_at: Optional[datetime] = None
    next_expected_checkpoint_id: Optional[UUID] = None
    next_expected_checkpoint_name: Optional[str] = None
    next_expected_arrival_at: Optional[datetime] = None
    hours_since_last_seen: Optional[float] = None
    expected_checkins_missed: Optional[int] = None
    total_distance_covered_km: Optional[float] = None
    total_checkins: int = 0
    current_segment_index: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JourneyDetailResponse(JourneyResponse):
    """Journey with recent presence history."""
    recent_presence: List["PresenceEventResponse"] = []


class JourneyListResponse(BaseModel):
    """Paginated list of journeys."""
    items: List[JourneyResponse]
    total: int
    page: int
    page_size: int


class JourneyStatusUpdateRequest(BaseModel):
    """Manually update journey status (admin only)."""
    status: JourneyStatus
    reason: Optional[str] = Field(None, max_length=255)


# ──────────────────────────────────────────────
# Presence Event Schemas
# ──────────────────────────────────────────────

class PresenceEventCreateRequest(BaseModel):
    """Record a new check-in or check-out event."""
    pilgrim_id: UUID
    checkpoint_id: UUID
    device_id: Optional[UUID] = Field(None, description="Device that performed the scan")
    operator_user_id: UUID = Field(..., description="Operator who performed the scan")
    direction: PresenceDirection = Field(PresenceDirection.CHECKIN)
    scan_result: ScanResult = Field(ScanResult.STANDARD_SUCCESS)
    notes: Optional[str] = Field(None, max_length=500)


class PresenceEventResponse(BaseModel):
    """Presence event record."""
    id: UUID
    pilgrim_id: UUID
    pilgrim_name: Optional[str] = None
    checkpoint_id: UUID
    checkpoint_name: Optional[str] = None
    device_id: Optional[UUID] = None
    operator_user_id: Optional[UUID] = None
    operator_name: Optional[str] = None
    scanned_at: datetime
    synced_at: datetime
    direction: str
    scan_result: str
    missing_person_match: bool
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PresenceEventListResponse(BaseModel):
    """Paginated list of presence events."""
    items: List[PresenceEventResponse]
    total: int
    page: int
    page_size: int


class PilgrimPresenceHistoryResponse(BaseModel):
    """Complete presence history for a pilgrim."""
    pilgrim_id: UUID
    pilgrim_name: str
    events: List[PresenceEventResponse]
    total_events: int


# ──────────────────────────────────────────────
# Offline Sync Schemas
# ──────────────────────────────────────────────

class OfflinePresenceEvent(BaseModel):
    """A single presence event from an offline device."""
    offline_mutation_id: UUID = Field(
        ...,
        description="UUID v4 generated by device for idempotency",
    )
    pilgrim_id: UUID
    checkpoint_id: UUID
    operator_user_id: UUID
    direction: PresenceDirection
    scan_result: ScanResult
    scanned_at: datetime = Field(
        ...,
        description="Device-reported timestamp of the scan",
    )
    notes: Optional[str] = None


class OfflineSyncBatchRequest(BaseModel):
    """Batch of offline events from a camp device."""
    device_id: UUID = Field(..., description="Device that generated these events")
    batch_ref: UUID = Field(
        ...,
        description="Unique batch reference for idempotency",
    )
    events: List[OfflinePresenceEvent] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Offline events to sync",
    )


class OfflineSyncBatchResponse(BaseModel):
    """Result of processing an offline sync batch."""
    batch_ref: UUID
    status: str
    total_events: int
    processed_count: int
    failed_count: int
    failed_events: List[Dict[str, Any]] = []
    message: str


# ──────────────────────────────────────────────
# Journey Intelligence Schemas
# ──────────────────────────────────────────────

class JourneyGapAlertResponse(BaseModel):
    """Alert for a pilgrim with MISS_RISK status."""
    journey_id: UUID
    pilgrim_id: UUID
    pilgrim_name: str
    last_seen_at: Optional[datetime] = None
    last_seen_location: Optional[str] = None
    hours_missing: float
    expected_next_checkpoint: Optional[str] = None
    route_name: Optional[str] = None


class RouteCongestionResponse(BaseModel):
    """Real-time route congestion data."""
    route_id: UUID
    route_name: str
    segment_id: UUID
    segment_name: str
    current_pilgrims: int
    congestion_level: str  # LOW, MODERATE, HIGH, CRITICAL
    average_pace_hours: float