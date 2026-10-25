import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Enum, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, Text
)
from app.core.db_types import BINARY, POINT
from sqlalchemy.orm import relationship
from app.core.database import Base


class EmergencyRequest(Base):
    """Complete lifecycle of an SOS emergency from creation to resolution."""
    __tablename__ = "emergency_requests"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(BINARY(16), nullable=False, index=True)
    pilgrim_id = Column(BINARY(16), nullable=False, index=True)
    type = Column(
        Enum("MEDICAL", "POLICE", "STRUCTURAL", name="emergency_type"),
        nullable=False
    )
    location = Column(POINT(srid=4326), nullable=True)
    location_description = Column(String(500), nullable=True)
    status = Column(
        Enum(
            "PENDING", "ACKNOWLEDGED", "DISPATCHED",
            "ON_SCENE", "RESOLVED", "ESCALATED",
            name="emergency_status"
        ),
        nullable=False,
        default="PENDING"
    )
    severity = Column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="emergency_severity"),
        default="HIGH"
    )

    # SLA tracking
    raised_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(BINARY(16), nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    on_scene_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    sla_deadline = Column(DateTime, nullable=False)  # raised_at + 180 seconds
    sla_breached = Column(Integer, default=0)         # 0=ok, 1=breached

    # Responder assignment
    responder_user_id = Column(BINARY(16), nullable=True)
    responder_camp_id = Column(BINARY(16), nullable=True)
    responder_type = Column(
        Enum("MEDICAL_OFFICER", "AMBULANCE", "POLICE", "RESCUE_TEAM",
             name="responder_type"),
        nullable=True
    )

    # Resolution
    resolution_summary = Column(Text, nullable=True)
    resolved_by = Column(BINARY(16), nullable=True)
    escalation_level = Column(
        Enum("L1", "L2", "L3", "L4", name="escalation_level"),
        default="L1"
    )
    escalated_at = Column(DateTime, nullable=True)
    escalation_reason = Column(String(255), nullable=True)

    # Source tracking
    source = Column(
        Enum("APP", "PORTAL", "OPERATOR", name="emergency_source"),
        default="APP"
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    medical_incident = relationship(
        "MedicalIncident",
        back_populates="emergency",
        uselist=False,
        lazy="selectin"
    )

    __table_args__ = (
        Index("ix_emergency_status", "status"),
        Index("ix_emergency_pilgrim_season", "pilgrim_id", "season_id"),
        Index("ix_emergency_raised", "raised_at"),
        Index("ix_emergency_sla", "sla_deadline", "status"),
        Index("ix_emergency_responder", "responder_user_id"),
    )


class MedicalIncident(Base):
    """Detailed medical record linked to an emergency request."""
    __tablename__ = "medical_incidents"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    emergency_id = Column(
        BINARY(16),
        ForeignKey("emergency_requests.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True
    )
    pilgrim_id = Column(BINARY(16), nullable=False, index=True)
    camp_id = Column(BINARY(16), nullable=True)
    medical_officer_id = Column(BINARY(16), nullable=True)

    # Triage & Assessment
    triage_level = Column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL", name="triage_level"),
        nullable=False
    )
    primary_complaint = Column(String(500), nullable=True)
    secondary_complaints = Column(JSON, nullable=True)
    symptoms_onset = Column(String(255), nullable=True)

    # Vital Signs
    vitals = Column(JSON, nullable=True)  # {"bp": "120/80", "pulse": 72, "temp": 98.6, "spo2": 98}
    consciousness = Column(
        Enum("ALERT", "VERBAL", "PAIN", "UNRESPONSIVE", name="consciousness_level"),
        nullable=True
    )

    # Pilgrim's medical context (snapshot at time of incident)
    known_conditions = Column(JSON, nullable=True)
    known_allergies = Column(JSON, nullable=True)
    current_medications = Column(JSON, nullable=True)
    blood_group = Column(String(5), nullable=True)

    # Treatment
    diagnosis = Column(String(500), nullable=True)
    treatment_given = Column(Text, nullable=True)
    medications_administered = Column(JSON, nullable=True)

    # Disposition
    disposition = Column(
        Enum("TREATING", "TREATED", "TRANSFERRED", "FATALITY", "REFERRED",
             name="incident_disposition"),
        default="TREATING"
    )
    disposition_notes = Column(Text, nullable=True)

    # Transfer details
    transfer_facility = Column(String(255), nullable=True)
    transfer_reason = Column(Text, nullable=True)
    ambulance_id = Column(BINARY(16), nullable=True)

    # Timestamps
    incident_started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    triage_completed_at = Column(DateTime, nullable=True)
    treatment_completed_at = Column(DateTime, nullable=True)
    transferred_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emergency = relationship("EmergencyRequest", back_populates="medical_incident")

    __table_args__ = (
        Index("ix_medical_incident_pilgrim", "pilgrim_id"),
        Index("ix_medical_incident_camp", "camp_id"),
        Index("ix_medical_incident_disposition", "disposition"),
    )


class EmergencyTimeline(Base):
    """Immutable append-only timeline of all status changes for an emergency."""
    __tablename__ = "emergency_timeline"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    emergency_id = Column(
        BINARY(16),
        ForeignKey("emergency_requests.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    event_type = Column(String(80), nullable=False)
    actor_id = Column(BINARY(16), nullable=True)
    actor_role = Column(String(50), nullable=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=True)
    payload = Column(JSON, nullable=True)
    notes = Column(String(500), nullable=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_timeline_emergency", "emergency_id", "occurred_at"),
    )


class DeceasedConfirmation(Base):
    """Two-actor confirmation for deceased protocol."""
    __tablename__ = "deceased_confirmations"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    emergency_id = Column(
        BINARY(16),
        ForeignKey("emergency_requests.id", ondelete="RESTRICT"),
        nullable=False
    )
    pilgrim_id = Column(BINARY(16), nullable=False, index=True)

    # First confirmation (Medical Officer)
    first_confirmer_id = Column(BINARY(16), nullable=True)
    first_confirmed_at = Column(DateTime, nullable=True)
    first_confirmation_notes = Column(Text, nullable=True)

    # Second confirmation (Police Officer or second Medical Officer)
    second_confirmer_id = Column(BINARY(16), nullable=True)
    second_confirmed_at = Column(DateTime, nullable=True)
    second_confirmation_notes = Column(Text, nullable=True)

    # Death details
    time_of_death = Column(DateTime, nullable=True)
    cause_of_death = Column(String(255), nullable=True)
    body_location = Column(String(255), nullable=True)  # Where body is kept

    # Next-of-kin notification
    next_of_kin_notified = Column(Integer, default=0)
    next_of_kin_notified_at = Column(DateTime, nullable=True)
    notification_method = Column(String(50), nullable=True)

    status = Column(
        Enum("PENDING_FIRST", "PENDING_SECOND", "CONFIRMED", "NOTIFIED",
             name="deceased_confirmation_status"),
        default="PENDING_FIRST"
    )

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)