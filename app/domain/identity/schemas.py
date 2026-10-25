"""
Identity domain Pydantic schemas.

Request/response validation for Pilgrim, Group, GroupMember, User, and Role operations.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class PilgrimStatus(str, Enum):
    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    MISSING = "MISSING"
    COMPLETED = "COMPLETED"
    REVOKED = "REVOKED"
    DECEASED = "DECEASED"


class RegistrationChannel(str, Enum):
    SELF_APP = "SELF_APP"
    COUNTER = "COUNTER"
    BULK_IMPORT = "BULK_IMPORT"


class GroupStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FRAGMENTED = "FRAGMENTED"
    COMPLETED = "COMPLETED"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DEACTIVATED = "DEACTIVATED"


class JoinMethod(str, Enum):
    QR_SCAN = "QR_SCAN"
    CODE_ENTRY = "CODE_ENTRY"
    OPERATOR_ASSIGNED = "OPERATOR_ASSIGNED"


# ──────────────────────────────────────────────
# Pilgrim Registration (Multi-Step Flow)
# ──────────────────────────────────────────────

class PilgrimInitiateRequest(BaseModel):
    """Step 1: Phone verification to start registration."""
    phone: str = Field(
        ...,
        pattern=r"^[6-9]\d{9}$",
        description="10-digit Indian mobile number",
        example="9876543210",
    )
    season_id: UUID = Field(..., description="Active season ID")


class PilgrimInitiateResponse(BaseModel):
    """Response after phone verification."""
    pilgrim_id: UUID
    status: str = "OTP_SENT"
    message: str = "OTP sent to phone number"


class PilgrimVerifyOTPRequest(BaseModel):
    """Verify OTP sent to phone."""
    pilgrim_id: UUID
    otp: str = Field(..., pattern=r"^\d{6}$", description="6-digit OTP")


class PilgrimProfileRequest(BaseModel):
    """Step 2: Personal and emergency contact details."""
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        description="Pilgrim's full name (Hindi or English)",
        example="राम कुमार",
    )
    age: Optional[int] = Field(None, ge=5, le=120, description="Age in years")
    gender: Optional[str] = Field(None, description="male, female, other")
    emergency_contact_name: Optional[str] = Field(
        None, min_length=2, max_length=150,
        description="Emergency contact person's name",
    )
    emergency_contact_phone: Optional[str] = Field(
        None,
        pattern=r"^[6-9]\d{9}$",
        description="Emergency contact phone number",
    )
    emergency_contact_relation: Optional[str] = Field(
        None, max_length=50,
        description="Relationship: father, mother, spouse, brother, etc.",
    )

    @validator("emergency_contact_phone")
    def phone_must_differ_from_pilgrim(cls, v: str, values: dict) -> str:
        # This is validated at service level since we don't have pilgrim phone here
        return v


class PilgrimMedicalRequest(BaseModel):
    """Step 3: Medical information."""
    blood_group: Optional[str] = Field(
        None,
        pattern=r"^(A|B|AB|O)[+-]$",
        description="Blood group: A+, A-, B+, B-, AB+, AB-, O+, O-",
    )
    medical_flags: Optional[List[str]] = Field(
        None,
        description="Known medical conditions: ['diabetes', 'hypertension', 'asthma']",
    )
    allergies: Optional[List[str]] = Field(
        None,
        description="Known allergies: ['penicillin', 'sulfa']",
    )
    current_medications: Optional[List[str]] = Field(
        None,
        description="Current medications",
    )


class PilgrimRouteSelectionRequest(BaseModel):
    """Step 4: Select journey route."""
    route_id: UUID = Field(..., description="Selected route ID")


class PilgrimCompleteRegistrationRequest(BaseModel):
    """Single-step registration for counter-assisted flow."""
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    full_name: str = Field(..., min_length=2, max_length=150)
    age: Optional[int] = Field(None, ge=5, le=120)
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    medical_flags: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    route_id: UUID


# ──────────────────────────────────────────────
# Pilgrim Response Schemas
# ──────────────────────────────────────────────

class PilgrimResponse(BaseModel):
    """Complete pilgrim profile."""
    id: UUID
    season_id: UUID
    full_name: str
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    medical_flags: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    photo_url: Optional[str] = None
    status: str
    route_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    registration_channel: Optional[str] = None
    qr_version: int
    qr_issued_at: Optional[datetime] = None
    qr_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PilgrimSummaryResponse(BaseModel):
    """Abbreviated pilgrim info for list views."""
    id: UUID
    full_name: str
    phone: Optional[str] = None
    blood_group: Optional[str] = None
    status: str
    photo_url: Optional[str] = None
    group_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class PilgrimListResponse(BaseModel):
    """Paginated list of pilgrims."""
    items: List[PilgrimResponse]
    total: int
    page: int
    page_size: int


class PilgrimSearchRequest(BaseModel):
    """Search pilgrims by various criteria."""
    phone: Optional[str] = None
    name: Optional[str] = None
    status: Optional[PilgrimStatus] = None
    group_id: Optional[UUID] = None
    route_id: Optional[UUID] = None
    blood_group: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


class PilgrimStatusUpdateRequest(BaseModel):
    """Update pilgrim status."""
    status: PilgrimStatus
    reason: Optional[str] = Field(None, max_length=255)


class PilgrimQRRevokeRequest(BaseModel):
    """Revoke a pilgrim's QR code."""
    reason: str = Field(..., max_length=255, description="Reason for revocation")
    operator_id: Optional[UUID] = None


