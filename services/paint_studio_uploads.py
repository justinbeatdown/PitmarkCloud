from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from services.paint_studio_template import MAX_TEMPLATE_BYTES


class UploadSessionError(RuntimeError):
    pass


MAX_CHUNK_BYTES = 768 * 1024
MAX_CHUNKS = 256
UPLOAD_TTL_SECONDS = 60 * 60
UPLOAD_ROOT = Path(tempfile.gettempdir()) / "pitmark-paint-studio-uploads"
ALLOWED_EXTENSIONS = {'.zip', '.psd', '.png', '.tga', '.jpg', '.jpeg', '.webp'}


def _clean_upload_id(upload_id: str) -> str:
    try:
        return str(uuid.UUID(str(upload_id or "").strip()))
    except (ValueError, AttributeError, TypeError) as exc:
        raise UploadSessionError("Invalid template upload session.") from exc


def _session_dir(upload_id: str) -> Path:
    return UPLOAD_ROOT / _clean_upload_id(upload_id)


def _safe_filename(filename: str) -> str:
    name = Path(str(filename or "template.zip")).name.strip() or "template.zip"
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadSessionError("Choose an iRacing template ZIP, PSD, PNG, TGA, JPG, or WEBP file.")
    return name


def cleanup_stale_uploads(now: float | None = None) -> None:
    moment = float(now if now is not None else time.time())
    try:
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        for child in UPLOAD_ROOT.iterdir():
            if not child.is_dir():
                continue
            try:
                age = moment - child.stat().st_mtime
            except OSError:
                continue
            if age > UPLOAD_TTL_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
    except OSError:
        return


def _metadata_path(session: Path) -> Path:
    return session / "meta.json"


def _source_path(session: Path) -> Path:
    return session / "source.bin"


def _load_metadata(session: Path) -> dict:
    try:
        data = json.loads(_metadata_path(session).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UploadSessionError("Template upload session is incomplete or expired.") from exc
    if not isinstance(data, dict):
        raise UploadSessionError("Template upload session metadata is invalid.")
    return data


def stage_psd_chunk(*, upload_id: str, filename: str, file_size: int, index: int, total: int, chunk: bytes) -> dict:
    cleanup_stale_uploads()
    session = _session_dir(upload_id)
    clean_name = _safe_filename(filename)
    size = int(file_size)
    part_index = int(index)
    part_total = int(total)

    if size <= 0 or size > MAX_TEMPLATE_BYTES:
        raise UploadSessionError("Template file must be between 1 byte and 150 MB.")
    if part_total <= 0 or part_total > MAX_CHUNKS:
        raise UploadSessionError("Template upload has an invalid chunk count.")
    if part_index < 0 or part_index >= part_total:
        raise UploadSessionError("Template upload has an invalid chunk index.")
    if not chunk or len(chunk) > MAX_CHUNK_BYTES:
        raise UploadSessionError("Template upload chunk is empty or too large.")

    session.mkdir(parents=True, exist_ok=True)
    meta_path = _metadata_path(session)
    expected = {"filename": clean_name, "file_size": size, "total": part_total}
    if meta_path.exists():
        existing = _load_metadata(session)
        if any(existing.get(key) != value for key, value in expected.items()):
            raise UploadSessionError("Template upload session metadata changed during upload.")
    else:
        meta_path.write_text(json.dumps(expected, separators=(",", ":")), encoding="utf-8")

    (session / f"{part_index:04d}.part").write_bytes(chunk)
    received = sum(1 for path in session.glob("*.part") if path.is_file())
    return {"ok": True, "received": received, "total": part_total}


def complete_psd_upload(upload_id: str) -> tuple[bytes, str]:
    cleanup_stale_uploads()
    session = _session_dir(upload_id)
    meta = _load_metadata(session)
    filename = _safe_filename(str(meta.get("filename") or "template.zip"))
    expected_size = int(meta.get("file_size") or 0)
    total = int(meta.get("total") or 0)
    if expected_size <= 0 or expected_size > MAX_TEMPLATE_BYTES or total <= 0 or total > MAX_CHUNKS:
        raise UploadSessionError("Template upload session metadata is invalid.")

    parts = [session / f"{index:04d}.part" for index in range(total)]
    missing = [path.name for path in parts if not path.is_file()]
    if missing:
        raise UploadSessionError(f"Template upload is missing {len(missing)} chunk(s).")

    source = _source_path(session)
    written = 0
    with source.open("wb") as out:
        for part in parts:
            data = part.read_bytes()
            written += len(data)
            if written > MAX_TEMPLATE_BYTES:
                raise UploadSessionError("Template file exceeds the 150 MB limit.")
            out.write(data)

    if written != expected_size:
        source.unlink(missing_ok=True)
        raise UploadSessionError("Template upload size did not match the selected file.")

    raw = source.read_bytes()
    for part in parts:
        part.unlink(missing_ok=True)
    return raw, filename


def read_staged_psd(upload_id: str) -> tuple[bytes, str]:
    cleanup_stale_uploads()
    session = _session_dir(upload_id)
    meta = _load_metadata(session)
    source = _source_path(session)
    if not source.is_file():
        raise UploadSessionError("Template upload session is incomplete or expired.")
    raw = source.read_bytes()
    if not raw or len(raw) > MAX_TEMPLATE_BYTES:
        raise UploadSessionError("Staged template is empty or exceeds the 150 MB limit.")
    return raw, _safe_filename(str(meta.get("filename") or "template.zip"))
