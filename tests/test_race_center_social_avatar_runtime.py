"""Social post/comment avatar responses use the same saved profile photos as full profiles."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp)/"social-avatars.db")
    os.environ["PITMARK_SIGNING_SECRET"]="avatar-test-secret-"+"V"*48
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.database import Base,engine
    from services import race_center_accounts as rc
    from api import standings_public

    Base.metadata.create_all(bind=engine)
    racer=rc.create_account("racer-avatar@example.invalid","SamplePassword123!","Racer Photo")
    follower=rc.create_account("follower-avatar@example.invalid","SamplePassword123!","Another Racer")
    racer_profile=rc.ensure_profile(racer.id)
    follower_profile=rc.ensure_profile(follower.id)
    rc.set_profile_photo(racer.id,b"WEBP-SAMPLE-AVATAR","image/webp")
    created=rc.create_post(racer.id,body="Race night is here")
    rc.add_comment(follower.id,created["id"],"Good luck!")
    app=FastAPI()
    app.include_router(standings_public.router)
    client=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    photo=client.get("/api/public/race-center/profile-photo/"+racer_profile["handle"])
    assert photo.status_code==200 and photo.content==b"WEBP-SAMPLE-AVATAR"
    assert photo.headers["content-type"]=="image/webp"
    posts=client.get("/api/public/race-center/profile-wall/"+racer_profile["handle"])
    assert posts.status_code==200,posts.text
    data=posts.json()["posts"][0]
    assert data["author"]["handle"]==racer_profile["handle"]
    assert data["author"]["photo_url"].endswith(racer_profile["handle"])
    assert data["comments"][0]["author"]["handle"]==follower_profile["handle"]
    assert data["comments"][0]["author"]["photo_url"].endswith(follower_profile["handle"])
    assert data["comment_count"]==1
    assert "email" not in data["author"] and "email" not in data["comments"][0]["author"]
    assert data["owner"] is False
    rc.toggle_reaction(follower.id,created["id"],"checkered")
    assert client.get("/api/public/race-center/profile-wall/"+racer_profile["handle"]).json()["posts"][0]["reactions"]["checkered"]==1
    print("Social photo endpoint and public post/comment author avatars PASS")
