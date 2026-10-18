"""Public Race Center social lists use real stored relationships, never private fields."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp)/"social-lists.db")
    os.environ["PITMARK_SIGNING_SECRET"]="social-contract-tests-"+"K"*50
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.database import Base,SessionLocal,engine
    from services import race_center_accounts as rc
    from api import standings_public

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        users=[
            rc.RaceCenterUser(email="tim@example.invalid",display_name="Tim Tester",password_salt="salt",password_hash="hash"),
            rc.RaceCenterUser(email="racer@example.invalid",display_name="Another Racer",password_salt="salt",password_hash="hash"),
            rc.RaceCenterUser(email="fan@example.invalid",display_name="Race Fan",password_salt="salt",password_hash="hash"),
        ]
        db.add_all(users);db.flush()
        ids=[u.id for u in users]
        for user_id,handle in zip(ids,("timtest","racer2","fan3")):
            db.add(rc.RaceCenterProfile(user_id=user_id,handle=handle))
        db.commit()
    assert rc.follow_user(ids[2],ids[0])["created"]
    assert rc.follow_user(ids[0],ids[1])["created"]
    rc.set_follow(ids[0],kind="series",key="sample-sprint",label="Example Sprint Cars")

    app=FastAPI()
    app.include_router(standings_public.router)
    client=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    url="/api/public/race-center/people/timtest/connections"
    followers=client.get(url,params={"kind":"followers"})
    assert followers.status_code==200,followers.text
    data=followers.json()
    assert data["total"]==1 and data["people"][0]["handle"]=="fan3"
    assert data["next_offset"] is None
    assert data["people"][0]["display_name"]=="Race Fan"
    assert not any(field in str(data) for field in ("fan@example.invalid","password_hash","session_version"))
    following=client.get(url,params={"kind":"following"})
    assert following.status_code==200
    assert following.json()["people"][0]["handle"]=="racer2"
    assert client.get(url,params={"kind":"following","limit":1,"offset":1}).json()["people"]==[]
    assert client.get(url,params={"kind":"bogus"}).status_code==422
    assert client.get(url,params={"kind":"followers","limit":100}).status_code==422
    assert client.get("/api/public/race-center/people/missing/connections").status_code==404
    assert client.get("/api/public/race-center/people/timtest").json()["series"][0]["label"]=="Example Sprint Cars"
    print("Social lists: public read, correct relationships, pagination, privacy PASS")
