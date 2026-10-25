"""
Platform domain models.

Foundation models for the Kanwar Sahayata system.
Season is the top-level aggregate that isolates each Yatra's data.
AuditEvent provides the immutable compliance ledger.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Date, Enum, DateTime, JSON, Index, Text
from app.core.db_types import BINARY
from app.core.database import Base


class Season(Base):
    """
    Top-level aggregate defining the operational universe.

    Every operational table is scoped to a season_id.
    This enforces multi-tenancy between different Yatra years
    and enables post-season archiving via status change.
    """

    __tablename__ = "seasons"

    id = Column(
        BINARY(16),
        primary_key=True,
        default=lambda: uuid.uuid4().bytes,
        comment="UUID v4 stored as BINARY(16) for clustered index optimization",
    )
    name = Column(
        String(100),
        nullable=False,
        unique=True,
        comment="e.g., 'Kanwar Yatra 2026'",
    )
    start_date = Column(
        Date,
        nullable=False,
        comment="First day of Yatra operations",
    )
    end_date = Column(
        Date,
        nullable=False,
        comment="Last day of Yatra operations",
    )
    status = Column(
        Enum(
            "PLANNING",
            "ACTIVE",
            "ARCHIVED",
            name="season_status",
        ),
        nullable=False,
        default="PLANNING",
        comment="PLANNING=setup phase, ACTIVE=yatra live, ARCHIVED=read-only",
    )
    description = Column(
        String(500),
        nullable=True,
        comment="Optional notes about this season",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp (immutable)",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last modification timestamp",
    )

    __table_args__ = (
        Index("ix_seasons_status", "status"),
        Index("ix_seasons_dates", "start_date", "end_date"),
        {"comment": "Seasons table - one row per Yatra year"},
    )

    def __repr__(self):
        return f"<Season(id={self.id.hex()}, name='{self.name}', status='{self.status}')>"


class AuditEvent(Base):
    """
    Immutable transactional outbox and government compliance ledger.

    Every state-changing operation across all domains produces
    an AuditEvent. This table is append-only at the database level.
    UPDATE and DELETE privileges are revoked for this table.

    Partitioned by occurred_at using RANGE partitioning for efficient
    archival and fast queries on recent events.
    """

    __tablename__ = "audit_events"

    id = Column(
        BINARY(16),
        primary_key=True,
        default=lambda: uuid.uuid4().bytes,
        comment="Unique audit event ID",
    )
    season_id = Column(
        BINARY(16),
        nullable=False,
        comment="Season scope for this event",
    )
    aggregate_type = Column(
        String(50),
        nullable=False,
        comment="Domain aggregate: pilgrim, journey, group, emergency, etc.",
    )
    aggregate_id = Column(
        BINARY(16),
        nullable=False,
        comment="ID of the entity this event pertains to",
    )
    event_type = Column(
        String(80),
        nullable=False,
        comment="Specific event: PILGRIM_REGISTERED, SOS_RAISED, etc.",
    )
    actor_id = Column(
        BINARY(16),
        nullable=True,
        comment="User ID who performed the action (NULL for system events)",
    )
    actor_role = Column(
        String(50),
        nullable=True,
        comment="Role of actor: pilgrim, camp_operator, system, etc.",
    )
    payload = Column(
        JSON,
        nullable=False,
        comment="Full event payload as JSON for complete audit trail",
    )
    source = Column(
        String(50),
        nullable=True,
        default="API",
        comment="Source of the event: API, PORTAL, SYSTEM, BULK_IMPORT",
    )
    ip_address = Column(
        String(45),
        nullable=True,
        comment="Client IP address for security auditing (IPv4 or IPv6)",
    )
    occurred_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the event occurred (server time)",
    )

    __table_args__ = (
        Index("ix_audit_aggregate", "aggregate_id"),
        Index("ix_audit_event_type", "event_type"),
        Index("ix_audit_occurred", "occurred_at"),
        Index("ix_audit_season_event", "season_id", "event_type"),
        Index("ix_audit_actor", "actor_id"),
        {"comment": "Immutable audit ledger - append only"},
    )

    def __repr__(self):
        return (
            f"<AuditEvent("
            f"aggregate_type='{self.aggregate_type}', "
            f"event_type='{self.event_type}', "
            f"occurred_at='{self.occurred_at}')>"
        )