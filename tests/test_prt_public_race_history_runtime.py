"""Verify explicit public PRT racing-history consent, retrieval, and revocation."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as temporary:
    dbfile=Path(temporary)/"prt-public-test.db"
    os.environ["DATABASE_URL"]="sqlite:///"+str(dbfile)
    os.environ["PITMARK_SIGNING_SECRET"]="test-only-PRT-publish-secret-"+("S"*44)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.database import Base, SessionLocal, engine
    from services import race_center_accounts
    from api import prt_race_center_bridge as bridge

    Base.metadata.create_all(bind=engine)
    owner=race_center_accounts.create_account("tester-prt-public@example.com","PublishedRacesSecret12345","PRT Tester")
    profile=race_center_accounts.ensure_profile(owner.id)
    with SessionLocal() as db:
        db.add(bridge.PrtSession(
            user_id=owner.id, source_id="12345678-1234-1234-1234-123456789abc",
            data_json=json.dumps({
                "date":"2026-10-17T17:00:00Z","track":"Lime Rock","car":"MX5",
                "series":"Rookie","laps":25,"incidents":2,"best_lap":66.8,
                "starting_position":8,"finishing_position":1,
                "id":"12345678-1234-1234-1234-123456789abc",
                "driver_name":"Private real-world name",
                "strength_of_field":1300
            })
        ))
        db.commit()
    app=FastAPI()
    app.include_router(bridge.router)
    client=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    url="/api/public/race-center/prt/public/"+profile["handle"]

    # Initially PRIVATE; no session record or summary exposed.
    closed=client.get(url)
    assert closed.status_code==200 and closed.json()=={"public":False},closed.text
    assert client.get("/api/public/race-center/prt/sharing").status_code==401

    # Only account owner can change visibility, with a same-origin request.
    data={"public":True}
    assert client.put("/api/public/race-center/prt/sharing",json=data).status_code==403
    client.cookies.set(race_center_accounts.SESSION_COOKIE,race_center_accounts.issue_session(owner))
    assert client.put("/api/public/race-center/prt/sharing",json=data).status_code==403
    allowed=client.put("/api/public/race-center/prt/sharing",json=data,headers={
        "Origin":"https://racecenter.pitmarkracing.com"
    })
    assert allowed.status_code==200,allowed.text

    # Anonymous visitor can read opt-in race fields, but never identifiers.
    visitor=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    response=visitor.get(url)
    assert response.status_code==200,response.text
    body=response.json()
    assert body["public"] is True and body["summary"]["sessions"]==1,body
    assert body["summary"]["wins"]==1
    assert body["sessions"][0]["best_lap"]==66.8
    assert "driver_name" not in body["sessions"][0]
    assert "id" not in body["sessions"][0]
    assert body["next_offset"] is None
    assert visitor.get(url+"?limit=101").status_code==422

    # Sharing can be revoked, immediately suppressing all public results.
    stop=client.put("/api/public/race-center/prt/sharing",json={"public":False},headers={
        "Origin":"https://racecenter.pitmarkracing.com"
    })
    assert stop.status_code==200,stop.text
    assert visitor.get(url).json()=={"public":False}
    print("PRT public results opt-in, fields allowlist and revocation PASS")
