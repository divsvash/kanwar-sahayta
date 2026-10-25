"""
Demo flow tests: auth, RBAC, and the full pilgrim registration journey.

Runs against a throwaway SQLite file with the demo seed applied.
"""

import asyncio
import os
import tempfile

_TMP_DB = os.path.join(tempfile.gettempdir(), "ks_test_demo.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["DEBUG"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import engine, Base, async_session_factory  # noqa: E402
import app.domain.platform.models  # noqa: E402,F401
import app.domain.identity.models  # noqa: E402,F401
import app.domain.journey.models  # noqa: E402,F401
import app.domain.safety.models  # noqa: E402,F401
from scripts.seed_demo import seed_if_empty  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ui.routes import DEMO_OTP  # noqa: E402


async def _prepare():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await seed_if_empty(session)


asyncio.run(_prepare())

app = create_app()
client = TestClient(app)

ADMIN = {"phone": "9000000001", "pin": "1234"}
CAMP_OP = {"phone": "9000000003", "pin": "1234"}


def _login_token(creds) -> str:
    resp = client.post("/api/v1/users/login", json=creds)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── auth ──────────────────────────────────────

def test_login_success():
    token = _login_token(ADMIN)
    assert token


def test_login_wrong_pin_rejected():
    resp = client.post("/api/v1/users/login", json={"phone": "9000000001", "pin": "9999"})
    assert resp.status_code in (401, 403), resp.text


# ── RBAC ──────────────────────────────────────

def test_user_admin_requires_permission():
    # unauthenticated
    assert client.get("/api/v1/users").status_code == 401
    # camp operator lacks user:manage
    op_token = _login_token(CAMP_OP)
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {op_token}"})
    assert resp.status_code == 403, resp.text
    # admin allowed
    admin_token = _login_token(ADMIN)
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text


def test_pilgrim_list_requires_auth():
    assert client.get("/api/v1/pilgrims").status_code == 401
    token = _login_token(CAMP_OP)  # camp operator HAS pilgrim:read
    resp = client.get("/api/v1/pilgrims", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text


# ── UI auth ───────────────────────────────────

def test_dashboard_redirects_when_logged_out():
    resp = client.get("/ui/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/ui/login"


def test_ui_login_flow():
    resp = client.post("/ui/login", data=ADMIN, follow_redirects=False)
    assert resp.status_code == 303
    assert "ks_demo_token" in resp.cookies
    dash = client.get("/ui/dashboard", cookies=resp.cookies)
    assert dash.status_code == 200
    assert "Kanwar Yatra 2026 (DEMO)" in dash.text


# ── full registration flow ────────────────────

def test_full_registration_flow():
    # step 1: phone
    resp = client.post("/ui/register", data={"phone": "9876500011"}, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    cookies = resp.cookies
    assert resp.headers["location"] == "/ui/register/otp"

    # step 2: wrong demo OTP fails, right one passes
    resp = client.post("/ui/register/otp", data={"otp": "000000"}, cookies=cookies)
    assert "does not match" in resp.text
    resp = client.post("/ui/register/otp", data={"otp": DEMO_OTP}, cookies=cookies, follow_redirects=False)
    assert resp.status_code == 303

    # step 3: profile
    resp = client.post("/ui/register/profile", cookies=cookies, data={
        "full_name": "Test Pilgrim", "age": "34", "gender": "female",
        "emergency_contact_name": "Test Kin", "emergency_contact_phone": "9876500012",
        "emergency_contact_relation": "spouse",
    }, follow_redirects=False)
    assert resp.status_code == 303, resp.text

    # step 4: medical
    resp = client.post("/ui/register/medical", cookies=cookies, data={
        "blood_group": "O+", "medical_flags": "asthma", "allergies": "", "current_medications": "",
    }, follow_redirects=False)
    assert resp.status_code == 303, resp.text

    # step 5: route picker lists seeded routes
    resp = client.get("/ui/register/route", cookies=cookies)
    assert resp.status_code == 200
    assert "Haridwar-Meerut Main (DEMO)" in resp.text

    # pick the first route id from the page
    import re
    route_id = re.search(r'name="route_id" value="([0-9a-f-]{36})"', resp.text).group(1)
    resp = client.post("/ui/register/route", cookies=cookies, data={"route_id": route_id}, follow_redirects=False)
    assert resp.status_code == 303, resp.text

    # done: QR card
    resp = client.get("/ui/register/done", cookies=cookies)
    assert resp.status_code == 200
    assert "Test Pilgrim" in resp.text
    assert "data:image/png;base64," in resp.text


def test_duplicate_phone_rejected():
    resp = client.post("/ui/register", data={"phone": "9811100001"})  # seeded pilgrim
    assert "already registered" in resp.text
