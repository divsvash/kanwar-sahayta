"""
Identity domain service layer.

Business logic for:
- Pilgrim registration (multi-step and single-step)
- Group management (create, join, leave, transfer leadership)
- User and Role administration
"""

from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.identity.models import Pilgrim, Group, GroupMember, User, Role
from app.domain.identity.repository import (
    PilgrimRepository, GroupRepository, GroupMemberRepository,
    UserRepository, RoleRepository,
)
from app.domain.identity.schemas import (
    PilgrimInitiateRequest, PilgrimProfileRequest,
    PilgrimMedicalRequest, PilgrimRouteSelectionRequest,
    PilgrimCompleteRegistrationRequest, PilgrimStatusUpdateRequest,
    PilgrimQRRevokeRequest, GroupCreateRequest, GroupJoinRequest,
    GroupLeaveRequest, GroupTransferLeadershipRequest,
    UserCreateRequest, UserLoginRequest, UserStatusUpdateRequest,
    RoleCreateRequest,
)
from app.core.exceptions import (
    NotFoundError, ValidationError, DuplicateError, ConflictError,
    ForbiddenError, UnauthorizedError,
)


class PilgrimService:
    """
    Manages pilgrim registration and lifecycle.

    Registration flow:
    1. Initiate (phone verification)
    2. Profile (personal + emergency contact)
    3. Medical (blood group, conditions, allergies)
    4. Route selection
    5. QR issuance (handled separately)
    """

    MAX_GROUP_SIZE = 50

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PilgrimRepository(session)
        self.group_repo = GroupRepository(session)
        self.group_member_repo = GroupMemberRepository(session)

    # ──────────────────────────────────────────
    # Registration Flow
    # ──────────────────────────────────────────

    async def initiate_registration(
        self, request: PilgrimInitiateRequest
    ) -> Pilgrim:
        """Step 1: Phone verification. Creates pilgrim in REGISTERED state."""
        # Check duplicate phone in active season
        existing = await self.repo.get_by_phone_and_season(
            request.phone, request.season_id
        )
        if existing:
            raise DuplicateError(
                f"Phone {request.phone} is already registered in this season",
                error_code="DUPLICATE_PHONE",
                details={"existing_pilgrim_id": str(UUID(bytes=existing.id))},
            )

        pilgrim = Pilgrim(
            id=uuid4().bytes,
            season_id=request.season_id.bytes,
            phone=request.phone,
            status="REGISTERED",
            registration_channel="SELF_APP",
        )
        return await self.repo.create(pilgrim)

    async def complete_profile(
        self, pilgrim_id: UUID, request: PilgrimProfileRequest
    ) -> Pilgrim:
        """Step 2: Personal and emergency contact details."""
        pilgrim = await self._get_pilgrim(pilgrim_id)

        if pilgrim.status not in ("REGISTERED",):
            raise ValidationError(
                f"Pilgrim status is {pilgrim.status}, expected REGISTERED",
                error_code="INVALID_STATUS",
            )

        pilgrim.full_name = request.full_name
        pilgrim.age = request.age
        pilgrim.gender = request.gender
        pilgrim.emergency_contact_name = request.emergency_contact_name
        pilgrim.emergency_contact_phone = request.emergency_contact_phone
        pilgrim.emergency_contact_relation = request.emergency_contact_relation
        pilgrim.updated_at = datetime.utcnow()

        return await self.repo.update(pilgrim)

    async def complete_medical(
        self, pilgrim_id: UUID, request: PilgrimMedicalRequest
    ) -> Pilgrim:
        """Step 3: Medical information."""
        pilgrim = await self._get_pilgrim(pilgrim_id)
        pilgrim.blood_group = request.blood_group
        pilgrim.medical_flags = request.medical_flags
        pilgrim.allergies = request.allergies
        pilgrim.current_medications = request.current_medications
        pilgrim.updated_at = datetime.utcnow()
        return await self.repo.update(pilgrim)

    async def select_route(
        self, pilgrim_id: UUID, request: PilgrimRouteSelectionRequest
    ) -> Pilgrim:
        """Step 4: Select journey route."""
        pilgrim = await self._get_pilgrim(pilgrim_id)
        pilgrim.route_id = request.route_id.bytes
        pilgrim.status = "ACTIVE"
        pilgrim.updated_at = datetime.utcnow()
        return await self.repo.update(pilgrim)

    async def complete_registration(
        self, request: PilgrimCompleteRegistrationRequest, season_id: UUID
    ) -> Pilgrim:
        """Single-step counter-assisted registration."""
        pilgrim = Pilgrim(
            id=uuid4().bytes,
            season_id=season_id.bytes,
            phone=request.phone,
            full_name=request.full_name,
            age=request.age,
            gender=request.gender,
            blood_group=request.blood_group,
            medical_flags=request.medical_flags,
            allergies=request.allergies,
            current_medications=request.current_medications,
            emergency_contact_name=request.emergency_contact_name,
            emergency_contact_phone=request.emergency_contact_phone,
            emergency_contact_relation=request.emergency_contact_relation,
            route_id=request.route_id.bytes,
            status="ACTIVE",
            registration_channel="COUNTER",
        )
        return await self.repo.create(pilgrim)

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    async def get_pilgrim(self, pilgrim_id: UUID) -> Pilgrim:
        return await self._get_pilgrim(pilgrim_id)

    async def list_pilgrims(
        self,
        season_id: UUID,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        group_id: Optional[UUID] = None,
        route_id: Optional[UUID] = None,
    ) -> Tuple[List[Pilgrim], int]:
        return await self.repo.list_by_season(
            season_id, page, page_size, status, group_id, route_id
        )

    async def search_pilgrims_by_name(
        self, season_id: UUID, name: str, limit: int = 20
    ) -> List[Pilgrim]:
        return await self.repo.search_by_name(season_id, name, limit)

    async def update_status(
        self, pilgrim_id: UUID, request: PilgrimStatusUpdateRequest
    ) -> Pilgrim:
        pilgrim = await self._get_pilgrim(pilgrim_id)
        pilgrim.status = request.status.value
        pilgrim.updated_at = datetime.utcnow()
        return await self.repo.update(pilgrim)

    async def revoke_qr(
        self, pilgrim_id: UUID, request: PilgrimQRRevokeRequest
    ) -> Pilgrim:
        pilgrim = await self._get_pilgrim(pilgrim_id)
        pilgrim.status = "REVOKED"
        pilgrim.qr_payload_hash = None
        pilgrim.qr_version = pilgrim.qr_version + 1
        pilgrim.updated_at = datetime.utcnow()
        return await self.repo.update(pilgrim)

    # ──────────────────────────────────────────
    # Group Management
    # ──────────────────────────────────────────

    async def create_group(self, request: GroupCreateRequest) -> Group:
        """Create a new group with the requesting pilgrim as leader."""
        leader = await self._get_active_pilgrim(request.leader_id)

        if leader.group_id:
            raise ConflictError(
                "Pilgrim is already in a group. Leave current group first.",
                error_code="ALREADY_IN_GROUP",
            )

        group_code = await self._generate_unique_group_code(request.season_id)

        group = Group(
            id=uuid4().bytes,
            season_id=request.season_id.bytes,
            group_code=group_code,
            leader_id=request.leader_id.bytes,
            name=request.name,
            status="ACTIVE",
        )
        group = await self.group_repo.create(group)

        # Add leader as first member
        member = GroupMember(
            id=uuid4().bytes,
            group_id=group.id,
            pilgrim_id=leader.id,
            join_method="CODE_ENTRY",
            status="ACTIVE",
        )
        await self.group_member_repo.add_member(member)

        # Update pilgrim's group_id
        leader.group_id = group.id
        leader.updated_at = datetime.utcnow()
        await self.repo.update(leader)

        return group

    async def join_group(self, request: GroupJoinRequest) -> GroupMember:
        """Join an existing group by code."""
        pilgrim = await self._get_active_pilgrim(request.pilgrim_id)

        if pilgrim.group_id:
            raise ConflictError(
                "Already in a group. Leave current group first.",
                error_code="ALREADY_IN_GROUP",
            )

        # Find group by code (need season_id from pilgrim)
        group = await self.group_repo.get_by_code_and_season(
            request.group_code,
            UUID(bytes=pilgrim.season_id),
        )
        if not group:
            raise NotFoundError(
                f"Group with code '{request.group_code}' not found",
                error_code="GROUP_NOT_FOUND",
            )

        # Check capacity
        active_count = await self.group_member_repo.count_active_members(
            UUID(bytes=group.id)
        )
        if active_count >= self.MAX_GROUP_SIZE:
            raise ValidationError(
                f"Group is full (max {self.MAX_GROUP_SIZE} members)",
                error_code="GROUP_FULL",
            )

        member = GroupMember(
            id=uuid4().bytes,
            group_id=group.id,
            pilgrim_id=pilgrim.id,
            join_method=request.join_method.value,
            status="ACTIVE",
        )
        member = await self.group_member_repo.add_member(member)

        pilgrim.group_id = group.id
        pilgrim.updated_at = datetime.utcnow()
        await self.repo.update(pilgrim)

        return member

    async def leave_group(self, request: GroupLeaveRequest) -> GroupMember:
        """Leave current group."""
        pilgrim = await self._get_active_pilgrim(request.pilgrim_id)

        if not pilgrim.group_id:
            raise ValidationError("Pilgrim is not in a group")

        group_id = UUID(bytes=pilgrim.group_id)
        group = await self.group_repo.get_by_id(group_id)

        # Leader cannot leave without transferring
        if UUID(bytes=group.leader_id) == request.pilgrim_id:
            raise ValidationError(
                "Group leader cannot leave. Transfer leadership first.",
                error_code="LEADER_CANNOT_LEAVE",
            )

        membership = await self.group_member_repo.get_active_membership(
            group_id, request.pilgrim_id
        )
        if not membership:
            raise NotFoundError("Active membership not found")

        membership.left_at = datetime.utcnow()
        membership.status = "LEFT"
        await self.group_member_repo.update(membership)

        pilgrim.group_id = None
        pilgrim.updated_at = datetime.utcnow()
        await self.repo.update(pilgrim)

        return membership

    async def transfer_leadership(
        self, group_id: UUID, request: GroupTransferLeadershipRequest
    ) -> Group:
        """Transfer group leadership to another active member."""
        group = await self.group_repo.get_by_id(group_id)

        # Verify new leader is an active member
        membership = await self.group_member_repo.get_active_membership(
            group_id, request.new_leader_id
        )
        if not membership:
            raise ValidationError(
                "New leader must be an active group member",
                error_code="NOT_GROUP_MEMBER",
            )

        group.leader_id = request.new_leader_id.bytes
        group.updated_at = datetime.utcnow()
        return await self.group_repo.update(group)

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    async def _get_pilgrim(self, pilgrim_id: UUID) -> Pilgrim:
        pilgrim = await self.repo.get_by_id(pilgrim_id)
        if not pilgrim:
            raise NotFoundError(f"Pilgrim {pilgrim_id} not found")
        return pilgrim

    async def _get_active_pilgrim(self, pilgrim_id: UUID) -> Pilgrim:
        pilgrim = await self.repo.get_active_pilgrim(pilgrim_id)
        if not pilgrim:
            raise NotFoundError(
                f"Active pilgrim {pilgrim_id} not found",
                error_code="PILGRIM_NOT_ACTIVE",
            )
        return pilgrim

    async def _generate_unique_group_code(self, season_id: UUID) -> str:
        """Generate a unique 6-char alphanumeric group code."""
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        # Remove ambiguous characters
        chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("1", "").replace("L", "")

        for _ in range(10):  # Max attempts
            code = "".join(random.choices(chars, k=6))
            existing = await self.group_repo.get_by_code_and_season(code, season_id)
            if not existing:
                return code

        raise ValidationError("Could not generate unique group code. Please try again.")


