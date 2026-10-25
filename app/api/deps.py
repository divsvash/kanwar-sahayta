"""
FastAPI dependency injection functions.

Provides reusable dependencies for:
- Database sessions
- Current active season resolution
- JWT authentication and user resolution
- Permission checking
"""

from uuid import UUID
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.core.database import get_db
from app.config import settings
from app.domain.platform.repository import SeasonRepository
from app.domain.identity.repository import UserRepository
from app.core.exceptions import SeasonNotActiveError

# ──────────────────────────────────────────────
# Security Schemes
# ──────────────────────────────────────────────

security = HTTPBearer(auto_error=False)


# ──────────────────────────────────────────────
# Database Dependency
# ──────────────────────────────────────────────

async def get_db_session() -> AsyncSession:
    """
    Yields an async database session.

    Session is automatically committed on success
    or rolled back on exception.
    """
    async for session in get_db():
        yield session


# ──────────────────────────────────────────────
# Season Dependencies
# ──────────────────────────────────────────────

async def get_current_season(
    db: AsyncSession = Depends(get_db_session),
) -> UUID:
    """
    Resolves the currently active season ID.

    Raises 400 if no season is ACTIVE.
    Used by all operational endpoints to scope data.
    """
    repo = SeasonRepository(db)
    season = await repo.get_active()
    if not season:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "SEASON_NOT_ACTIVE",
                "message": "No active season. Operations require an ACTIVE season.",
            },
        )
    return UUID(bytes=season.id)


async def get_current_season_optional(
    db: AsyncSession = Depends(get_db_session),
) -> Optional[UUID]:
    """
    Resolves the active season ID if one exists.
    Returns None if no season is active.
    Used by admin endpoints that work across seasons.
    """
    repo = SeasonRepository(db)
    season = await repo.get_active()
    return UUID(bytes=season.id) if season else None


# ──────────────────────────────────────────────
# Authentication Dependencies
# ──────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[dict]:
    """
    Resolves the current authenticated user from JWT token.

    Returns user dict with id and role, or None if no valid token.
    Does NOT raise 401 - endpoints decide if auth is required.
    """
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if not user_id:
            return None

        # Verify user still exists and is active
        repo = UserRepository(db)
        user = await repo.get_by_id(UUID(user_id))
        if not user or user.status != "ACTIVE":
            return None

        return {
            "id": UUID(user_id),
            "role_id": UUID(bytes=user.role_id),
            "role_name": user.role.name if user.role else None,
            "phone": user.phone,
        }
    except JWTError:
        return None


async def get_current_active_user(
    current_user: Optional[dict] = Depends(get_current_user),
) -> dict:
    """
    Requires a valid authenticated user.
    Raises 401 if no valid token.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "UNAUTHORIZED",
                "message": "Valid authentication token required",
            },
        )
    return current_user


# ──────────────────────────────────────────────
# Role-Based Permission Dependencies
# ──────────────────────────────────────────────

class PermissionChecker:
    """
    Factory for permission-checking dependencies.

    Usage:
        require_permission = PermissionChecker("pilgrim:read")
        @router.get("/pilgrims")
        async def list_pilgrims(
            user: dict = Depends(require_permission),
            ...
        ):
    """

    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(
        self,
        current_user: dict = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> dict:
        """Check if the current user has the required permission."""
        repo = UserRepository(db)
        user = await repo.get_by_id(current_user["id"])
        if not user or not user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": f"Permission '{self.required_permission}' required",
                },
            )

        permissions = user.role.permissions or []
        if self.required_permission not in permissions and "*" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FORBIDDEN",
                    "message": f"Permission '{self.required_permission}' required",
                },
            )

        return current_user


# ──────────────────────────────────────────────
# Common Permission Instances
# ──────────────────────────────────────────────

RequirePilgrimRead = PermissionChecker("pilgrim:read")
RequirePilgrimWrite = PermissionChecker("pilgrim:write")
RequirePresenceWrite = PermissionChecker("presence:write")
RequireAdminAccess = PermissionChecker("admin:access")

# ──────────────────────────────────────────────
# Role-based access control (added for demo hardening)
# ──────────────────────────────────────────────

from app.domain.identity.repository import RoleRepository


def require_permissions(*required: str):
    """
    Dependency factory enforcing role permissions.

    Roles carry a JSON permission array; "*" grants everything.
    Raises 401 when unauthenticated, 403 when the role lacks
    every one of the required permissions.
    """
    from fastapi import HTTPException, status

    async def checker(
        current_user: Optional[dict] = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> dict:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        role_repo = RoleRepository(db)
        role = await role_repo.get_by_id(current_user["role_id"])
        perms = role.permissions if role and role.permissions else []
        if "*" in perms:
            return current_user
        for req in required:
            if req in perms:
                return current_user
            # allow "domain:*" style grants
            domain = req.split(":", 1)[0] + ":*"
            if domain in perms:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.get('role_name')}' lacks permission: {', '.join(required)}",
        )

    return checker
