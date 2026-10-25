from pydantic import BaseModel, Field, validator
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict
from enum import Enum


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class EmergencyType(str, Enum):
    MEDICAL = "MEDICAL"
    POLICE = "POLICE"
    STRUCTURAL = "STRUCTURAL"

class EmergencyStatus(str, Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISPATCHED = "DISPATCHED"
    ON_SCENE = "ON_SCENE"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

class EmergencySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class TriageLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Disposition(str, Enum):
    TREATING = "TREATING"
    TREATED = "TREATED"
    TRANSFERRED = "TRANSFERRED"
    FATALITY = "FATALITY"
    REFERRED = "REFERRED"

class EscalationLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"

class ResponderType(str, Enum):
    MEDICAL_OFFICER = "MEDICAL_OFFICER"
    AMBULANCE = "AMBULANCE"
    POLICE = "POLICE"
    RESCUE_TEAM = "RESCUE_TEAM"

class ConsciousnessLevel(str, Enum):
    ALERT = "ALERT"
    VERBAL = "VERBAL"
    PAIN = "PAIN"
    UNRESPONSIVE = "UNRESPONSIVE"


# ──────────────────────────────────────────────
# SOS Request Schemas
# ──────────────────────────────────────────────

class SOSCreateRequest(BaseModel):
    """Pilgrim or Operator raises an SOS."""
    pilgrim_id: UUID
    type: EmergencyType = EmergencyType.MEDICAL
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_description: Optional[str] = Field(None, max_length=500)
    source: str = "APP"  # APP, PORTAL, OPERATOR

    @validator("latitude")
    def validate_latitude(cls, v):
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @validator("longitude")
    def validate_longitude(cls, v):
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


class SOSResponse(BaseModel):
    """Response after SOS is raised."""
    id: UUID
    pilgrim_id: UUID
    type: str
    status: str
    severity: str
    raised_at: datetime
    sla_deadline: datetime
    location_description: Optional[str]
    source: str
    message: str = "SOS raised successfully. Help is on the way."

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Emergency Request Schemas
# ──────────────────────────────────────────────

class EmergencyAcknowledgeRequest(BaseModel):
    """Control Room Operator acknowledges an SOS."""
    operator_id: UUID


class EmergencyDispatchRequest(BaseModel):
    """Dispatch a responder to the emergency."""
    responder_user_id: UUID
    responder_camp_id: Optional[UUID] = None
    responder_type: ResponderType = ResponderType.MEDICAL_OFFICER
    operator_id: UUID


class EmergencyOnSceneRequest(BaseModel):
    """Responder confirms arrival at scene."""
    responder_user_id: UUID
    notes: Optional[str] = None


class EmergencyResolveRequest(BaseModel):
    """Resolve/close the emergency."""
    operator_id: UUID
    resolution_summary: Optional[str] = Field(None, max_length=1000)


class EmergencyEscalateRequest(BaseModel):
    """Manually escalate to next level."""
    operator_id: UUID
    reason: str = Field(..., max_length=255)
    target_level: EscalationLevel = EscalationLevel.L2


class EmergencyResponse(BaseModel):
    """Full emergency request response."""
    id: UUID
    pilgrim_id: UUID
    pilgrim_name: Optional[str] = None
    pilgrim_blood_group: Optional[str] = None
    pilgrim_medical_flags: Optional[dict] = None
    pilgrim_emergency_contact_name: Optional[str] = None
    pilgrim_emergency_contact_phone: Optional[str] = None
    type: str
    status: str
    severity: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_description: Optional[str]
    source: str
    responder_user_id: Optional[UUID] = None
    responder_type: Optional[str] = None
    raised_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    dispatched_at: Optional[datetime] = None
    on_scene_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    sla_deadline: datetime
    sla_breached: int
    escalation_level: str
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None
    resolution_summary: Optional[str] = None
    medical_incident: Optional["MedicalIncidentResponse"] = None
    timeline: List["EmergencyTimelineResponse"] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmergencyListResponse(BaseModel):
    items: List[EmergencyResponse]
    total: int
    page: int
    page_size: int


class EmergencyStatusUpdate(BaseModel):
    status: EmergencyStatus


# ──────────────────────────────────────────────
# Medical Incident Schemas
# ──────────────────────────────────────────────

class MedicalIncidentCreateRequest(BaseModel):
    """Start a medical incident for an emergency."""
    emergency_id: UUID
    medical_officer_id: UUID
    camp_id: Optional[UUID] = None
    triage_level: TriageLevel
    primary_complaint: Optional[str] = Field(None, max_length=500)
    secondary_complaints: Optional[List[str]] = None
    symptoms_onset: Optional[str] = None
    vitals: Optional[Dict[str, str]] = None  # {"bp": "120/80", "pulse": "72", ...}
    consciousness: Optional[ConsciousnessLevel] = None
    known_conditions: Optional[List[str]] = None
    known_allergies: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    blood_group: Optional[str] = None


class MedicalIncidentUpdateRequest(BaseModel):
    """Update treatment details."""
    diagnosis: Optional[str] = Field(None, max_length=500)
    treatment_given: Optional[str] = None
    medications_administered: Optional[List[Dict[str, str]]] = None
    vitals: Optional[Dict[str, str]] = None
    disposition: Optional[Disposition] = None
    disposition_notes: Optional[str] = None


class MedicalTransferRequest(BaseModel):
    """Initiate transfer to another facility."""
    transfer_facility: str = Field(..., max_length=255)
    transfer_reason: str = Field(..., max_length=1000)
    ambulance_id: Optional[UUID] = None


class MedicalIncidentResponse(BaseModel):
    id: UUID
    emergency_id: UUID
    pilgrim_id: UUID
    triage_level: str
    primary_complaint: Optional[str]
    secondary_complaints: Optional[dict]
    vitals: Optional[dict]
    consciousness: Optional[str]
    known_conditions: Optional[dict]
    known_allergies: Optional[dict]
    blood_group: Optional[str]
    diagnosis: Optional[str]
    treatment_given: Optional[str]
    medications_administered: Optional[dict]
    disposition: str
    disposition_notes: Optional[str]
    transfer_facility: Optional[str]
    transfer_reason: Optional[str]
    incident_started_at: datetime
    treatment_completed_at: Optional[datetime]
    transferred_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Deceased Confirmation Schemas
# ──────────────────────────────────────────────

class DeceasedConfirmationCreate(BaseModel):
    emergency_id: UUID
    pilgrim_id: UUID
    time_of_death: datetime
    cause_of_death: Optional[str] = Field(None, max_length=255)
    body_location: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class DeceasedSecondConfirmationRequest(BaseModel):
    confirmer_id: UUID
    notes: Optional[str] = None


class DeceasedConfirmationResponse(BaseModel):
    id: UUID
    emergency_id: UUID
    pilgrim_id: UUID
    first_confirmer_id: Optional[UUID]
    first_confirmed_at: Optional[datetime]
    second_confirmer_id: Optional[UUID]
    second_confirmed_at: Optional[datetime]
    time_of_death: Optional[datetime]
    cause_of_death: Optional[str]
    status: str
    next_of_kin_notified: int
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Emergency Timeline Schemas
# ──────────────────────────────────────────────

class EmergencyTimelineResponse(BaseModel):
    id: UUID
    emergency_id: UUID
    event_type: str
    actor_id: Optional[UUID]
    actor_role: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    payload: Optional[dict]
    notes: Optional[str]
    occurred_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Aggregate: Emergency + Medical + Timeline
# ──────────────────────────────────────────────

class EmergencyDetailResponse(EmergencyResponse):
    """Full emergency detail with medical incident and complete timeline."""
    pilgrim_last_known_location: Optional[str] = None
    pilgrim_journey_status: Optional[str] = None
    nearest_medical_camps: List[dict] = []


class SOSStatsResponse(BaseModel):
    """Statistical summary for dashboard."""
    total_active: int
    pending: int
    acknowledged: int
    dispatched: int
    on_scene: int
    avg_response_time_seconds: Optional[float] = None
    sla_breach_count: int
    by_severity: Dict[str, int] = {}