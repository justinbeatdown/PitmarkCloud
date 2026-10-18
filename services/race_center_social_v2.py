"""Race Center social V2: authenticated notifications, safely bounded media and moderation.

No new privileges. Existing session cookies, staff-role gate and SQL database apply.
Media lives in the configured durable SQL database until dedicated object storage exists:
short clips only, never silently accepting unbounded video uploads.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column
from services.database import Base, SessionLocal
from services import race_center_accounts as accounts
from services import race_center_entities

log=logging.getLogger("pitmark.race_center.social")
MAX_IMAGE=5*1024*1024
MAX_VIDEO=12*1024*1024
ALLOWED_REASONS={"spam","harassment","abuse","impersonation","unsafe","other"}

def now():
    return datetime.now(timezone.utc)

class RaceSocialMedia(Base):
    __tablename__="race_center_post_media_v2"
    post_id: Mapped[int]=mapped_column(ForeignKey("race_center_posts.id",ondelete="CASCADE"),primary_key=True)
    owner_id: Mapped[int]=mapped_column(ForeignKey("race_center_users.id",ondelete="CASCADE"),index=True)
    media_type: Mapped[str]=mapped_column(String(15),nullable=False)
    content_type: Mapped[str]=mapped_column(String(40),nullable=False)
    media_data: Mapped[bytes]=mapped_column(LargeBinary,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class RaceSocialReply(Base):
    __tablename__="race_center_comment_replies_v2"
    child_comment_id: Mapped[int]=mapped_column(ForeignKey("race_center_comments.id",ondelete="CASCADE"),primary_key=True)
    parent_comment_id: Mapped[int]=mapped_column(ForeignKey("race_center_comments.id",ondelete="CASCADE"),index=True)

class RaceSocialNotification(Base):
    __tablename__="race_center_notifications_v2"
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    recipient_id: Mapped[int]=mapped_column(ForeignKey("race_center_users.id",ondelete="CASCADE"),index=True)
    actor_id: Mapped[int]=mapped_column(ForeignKey("race_center_users.id",ondelete="CASCADE"))
    kind: Mapped[str]=mapped_column(String(30),nullable=False)
    post_id: Mapped[int | None]=mapped_column(Integer,nullable=True)
    comment_id: Mapped[int | None]=mapped_column(Integer,nullable=True)
    read: Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)

class RaceSocialReport(Base):
    __tablename__="race_center_reports_v2"
    __table_args__=(UniqueConstraint("reporter_id","target_type","target_id",name="uq_race_report_one_per_user"),)
    id: Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    reporter_id: Mapped[int]=mapped_column(ForeignKey("race_center_users.id",ondelete="CASCADE"),index=True)
    target_type: Mapped[str]=mapped_column(String(15),nullable=False)
    target_id: Mapped[int]=mapped_column(Integer,nullable=False)
    reason: Mapped[str]=mapped_column(String(30),nullable=False)
    details: Mapped[str]=mapped_column(Text,default="")
    status: Mapped[str]=mapped_column(String(20),default="pending",index=True)
    reviewer_id: Mapped[int | None]=mapped_column(Integer,nullable=True)
    review_note: Mapped[str]=mapped_column(Text,default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    reviewed_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True),nullable=True)

def _notify(db,recipient:int,actor:int,kind:str,post_id:int|None=None,comment_id:int|None=None):
    if recipient==actor:return
    db.add(RaceSocialNotification(recipient_id=recipient,actor_id=actor,kind=kind,post_id=post_id,comment_id=comment_id))

def notify_follow(follower_id:int,followed_id:int):
    with SessionLocal() as db:
        # Guard idempotent semantics at the caller; no notice for an unfollow.
        relation=db.scalar(select(accounts.RaceCenterConnection.id).where(
            accounts.RaceCenterConnection.follower_user_id==follower_id,
            accounts.RaceCenterConnection.followed_user_id==followed_id).limit(1))
        if not relation:return
        _notify(db,followed_id,follower_id,"new_follower")
        db.commit()

def add_thread_comment(author_id:int,post_id:int,body:str,parent_comment_id:int|None=None):
    clean=(body or "").strip()
    if not clean or len(clean)>600:raise ValueError("Comments must be 1–600 characters.")
    with SessionLocal() as db:
        post=db.get(accounts.RaceCenterPost,post_id)
        if not post or post.deleted or post.visibility!="public":
            raise ValueError("Post not found.")
        parent=None
        if parent_comment_id is not None:
            parent=db.get(accounts.RaceCenterComment,parent_comment_id)
            if not parent or parent.deleted or parent.post_id!=post_id:
                raise ValueError("The comment you're replying to is not available.")
            # Keep a readable one-level conversation; a reply to a reply
            # points to the original parent instead of nesting indefinitely.
            original=db.get(RaceSocialReply,parent_comment_id)
            if original:
                parent=db.get(accounts.RaceCenterComment,original.parent_comment_id)
                if not parent or parent.deleted:raise ValueError("Original comment unavailable.")
        row=accounts.RaceCenterComment(post_id=post_id,user_id=author_id,body=clean)
        db.add(row);db.flush()
        if parent:
            db.add(RaceSocialReply(child_comment_id=row.id,parent_comment_id=parent.id))
            _notify(db,parent.user_id,author_id,"reply",post_id,row.id)
        _notify(db,post.user_id,author_id,"comment",post_id,row.id)
        db.commit()
        return {"id":row.id,"ok":True}

def list_notifications(user_id:int,limit:int=40):
    with SessionLocal() as db:
        unread=db.scalar(select(func.count(RaceSocialNotification.id)).where(
            RaceSocialNotification.recipient_id==user_id,RaceSocialNotification.read.is_(False))) or 0
        rows=db.scalars(select(RaceSocialNotification).where(
            RaceSocialNotification.recipient_id==user_id).order_by(
                RaceSocialNotification.created_at.desc(),RaceSocialNotification.id.desc()
            ).limit(max(1,min(int(limit),60)))).all()
        actors={i:db.get(accounts.RaceCenterUser,i) for i in {r.actor_id for r in rows}}
        profiles={i:db.get(accounts.RaceCenterProfile,i) for i in actors}
        notices=[]
        for n in rows:
            p=profiles.get(n.actor_id)
            u=actors.get(n.actor_id)
            handle=p.handle if p else ""
            notices.append({
                "id":n.id,"kind":n.kind,"read":n.read,
                "created_at":n.created_at.isoformat() if n.created_at else None,
                "actor":{"name":u.display_name if u else "Racer","handle":handle,
                         "photo_url":"/api/public/race-center/profile-photo/"+handle if handle else ""},
                "post_id":n.post_id,
                "url":"/race-center/social"+("?post="+str(n.post_id) if n.post_id else "") if n.post_id
                       else "/race-center/u/"+quote(handle,safe="") if handle else "/race-center",
            })
        return {"unread":unread,"notifications":notices}

def mark_notifications_read(user_id:int,ids:list[int]|None=None):
    with SessionLocal() as db:
        stmt=select(RaceSocialNotification).where(RaceSocialNotification.recipient_id==user_id,
                 RaceSocialNotification.read.is_(False))
        if ids is not None:
            stmt=stmt.where(RaceSocialNotification.id.in_([int(x) for x in ids[:100]]))
        count=0
        for row in db.scalars(stmt).all():
            row.read=True;count+=1
        db.commit()
        return {"ok":True,"marked":count}

def sniff_media(data:bytes,declared:str):
    mime=(declared or "").split(";",1)[0].lower().strip()
    if mime=="image/jpeg" and data.startswith(b"\xff\xd8\xff"):return "image",mime,MAX_IMAGE
    if mime=="image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"):return "image",mime,MAX_IMAGE
    if mime=="image/webp" and data[:4]==b"RIFF" and data[8:12]==b"WEBP":return "image",mime,MAX_IMAGE
    if mime=="video/mp4" and data[4:8]==b"ftyp":return "video",mime,MAX_VIDEO
    if mime=="video/webm" and data.startswith(b"\x1a\x45\xdf\xa3"):return "video",mime,MAX_VIDEO
    raise ValueError("Supported formats: JPEG, PNG, WebP, MP4, WebM.")

def save_media(owner_id:int,post_id:int,data:bytes,declared:str):
    kind,mime,limit=sniff_media(data,declared)
    if len(data)>limit:raise ValueError("Media too large (images 5 MB, videos 12 MB).")
    with SessionLocal() as db:
        post=db.get(accounts.RaceCenterPost,post_id)
        if not post or post.deleted or post.user_id!=owner_id:raise ValueError("Only the author can attach media.")
        row=db.get(RaceSocialMedia,post_id)
        if row is None:
            row=RaceSocialMedia(post_id=post_id,owner_id=owner_id,media_type=kind,
                               content_type=mime,media_data=data)
            db.add(row)
        else:
            row.content_type=mime;row.media_type=kind;row.media_data=data
        db.commit()
    return {"ok":True,"type":kind,"url":"/api/public/race-center/feed/"+str(post_id)+"/media"}

def media_for_post(post_id:int):
    with SessionLocal() as db:
        post=db.get(accounts.RaceCenterPost,post_id)
        if not post or post.deleted or post.visibility!="public":return None
        media=db.get(RaceSocialMedia,post_id)
        return (bytes(media.media_data),media.content_type) if media else None

def attach_media(posts:list[dict]):
    if not posts:return posts
    ids=[int(p["id"]) for p in posts]
    with SessionLocal() as db:
        media=db.scalars(select(RaceSocialMedia).where(RaceSocialMedia.post_id.in_(ids))).all()
        indexed={m.post_id:m.media_type for m in media}
    for post in posts:
        kind=indexed.get(post["id"])
        post["media"]={"type":kind,"url":"/api/public/race-center/feed/"+str(post["id"])+"/media"} if kind else None
    return posts

def enrich_replies(posts:list[dict]):
    ids=[c["id"] for p in posts for c in p.get("comments",[])]
    if not ids:return posts
    with SessionLocal() as db:
        rows=db.scalars(select(RaceSocialReply).where(RaceSocialReply.child_comment_id.in_(ids))).all()
        relations={r.child_comment_id:r.parent_comment_id for r in rows}
    for post in posts:
        for comment in post.get("comments",[]):
            comment["parent_comment_id"]=relations.get(comment["id"])
    return posts

def get_feed(user_id:int|None,mode:str="following",limit:int=30,offset:int=0):
    if mode not in {"following","discover"}:raise ValueError("Unknown feed.")
    if mode=="following" and user_id is None:raise PermissionError("Sign in to view Following.")
    follows=accounts.list_follows(user_id) if user_id else []
    series=[x["key"] for x in follows if x["kind"]=="series"]
    drivers=[x["key"] for x in follows if x["kind"]=="driver"]
    # Use DB-level filtering before offset, not a truncated global feed.
    posts=accounts.list_posts(
        viewer_user_id=user_id,limit=limit,offset=offset,
        series_keys=series if mode=="following" else None,
        driver_keys=drivers if mode=="following" else None,
        following_only=mode=="following",
        discover_all=mode=="discover",
    )
    attach_media(posts);enrich_replies(posts)
    # Source-backed series race-day entries, never fabricated user posts.
    activity=[]
    if mode=="following" and follows:
        try:
            brief=race_center_entities.my_racing_brief(follows)
            for kind in ("live","upcoming","movement"):
                for row in (brief.get(kind) or [])[:8]:
                    key=str(row.get("series_key") or "")
                    activity.append({
                        "kind":kind,
                        "title":str(row.get("name") or row.get("series_name") or row.get("driver") or "Racing update"),
                        "description":str(row.get("series_name") or row.get("track") or ""),
                        "time":row.get("start") if kind=="upcoming" else None,
                        "url":"/race-center/event/"+quote(str(row.get("key") or ""),safe="")
                              if kind in {"live","upcoming"} else
                              "/race-center/standings",
                    })
        except Exception:
            log.exception("Unable to load following series race activity")
    return {"mode":mode,"posts":posts,"activities":activity[:16],
            "next_offset":offset+len(posts) if len(posts)>=limit else None,
            "follows":{"people":len(accounts.followed_user_ids(user_id)) if user_id else 0,
                       "series":len(series),"drivers":len(drivers)}}

def submit_report(reporter:int,target_type:str,target_id:int,reason:str,details:str=""):
    if target_type not in {"post","comment"} or reason not in ALLOWED_REASONS:
        raise ValueError("Select a valid report target and reason.")
    with SessionLocal() as db:
        target=db.get(accounts.RaceCenterPost if target_type=="post" else accounts.RaceCenterComment,target_id)
        if not target or target.deleted:raise ValueError("Content not found.")
        old=db.scalar(select(RaceSocialReport.id).where(
            RaceSocialReport.reporter_id==reporter,RaceSocialReport.target_type==target_type,
            RaceSocialReport.target_id==target_id))
        if old:return {"ok":True,"already_reported":True}
        row=RaceSocialReport(reporter_id=reporter,target_type=target_type,target_id=target_id,
                             reason=reason,details=(details or "").strip()[:1000])
        db.add(row);db.commit()
    return {"ok":True,"already_reported":False}

def moderation_queue(limit:int=70):
    with SessionLocal() as db:
        rows=db.scalars(select(RaceSocialReport).where(RaceSocialReport.status=="pending").order_by(
            RaceSocialReport.created_at.asc()).limit(max(1,min(limit,100)))).all()
        reports=[]
        for r in rows:
            target=db.get(accounts.RaceCenterPost if r.target_type=="post" else accounts.RaceCenterComment,r.target_id)
            reports.append({"id":r.id,"target_type":r.target_type,"target_id":r.target_id,
                "reason":r.reason,"details":r.details,"submitted_at":r.created_at.isoformat(),
                "content":str(target.body if target else "[deleted]")[:600],
                "reporter_id":r.reporter_id})
        return {"reports":reports}

def review_report(staff_id:int,report_id:int,action:str,note:str=""):
    if action not in {"dismissed","removed"}:raise ValueError("Review action must be dismissed or removed.")
    with SessionLocal() as db:
        row=db.get(RaceSocialReport,report_id)
        if not row:raise ValueError("Report not found.")
        if row.status!="pending":raise ValueError("Report already reviewed.")
        if action=="removed":
            target=db.get(accounts.RaceCenterPost if row.target_type=="post" else accounts.RaceCenterComment,row.target_id)
            if target:target.deleted=True
            # Resolve duplicate reports on the removed content too.
            for duplicate in db.scalars(select(RaceSocialReport).where(
                RaceSocialReport.target_type==row.target_type,
                RaceSocialReport.target_id==row.target_id,
                RaceSocialReport.status=="pending")).all():
                duplicate.status="removed";duplicate.reviewer_id=staff_id
                duplicate.review_note=(note or "").strip()[:1000];duplicate.reviewed_at=now()
        else:
            row.status=action;row.reviewer_id=staff_id;row.review_note=(note or "").strip()[:1000]
            row.reviewed_at=now()
        db.commit()
        return {"ok":True,"status":action}