class PilgrimQRIssueRequest(BaseModel):
    """Issue a new QR after revocation."""
    operator_id: Optional[UUID] = None


class PilgrimBulkRegisterRequest(BaseModel):
    """Bulk registration of multiple pilgrims."""
    pilgrims: List[PilgrimCompleteRegistrationRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of pilgrims to register",
    )


class PilgrimBulkRegisterResponse(BaseModel):
    """Result of bulk registration."""
    success_count: int
    failure_count: int
    errors: List[Dict[str, Any]] = []
    pilgrim_ids: List[UUID] = []


# ──────────────────────────────────────────────
# Group Request Schemas
# ──────────────────────────────────────────────

class GroupCreateRequest(BaseModel):
    """Create a new pilgrim group."""
    leader_id: UUID = Field(..., description="Pilgrim ID of group leader")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Optional group name")
    season_id: UUID = Field(..., description="Active season ID")


class GroupJoinRequest(BaseModel):
    """Join an existing group."""
    group_code: str = Field(
        ...,
        min_length=6,
        max_length=10,
        description="Group code (case-insensitive)",
    )
    pilgrim_id: UUID = Field(..., description="Pilgrim ID of joining member")
    join_method: JoinMethod = Field(JoinMethod.CODE_ENTRY, description="How the pilgrim is joining")


class GroupLeaveRequest(BaseModel):
    """Leave current group."""
    pilgrim_id: UUID
    reason: Optional[str] = Field(None, max_length=255)


class GroupTransferLeadershipRequest(BaseModel):
    """Transfer group leadership to another member."""
    new_leader_id: UUID = Field(..., description="Pilgrim ID of new leader")
    reason: Optional[str] = Field(None, max_length=255)


# ──────────────────────────────────────────────
# Group Response Schemas
# ──────────────────────────────────────────────

class GroupMemberResponse(BaseModel):
    """Group member details with last known status."""
    pilgrim_id: UUID
    full_name: str
    photo_url: Optional[str] = None
    blood_group: Optional[str] = None
    medical_flags: Optional[List[str]] = None
    last_checkin_at: Optional[datetime] = None
    last_checkpoint_name: Optional[str] = None
    journey_status: Optional[str] = None
    membership_status: str
    joined_at: datetime

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    """Group details."""
    id: UUID
    season_id: UUID
    group_code: str
    leader_id: UUID
    leader_name: Optional[str] = None
    name: Optional[str] = None
    status: str
    max_members: int
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupDetailResponse(GroupResponse):
    """Group with member list."""
    members: List[GroupMemberResponse] = []


class GroupListResponse(BaseModel):
    """Paginated list of groups."""
    items: List[GroupResponse]
    total: int
    page: int
    page_size: int


class GroupMembershipHistoryResponse(BaseModel):
    """History of group membership changes."""
    pilgrim_id: UUID
    pilgrim_name: str
    action: str
    timestamp: datetime
    details: Optional[str] = None


# ──────────────────────────────────────────────
# Role Schemas
# ──────────────────────────────────────────────

class RoleCreateRequest(BaseModel):
    """Create a new system role."""
    name: str = Field(..., min_length=2, max_length=50)
    permissions: List[str] = Field(..., min_length=1, description="List of permission strings")
    description: Optional[str] = Field(None, max_length=255)


class RoleResponse(BaseModel):
    """Role details."""
    id: UUID
    name: str
    permissions: List[str]
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """List of all roles."""
    items: List[RoleResponse]
    total: int


# ──────────────────────────────────────────────
# User Schemas
# ──────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    """Create a new system user."""
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    pin: str = Field(..., pattern=r"^\d{4}$", description="4-digit PIN")
    full_name: str = Field(..., min_length=2, max_length=150)
    role_id: UUID


class UserResponse(BaseModel):
    """User details (never includes PIN hash)."""
    id: UUID
    role_id: UUID
    role_name: Optional[str] = None
    phone: str
    full_name: Optional[str] = None
    status: str
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated list of users."""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserStatusUpdateRequest(BaseModel):
    """Suspend or reactivate a user."""
    status: UserStatus
    reason: Optional[str] = Field(None, max_length=255)


class UserLoginRequest(BaseModel):
    """User login with phone and PIN."""
    phone: str = Field(..., pattern=r"^[6-9]\d{9}$")
    pin: str = Field(..., pattern=r"^\d{4}$")


class UserLoginResponse(BaseModel):
    """JWT token on successful login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 43200  # 12 hours in seconds
    user: UserResponse