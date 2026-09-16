from pathlib import Path
import sys

# Final exact-head verification trigger for the guarded Applicant Center identity edit.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.early_access_admin import _application_cards
from services.database import Base
from services.prt_applications import PrtEarlyAccessApplication
import services.prt_application_admin as application_admin


def _row(application_id: int, status: str, name: str, email: str) -> dict:
    return {
        "id": application_id,
        "full_name": name,
        "email": email,
        "discord_username": "tester",
        "iracing_name": "Odyssey Motorsport TV",
        "disciplines": "Broadcaster / Production",
        "race_frequency": "Every week",
        "current_tools": "OBS / ATVO",
        "goals": "Broadcast feedback",
        "source": "website",
        "asset": "",
        "placement": "quick-apply-broadcaster",
        "status": status,
        "created_at": "2026-09-16T21:00:00+00:00",
    }


def main() -> None:
    assert hasattr(application_admin, "update_application_identity"), "identity edit service is missing"

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    application_admin.SessionLocal = Session

    with Session() as db:
        db.add_all(
            [
                PrtEarlyAccessApplication(id=1, full_name="Typo Name", email="typo@gmail.con", status="new"),
                PrtEarlyAccessApplication(id=2, full_name="Hold Name", email="hold@example.com", status="hold"),
                PrtEarlyAccessApplication(id=3, full_name="Accepted Name", email="accepted@example.com", status="accepted"),
                PrtEarlyAccessApplication(id=4, full_name="Existing Person", email="existing@example.com", status="new"),
            ]
        )
        db.commit()

    result = application_admin.update_application_identity(1, "  Lesean Young-Dilworth  ", "  ElzonThaBeat@GMAIL.COM  ")
    assert result["full_name"] == "Lesean Young-Dilworth"
    assert result["email"] == "elzonthabeat@gmail.com"
    with Session() as db:
        corrected = db.get(PrtEarlyAccessApplication, 1)
        assert corrected.full_name == "Lesean Young-Dilworth"
        assert corrected.email == "elzonthabeat@gmail.com"

    hold_result = application_admin.update_application_identity(2, "Held Applicant", "held@example.com")
    assert hold_result["full_name"] == "Held Applicant"
    assert hold_result["email"] == "held@example.com"

    try:
        application_admin.update_application_identity(3, "Changed Accepted", "changed@example.com")
        raise AssertionError("accepted application identity edit should be blocked")
    except ValueError as exc:
        assert "New or On Hold" in str(exc)

    try:
        application_admin.update_application_identity(1, "Lesean Young-Dilworth", "existing@example.com")
        raise AssertionError("duplicate email should be blocked")
    except ValueError as exc:
        assert "already belongs" in str(exc)

    try:
        application_admin.update_application_identity(1, "Lesean Young-Dilworth", "not-an-email")
        raise AssertionError("invalid email should be blocked")
    except ValueError as exc:
        assert "valid email" in str(exc)

    new_card = _application_cards([_row(18, "new", "Lesean Young-Dilwortg", "elzonthabeat@gmail.con")])
    assert '/control/early-access/18/identity' in new_card
    assert 'name="full_name"' in new_card
    assert 'name="email"' in new_card
    assert "CORRECT NAME / EMAIL" in new_card

    hold_card = _application_cards([_row(18, "hold", "Lesean Young-Dilwortg", "elzonthabeat@gmail.con")])
    assert '/control/early-access/18/identity' in hold_card

    accepted_card = _application_cards([_row(18, "accepted", "Lesean Young-Dilworth", "elzonthabeat@gmail.com")])
    assert '/control/early-access/18/identity' not in accepted_card

    print("PRT applicant identity edit contract OK")


if __name__ == "__main__":
    main()
