from __future__ import annotations

import base64
import re
from io import BytesIO
from typing import Iterable

from PIL import Image


class PsdStudioError(RuntimeError):
    pass


MAX_PSD_BYTES = 80 * 1024 * 1024
VALID_ROLES = {"paint", "guide", "overlay", "ignore"}

_ROLE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ignore", ("spec", "specular", "rough", "metal", "normal", "instructions", "read me", "readme", "notes")),
    ("guide", ("wire", "wireframe", "uv", "mesh", "outline", "guide", "template")),
    ("overlay", ("decal", "contingency", "mandatory", "stamp", "logo", "logos")),
)


def _normalized_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def explicit_role_for_name(name: str) -> str | None:
    clean = _normalized_name(name)
    for role, hints in _ROLE_HINTS:
        if any(hint in clean for hint in hints):
            return role
    return None


def classify_layer_role(name: str, inherited_role: str | None = None) -> str:
    explicit = explicit_role_for_name(name)
    if explicit:
        return explicit
    if inherited_role in VALID_ROLES:
        return inherited_role
    return "paint"


def _blend_mode_value(layer) -> str:
    value = getattr(layer, "blend_mode", "normal")
    return str(getattr(value, "value", value) or "normal")


def _layer_kind(layer) -> str:
    return str(getattr(layer, "kind", "layer") or "layer")


def _is_group(layer) -> bool:
    if _layer_kind(layer) in {"group", "artboard"}:
        return True
    try:
        iter(layer)
        return True
    except TypeError:
        return False


def _children(layer) -> list:
    if not _is_group(layer):
        return []
    try:
        return list(layer)
    except TypeError:
        return []


def _bbox(layer) -> list[int]:
    box = getattr(layer, "bbox", (0, 0, 0, 0)) or (0, 0, 0, 0)
    try:
        return [int(box[0]), int(box[1]), int(box[2]), int(box[3])]
    except Exception:
        return [0, 0, 0, 0]


def _png_b64(image: Image.Image) -> str:
    out = BytesIO()
    image.convert("RGBA").save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def _transparent(width: int, height: int) -> Image.Image:
    return Image.new("RGBA", (width, height), (0, 0, 0, 0))


def _composite_role(psd, width: int, height: int, included_ids: set[int]) -> Image.Image:
    if not included_ids:
        return _transparent(width, height)
    try:
        image = psd.composite(
            viewport=(0, 0, width, height),
            layer_filter=lambda layer: id(layer) in included_ids,
            apply_icc=True,
        )
    except TypeError:
        # Compatibility with older psd-tools releases that do not expose
        # apply_icc on PSDImage.composite().
        image = psd.composite(
            viewport=(0, 0, width, height),
            layer_filter=lambda layer: id(layer) in included_ids,
        )
    except Exception as exc:
        raise PsdStudioError(f"Could not render PSD layers: {exc}") from exc

    if image is None:
        return _transparent(width, height)
    rgba = image.convert("RGBA")
    if rgba.size != (width, height):
        canvas = _transparent(width, height)
        canvas.alpha_composite(rgba, (0, 0))
        return canvas
    return rgba


def _walk_manifest(
    nodes: Iterable,
    *,
    role_overrides: dict[str, str],
    inherited_role: str | None,
    inherited_locked: bool,
    parent_visible: bool,
    parent_ids: tuple[int, ...],
    path_prefix: tuple[int, ...],
    include_by_role: dict[str, set[int]],
) -> list[dict]:
    manifest: list[dict] = []

    for index, layer in enumerate(nodes):
        path_parts = path_prefix + (index,)
        path = "/".join(str(part) for part in path_parts)
        name = str(getattr(layer, "name", "Layer") or "Layer")
        override = role_overrides.get(path)
        if override not in VALID_ROLES:
            override = None

        own_explicit = explicit_role_for_name(name)
        if override:
            role = override
            locked = True
            source = "override"
        elif inherited_locked and inherited_role in VALID_ROLES:
            role = inherited_role
            locked = True
            source = "inherited_override"
        else:
            role = own_explicit or (inherited_role if inherited_role in VALID_ROLES else "paint")
            locked = False
            source = "name" if own_explicit else ("inherited" if inherited_role in VALID_ROLES else "default")

        own_visible = bool(getattr(layer, "visible", True))
        effective_visible = parent_visible and own_visible
        layer_id = id(layer)
        children = _children(layer)

        if role != "ignore" and effective_visible:
            include_by_role[role].add(layer_id)
            include_by_role[role].update(parent_ids)

        child_manifest = _walk_manifest(
            children,
            role_overrides=role_overrides,
            inherited_role=role,
            inherited_locked=locked,
            parent_visible=effective_visible,
            parent_ids=parent_ids + (layer_id,),
            path_prefix=path_parts,
            include_by_role=include_by_role,
        ) if children else []

        manifest.append(
            {
                "id": path,
                "path": path,
                "name": name,
                "kind": _layer_kind(layer),
                "role": role,
                "role_source": source,
                "visible": own_visible,
                "effective_visible": effective_visible,
                "opacity": int(getattr(layer, "opacity", 255) or 0),
                "blend_mode": _blend_mode_value(layer),
                "bbox": _bbox(layer),
                "children": child_manifest,
            }
        )

    return manifest


def parse_psd_template(
    psd_bytes: bytes,
    filename: str,
    role_overrides: dict[str, str] | None = None,
) -> dict:
    if not filename.lower().endswith(".psd"):
        raise PsdStudioError("Choose an original iRacing .psd template.")
    if not psd_bytes:
        raise PsdStudioError("PSD file is empty.")
    if len(psd_bytes) > MAX_PSD_BYTES:
        raise PsdStudioError("PSD file must be 80 MB or smaller.")

    clean_overrides = {
        str(key): str(value).lower()
        for key, value in (role_overrides or {}).items()
        if str(value).lower() in VALID_ROLES
    }

    try:
        from psd_tools import PSDImage

        psd = PSDImage.open(BytesIO(psd_bytes))
    except Exception as exc:
        raise PsdStudioError(f"Could not read this PSD: {exc}") from exc

    width = int(getattr(psd, "width", 0) or 0)
    height = int(getattr(psd, "height", 0) or 0)
    if width <= 0 or height <= 0:
        raise PsdStudioError("PSD has invalid canvas dimensions.")

    include_by_role = {role: set() for role in ("paint", "guide", "overlay")}
    try:
        manifest = _walk_manifest(
            list(psd),
            role_overrides=clean_overrides,
            inherited_role=None,
            inherited_locked=False,
            parent_visible=True,
            parent_ids=(),
            path_prefix=(),
            include_by_role=include_by_role,
        )
    except Exception as exc:
        raise PsdStudioError(f"Could not inspect PSD layers: {exc}") from exc

    if not manifest:
        raise PsdStudioError("PSD contains no usable layers.")

    paint = _composite_role(psd, width, height, include_by_role["paint"])
    guide = _composite_role(psd, width, height, include_by_role["guide"])
    overlay = _composite_role(psd, width, height, include_by_role["overlay"])

    return {
        "name": filename,
        "width": width,
        "height": height,
        "layers": manifest,
        "paint_png": _png_b64(paint),
        "guide_png": _png_b64(guide),
        "overlay_png": _png_b64(overlay),
        "has_guide": bool(include_by_role["guide"]),
        "has_overlay": bool(include_by_role["overlay"]),
    }
