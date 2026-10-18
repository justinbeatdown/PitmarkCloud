"""Verify only server-authorized staff can open the admin UI and review queues."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp)/"staff-admin-test.db")
    os.environ["PITMARK_SIGNING_SECRET"]="test-staff-admin-long-secret-"+"R"*40
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.database import Base,engine,SessionLocal
    from services import race_center_accounts as rc
    from api import standings_public

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        staff=rc.RaceCenterUser(email="justin@pitmarkracing.com",display_name="Site Founder",password_salt="salt",password_hash="hash")
        visitor=rc.RaceCenterUser(email="visitor@example.invalid",display_name="Racer",password_salt="salt",password_hash="hash")
        db.add_all([staff,visitor]);db.commit()
        staff_id=staff.id;visitor_id=visitor.id

    app=FastAPI()
    app.include_router(standings_public.router)
    client=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    admin="/race-center/admin"
    assert client.get(admin).status_code==401
    assert client.get("/api/public/race-center/entity-claims/review").status_code==401
    outsider=rc.RaceCenterAccount(id=visitor_id,email="visitor@example.invalid",display_name="Racer",session_version=1)
    client.cookies.set(rc.SESSION_COOKIE,rc.issue_session(outsider))
    assert client.get(admin).status_code==403
    assert client.get("/api/public/race-center/series-submissions/review").status_code==403
    assert client.get("/api/public/race-center/entity-claims/review").status_code==403
    founder=rc.RaceCenterAccount(id=staff_id,email="justin@pitmarkracing.com",display_name="Site Founder",session_version=1)
    client.cookies.set(rc.SESSION_COOKIE,rc.issue_session(founder))
    response=client.get(admin)
    assert response.status_code==200,response.text[:300]
    assert "Race Center Staff Admin" in response.text
    assert client.get("/api/public/race-center/series-submissions/review?status=pending").status_code==200
    assert client.get("/api/public/race-center/entity-claims/review?status=pending").status_code==200
    print("Race Center Staff Admin authenticated role checks PASS")
