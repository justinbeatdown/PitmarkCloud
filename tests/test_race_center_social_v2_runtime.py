"""End-to-end Race Center Social V2 contract: feeds, replies, alerts, media, reports."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

with TemporaryDirectory() as tmp:
    os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp)/"social-v2.db")
    os.environ["PITMARK_SIGNING_SECRET"]="race-social-v2-testing-"+"Z"*45
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.database import Base,engine,SessionLocal
    from services import race_center_accounts as accounts
    from services import race_center_social_v2 as social
    from api import standings_public
    Base.metadata.create_all(bind=engine)

    me=accounts.create_account("me-v2@example.test","TestPassword12345!","My Racer")
    followed=accounts.create_account("followed-v2@example.test","TestPassword12345!","Followed Driver")
    outsider=accounts.create_account("outsider-v2@example.test","TestPassword12345!","Unrelated Racer")
    staff=accounts.create_account("justin@pitmarkracing.com","TestPassword12345!","Founder")
    for person in (me,followed,outsider,staff):accounts.ensure_profile(person.id)
    assert accounts.follow_user(me.id,followed.id)["created"] is True
    social.notify_follow(me.id,followed.id)
    follower_notices=social.list_notifications(followed.id)
    assert follower_notices["unread"]==1
    assert follower_notices["notifications"][0]["kind"]=="new_follower"
    assert social.list_notifications(me.id)["unread"]==0
    assert social.mark_notifications_read(followed.id)["marked"]==1
    assert social.list_notifications(followed.id)["unread"]==0

    mine=accounts.create_post(me.id,body="My own practice")
    friend=accounts.create_post(followed.id,body="Followed driver update")
    outsider_post=accounts.create_post(outsider.id,body="Unrelated public general post")
    accounts.set_follow(me.id,kind="series",key="race-series-88",label="Series 88")
    accounts.set_follow(me.id,kind="driver",key="race-driver-17",label="Driver 17")
    series_post=accounts.create_post(outsider.id,body="Official series news",series_key="race-series-88")
    driver_post=accounts.create_post(outsider.id,body="Driver in series",driver_key="race-driver-17")
    with patch.object(social.race_center_entities,"my_racing_brief",return_value={}),\
         patch.object(social.race_center_owner_hub,"followed_updates",return_value=[]):
        following=social.get_feed(me.id,"following",40)
        discover=social.get_feed(me.id,"discover",40)
    followed_ids={row["id"] for row in following["posts"]}
    discovered_ids={row["id"] for row in discover["posts"]}
    assert mine["id"] in followed_ids and friend["id"] in followed_ids
    assert series_post["id"] in followed_ids and driver_post["id"] in followed_ids
    assert outsider_post["id"] not in followed_ids
    assert outsider_post["id"] in discovered_ids
    assert following["mode"]=="following" and discover["mode"]=="discover"
    try:social.get_feed(None,"following")
    except PermissionError:pass
    else:raise AssertionError("Anonymous following feed not protected")

    top=social.add_thread_comment(me.id,friend["id"],"Thanks!")
    reply=social.add_thread_comment(followed.id,friend["id"],"You're welcome",top["id"])
    notices=social.list_notifications(me.id)
    assert any(row["kind"]=="reply" for row in notices["notifications"])
    with patch.object(social.race_center_entities,"my_racing_brief",return_value={}),\
         patch.object(social.race_center_owner_hub,"followed_updates",return_value=[]):
        stream=social.get_feed(me.id,"following",40)
    threaded=next(p for p in stream["posts"] if p["id"]==friend["id"])
    comment=next(c for c in threaded["comments"] if c["id"]==reply["id"])
    assert comment["parent_comment_id"]==top["id"],comment

    example=b"\x89PNG\r\n\x1a\n"+b"\x00"*120
    up=social.save_media(me.id,mine["id"],example,"image/png")
    assert up["type"]=="image"
    assert social.media_for_post(mine["id"])==(example,"image/png")
    try:social.save_media(outsider.id,mine["id"],example,"image/png")
    except ValueError:pass
    else:raise AssertionError("Other user attached media to my post")
    try:social.save_media(me.id,mine["id"],b"<svg></svg>","image/svg+xml")
    except ValueError:pass
    else:raise AssertionError("Unsafe media type accepted")

    assert social.submit_report(me.id,"post",outsider_post["id"],"spam",details="Spam account")["ok"]
    assert social.submit_report(me.id,"post",outsider_post["id"],"spam")["already_reported"]
    queue=social.moderation_queue()
    assert len(queue["reports"])==1
    assert "Unrelated public" in queue["reports"][0]["content"]
    result=social.review_report(staff.id,queue["reports"][0]["id"],"removed","Violation reviewed.")
    assert result["status"]=="removed"
    assert social.media_for_post(outsider_post["id"]) is None
    assert outsider_post["id"] not in {r["id"] for r in accounts.list_posts(discover_all=True)}

    app=FastAPI()
    app.include_router(standings_public.router)
    browser=TestClient(app,base_url="https://racecenter.pitmarkracing.com")
    anon=browser.get("/api/public/race-center/social/timeline")
    assert anon.status_code==401,anon.text
    public=browser.get("/api/public/race-center/social/timeline?mode=discover")
    assert public.status_code==200,public.text
    assert browser.get("/api/public/race-center/social/notifications").status_code==401
    assert browser.get("/api/public/race-center/social/reports/review").status_code==401
    # Media is public only for public non-deleted posts.
    media=browser.get("/api/public/race-center/feed/"+str(mine["id"])+"/media")
    assert media.status_code==200 and media.content==example
    assert media.headers["X-Content-Type-Options"]=="nosniff"
    chunk=browser.get("/api/public/race-center/feed/"+str(mine["id"])+"/media",headers={"Range":"bytes=0-7"})
    assert chunk.status_code==206 and chunk.content==example[:8],chunk.text
    assert chunk.headers["Content-Range"]==f"bytes 0-7/{len(example)}"
    assert browser.get("/api/public/race-center/feed/"+str(mine["id"])+"/media",
                       headers={"Range":"bytes=999999-"}).status_code==416
    small_mp4=bytes([0,0,0,24])+b"ftypisom"+bytes(48)
    assert social.save_media(outsider.id,series_post["id"],small_mp4,"video/mp4")["type"]=="video"
    clip=browser.get("/api/public/race-center/feed/"+str(series_post["id"])+"/media",
                     headers={"Range":"bytes=8-11"})
    assert clip.status_code==206 and clip.content==b"isom"
    print("Following vs Discover, actor notifications, replies, media, reports and auth PASS")
