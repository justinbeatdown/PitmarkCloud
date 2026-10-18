"""Runtime test: official partner badge stays with an immutable account ID."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    os.environ["DATABASE_URL"]="sqlite:///"+str(Path(tmp)/"badge.db")
    from services.database import Base, engine, SessionLocal
    from services import race_center_accounts as rc

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        tim=rc.RaceCenterUser(email="tim@example.invalid",display_name="Tim Chappell",password_salt="salt",password_hash="hash")
        other=rc.RaceCenterUser(email="other@example.invalid",display_name="Other Driver",password_salt="salt",password_hash="hash")
        db.add_all([tim,other]);db.flush()
        tim_id=tim.id
        other_id=other.id
        db.add_all([
          rc.RaceCenterProfile(user_id=tim_id,handle="timmyneutron020"),
          rc.RaceCenterProfile(user_id=other_id,handle="otherdriver"),
        ])
        db.commit()

    assert rc.seed_tim_official_partner_badge()
    assert rc.seed_tim_official_partner_badge()
    person=rc.public_profile_by_handle("timmyneutron020")
    assert person["official_badge"]["kind"]=="partner"
    assert person["staff"]=={}
    with SessionLocal() as db:
        db.get(rc.RaceCenterProfile,tim_id).handle="newtimhandle"
        db.get(rc.RaceCenterProfile,other_id).handle="timmyneutron020"
        db.commit()
    assert rc.seed_tim_official_partner_badge()
    assert rc.public_profile_by_handle("newtimhandle")["official_badge"]["kind"]=="partner"
    assert rc.public_profile_by_handle("timmyneutron020")["official_badge"]=={}
    print("Official Partner account ID and non-staff guard PASS")