class UserService:
    """Manages system user accounts and authentication."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def create_user(self, request: UserCreateRequest) -> User:
        """Create a new system user."""
        # Check duplicate phone
        existing = await self.repo.get_by_phone(request.phone)
        if existing:
            raise DuplicateError(
                f"User with phone {request.phone} already exists",
                error_code="DUPLICATE_PHONE",
            )

        # Verify role exists
        role = await self.role_repo.get_by_id(request.role_id)
        if not role:
            raise NotFoundError(f"Role {request.role_id} not found")

        # Hash PIN
        import bcrypt
        pin_hash = bcrypt.hashpw(
            request.pin.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        user = User(
            id=uuid4().bytes,
            role_id=request.role_id.bytes,
            phone=request.phone,
            pin_hash=pin_hash,
            full_name=request.full_name,
            status="ACTIVE",
        )
        return await self.repo.create(user)

    async def authenticate(self, request: UserLoginRequest) -> User:
        """Authenticate user with phone and PIN."""
        user = await self.repo.get_by_phone(request.phone)
        if not user:
            raise UnauthorizedError("Invalid phone or PIN")

        if user.status != "ACTIVE":
            raise ForbiddenError(f"Account is {user.status}")

        import bcrypt
        if not bcrypt.checkpw(
            request.pin.encode("utf-8"),
            user.pin_hash.encode("utf-8"),
        ):
            raise UnauthorizedError("Invalid phone or PIN")

        user.last_login_at = datetime.utcnow()
        await self.repo.update(user)

        return user

    async def get_user(self, user_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def list_users(
        self, page: int = 1, page_size: int = 50, status: Optional[str] = None
    ) -> Tuple[List[User], int]:
        return await self.repo.list_all(page, page_size, status)

    async def update_status(
        self, user_id: UUID, request: UserStatusUpdateRequest
    ) -> User:
        user = await self.get_user(user_id)
        user.status = request.status.value
        user.updated_at = datetime.utcnow()
        return await self.repo.update(user)


class RoleService:
    """Manages system roles and permissions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RoleRepository(session)

    async def create_role(self, request: RoleCreateRequest) -> Role:
        existing = await self.repo.get_by_name(request.name)
        if existing:
            raise DuplicateError(f"Role '{request.name}' already exists")

        role = Role(
            id=uuid4().bytes,
            name=request.name,
            permissions=request.permissions,
            description=request.description,
        )
        return await self.repo.create(role)

    async def get_role(self, role_id: UUID) -> Role:
        role = await self.repo.get_by_id(role_id)
        if not role:
            raise NotFoundError(f"Role {role_id} not found")
        return role

    async def list_roles(self) -> List[Role]:
        return await self.repo.list_all()