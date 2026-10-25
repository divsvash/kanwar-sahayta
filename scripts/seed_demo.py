"""
Demo seed for Kanwar Sahayta.

Creates one ACTIVE season, four roles, three operator users, two routes
with checkpoints, and twelve fake pilgrims (some grouped, some with
journeys). Everything is clearly fake; safe to re-run (skips when the
season already exists).
"""

import uuid
from datetime import date

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.identity.models import Role, User, Pilgrim, Group, GroupMember
from app.domain.journey.models import Route, Checkpoint, Journey
from app.domain.platform.models import Season

SEASON_NAME = "Kanwar Yatra 2026 (DEMO)"

ROLES = [
    ("admin", ["*"], "Full access"),
    ("control_room_operator", ["pilgrim:read", "pilgrim:write", "presence:read", "presence:write", "route:read", "safety:read", "safety:write"], "District control room staff"),
    ("camp_operator", ["pilgrim:read", "presence:read", "presence:write"], "Checkpoint/camp scanner operators"),
    ("medical_officer", ["pilgrim:read", "safety:read", "safety:write"], "Medical camp staff"),
]

USERS = [
    ("9000000001", "1234", "Demo Admin", "admin"),
    ("9000000002", "1234", "Demo Control Room", "control_room_operator"),
    ("9000000003", "1234", "Demo Camp Operator", "camp_operator"),
]

ROUTES = [
    {
        "name": "Haridwar-Meerut Main (DEMO)",
        "description": "Main dak kanwar corridor via Roorkee and Muzaffarnagar",
        "distance": 190.0, "hours": 96.0,
        "checkpoints": [
            ("Har Ki Pauri Entry", 29.9560, 78.1710, "IN", "ENTRY", "Haridwar"),
            ("Roorkee Transit Camp", 29.8543, 77.8880, "EN_ROUTE", "TRANSIT_CAMP", "Haridwar"),
            ("Muzaffarnagar Rest Camp", 29.4727, 77.7085, "EN_ROUTE", "REST_CAMP", "Muzaffarnagar"),
            ("Meerut Medical Camp", 28.9845, 77.7064, "EN_ROUTE", "MEDICAL_CAMP", "Meerut"),
            ("Meerut Exit", 28.8010, 77.5630, "OUT", "EXIT", "Meerut"),
        ],
    },
    {
        "name": "Delhi-Haridwar via Baghpat (DEMO)",
        "description": "Alternate corridor for Delhi-origin kanwariyas",
        "distance": 220.0, "hours": 110.0,
        "checkpoints": [
            ("Delhi ISBT Entry", 28.6680, 77.2320, "IN", "ENTRY", "Delhi"),
            ("Baghpat Police Post", 28.9440, 77.2180, "EN_ROUTE", "POLICE_POST", "Baghpat"),
            ("Shamli Rest Camp", 29.4490, 77.3090, "EN_ROUTE", "REST_CAMP", "Shamli"),
            ("Roorkee Exit", 29.8700, 77.8900, "OUT", "EXIT", "Haridwar"),
        ],
    },
]

PILGRIMS = [
    ("Ramesh Chand", "9811100001", 42, "male", "B+", ["diabetes"], None),
    ("Suresh Yadav", "9811100002", 38, "male", "O+", None, None),
    ("Mahesh Kumar", "9811100003", 45, "male", "A+", ["hypertension"], ["amlodipine"]),
    ("Dinesh Pal", "9811100004", 29, "male", "B-", None, None),
    ("Kamla Devi", "9811100005", 51, "female", "AB+", ["asthma"], None),
    ("Sunita Sharma", "9811100006", 47, "female", "O-", None, None),
    ("Radhe Shyam", "9811100007", 60, "male", "A-", ["diabetes", "hypertension"], ["metformin"]),
    ("Gopal Das", "9811100008", 33, "male", "O+", None, None),
    ("Hanuman Prasad", "9811100009", 55, "male", "B+", None, None),
    ("Chotu Lal", "9811100010", 24, "male", "AB-", None, None),
    ("Bimla Rani", "9811100011", 49, "female", "A+", None, None),
    ("Om Prakash", "9811100012", 36, "male", "O+", None, None),
]


def _pin_hash(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_if_empty(db: AsyncSession) -> bool:
    """Seed the demo dataset. Returns True when seeding happened."""
    existing = await db.execute(select(Season).where(Season.name == SEASON_NAME))
    if existing.scalar_one_or_none():
        return False

    season = Season(
        id=uuid.uuid4().bytes,
        name=SEASON_NAME,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 31),
        status="ACTIVE",
        description="DEMO season with fake data only",
    )
    db.add(season)
    await db.flush()

    role_map = {}
    for name, perms, desc in ROLES:
        role = Role(id=uuid.uuid4().bytes, name=name, permissions=perms, description=desc)
        db.add(role)
        role_map[name] = role
    await db.flush()

    for phone, pin, full_name, role_name in USERS:
        db.add(User(
            id=uuid.uuid4().bytes,
            role_id=role_map[role_name].id,
            phone=phone,
            pin_hash=_pin_hash(pin),
            full_name=full_name,
            status="ACTIVE",
        ))
    await db.flush()

    route_objs = []
    for r in ROUTES:
        route = Route(
            id=uuid.uuid4().bytes,
            season_id=season.id,
            name=r["name"],
            description=r["description"],
            status="ACTIVE",
            total_distance_km=r["distance"],
            estimated_hours=r["hours"],
        )
        db.add(route)
        route_objs.append((route, r["checkpoints"]))
    await db.flush()

    for route, checkpoints in route_objs:
        for name, lat, lon, direction, ctype, district in checkpoints:
            db.add(Checkpoint(
                id=uuid.uuid4().bytes,
                camp_id=None,
                name=name + " (DEMO)",
                location=f"POINT({lon} {lat})",  # WKT; stored as text in the demo DB
                direction=direction,
                checkpoint_type=ctype,
                status="ACTIVE",
                district=district,
            ))
    await db.flush()

    pilgrim_objs = []
    for name, phone, age, gender, bg, flags, meds in PILGRIMS:
        p = Pilgrim(
            id=uuid.uuid4().bytes,
            season_id=season.id,
            full_name=name + " (DEMO)",
            phone=phone,
            age=age,
            gender=gender,
            blood_group=bg,
            medical_flags=flags,
            current_medications=meds,
            status="REGISTERED",
            registration_channel="SELF_APP",
            route_id=route_objs[0][0].id,
            qr_version=1,
        )
        db.add(p)
        pilgrim_objs.append(p)
    await db.flush()

    # one demo group with four members, leader = first pilgrim
    group = Group(
        id=uuid.uuid4().bytes,
        season_id=season.id,
        group_code="DEMO-001",
        leader_id=pilgrim_objs[0].id,
        name="Shiv Bhakt Mandal (DEMO)",
        status="ACTIVE",
        max_members=20,
    )
    db.add(group)
    await db.flush()
    for p in pilgrim_objs[:4]:
        p.group_id = group.id
        db.add(GroupMember(
            id=uuid.uuid4().bytes,
            group_id=group.id,
            pilgrim_id=p.id,
            join_method="CODE_ENTRY",
            status="ACTIVE",
        ))

    # journeys for every pilgrim on their selected route
    for p in pilgrim_objs:
        db.add(Journey(
            id=uuid.uuid4().bytes,
            pilgrim_id=p.id,
            route_id=p.route_id,
            status="PLANNED",
            total_checkins=0,
            current_segment_index=0,
        ))

    await db.commit()
    return True
