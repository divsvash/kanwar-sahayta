from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from typing import Optional


@dataclass
class SOSRaised:
    emergency_id: UUID
    pilgrim_id: UUID
    type: str
    season_id: UUID
    source: str
    latitude: Optional[float]
    longitude: Optional[float]
    raised_at: datetime


@dataclass
class SOSAcknowledged:
    emergency_id: UUID
    acknowledged_by: UUID
    acknowledged_at: datetime
    sla_breached: bool


@dataclass
class SOSResponderAssigned:
    emergency_id: UUID
    responder_user_id: UUID
    responder_type: str
    assigned_by: UUID
    assigned_at: datetime


@dataclass
class SOSResponderDispatched:
    emergency_id: UUID
    dispatched_at: datetime


@dataclass
class SOSOnScene:
    emergency_id: UUID
    responder_user_id: UUID
    arrived_at: datetime


@dataclass
class SOSAutoEscalated:
    emergency_id: UUID
    from_level: str
    to_level: str
    reason: str
    escalated_at: datetime


@dataclass
class SOSResolved:
    emergency_id: UUID
    resolved_by: UUID
    resolved_at: datetime
    resolution_summary: Optional[str]


@dataclass
class MedicalIncidentOpened:
    emergency_id: UUID
    incident_id: UUID
    triage_level: str
    opened_by: UUID


@dataclass
class MedicalIncidentClosed:
    emergency_id: UUID
    incident_id: UUID
    disposition: str


@dataclass
class MedicalTransferInitiated:
    emergency_id: UUID
    incident_id: UUID
    transfer_facility: str


@dataclass
class DeceasedConfirmed:
    emergency_id: UUID
    pilgrim_id: UUID
    first_confirmer_id: UUID
    second_confirmer_id: UUID
    time_of_death: datetime
    confirmed_at: datetime


@dataclass
class NextOfKinNotified:
    emergency_id: UUID
    pilgrim_id: UUID
    contact_phone: str
    notification_method: str
    notified_at: datetime