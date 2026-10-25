"""
Demo browser UI for Kanwar Sahayta.

Server-rendered pages (Jinja2 + plain HTML forms) served by the same
FastAPI process as the API. Covers the first reviewable slice:

- operator login (phone + PIN, JWT in an HttpOnly cookie)
- role-aware dashboard
- pilgrim self-registration with a clearly marked DEMO OTP
- QR identity card for a registered pilgrim

Everything here talks to the real domain services; no parallel demo logic.
"""

import base64
import io
import json
from pathlib import Path
from typing import Optional
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import settings
from app.core.exceptions import AppException
from app.domain.identity.models import Pilgrim, User
from app.domain.identity.schemas import (
    PilgrimInitiateRequest, PilgrimProfileRequest, PilgrimMedicalRequest,
    PilgrimRouteSelectionRequest, UserLoginRequest,
)
from app.domain.identity.service import PilgrimService, UserService
from app.domain.identity.repository import UserRepository
from app.domain.journey.models import Route, Checkpoint
from app.domain.journey.repository import RouteRepository
from app.domain.platform.repository import SeasonRepository

router = APIRouter(prefix="/ui", tags=["UI"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

AUTH_COOKIE = "ks_demo_token"
REG_COOKIE = "ks_demo_reg"

# DEMO ONLY: no SMS gateway exists in this build, so registration uses a
# fixed, on-screen demo OTP. Never ship this to a real deployment.
DEMO_OTP = "246810"


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


async def _current_user(request: Request, db: AsyncSession) -> Optional[User]:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    if not user or user.status != "ACTIVE":
        return None
    return user


async def _active_season(db: AsyncSession):
    season = await SeasonRepository(db).get_active()
    if not season:
        raise AppException(
            status_code=503,
            message="No active season. Run the demo seed script first.",
            error_code="NO_ACTIVE_SEASON",
        )
    return season


def _reg_pilgrim_id(request: Request) -> Optional[UUID]:
    raw = request.cookies.get(REG_COOKIE)
    try:
        return UUID(raw) if raw else None
    except ValueError:
        return None


def _render(request: Request, template: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx)


# ──────────────────────────────────────────────
# Operator login / logout
# ──────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render(request, "login.html", error=None)


@router.post("/login")
async def login_submit(
    request: Request,
    phone: str = Form(...),
    pin: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    service = UserService(db)
    try:
        user = await service.authenticate(UserLoginRequest(phone=phone.strip(), pin=pin.strip()))
    except AppException as exc:
        return _render(request, "login.html", error=exc.message)

    from datetime import datetime, timedelta
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    token = jwt.encode(
        {"sub": str(UUID(bytes=user.id)), "role": user.role.name if user.role else None,
         "exp": expire, "iat": datetime.utcnow()},
        settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )
    resp = _redirect("/ui/dashboard")
    resp.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
async def logout():
    resp = _redirect("/ui/login")
    resp.delete_cookie(AUTH_COOKIE)
    return resp


# ──────────────────────────────────────────────
# Dashboard (login required)
# ──────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db_session)):
    user = await _current_user(request, db)
    if not user:
        return _redirect("/ui/login")
    season = await _active_season(db)
    pilgrim_count = (await db.execute(
        select(func.count(Pilgrim.id)).where(Pilgrim.season_id == season.id)
    )).scalar()
    route_count = (await db.execute(
        select(func.count(Route.id)).where(Route.season_id == season.id)
    )).scalar()
    checkpoint_count = (await db.execute(select(func.count(Checkpoint.id)))).scalar()
    return _render(
        request, "dashboard.html",
        user=user, season=season,
        pilgrim_count=pilgrim_count, route_count=route_count,
        checkpoint_count=checkpoint_count,
    )


# ──────────────────────────────────────────────
# Pilgrim self-registration (public, demo OTP)
# ──────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_phone_page(request: Request):
    return _render(request, "register_phone.html", error=None, phone="")


@router.post("/register")
async def register_phone_submit(
    request: Request,
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    season = await _active_season(db)
    phone = phone.strip()
    try:
        pilgrim = await PilgrimService(db).initiate_registration(
            PilgrimInitiateRequest(phone=phone, season_id=UUID(bytes=season.id))
        )
    except AppException as exc:
        return _render(request, "register_phone.html", error=exc.message, phone=phone)
    except Exception:
        return _render(request, "register_phone.html",
                       error="Enter a valid 10-digit Indian mobile number.", phone=phone)
    resp = _redirect("/ui/register/otp")
    resp.set_cookie(REG_COOKIE, str(UUID(bytes=pilgrim.id)), httponly=True, samesite="lax")
    return resp


@router.get("/register/otp", response_class=HTMLResponse)
async def register_otp_page(request: Request):
    if not _reg_pilgrim_id(request):
        return _redirect("/ui/register")
    return _render(request, "register_otp.html", error=None, demo_otp=DEMO_OTP)


@router.post("/register/otp")
async def register_otp_submit(request: Request, otp: str = Form(...)):
    if not _reg_pilgrim_id(request):
        return _redirect("/ui/register")
    if otp.strip() != DEMO_OTP:
        return _render(request, "register_otp.html",
                       error="That code does not match the demo OTP.", demo_otp=DEMO_OTP)
    return _redirect("/ui/register/profile")


@router.get("/register/profile", response_class=HTMLResponse)
async def register_profile_page(request: Request):
    if not _reg_pilgrim_id(request):
        return _redirect("/ui/register")
    return _render(request, "register_profile.html", error=None, form={})


@router.post("/register/profile")
async def register_profile_submit(
    request: Request,
    full_name: str = Form(...),
    age: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    emergency_contact_name: Optional[str] = Form(None),
    emergency_contact_phone: Optional[str] = Form(None),
    emergency_contact_relation: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
):
    pilgrim_id = _reg_pilgrim_id(request)
    if not pilgrim_id:
        return _redirect("/ui/register")
    try:
        await PilgrimService(db).complete_profile(
            pilgrim_id,
            PilgrimProfileRequest(
                full_name=full_name.strip(),
                age=int(age) if age else None,
                gender=gender or None,
                emergency_contact_name=emergency_contact_name or None,
                emergency_contact_phone=emergency_contact_phone or None,
                emergency_contact_relation=emergency_contact_relation or None,
            ),
        )
    except (AppException, Exception) as exc:
        msg = getattr(exc, "message", "Check the details and try again.")
        return _render(request, "register_profile.html", error=msg, form={})
    return _redirect("/ui/register/medical")


def _split_list(raw: Optional[str]) -> Optional[list]:
    if not raw:
        return None
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or None


@router.get("/register/medical", response_class=HTMLResponse)
async def register_medical_page(request: Request):
    if not _reg_pilgrim_id(request):
        return _redirect("/ui/register")
    return _render(request, "register_medical.html", error=None)


@router.post("/register/medical")
async def register_medical_submit(
    request: Request,
    blood_group: Optional[str] = Form(None),
    medical_flags: Optional[str] = Form(None),
    allergies: Optional[str] = Form(None),
    current_medications: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
):
    pilgrim_id = _reg_pilgrim_id(request)
    if not pilgrim_id:
        return _redirect("/ui/register")
    try:
        await PilgrimService(db).complete_medical(
            pilgrim_id,
            PilgrimMedicalRequest(
                blood_group=blood_group or None,
                medical_flags=_split_list(medical_flags),
                allergies=_split_list(allergies),
                current_medications=_split_list(current_medications),
            ),
        )
    except (AppException, Exception) as exc:
        msg = getattr(exc, "message", "Check the details and try again.")
        return _render(request, "register_medical.html", error=msg)
    return _redirect("/ui/register/route")


@router.get("/register/route", response_class=HTMLResponse)
async def register_route_page(request: Request, db: AsyncSession = Depends(get_db_session)):
    if not _reg_pilgrim_id(request):
        return _redirect("/ui/register")
    season = await _active_season(db)
    routes, _ = await RouteRepository(db).list_by_season(UUID(bytes=season.id), page_size=50)
    return _render(request, "register_route.html", error=None, routes=routes,
                   uuid_hex=lambda b: str(UUID(bytes=b)))


@router.post("/register/route")
async def register_route_submit(
    request: Request,
    route_id: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    pilgrim_id = _reg_pilgrim_id(request)
    if not pilgrim_id:
        return _redirect("/ui/register")
    try:
        await PilgrimService(db).select_route(
            pilgrim_id, PilgrimRouteSelectionRequest(route_id=UUID(route_id))
        )
    except (AppException, Exception) as exc:
        season = await _active_season(db)
        routes, _ = await RouteRepository(db).list_by_season(UUID(bytes=season.id), page_size=50)
        msg = getattr(exc, "message", "Could not save the route. Try again.")
        return _render(request, "register_route.html", error=msg, routes=routes,
                       uuid_hex=lambda b: str(UUID(bytes=b)))
    return _redirect("/ui/register/done")


@router.get("/register/done", response_class=HTMLResponse)
async def register_done(request: Request, db: AsyncSession = Depends(get_db_session)):
    pilgrim_id = _reg_pilgrim_id(request)
    if not pilgrim_id:
        return _redirect("/ui/register")
    pilgrim = await PilgrimService(db).get_pilgrim(pilgrim_id)

    payload = json.dumps({
        "app": "kanwar-sahayta-demo",
        "pilgrim_id": str(pilgrim_id),
        "name": pilgrim.full_name,
        "v": 1,
    })
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    resp = _render(request, "qr_card.html", pilgrim=pilgrim, qr_data_uri=qr_data_uri)
    resp.delete_cookie(REG_COOKIE)
    return resp
