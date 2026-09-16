from __future__ import annotations

import re

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+){1,3})(?:[-+].*)?$", re.IGNORECASE)
_VERSION_SEARCH_RE = re.compile(r"\bv?(\d+\.\d+\.\d+(?:\.\d+)?)\b", re.IGNORECASE)


def version_key(value: object) -> tuple[int, ...] | None:
    text = str(value or "").strip()
    match = _VERSION_RE.fullmatch(text)
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def compare_versions(candidate: object, baseline: object) -> int | None:
    candidate_key = version_key(candidate)
    baseline_key = version_key(baseline)
    if candidate_key is None or baseline_key is None:
        return None
    return (candidate_key > baseline_key) - (candidate_key < baseline_key)


def newest_version(*values: object) -> str | None:
    best_text: str | None = None
    best_key: tuple[int, ...] | None = None
    for value in values:
        text = str(value or "").strip().lstrip("vV")
        key = version_key(text)
        if key is None:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best_text = text
    return best_text


def extract_version(value: object) -> str | None:
    match = _VERSION_SEARCH_RE.search(str(value or ""))
    return match.group(1) if match else None
