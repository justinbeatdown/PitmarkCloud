from __future__ import annotations

from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base, SessionLocal


class MailIdentityPreference(Base):
    __tablename__ = "pitmark_mail_identity_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identity_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    signature_html: Mapped[str] = mapped_column(Text, default="")
    signature_enabled: Mapped[str] = mapped_column(String(8), default="true")


def list_preferences() -> dict[str, dict]:
    with SessionLocal() as db:
        rows = list(db.scalars(select(MailIdentityPreference)).all())
        return {
            row.identity_key: {
                "identity_key": row.identity_key,
                "signature_html": row.signature_html or "",
                "signature_enabled": str(row.signature_enabled).lower() != "false",
            }
            for row in rows
        }


def get_preference(identity_key: str) -> dict:
    key = (identity_key or "mail").strip().lower()
    with SessionLocal() as db:
        row = db.scalars(
            select(MailIdentityPreference).where(MailIdentityPreference.identity_key == key)
        ).first()
        if not row:
            return {"identity_key": key, "signature_html": "", "signature_enabled": True}
        return {
            "identity_key": row.identity_key,
            "signature_html": row.signature_html or "",
            "signature_enabled": str(row.signature_enabled).lower() != "false",
        }


def save_preference(identity_key: str, *, signature_html: str, signature_enabled: bool) -> dict:
    key = (identity_key or "mail").strip().lower()
    clean = str(signature_html or "")[:20000]
    with SessionLocal() as db:
        row = db.scalars(
            select(MailIdentityPreference).where(MailIdentityPreference.identity_key == key)
        ).first()
        if row is None:
            row = MailIdentityPreference(identity_key=key)
            db.add(row)
        row.signature_html = clean
        row.signature_enabled = "true" if signature_enabled else "false"
        db.commit()
        db.refresh(row)
        return {
            "identity_key": row.identity_key,
            "signature_html": row.signature_html or "",
            "signature_enabled": str(row.signature_enabled).lower() != "false",
        }
