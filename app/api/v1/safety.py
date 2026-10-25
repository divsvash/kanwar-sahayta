from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.api.deps import get_db, get_current_season, get_current_user
from app.domain.safety.service import (
    EmergencyService, MedicalIncidentService, DeceasedConfirmationService
)
from app.domain.safety.schemas import (
    SOSCreateRequest, SOSResponse,
    EmergencyAcknowledgeRequest, EmergencyDispatchRequest,
    EmergencyOnSceneRequest, EmergencyResolveRequest,
    EmergencyEscalateRequest,
    EmergencyResponse, EmergencyDetailResponse, EmergencyListResponse,
    MedicalIncidentCreateRequest, MedicalIncidentUpdateRequest,
    MedicalTransferRequest, MedicalIncidentResponse,
    DeceasedConfirmationCreate, DeceasedSecondConfirmationRequest,
    DeceasedConfirmationResponse,
)

router = APIRouter(prefix="/safety", tags=["Safety"])


# ──────────────────────────────────────────────
# SOS Endpoints
# ──────────────────────────────────────────────

@router.post("/sos", response_model=SOSResponse, status_code=201)
async def raise_sos(
    request: SOSCreateRequest,
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db),
):
    """Pilgrim or operator raises an SOS emergency."""
    service = EmergencyService(db)
    emergency = await service.raise_sos(request, season_id)
    return SOSResponse(
        id=UUID(bytes=emergency.id),
        pilgrim_id=UUID(bytes=emergency.pilgrim_id),
        type=emergency.type,
        status=emergency.status,
        severity=emergency.severity,
        raised_at=emergency.raised_at,
        sla_deadline=emergency.sla_deadline,
        location_description=emergency.location_description,
        source=emergency.source,
    )


# ──────────────────────────────────────────────
# Emergency Management Endpoints
# ──────────────────────────────────────────────

@router.get("/emergencies", response_model=EmergencyListResponse)
async def list_active_emergencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db),
):
    """List all non-resolved emergencies."""
    service = EmergencyService(db)
    items, total = await service.list_active_emergencies(season_id, page, page_size)
    return EmergencyListResponse(
        items=[EmergencyResponse.from_orm(e) for e in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/emergencies/{emergency_id}", response_model=EmergencyDetailResponse)
async def get_emergency_detail(
    emergency_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """Get full emergency detail with medical incident and timeline."""
    service = EmergencyService(db)
    emergency = await service.get_emergency(emergency_id)
    timeline = await service.get_emergency_timeline(emergency_id)

    response = EmergencyDetailResponse.from_orm(emergency)
    response.timeline = [
        {"id": UUID(bytes=t.id), "event_type": t.event_type, "occurred_at": t.occurred_at}
        for t in timeline
    ]
    return response


@router.put("/emergencies/{emergency_id}/acknowledge", response_model=EmergencyResponse)
async def acknowledge_emergency(
    emergency_id: UUID,
    request: EmergencyAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Control Room operator acknowledges the emergency."""
    service = EmergencyService(db)
    emergency = await service.acknowledge_emergency(emergency_id, request)
    return EmergencyResponse.from_orm(emergency)


@router.put("/emergencies/{emergency_id}/dispatch", response_model=EmergencyResponse)
async def dispatch_responder(
    emergency_id: UUID,
    request: EmergencyDispatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Assign and dispatch a responder."""
    service = EmergencyService(db)
    emergency = await service.dispatch_responder(emergency_id, request)
    return EmergencyResponse.from_orm(emergency)


@router.put("/emergencies/{emergency_id}/on-scene", response_model=EmergencyResponse)
async def mark_on_scene(
    emergency_id: UUID,
    request: EmergencyOnSceneRequest,
    db: AsyncSession = Depends(get_db),
):
    """Responder confirms arrival at scene."""
    service = EmergencyService(db)
    emergency = await service.mark_on_scene(emergency_id, request)
    return EmergencyResponse.from_orm(emergency)


@router.put("/emergencies/{emergency_id}/resolve", response_model=EmergencyResponse)
async def resolve_emergency(
    emergency_id: UUID,
    request: EmergencyResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resolve/close the emergency."""
    service = EmergencyService(db)
    emergency = await service.resolve_emergency(emergency_id, request)
    return EmergencyResponse.from_orm(emergency)


@router.put("/emergencies/{emergency_id}/escalate", response_model=EmergencyResponse)
async def escalate_emergency(
    emergency_id: UUID,
    request: EmergencyEscalateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Escalate to next authority level."""
    service = EmergencyService(db)
    emergency = await service.escalate_emergency(emergency_id, request)
    return EmergencyResponse.from_orm(emergency)


# ──────────────────────────────────────────────
# Medical Incident Endpoints
# ──────────────────────────────────────────────

@router.post("/medical-incidents", response_model=MedicalIncidentResponse, status_code=201)
async def create_medical_incident(
    request: MedicalIncidentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a medical incident record for an emergency."""
    service = MedicalIncidentService(db)
    incident = await service.create_incident(request)
    return MedicalIncidentResponse.from_orm(incident)


@router.put("/medical-incidents/{incident_id}", response_model=MedicalIncidentResponse)
async def update_medical_incident(
    incident_id: UUID,
    request: MedicalIncidentUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update treatment details and disposition."""
    service = MedicalIncidentService(db)
    incident = await service.update_incident(incident_id, request)
    return MedicalIncidentResponse.from_orm(incident)


@router.put("/medical-incidents/{incident_id}/transfer", response_model=MedicalIncidentResponse)
async def transfer_patient(
    incident_id: UUID,
    request: MedicalTransferRequest,
    db: AsyncSession = Depends(get_db),
):
    """Initiate patient transfer to another facility."""
    service = MedicalIncidentService(db)
    incident = await service.initiate_transfer(incident_id, request)
    return MedicalIncidentResponse.from_orm(incident)


@router.get("/medical-incidents/{incident_id}", response_model=MedicalIncidentResponse)
async def get_medical_incident(
    incident_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a medical incident record."""
    service = MedicalIncidentService(db)
    incident = await service.get_incident(incident_id)
    return MedicalIncidentResponse.from_orm(incident)


# ──────────────────────────────────────────────
# Deceased Confirmation Endpoints
# ──────────────────────────────────────────────

@router.post("/deceased-confirmations", response_model=DeceasedConfirmationResponse, status_code=201)
async def create_deceased_confirmation(
    request: DeceasedConfirmationCreate,
    confirmer_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """First confirmation of death (Medical Officer)."""
    service = DeceasedConfirmationService(db)
    confirmation = await service.create_confirmation(request, confirmer_id)
    return DeceasedConfirmationResponse.from_orm(confirmation)


@router.put(
    "/deceased-confirmations/{confirmation_id}/second",
    response_model=DeceasedConfirmationResponse
)
async def second_deceased_confirmation(
    confirmation_id: UUID,
    request: DeceasedSecondConfirmationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Second confirmation of death (Police Officer or second Medical Officer)."""
    service = DeceasedConfirmationService(db)
    confirmation = await service.second_confirmation(confirmation_id, request)
    return DeceasedConfirmationResponse.from_orm(confirmation)


@router.get(
    "/deceased-confirmations/{confirmation_id}",
    response_model=DeceasedConfirmationResponse
)
async def get_deceased_confirmation(
    confirmation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get deceased confirmation record."""
    service = DeceasedConfirmationService(db)
    confirmation = await service.get_confirmation(confirmation_id)
    return DeceasedConfirmationResponse.from_orm(confirmation)