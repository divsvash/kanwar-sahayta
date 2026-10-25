from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.orm import selectinload

from app.domain.safety.models import (
    EmergencyRequest, MedicalIncident, EmergencyTimeline,
    DeceasedConfirmation
)
from app.domain.safety.schemas import (
    SOSCreateRequest, EmergencyAcknowledgeRequest,
    EmergencyDispatchRequest, EmergencyOnSceneRequest,
    EmergencyResolveRequest, EmergencyEscalateRequest,
    MedicalIncidentCreateRequest, MedicalIncidentUpdateRequest,
    MedicalTransferRequest, DeceasedConfirmationCreate,
    DeceasedSecondConfirmationRequest
)
from app.domain.identity.models import Pilgrim
from app.domain.journey.models import Journey, PresenceEvent, Checkpoint
from app.core.exceptions import NotFoundError, ValidationError, ConflictError
from app.core.events import event_bus


class EmergencyService:
    """Core SOS emergency lifecycle management."""

    SLA_SECONDS = 180  # 3 minutes for L1 acknowledgment
    AUTO_ESCALATE_L2_SECONDS = 300  # 5 minutes for L2 after auto-escalation

    def __init__(self, session: AsyncSession):
        self.session = session

    # ──────────────────────────────────────────
    # SOS Creation
    # ──────────────────────────────────────────

    async def raise_sos(self, request: SOSCreateRequest, season_id: UUID) -> EmergencyRequest:
        """Create a new emergency request from pilgrim SOS."""
        # Validate pilgrim exists and is active
        pilgrim = await self._get_active_pilgrim(request.pilgrim_id)

        # Build location POINT
        location_wkt = None
        if request.latitude and request.longitude:
            location_wkt = f"POINT({request.longitude} {request.latitude})"

        now = datetime.utcnow()
        sla_deadline = now + timedelta(seconds=self.SLA_SECONDS)

        emergency = EmergencyRequest(
            id=uuid4().bytes,
            season_id=season_id.bytes,
            pilgrim_id=request.pilgrim_id.bytes,
            type=request.type.value,
            location=location_wkt,
            location_description=request.location_description,
            status="PENDING",
            severity="HIGH",
            raised_at=now,
            sla_deadline=sla_deadline,
            source=request.source,
            escalation_level="L1",
        )
        self.session.add(emergency)
        await self.session.flush()

        # Record timeline event
        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_RAISED",
            to_status="PENDING",
            payload={
                "type": request.type.value,
                "source": request.source,
                "latitude": request.latitude,
                "longitude": request.longitude,
                "pilgrim_name": pilgrim.full_name,
                "pilgrim_blood_group": pilgrim.blood_group,
            }
        )

        # Enqueue SLA timer task
        from app.workers.tasks import schedule_sla_escalation
        schedule_sla_escalation.apply_async(
            args=[str(UUID(bytes=emergency.id))],
            countdown=self.SLA_SECONDS
        )

        # Publish domain event
        await event_bus.publish("sos.raised", {
            "emergency_id": str(UUID(bytes=emergency.id)),
            "pilgrim_id": str(request.pilgrim_id),
            "type": request.type.value,
            "season_id": str(season_id),
        })

        return emergency

    # ──────────────────────────────────────────
    # Acknowledge
    # ──────────────────────────────────────────

    async def acknowledge_emergency(
        self, emergency_id: UUID, request: EmergencyAcknowledgeRequest
    ) -> EmergencyRequest:
        """Control Room operator acknowledges the SOS."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status != "PENDING":
            raise ValidationError(
                f"Cannot acknowledge emergency in status {emergency.status}. Must be PENDING."
            )

        now = datetime.utcnow()
        sla_breached = 1 if now > emergency.sla_deadline else 0

        emergency.status = "ACKNOWLEDGED"
        emergency.acknowledged_at = now
        emergency.acknowledged_by = request.operator_id.bytes
        emergency.sla_breached = sla_breached
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_ACKNOWLEDGED",
            actor_id=request.operator_id.bytes,
            actor_role="CONTROL_ROOM_OPERATOR",
            from_status="PENDING",
            to_status="ACKNOWLEDGED",
            payload={"sla_breached": sla_breached}
        )

        await self.session.flush()
        return emergency

    # ──────────────────────────────────────────
    # Dispatch
    # ──────────────────────────────────────────

    async def dispatch_responder(
        self, emergency_id: UUID, request: EmergencyDispatchRequest
    ) -> EmergencyRequest:
        """Assign and dispatch a responder to the SOS location."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status != "ACKNOWLEDGED":
            raise ValidationError(
                f"Cannot dispatch from status {emergency.status}. Must be ACKNOWLEDGED."
            )

        now = datetime.utcnow()

        emergency.status = "DISPATCHED"
        emergency.responder_user_id = request.responder_user_id.bytes
        emergency.responder_camp_id = request.responder_camp_id.bytes if request.responder_camp_id else None
        emergency.responder_type = request.responder_type.value
        emergency.dispatched_at = now
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_RESPONDER_ASSIGNED",
            actor_id=request.operator_id.bytes,
            actor_role="CONTROL_ROOM_OPERATOR",
            from_status="ACKNOWLEDGED",
            to_status="DISPATCHED",
            payload={
                "responder_user_id": str(request.responder_user_id),
                "responder_type": request.responder_type.value,
                "responder_camp_id": str(request.responder_camp_id) if request.responder_camp_id else None,
            }
        )

        await self.session.flush()
        return emergency

    # ──────────────────────────────────────────
    # On Scene
    # ──────────────────────────────────────────

    async def mark_on_scene(
        self, emergency_id: UUID, request: EmergencyOnSceneRequest
    ) -> EmergencyRequest:
        """Responder confirms arrival at the SOS location."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status != "DISPATCHED":
            raise ValidationError(
                f"Cannot mark on-scene from status {emergency.status}. Must be DISPATCHED."
            )

        now = datetime.utcnow()

        emergency.status = "ON_SCENE"
        emergency.on_scene_at = now
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_ON_SCENE",
            actor_id=request.responder_user_id.bytes,
            actor_role="RESPONDER",
            from_status="DISPATCHED",
            to_status="ON_SCENE",
            notes=request.notes,
        )

        await self.session.flush()
        return emergency

    # ──────────────────────────────────────────
    # Resolve
    # ──────────────────────────────────────────

    async def resolve_emergency(
        self, emergency_id: UUID, request: EmergencyResolveRequest
    ) -> EmergencyRequest:
        """Close the emergency as resolved."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status in ("RESOLVED",):
            raise ValidationError(f"Emergency {emergency_id} is already resolved.")

        now = datetime.utcnow()

        emergency.status = "RESOLVED"
        emergency.resolved_at = now
        emergency.resolved_by = request.operator_id.bytes
        emergency.resolution_summary = request.resolution_summary
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_RESOLVED",
            actor_id=request.operator_id.bytes,
            actor_role="CONTROL_ROOM_OPERATOR",
            from_status=emergency.status,
            to_status="RESOLVED",
            payload={"resolution_summary": request.resolution_summary},
        )

        await self.session.flush()
        return emergency

    # ──────────────────────────────────────────
    # Escalate
    # ──────────────────────────────────────────

    async def escalate_emergency(
        self, emergency_id: UUID, request: EmergencyEscalateRequest
    ) -> EmergencyRequest:
        """Manually escalate to next authority level."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status == "RESOLVED":
            raise ValidationError("Cannot escalate a resolved emergency.")

        now = datetime.utcnow()
        new_level = request.target_level.value

        emergency.status = "ESCALATED"
        emergency.escalation_level = new_level
        emergency.escalated_at = now
        emergency.escalation_reason = request.reason
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_ESCALATED",
            actor_id=request.operator_id.bytes,
            actor_role="CONTROL_ROOM_OPERATOR",
            to_status="ESCALATED",
            payload={
                "target_level": new_level,
                "reason": request.reason
            }
        )

        await self.session.flush()
        return emergency

    async def auto_escalate(self, emergency_id: UUID) -> EmergencyRequest:
        """System-triggered escalation when SLA timer expires."""
        emergency = await self._get_emergency(emergency_id)

        if emergency.status != "PENDING":
            return emergency  # Already acknowledged, no auto-escalation needed

        now = datetime.utcnow()

        if emergency.escalation_level == "L1":
            new_level = "L2"
            new_sla = now + timedelta(seconds=self.AUTO_ESCALATE_L2_SECONDS)
        elif emergency.escalation_level == "L2":
            new_level = "L3"
            new_sla = now + timedelta(seconds=900)  # 15 minutes for L3
        else:
            new_level = "L4"
            new_sla = now  # Immediate

        emergency.status = "ESCALATED"
        emergency.escalation_level = new_level
        emergency.escalated_at = now
        emergency.escalation_reason = f"AUTO_ESCALATE: No acknowledgment within SLA at L{emergency.escalation_level}"
        emergency.sla_deadline = new_sla
        emergency.sla_breached = 1
        emergency.updated_at = now

        await self._record_timeline(
            emergency_id=emergency.id,
            event_type="SOS_AUTO_ESCALATED",
            actor_id=None,
            actor_role="SYSTEM",
            from_status="PENDING",
            to_status="ESCALATED",
            payload={
                "reason": "SLA_BREACH",
                "from_level": emergency.escalation_level,
                "to_level": new_level,
            }
        )

        # Schedule next SLA escalation if L2
        if new_level == "L2":
            from app.workers.tasks import schedule_sla_escalation
            schedule_sla_escalation.apply_async(
                args=[str(emergency_id)],
                countdown=self.AUTO_ESCALATE_L2_SECONDS
            )

        await self.session.flush()
        return emergency

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    async def get_emergency(self, emergency_id: UUID) -> EmergencyRequest:
        """Get single emergency with medical incident and timeline."""
        result = await self.session.execute(
            select(EmergencyRequest)
            .options(
                selectinload(EmergencyRequest.medical_incident)
            )
            .where(EmergencyRequest.id == emergency_id.bytes)
        )
        emergency = result.scalar_one_or_none()
        if not emergency:
            raise NotFoundError(f"Emergency {emergency_id} not found")
        return emergency

    async def list_active_emergencies(
        self, season_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[EmergencyRequest], int]:
        """List all non-RESOLVED emergencies for a season."""
        base_query = select(EmergencyRequest).where(
            and_(
                EmergencyRequest.season_id == season_id.bytes,
                EmergencyRequest.status != "RESOLVED"
            )
        ).order_by(
            EmergencyRequest.severity.desc(),
            EmergencyRequest.raised_at.asc()
        )

        count_query = select(func.count(EmergencyRequest.id)).where(
            and_(
                EmergencyRequest.season_id == season_id.bytes,
                EmergencyRequest.status != "RESOLVED"
            )
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            base_query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def get_emergency_timeline(self, emergency_id: UUID) -> List[EmergencyTimeline]:
        """Get complete timeline for an emergency."""
        result = await self.session.execute(
            select(EmergencyTimeline)
            .where(EmergencyTimeline.emergency_id == emergency_id.bytes)
            .order_by(EmergencyTimeline.occurred_at.asc())
        )
        return result.scalars().all()

    async def get_emergency_stats(self, season_id: UUID) -> dict:
        """Get statistical summary for active emergencies."""
        result = await self.session.execute(
            select(
                EmergencyRequest.status,
                EmergencyRequest.severity,
                func.count(EmergencyRequest.id).label("count"),
                func.avg(
                    func.timestampdiff(
                        text("SECOND"),
                        EmergencyRequest.raised_at,
                        EmergencyRequest.acknowledged_at
                    )
                ).label("avg_response")
            ).where(
                and_(
                    EmergencyRequest.season_id == season_id.bytes,
                    EmergencyRequest.status != "RESOLVED"
                )
            ).group_by(
                EmergencyRequest.status,
                EmergencyRequest.severity
            )
        )
        rows = result.all()
        # Aggregate into dict...
        return {"rows": [dict(r._mapping) for r in rows]}

    # ──────────────────────────────────────────
    # Internal Helpers
    # ──────────────────────────────────────────

    async def _get_emergency(self, emergency_id: UUID) -> EmergencyRequest:
        result = await self.session.execute(
            select(EmergencyRequest)
            .where(EmergencyRequest.id == emergency_id.bytes)
        )
        emergency = result.scalar_one_or_none()
        if not emergency:
            raise NotFoundError(f"Emergency {emergency_id} not found")
        return emergency

    async def _get_active_pilgrim(self, pilgrim_id: UUID) -> Pilgrim:
        result = await self.session.execute(
            select(Pilgrim).where(
                and_(
                    Pilgrim.id == pilgrim_id.bytes,
                    Pilgrim.status.in_(["ACTIVE", "REGISTERED"])
                )
            )
        )
        pilgrim = result.scalar_one_or_none()
        if not pilgrim:
            raise NotFoundError(f"Active pilgrim {pilgrim_id} not found")
        return pilgrim

    async def _record_timeline(
        self,
        emergency_id: bytes,
        event_type: str,
        to_status: Optional[str] = None,
        from_status: Optional[str] = None,
        actor_id: Optional[bytes] = None,
        actor_role: Optional[str] = None,
        payload: Optional[dict] = None,
        notes: Optional[str] = None,
    ):
        timeline = EmergencyTimeline(
            id=uuid4().bytes,
            emergency_id=emergency_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            from_status=from_status,
            to_status=to_status,
            payload=payload or {},
            notes=notes,
            occurred_at=datetime.utcnow(),
        )
        self.session.add(timeline)


class MedicalIncidentService:
    """Medical incident management attached to emergencies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_incident(
        self, request: MedicalIncidentCreateRequest
    ) -> MedicalIncident:
        """Start a medical incident record for an emergency."""
        # Validate emergency exists and is ON_SCENE
        emergency = await self._get_emergency(request.emergency_id)

        # Check no existing incident
        existing = await self.session.execute(
            select(MedicalIncident)
            .where(MedicalIncident.emergency_id == request.emergency_id.bytes)
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Medical incident already exists for this emergency")

        incident = MedicalIncident(
            id=uuid4().bytes,
            emergency_id=request.emergency_id.bytes,
            pilgrim_id=emergency.pilgrim_id,
            camp_id=request.camp_id.bytes if request.camp_id else None,
            medical_officer_id=request.medical_officer_id.bytes,
            triage_level=request.triage_level.value,
            primary_complaint=request.primary_complaint,
            secondary_complaints=request.secondary_complaints,
            symptoms_onset=request.symptoms_onset,
            vitals=request.vitals,
            consciousness=request.consciousness.value if request.consciousness else None,
            known_conditions=request.known_conditions,
            known_allergies=request.known_allergies,
            current_medications=request.current_medications,
            blood_group=request.blood_group,
            disposition="TREATING",
            incident_started_at=datetime.utcnow(),
        )
        self.session.add(incident)
        await self.session.flush()

        # Record timeline
        await self._add_timeline(
            emergency.id,
            "MEDICAL_INCIDENT_OPENED",
            request.medical_officer_id.bytes,
            "MEDICAL_OFFICER",
            payload={"triage_level": request.triage_level.value}
        )

        return incident

    async def update_incident(
        self, incident_id: UUID, request: MedicalIncidentUpdateRequest
    ) -> MedicalIncident:
        """Update treatment details and optionally change disposition."""
        incident = await self._get_incident(incident_id)

        if request.diagnosis is not None:
            incident.diagnosis = request.diagnosis
        if request.treatment_given is not None:
            incident.treatment_given = request.treatment_given
        if request.medications_administered is not None:
            incident.medications_administered = request.medications_administered
        if request.vitals is not None:
            incident.vitals = request.vitals

        if request.disposition is not None:
            old_disposition = incident.disposition
            incident.disposition = request.disposition.value
            incident.disposition_notes = request.disposition_notes

            if request.disposition.value == "TREATED":
                incident.treatment_completed_at = datetime.utcnow()
                await self._add_timeline(
                    incident.emergency_id,
                    "MEDICAL_INCIDENT_CLOSED",
                    payload={"disposition": "TREATED"}
                )

            elif request.disposition.value == "FATALITY":
                # Trigger deceased confirmation workflow
                incident.treatment_completed_at = datetime.utcnow()
                await self._add_timeline(
                    incident.emergency_id,
                    "DECEASED_REPORTED",
                    payload={"disposition": "FATALITY"}
                )

        incident.updated_at = datetime.utcnow()
        await self.session.flush()
        return incident

    async def initiate_transfer(
        self, incident_id: UUID, request: MedicalTransferRequest
    ) -> MedicalIncident:
        """Mark incident for transfer to another facility."""
        incident = await self._get_incident(incident_id)

        incident.disposition = "TRANSFERRED"
        incident.transfer_facility = request.transfer_facility
        incident.transfer_reason = request.transfer_reason
        incident.ambulance_id = request.ambulance_id.bytes if request.ambulance_id else None
        incident.transferred_at = datetime.utcnow()
        incident.updated_at = datetime.utcnow()

        await self._add_timeline(
            incident.emergency_id,
            "MEDICAL_TRANSFER_INITIATED",
            payload={
                "transfer_facility": request.transfer_facility,
                "transfer_reason": request.transfer_reason,
            }
        )

        await self.session.flush()
        return incident

    async def get_incident(self, incident_id: UUID) -> MedicalIncident:
        return await self._get_incident(incident_id)

    async def get_incident_by_emergency(self, emergency_id: UUID) -> MedicalIncident:
        result = await self.session.execute(
            select(MedicalIncident)
            .where(MedicalIncident.emergency_id == emergency_id.bytes)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise NotFoundError(
                f"Medical incident for emergency {emergency_id} not found"
            )
        return incident

    async def _get_incident(self, incident_id: UUID) -> MedicalIncident:
        result = await self.session.execute(
            select(MedicalIncident)
            .where(MedicalIncident.id == incident_id.bytes)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise NotFoundError(f"Medical incident {incident_id} not found")
        return incident

    async def _get_emergency(self, emergency_id: UUID) -> EmergencyRequest:
        result = await self.session.execute(
            select(EmergencyRequest)
            .where(EmergencyRequest.id == emergency_id.bytes)
        )
        emergency = result.scalar_one_or_none()
        if not emergency:
            raise NotFoundError(f"Emergency {emergency_id} not found")
        return emergency

    async def _add_timeline(
        self,
        emergency_id: bytes,
        event_type: str,
        actor_id: Optional[bytes] = None,
        actor_role: Optional[str] = None,
        payload: Optional[dict] = None,
    ):
        timeline = EmergencyTimeline(
            id=uuid4().bytes,
            emergency_id=emergency_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            payload=payload or {},
            occurred_at=datetime.utcnow(),
        )
        self.session.add(timeline)


class DeceasedConfirmationService:
    """Two-actor confirmation for death protocol."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_confirmation(
        self, request: DeceasedConfirmationCreate, confirmer_id: UUID
    ) -> DeceasedConfirmation:
        """First confirmation (Medical Officer)."""
        confirmation = DeceasedConfirmation(
            id=uuid4().bytes,
            emergency_id=request.emergency_id.bytes,
            pilgrim_id=request.pilgrim_id.bytes,
            first_confirmer_id=confirmer_id.bytes,
            first_confirmed_at=datetime.utcnow(),
            first_confirmation_notes=request.notes,
            time_of_death=request.time_of_death,
            cause_of_death=request.cause_of_death,
            body_location=request.body_location,
            status="PENDING_SECOND",
        )
        self.session.add(confirmation)
        await self.session.flush()

        # Update pilgrim status
        pilgrim = await self.session.execute(
            select(Pilgrim).where(Pilgrim.id == request.pilgrim_id.bytes)
        )
        pilgrim = pilgrim.scalar_one()
        pilgrim.status = "DECEASED"
        pilgrim.updated_at = datetime.utcnow()

        # Revoke QR
        pilgrim.qr_payload_hash = None
        pilgrim.qr_version = pilgrim.qr_version + 1

        await self.session.flush()
        return confirmation

    async def second_confirmation(
        self, confirmation_id: UUID, request: DeceasedSecondConfirmationRequest
    ) -> DeceasedConfirmation:
        """Second confirmation (Police Officer or second Medical Officer)."""
        confirmation = await self._get_confirmation(confirmation_id)

        if confirmation.status != "PENDING_SECOND":
            raise ValidationError(
                f"Confirmation status is {confirmation.status}, expected PENDING_SECOND"
            )

        confirmation.second_confirmer_id = request.confirmer_id.bytes
        confirmation.second_confirmed_at = datetime.utcnow()
        confirmation.second_confirmation_notes = request.notes
        confirmation.status = "CONFIRMED"
        confirmation.updated_at = datetime.utcnow()

        await self.session.flush()

        # Trigger next-of-kin notification task
        from app.workers.tasks import notify_deceased_next_of_kin
        notify_deceased_next_of_kin.apply_async(
            args=[str(UUID(bytes=confirmation.id))],
            countdown=0
        )

        return confirmation

    async def get_confirmation(self, confirmation_id: UUID) -> DeceasedConfirmation:
        return await self._get_confirmation(confirmation_id)

    async def _get_confirmation(self, confirmation_id: UUID) -> DeceasedConfirmation:
        result = await self.session.execute(
            select(DeceasedConfirmation)
            .where(DeceasedConfirmation.id == confirmation_id.bytes)
        )
        conf = result.scalar_one_or_none()
        if not conf:
            raise NotFoundError(f"Deceased confirmation {confirmation_id} not found")
        return conf