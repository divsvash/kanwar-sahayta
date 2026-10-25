"""
User API endpoints.

User CRUD, authentication, and role management.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.domain.identity.service import UserService, RoleService
from app.domain.identity.schemas import (
    UserCreateRequest, UserLoginRequest, UserStatusUpdateRequest,
    UserResponse, UserLoginResponse, UserListResponse,
    RoleCreateRequest, RoleResponse, RoleListResponse,
)
from app.config import settings

router = APIRouter(prefix="/users", tags=["Users"])


# ──────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────

@router.post("/login", response_model=UserLoginResponse)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Authenticate user with phone and PIN. Returns JWT token."""
    from jose import jwt
    from datetime import datetime, timedelta

    service = UserService(db)
    user = await service.authenticate(request)

    # Generate JWT
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(UUID(bytes=user.id)),
        "role": user.role.name if user.role else None,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    return UserLoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=_user_to_response(user),
    )


# ──────────────────────────────────────────────
# User CRUD
# ──────────────────────────────────────────────

@router.post("", response_model=UserResponse, status_code=201, dependencies=[Depends(require_permissions("user:manage"))])
async def create_user(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new system user."""
    service = UserService(db)
    user = await service.create_user(request)
    return _user_to_response(user)


@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_permissions("user:manage"))])
async def get_user(
    user_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get user by ID."""
    service = UserService(db)
    user = await service.get_user(user_id)
    return _user_to_response(user)


@router.get("", response_model=UserListResponse, dependencies=[Depends(require_permissions("user:manage"))])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """List users with pagination."""
    service = UserService(db)
    items, total = await service.list_users(page, page_size, status)
    return UserListResponse(
        items=[_user_to_response(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put("/{user_id}/status", response_model=UserResponse, dependencies=[Depends(require_permissions("user:manage"))])
async def update_user_status(
    user_id: UUID,
    request: UserStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Suspend or reactivate a user."""
    service = UserService(db)
    user = await service.update_status(user_id, request)
    return _user_to_response(user)


# ──────────────────────────────────────────────
# Roles
# ──────────────────────────────────────────────

@router.post("/roles", response_model=RoleResponse, status_code=201, dependencies=[Depends(require_permissions("user:manage"))])
async def create_role(
    request: RoleCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new system role."""
    service = RoleService(db)
    role = await service.create_role(request)
    return RoleResponse(
        id=UUID(bytes=role.id),
        name=role.name,
        permissions=role.permissions,
        description=role.description,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    db: AsyncSession = Depends(get_db_session),
):
    """List all system roles."""
    service = RoleService(db)
    roles = await service.list_roles()
    return RoleListResponse(
        items=[
            RoleResponse(
                id=UUID(bytes=r.id),
                name=r.name,
                permissions=r.permissions,
                description=r.description,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in roles
        ],
        total=len(roles),
    )


# ──────────────────────────────────────────────
# Response Builder
# ──────────────────────────────────────────────

def _user_to_response(user) -> UserResponse:
    """Convert User model to response schema."""
    return UserResponse(
        id=UUID(bytes=user.id),
        role_id=UUID(bytes=user.role_id),
        role_name=user.role.name if user.role else None,
        phone=user.phone,
        full_name=user.full_name,
        status=user.status,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )