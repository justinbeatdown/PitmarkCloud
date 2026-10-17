"""Import and model registration smoke test on the actual FastAPI/SQLAlchemy stack."""
import os
os.environ["PITMARK_SIGNING_SECRET"] = "x" * 48
os.environ["DATABASE_URL"] = "sqlite:///./data/prt-bridge-ci.sqlite3"

from fastapi import FastAPI
from services.database import Base, engine
from api import prt_race_center_bridge

app = FastAPI()
app.include_router(prt_race_center_bridge.router)
Base.metadata.create_all(bind=engine)
paths = {route.path for route in app.routes}
assert "/api/public/race-center/prt/link/start" in paths
assert "/api/public/race-center/prt/link/token" in paths
assert "/api/public/race-center/prt/sessions" in paths
assert "/race-center/prt-connect" in paths
assert {"race_center_prt_pairs", "race_center_prt_devices", "race_center_prt_sessions"}.issubset(Base.metadata.tables)
print("Race Center PRT bridge import, route and DB smoke PASS")
