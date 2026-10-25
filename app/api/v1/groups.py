"""
Group API endpoints.

Create, join, leave, transfer leadership, and query groups.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_current_season
from app.domain.identity.service import PilgrimService
from app.domain.identity.repository import (
    GroupRepository, GroupMemberRepository,
)
from app.domain.identity.schemas import (
    GroupCreateRequest, GroupJoinRequest, GroupLeaveRequest,
    GroupTransferLeadershipRequest,
    GroupResponse, GroupDetailResponse, GroupMemberResponse,
    GroupListResponse,
)

router = APIRouter(prefix="/groups", tags=["Groups"])


# ──────────────────────────────────────────────
# Group Management
# ──────────────────────────────────────────────

@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    request: GroupCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new pilgrim group."""
    service = PilgrimService(db)
    group = await service.create_group(request)
    return _group_to_response(group, 1)


@router.post("/join", response_model=GroupMemberResponse, status_code=201)
async def join_group(
    request: GroupJoinRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Join an existing group by code."""
    service = PilgrimService(db)
    member = await service.join_group(request)
    return GroupMemberResponse(
        pilgrim_id=UUID(bytes=member.pilgrim_id),
        full_name="",
        membership_status=member.status,
        joined_at=member.joined_at,
    )


@router.post("/leave", response_model=dict)
async def leave_group(
    request: GroupLeaveRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Leave current group."""
    service = PilgrimService(db)
    await service.leave_group(request)
    return {"message": "Successfully left the group"}


@router.put("/{group_id}/transfer-leadership", response_model=GroupResponse)
async def transfer_leadership(
    group_id: UUID,
    request: GroupTransferLeadershipRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Transfer group leadership to another member."""
    service = PilgrimService(db)
    group = await service.transfer_leadership(group_id, request)
    member_count = await GroupMemberRepository(db).count_active_members(group_id)
    return _group_to_response(group, member_count)


# ──────────────────────────────────────────────
# Queries
# ──────────────────────────────────────────────

@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Get group details with member list."""
    group_repo = GroupRepository(db)
    group = await group_repo.get_by_id(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")

    member_repo = GroupMemberRepository(db)
    members = await member_repo.get_group_members(group_id, "ACTIVE")

    return GroupDetailResponse(
        id=UUID(bytes=group.id),
        season_id=UUID(bytes=group.season_id),
        group_code=group.group_code,
        leader_id=UUID(bytes=group.leader_id),
        leader_name=group.leader.full_name if group.leader else None,
        name=group.name,
        status=group.status,
        max_members=group.max_members,
        member_count=len(members),
        created_at=group.created_at,
        updated_at=group.updated_at,
        members=[
            GroupMemberResponse(
                pilgrim_id=UUID(bytes=m.pilgrim_id),
                full_name=m.pilgrim.full_name if m.pilgrim else "",
                photo_url=m.pilgrim.photo_url if m.pilgrim else None,
                blood_group=m.pilgrim.blood_group if m.pilgrim else None,
                medical_flags=m.pilgrim.medical_flags if m.pilgrim else None,
                membership_status=m.status,
                joined_at=m.joined_at,
            )
            for m in members
        ],
    )


@router.get("", response_model=GroupListResponse)
async def list_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    season_id: UUID = Depends(get_current_season),
    db: AsyncSession = Depends(get_db_session),
):
    """List groups for the active season."""
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)
    items, total = await group_repo.list_by_season(season_id, page, page_size)

    group_responses = []
    for group in items:
        count = await member_repo.count_active_members(UUID(bytes=group.id))
        group_responses.append(_group_to_response(group, count))

    return GroupListResponse(
        items=group_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


# ──────────────────────────────────────────────
# Response Builder
# ──────────────────────────────────────────────

def _group_to_response(group, member_count: int) -> GroupResponse:
    """Convert Group model to response schema."""
    return GroupResponse(
        id=UUID(bytes=group.id),
        season_id=UUID(bytes=group.season_id),
        group_code=group.group_code,
        leader_id=UUID(bytes=group.leader_id),
        leader_name=group.leader.full_name if group.leader else None,
        name=group.name,
        status=group.status,
        max_members=group.max_members,
        member_count=member_count,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )