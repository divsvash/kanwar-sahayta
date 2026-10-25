"""
Identity domain repository.

Data access layer for Pilgrim, Group, GroupMember, User, and Role entities.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from app.domain.identity.models import (
    Pilgrim, Group, GroupMember, User, Role
)


class PilgrimRepository:
    """Data access for Pilgrim aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, pilgrim: Pilgrim) -> Pilgrim:
        self.session.add(pilgrim)
        await self.session.flush()
        return pilgrim

    async def get_by_id(self, pilgrim_id: UUID) -> Optional[Pilgrim]:
        result = await self.session.execute(
            select(Pilgrim)
            .options(selectinload(Pilgrim.group), selectinload(Pilgrim.route))
            .where(Pilgrim.id == pilgrim_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_phone_and_season(
        self, phone: str, season_id: UUID
    ) -> Optional[Pilgrim]:
        """Find pilgrim by phone within a season (for duplicate check)."""
        result = await self.session.execute(
            select(Pilgrim).where(
                and_(
                    Pilgrim.phone == phone,
                    Pilgrim.season_id == season_id.bytes,
                    Pilgrim.status.in_(["REGISTERED", "ACTIVE"]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_season(
        self,
        season_id: UUID,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        group_id: Optional[UUID] = None,
        route_id: Optional[UUID] = None,
    ) -> Tuple[List[Pilgrim], int]:
        """List pilgrims with optional filters."""
        query = select(Pilgrim).options(
            selectinload(Pilgrim.group),
            selectinload(Pilgrim.route),
        )
        count_query = select(func.count(Pilgrim.id))
        conditions = [Pilgrim.season_id == season_id.bytes]

        if status:
            conditions.append(Pilgrim.status == status)
        if group_id:
            conditions.append(Pilgrim.group_id == group_id.bytes)
        if route_id:
            conditions.append(Pilgrim.route_id == route_id.bytes)

        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
        query = query.order_by(Pilgrim.created_at.desc())

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def search_by_name(
        self, season_id: UUID, name: str, limit: int = 20
    ) -> List[Pilgrim]:
        """Search pilgrims by name (LIKE query)."""
        result = await self.session.execute(
            select(Pilgrim)
            .options(selectinload(Pilgrim.group))
            .where(
                and_(
                    Pilgrim.season_id == season_id.bytes,
                    Pilgrim.full_name.ilike(f"%{name}%"),
                )
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_pilgrim(self, pilgrim_id: UUID) -> Optional[Pilgrim]:
        """Get pilgrim only if ACTIVE or REGISTERED."""
        result = await self.session.execute(
            select(Pilgrim).where(
                and_(
                    Pilgrim.id == pilgrim_id.bytes,
                    Pilgrim.status.in_(["ACTIVE", "REGISTERED"]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def update(self, pilgrim: Pilgrim) -> Pilgrim:
        await self.session.flush()
        return pilgrim

    async def bulk_create(self, pilgrims: List[Pilgrim]) -> List[Pilgrim]:
        self.session.add_all(pilgrims)
        await self.session.flush()
        return pilgrims

    async def count_by_season(self, season_id: UUID, status: Optional[str] = None) -> int:
        query = select(func.count(Pilgrim.id)).where(
            Pilgrim.season_id == season_id.bytes
        )
        if status:
            query = query.where(Pilgrim.status == status)
        return (await self.session.execute(query)).scalar()


class GroupRepository:
    """Data access for Group aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, group: Group) -> Group:
        self.session.add(group)
        await self.session.flush()
        return group

    async def get_by_id(self, group_id: UUID) -> Optional[Group]:
        result = await self.session.execute(
            select(Group)
            .options(
                selectinload(Group.leader),
                selectinload(Group.members),
            )
            .where(Group.id == group_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_code_and_season(
        self, group_code: str, season_id: UUID
    ) -> Optional[Group]:
        result = await self.session.execute(
            select(Group).where(
                and_(
                    Group.group_code == group_code.upper(),
                    Group.season_id == season_id.bytes,
                    Group.status == "ACTIVE",
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_season(
        self, season_id: UUID, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Group], int]:
        query = (
            select(Group)
            .options(selectinload(Group.leader))
            .where(Group.season_id == season_id.bytes)
            .order_by(desc(Group.created_at))
        )
        count_query = (
            select(func.count(Group.id))
            .where(Group.season_id == season_id.bytes)
        )

        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def update(self, group: Group) -> Group:
        await self.session.flush()
        return group


class GroupMemberRepository:
    """Data access for GroupMember join table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_member(self, member: GroupMember) -> GroupMember:
        self.session.add(member)
        await self.session.flush()
        return member

    async def get_active_membership(
        self, group_id: UUID, pilgrim_id: UUID
    ) -> Optional[GroupMember]:
        result = await self.session.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id == group_id.bytes,
                    GroupMember.pilgrim_id == pilgrim_id.bytes,
                    GroupMember.status == "ACTIVE",
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_group_members(
        self, group_id: UUID, status: str = "ACTIVE"
    ) -> List[GroupMember]:
        result = await self.session.execute(
            select(GroupMember)
            .options(selectinload(GroupMember.pilgrim))
            .where(
                and_(
                    GroupMember.group_id == group_id.bytes,
                    GroupMember.status == status,
                )
            )
        )
        return result.scalars().all()

    async def count_active_members(self, group_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(GroupMember.id)).where(
                and_(
                    GroupMember.group_id == group_id.bytes,
                    GroupMember.status == "ACTIVE",
                )
            )
        )
        return result.scalar()

    async def update(self, member: GroupMember) -> GroupMember:
        await self.session.flush()
        return member


class UserRepository:
    """Data access for User aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == user_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Optional[User]:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.phone == phone)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, page: int = 1, page_size: int = 50, status: Optional[str] = None
    ) -> Tuple[List[User], int]:
        query = select(User).options(selectinload(User.role))
        count_query = select(func.count(User.id))

        if status:
            query = query.where(User.status == status)
            count_query = count_query.where(User.status == status)

        query = query.order_by(User.created_at.desc())
        total = (await self.session.execute(count_query)).scalar()
        items = (await self.session.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        return items, total

    async def update(self, user: User) -> User:
        await self.session.flush()
        return user


class RoleRepository:
    """Data access for Role aggregate."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role

    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        result = await self.session.execute(
            select(Role).where(Role.id == role_id.bytes)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Role]:
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[Role]:
        result = await self.session.execute(select(Role))
        return result.scalars().all()