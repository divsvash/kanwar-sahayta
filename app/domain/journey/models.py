"""
Journey domain models.

Answers: Where is every pilgrim going?
Where have they been observed?
What is their current journey status?
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Enum, DateTime,
    ForeignKey, Index, UniqueConstraint, Boolean, Text,
)
from app.core.db_types import BINARY, POINT, LINESTRING
from sqlalchemy.orm import relationship
from app.core.database import Base


class Route(Base):
    """
    A declared pilgrimage route for a season.

    Routes are composed of ordered segments connecting checkpoints.
    Pilgrims declare their intended route during registration.
    """

    __tablename__ = "routes"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(
        BINARY(16),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Season scope",
    )
    name = Column(
        String(150),
        nullable=False,
        comment="Route name: 'Meerut-Haridwar Main', 'Baghpat-Haridwar Alternate'",
    )
    description = Column(
        String(500),
        nullable=True,
        comment="Human-readable route description",
    )
    status = Column(
        Enum("ACTIVE", "INACTIVE", name="route_status"),
        nullable=False,
        default="ACTIVE",
        comment="Whether this route is available for the current season",
    )
    total_distance_km = Column(
        Float,
        nullable=True,
        comment="Total route distance in kilometers (sum of segments)",
    )
    estimated_hours = Column(
        Float,
        nullable=True,
        comment="Estimated total walking time in hours",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    segments = relationship(
        "RouteSegment",
        back_populates="route",
        lazy="selectin",
        order_by="RouteSegment.sequence_order",
    )

    __table_args__ = (
        Index("ix_routes_season", "season_id"),
        Index("ix_routes_status", "status"),
        {"comment": "Pilgrimage routes for a season"},
    )

    def __repr__(self):
        return f"<Route(id={self.id.hex()}, name='{self.name}', status='{self.status}')>"


class Checkpoint(Base):
    """
    A physical location where pilgrim presence can be recorded.

    Checkpoints are attached to camps (rest, medical, transit) or
    standalone milestones along routes. Each checkpoint has a GPS
    location and a direction (IN/OUT/EN_ROUTE).
    """

    __tablename__ = "checkpoints"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    camp_id = Column(
        BINARY(16),
        nullable=True,
        index=True,
        comment="FK to camps table (Phase 2). NULL for standalone checkpoints.",
    )
    name = Column(
        String(150),
        nullable=False,
        comment="Checkpoint name: 'Modinagar Rest Camp Entry', 'Har Ki Pauri Exit'",
    )
    location = Column(
        POINT(srid=4326),
        nullable=False,
        comment="GPS coordinates as MySQL spatial POINT (SRID 4326 WGS 84)",
    )
    direction = Column(
        Enum("IN", "OUT", "EN_ROUTE", name="checkpoint_direction"),
        nullable=False,
        comment="IN=entry scan, OUT=exit scan, EN_ROUTE=midpoint scan",
    )
    checkpoint_type = Column(
        Enum(
            "ENTRY", "EXIT", "REST_CAMP", "MEDICAL_CAMP",
            "TRANSIT_CAMP", "MILESTONE", "POLICE_POST",
            name="checkpoint_type",
        ),
        nullable=False,
        comment="Type of facility at this checkpoint",
    )
    status = Column(
        Enum("ACTIVE", "OFFLINE", "CLOSED", name="checkpoint_status"),
        nullable=False,
        default="ACTIVE",
        comment="Current operational status",
    )
    district = Column(
        String(100),
        nullable=True,
        comment="Administrative district for reporting",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_checkpoints_status", "status"),
        Index("ix_checkpoints_type", "checkpoint_type"),
        Index("ix_checkpoints_camp", "camp_id"),
        {"comment": "Physical checkpoints where pilgrim presence is scanned"},
    )

    def __repr__(self):
        return f"<Checkpoint(id={self.id.hex()}, name='{self.name}', type='{self.checkpoint_type}')>"


class RouteSegment(Base):
    """
    A segment of a route connecting two checkpoints.

    Contains the spatial linestring for mapping, distance,
    and estimated walking time. Used by Journey Intelligence
    Engine for gap detection and missing person search polygons.
    """

    __tablename__ = "route_segments"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(
        BINARY(16),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Season scope",
    )
    route_id = Column(
        BINARY(16),
        ForeignKey("routes.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Parent route",
    )
    sequence_order = Column(
        Integer,
        nullable=False,
        comment="Order of this segment within the route (0-based)",
    )
    start_checkpoint_id = Column(
        BINARY(16),
        ForeignKey("checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Starting checkpoint of this segment",
    )
    end_checkpoint_id = Column(
        BINARY(16),
        ForeignKey("checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Ending checkpoint of this segment",
    )
    polyline = Column(
        LINESTRING(srid=4326),
        nullable=True,
        comment="Spatial linestring for map rendering and distance calculation",
    )
    distance_km = Column(
        Float,
        nullable=False,
        comment="Distance in kilometers",
    )
    nominal_walking_hours = Column(
        Float,
        nullable=False,
        comment="Estimated walking time in hours at average pace (3 km/h)",
    )
    difficulty = Column(
        Enum("EASY", "MODERATE", "DIFFICULT", name="segment_difficulty"),
        nullable=True,
        default="MODERATE",
        comment="Terrain difficulty",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    route = relationship("Route", back_populates="segments")
    start_checkpoint = relationship(
        "Checkpoint",
        foreign_keys=[start_checkpoint_id],
        lazy="joined",
    )
    end_checkpoint = relationship(
        "Checkpoint",
        foreign_keys=[end_checkpoint_id],
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_route_segments_route", "route_id", "sequence_order"),
        UniqueConstraint("route_id", "sequence_order", name="uq_segment_order"),
        {"comment": "Route segments connecting checkpoints"},
    )

    def __repr__(self):
        return (
            f"<RouteSegment("
            f"route_id={self.route_id.hex()}, "
            f"order={self.sequence_order}, "
            f"distance={self.distance_km}km)"
        )


class Journey(Base):
    """
    1:1 aggregate tracking a pilgrim's journey state.

    This is a PERFORMANCE-OPTIMIZED PROJECTION (ADR-002).
    It is rebuilt periodically by the dashboard_projector worker
    from the PresenceEvent ledger. It is NOT the source of truth -
    the PresenceEvent stream is.

    Updated after every PresenceEvent by the PresenceService.
    Rebuilt every 5 minutes by Celery worker for consistency.
    """

    __tablename__ = "journeys"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    pilgrim_id = Column(
        BINARY(16),
        ForeignKey("pilgrims.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        comment="1:1 relationship with pilgrim",
    )
    route_id = Column(
        BINARY(16),
        ForeignKey("routes.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Declared route for this journey",
    )
    status = Column(
        Enum(
            "PLANNED",       # Not yet started
            "IN_PROGRESS",   # At least one check-in recorded
            "MISS_RISK",     # No check-in for > 36 hours (gap detection)
            "COMPLETED",     # Reached destination checkpoint
            name="journey_status",
        ),
        nullable=False,
        default="PLANNED",
        comment="Computed journey status from PresenceEvent analysis",
    )

    # Timing
    started_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp of first PresenceEvent",
    )
    completed_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp when destination checkpoint was reached",
    )

    # Current position
    last_presence_event_id = Column(
        BINARY(16),
        nullable=True,
        comment="ID of the most recent PresenceEvent",
    )
    last_checkpoint_id = Column(
        BINARY(16),
        ForeignKey("checkpoints.id", ondelete="SET NULL"),
        nullable=True,
        comment="Last checkpoint where pilgrim was observed",
    )
    last_known_location = Column(
        POINT(srid=4326),
        nullable=True,
        comment="GPS coordinates of last known location",
    )
    last_observed_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp of last PresenceEvent (scanned_at)",
    )

    # Prediction
    next_expected_checkpoint_id = Column(
        BINARY(16),
        ForeignKey("checkpoints.id", ondelete="SET NULL"),
        nullable=True,
        comment="Next checkpoint pilgrim is expected to reach",
    )
    next_expected_arrival_at = Column(
        DateTime,
        nullable=True,
        comment="Estimated arrival time at next checkpoint (based on walking pace)",
    )

    # Gap detection
    hours_since_last_seen = Column(
        Float,
        nullable=True,
        default=0.0,
        comment="Hours elapsed since last PresenceEvent",
    )
    expected_checkins_missed = Column(
        Integer,
        nullable=True,
        default=0,
        comment="Number of expected checkpoints passed without observation",
    )

    # Statistics
    total_distance_covered_km = Column(
        Float,
        nullable=True,
        default=0.0,
        comment="Total distance covered based on check-ins",
    )
    total_checkins = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of PresenceEvents for this journey",
    )
    current_segment_index = Column(
        Integer,
        nullable=True,
        comment="Index of current route segment (0-based)",
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pilgrim = relationship("Pilgrim", back_populates="journey")
    route = relationship("Route", lazy="joined")
    last_checkpoint = relationship(
        "Checkpoint",
        foreign_keys=[last_checkpoint_id],
        lazy="joined",
    )
    next_checkpoint = relationship(
        "Checkpoint",
        foreign_keys=[next_expected_checkpoint_id],
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_journeys_status", "status"),
        Index("ix_journeys_next_arrival", "next_expected_arrival_at"),
        Index("ix_journeys_last_seen", "last_observed_at"),
        Index("ix_journeys_risk", "status", "hours_since_last_seen"),
        {"comment": "Journey projection - rebuilt every 5 minutes"},
    )

    def __repr__(self):
        return f"<Journey(pilgrim_id={self.pilgrim_id.hex()}, status='{self.status}')>"


class PresenceEvent(Base):
    """
    IMMUTABLE ledger of every pilgrim check-in/check-out.

    This is the source of truth for all pilgrim movement.
    Appended only - never updated or deleted.
    Partitioned by scanned_at for efficient ingestion and archival.

    No foreign keys to allow MySQL RANGE partitioning without
    cross-partition FK locking issues.
    """

    __tablename__ = "presence_events"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(
        BINARY(16),
        nullable=False,
        comment="Season scope",
    )
    pilgrim_id = Column(
        BINARY(16),
        nullable=False,
        comment="Pilgrim who was scanned",
    )
    checkpoint_id = Column(
        BINARY(16),
        nullable=False,
        comment="Checkpoint where scan occurred",
    )
    device_id = Column(
        BINARY(16),
        nullable=True,
        comment="Device that performed the scan",
    )
    operator_user_id = Column(
        BINARY(16),
        nullable=True,
        comment="Operator who performed the scan",
    )
    sync_batch_id = Column(
        BINARY(16),
        nullable=True,
        comment="NULL=live online scan, NOT NULL=offline batch sync",
    )

    # Timing
    scanned_at = Column(
        DateTime,
        nullable=False,
        comment="Device-reported timestamp of the scan",
    )
    synced_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Server timestamp when event was recorded",
    )

    # Idempotency
    offline_mutation_id = Column(
        BINARY(16),
        nullable=False,
        comment="UUID v4 generated by device for idempotency (live scans also have this)",
    )

    # Event type
    direction = Column(
        Enum("CHECKIN", "CHECKOUT", "AUTO_CHECKOUT", name="presence_direction"),
        nullable=False,
        comment="CHECKIN=entry, CHECKOUT=exit, AUTO_CHECKOUT=system-generated exit",
    )

    # Scan result
    scan_result = Column(
        String(50),
        nullable=False,
        default="STANDARD_SUCCESS",
        comment="STANDARD_SUCCESS, MEDICAL_FLAG, MISSING_PERSON_MATCH, REVOKED_QR, etc.",
    )
    missing_person_match = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this scan matched an active missing person case",
    )

    # Notes
    notes = Column(
        String(500),
        nullable=True,
        comment="Operator notes (e.g., reason for manual check-in)",
    )

    __table_args__ = (
        Index("ix_presence_pilgrim", "pilgrim_id"),
        Index("ix_presence_checkpoint_time", "checkpoint_id", "scanned_at"),
        Index("ix_presence_season", "season_id"),
        Index("ix_presence_sync_batch", "sync_batch_id"),
        Index("ix_presence_operator", "operator_user_id"),
        UniqueConstraint(
            "offline_mutation_id",
            name="uq_offline_mutation",
        ),
        {"comment": "Immutable presence ledger - append only. Partitioned by scanned_at."},
    )

    def __repr__(self):
        return (
            f"<PresenceEvent("
            f"pilgrim_id={self.pilgrim_id.hex()}, "
            f"checkpoint_id={self.checkpoint_id.hex()}, "
            f"direction='{self.direction}', "
            f"scanned_at='{self.scanned_at}')>"
        )