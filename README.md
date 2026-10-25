# Kanwar Sahayata - Local Demo

District administration platform for Kanwar Yatra operations: a runnable
local demo with operator login, role-based access, and the full pilgrim
registration flow ending in a QR identity card.

**LOCAL DEMO ONLY. Fake data, fixed demo OTP, not a real emergency service.**

## Run it

```bash
pip install -r requirements-demo.txt
python run_demo.py
```

Open http://127.0.0.1:8000

- Creates `kanwar_demo.db` (SQLite), creates tables, seeds fake demo data on first run.
- Delete `kanwar_demo.db` to reset.

## Demo logins (operators)

| Role | Phone | PIN |
|---|---|---|
| Admin | 9000000001 | 1234 |
| Control room | 9000000002 | 1234 |
| Camp operator | 9000000003 | 1234 |

Pilgrim registration (/ui/register) needs no login. The demo OTP is
shown on screen during registration (`246810`) - no SMS is sent.

## What works in this piece

- Operator login (phone + PIN, JWT in HttpOnly cookie) and logout
- Role-aware dashboard (season, pilgrim/route/checkpoint counts)
- 5-step pilgrim registration: phone, demo OTP, profile, medical, route -> QR card
- REST API: platform/seasons, pilgrims, groups, users+login, routes,
  checkpoints, journeys, presence, safety (SOS)
- Role-based access control on sensitive API endpoints
- Test suite: `python -m pytest tests/ -q` (8 tests: auth, RBAC, UI, full flow)

## Deliberate demo limits

- OTP is a fixed, on-screen code (no SMS gateway)
- SQLite storage; MySQL docker path still available via DATABASE_URL
  (checkpoint proximity search falls back to Python haversine on SQLite)
- Geometry stored as WKT text; spatial SQL (ST_Distance) is MySQL-only
- Camp, notification, admin, audit domains are still empty stubs
- The original test files were empty; the included suite covers the demo flows
- No deployment, no real data, no real emergency function

