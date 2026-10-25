"""
Identity domain models.

Core identity system for Kanwar Sahayata.
Answers: Who is every pilgrim? Who operates the system?
How do pilgrims travel together?
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Enum, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, Boolean, Text,
)
from app.core.db_types import BINARY
from sqlalchemy.orm import relationship
from app.core.database import Base


class Role(Base):
    """
    System roles with permission sets.

    Defines what each user type can do in the system.
    Permissions are stored as a JSON array of strings.
    """

    __tablename__ = "roles"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    name = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="Role name: pilgrim, camp_operator, medical_officer, control_room_operator, admin",
    )
    permissions = Column(
        JSON,
        nullable=False,
        comment="Array of permission strings: ['pilgrim:read', 'presence:write', ...]",
    )
    description = Column(
        String(255),
        nullable=True,
        comment="Human-readable description of this role",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="role", lazy="selectin")

    __table_args__ = (
        {"comment": "System roles with granular permissions"},
    )

    def __repr__(self):
        return f"<Role(id={self.id.hex()}, name='{self.name}')>"


class User(Base):
    """
    System operators: camp operators, medical officers, control room staff.

    Authenticated via device-bound certificate + PIN for field operators.
    Control room and admin users use standard JWT authentication.
    """

    __tablename__ = "users"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    role_id = Column(
        BINARY(16),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        comment="FK to roles table",
    )
    phone = Column(
        String(15),
        nullable=False,
        unique=True,
        comment="Mobile number used as username",
    )
    pin_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hash of 4-digit PIN for field operators",
    )
    full_name = Column(
        String(150),
        nullable=True,
        comment="User's full name",
    )
    status = Column(
        Enum("ACTIVE", "SUSPENDED", "DEACTIVATED", name="user_status"),
        nullable=False,
        default="ACTIVE",
        comment="Account status",
    )
    last_login_at = Column(
        DateTime,
        nullable=True,
        comment="Last successful login timestamp",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = relationship("Role", back_populates="users", lazy="joined")

    __table_args__ = (
        Index("ix_users_phone", "phone"),
        Index("ix_users_status", "status"),
        Index("ix_users_role", "role_id"),
        {"comment": "System users - operators and administrators"},
    )

    def __repr__(self):
        return f"<User(id={self.id.hex()}, phone='{self.phone}', status='{self.status}')>"


class Pilgrim(Base):
    """
    The core entity - every registered pilgrim in the Yatra.

    Contains personal details, medical information, emergency contacts,
    and QR identity lifecycle state. Season-scoped via season_id.
    """

    __tablename__ = "pilgrims"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(
        BINARY(16),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Season scope - which Yatra year",
    )
    group_id = Column(
        BINARY(16),
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
        comment="Current group membership (NULL if solo)",
    )

    # Personal details
    full_name = Column(String(150), nullable=True, comment="Pilgrim's full name (NULL until the profile step completes)")
    phone = Column(String(15), nullable=True, comment="Mobile number (may be NULL for dependents)")
    age = Column(Integer, nullable=True, comment="Age in years")
    gender = Column(String(10), nullable=True, comment="Gender: male, female, other")

    # Medical information
    blood_group = Column(
        String(5),
        nullable=True,
        comment="Blood group: A+, A-, B+, B-, AB+, AB-, O+, O-",
    )
    medical_flags = Column(
        JSON,
        nullable=True,
        comment="Array of medical conditions: ['diabetes', 'hypertension', 'asthma']",
    )
    allergies = Column(
        JSON,
        nullable=True,
        comment="Array of known allergies: ['penicillin', 'sulfa']",
    )
    current_medications = Column(
        JSON,
        nullable=True,
        comment="Array of current medications",
    )

    # Emergency contact
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_phone = Column(String(15), nullable=True)
    emergency_contact_relation = Column(String(50), nullable=True)

    # Photo
    photo_url = Column(
        String(500),
        nullable=True,
        comment="MinIO object key for registration photo",
    )

    # QR Identity
    qr_payload_hash = Column(
        String(64),
        nullable=True,
        comment="SHA-256 hash of the last issued QR payload for integrity verification",
    )
    qr_version = Column(
        Integer,
        nullable=False,
        default=1,
        comment="Monotonically increasing version of QR payload",
    )
    qr_issued_at = Column(
        DateTime,
        nullable=True,
        comment="When the current QR was issued",
    )
    qr_expires_at = Column(
        DateTime,
        nullable=True,
        comment="When the current QR expires (end of season typically)",
    )

    # Journey reference
    route_id = Column(
        BINARY(16),
        ForeignKey("routes.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Declared route for this pilgrim's journey",
    )

    # Status
    status = Column(
        Enum(
            "REGISTERED",      # Profile created, QR pending
            "ACTIVE",          # QR issued, can check in
            "MISSING",         # Formally reported missing
            "COMPLETED",       # Reached destination
            "REVOKED",         # QR revoked (lost, compromised)
            "DECEASED",        # Death confirmed
            name="pilgrim_status",
        ),
        nullable=False,
        default="REGISTERED",
        comment="Current pilgrim status",
    )

    # Registration metadata
    registration_channel = Column(
        Enum("SELF_APP", "COUNTER", "BULK_IMPORT", name="registration_channel"),
        nullable=True,
        default="SELF_APP",
        comment="How the pilgrim registered",
    )
    registered_by_user_id = Column(
        BINARY(16),
        nullable=True,
        comment="User ID who registered this pilgrim (for counter registrations)",
    )

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    group = relationship("Group", back_populates="members", foreign_keys=[group_id], lazy="selectin")
    route = relationship("Route", lazy="joined")
    journey = relationship("Journey", back_populates="pilgrim", uselist=False, lazy="selectin")

    __table_args__ = (
        Index("ix_pilgrims_season", "season_id"),
        Index("ix_pilgrims_status", "status"),
        Index("ix_pilgrims_phone_season", "phone", "season_id"),
        Index("ix_pilgrims_group", "group_id"),
        Index("ix_pilgrims_route", "route_id"),
        Index("ix_pilgrims_qr_expires", "qr_expires_at"),
        Index("ix_pilgrims_name", "full_name"),
        {"comment": "Core pilgrim entity - one row per registered pilgrim per season"},
    )

    def __repr__(self):
        return f"<Pilgrim(id={self.id.hex()}, name='{self.full_name}', status='{self.status}')>"


class Group(Base):
    """
    Operational safety structure - not a social feature.

    Groups allow tracking pilgrims traveling together.
    A group has one leader and up to 50 members.
    """

    __tablename__ = "groups"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    season_id = Column(
        BINARY(16),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Season scope",
    )
    group_code = Column(
        String(10),
        nullable=False,
        comment="6-character alphanumeric code for joining (case-insensitive)",
    )
    leader_id = Column(
        BINARY(16),
        ForeignKey("pilgrims.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Group leader pilgrim ID",
    )
    name = Column(
        String(100),
        nullable=True,
        comment="Optional group name set by leader",
    )
    status = Column(
        Enum("ACTIVE", "FRAGMENTED", "COMPLETED", name="group_status"),
        nullable=False,
        default="ACTIVE",
        comment="ACTIVE=traveling together, FRAGMENTED=spread across segments, COMPLETED=journey done",
    )
    max_members = Column(
        Integer,
        nullable=False,
        default=50,
        comment="Maximum allowed members (configurable up to 50)",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    leader = relationship("Pilgrim", foreign_keys=[leader_id], lazy="joined")
    members = relationship(
        "Pilgrim",
        back_populates="group",
        foreign_keys="Pilgrim.group_id",
        lazy="selectin",
    )
    membership_records = relationship(
        "GroupMember",
        back_populates="group",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("season_id", "group_code", name="uq_group_code_season"),
        Index("ix_groups_season", "season_id"),
        Index("ix_groups_status", "status"),
        Index("ix_groups_leader", "leader_id"),
        {"comment": "Pilgrim travel groups - operational safety structures"},
    )

    def __repr__(self):
        return f"<Group(id={self.id.hex()}, code='{self.group_code}', status='{self.status}')>"


class GroupMember(Base):
    """
    Explicit join table for group membership with audit trail.

    Tracks when pilgrims join and leave groups.
    Enables historical membership analysis and supports
    the group fragmentation detection algorithm.
    """

    __tablename__ = "group_members"

    id = Column(BINARY(16), primary_key=True, default=lambda: uuid.uuid4().bytes)
    group_id = Column(
        BINARY(16),
        ForeignKey("groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pilgrim_id = Column(
        BINARY(16),
        ForeignKey("pilgrims.id", ondelete="RESTRICT"),
        nullable=False,
    )
    joined_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When pilgrim joined the group",
    )
    left_at = Column(
        DateTime,
        nullable=True,
        comment="When pilgrim left the group (NULL if still active)",
    )
    join_method = Column(
        Enum("QR_SCAN", "CODE_ENTRY", "OPERATOR_ASSIGNED", name="join_method"),
        nullable=False,
        default="CODE_ENTRY",
        comment="How the pilgrim joined the group",
    )
    status = Column(
        Enum("ACTIVE", "LEFT", "REMOVED", name="membership_status"),
        nullable=False,
        default="ACTIVE",
        comment="Current membership status",
    )

    # Relationships
    group = relationship("Group", back_populates="membership_records")
    pilgrim = relationship("Pilgrim", foreign_keys=[pilgrim_id], lazy="joined")

    __table_args__ = (
        Index("ix_group_members_active", "group_id", "status"),
        Index("ix_group_members_pilgrim", "pilgrim_id"),
        UniqueConstraint(
            "group_id", "pilgrim_id", "status",
            name="uq_active_membership",
        ),
        {"comment": "Group membership audit trail"},
    )

    def __repr__(self):
        return f"<GroupMember(group_id={self.group_id.hex()}, pilgrim_id={self.pilgrim_id.hex()}, status='{self.status}')>"