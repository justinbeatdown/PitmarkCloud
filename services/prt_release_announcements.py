from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import discord
import httpx

from services import persistent_store
from utils.config import settings

log = logging.getLogger("pitmark.discord.prt_release")

STATE_KEY = "prt_release_last_announced_version"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_CHANGE_ITEMS = 30
MAX_FIELD_CHARS = 1000


def _clean_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        lines: list[str] = []
        for raw in value.replace("\r", "").split("\n"):
            line = raw.strip().lstrip("-•* ").strip()
            if line:
                lines.append(line)
        return lines
    return []


def normalize_release(manifest: dict[str, Any]) -> dict[str, Any]:
    version = str(manifest.get("version") or "").strip().lstrip("v")
    if not version:
        raise ValueError("PRT release manifest is missing version")

    notes_payload = manifest.get("releaseNotes")
    source = manifest
    if notes_payload is not None:
        if not isinstance(notes_payload, dict):
            raise ValueError(f"PRT release {version} has invalid releaseNotes payload")
        notes_version = str(notes_payload.get("version") or "").strip().lstrip("v")
        if not notes_version or notes_version != version:
            raise ValueError(
                f"PRT release-note version mismatch: manifest={version} notes={notes_version or 'missing'}"
            )
        source = notes_payload

    changes = _clean_lines(source.get("changes")) or _clean_lines(source.get("notes"))
    if not changes and source is not manifest:
        changes = _clean_lines(manifest.get("changes")) or _clean_lines(manifest.get("notes"))
    if not changes:
        raise ValueError(f"PRT release {version} has no release notes")

    title = str(source.get("title") or manifest.get("title") or f"PRT v{version}").strip()
    summary = str(
        source.get("summary")
        or manifest.get("summary")
        or "A new Pitmark Racing Tools build is available."
    ).strip()

    return {
        "version": version,
        "title": title[:256],
        "summary": summary[:4000],
        "changes": changes[:MAX_CHANGE_ITEMS],
        "required": bool(manifest.get("required", False)),
    }


def _change_chunks(changes: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""
    for item in changes:
        line = f"• {item}".strip()
        if len(line) > MAX_FIELD_CHARS:
            line = line[: MAX_FIELD_CHARS - 3].rstrip() + "..."
        candidate = line if not current else f"{current}\n{line}"
        if len(candidate) <= MAX_FIELD_CHARS:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = line
    if current:
        chunks.append(current)
    return chunks[:8]


def build_release_embed(release: dict[str, Any]) -> discord.Embed:
    version = str(release["version"])
    embed = discord.Embed(
        title=f"🏁 PRT v{version} IS LIVE",
        description=str(release.get("summary") or "A new Pitmark Racing Tools build is available."),
        color=0xFF5500,
    )

    for index, chunk in enumerate(_change_chunks(list(release.get("changes") or []))):
        embed.add_field(
            name="What changed" if index == 0 else "What changed — continued",
            value=chunk,
            inline=False,
        )

    embed.add_field(
        name="Update",
        value=(
            "Open PRT to update automatically, or download the latest Windows build from "
            "https://prt.pitmarkracing.com/"
        ),
        inline=False,
    )
    if release.get("required"):
        embed.add_field(
            name="Update status",
            value="This release is marked as a required update.",
            inline=False,
        )
    embed.set_footer(text="Pitmark Racing Co. • Leave Your Mark.")
    return embed
