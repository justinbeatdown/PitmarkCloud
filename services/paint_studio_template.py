from __future__ import annotations

import base64
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from PIL import Image, ImageFile

from services.paint_studio_psd import PsdStudioError, parse_psd_template

ImageFile.LOAD_TRUNCATED_IMAGES = True

MAX_TEMPLATE_BYTES = 150 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 250
MAX_ARCHIVE_UNCOMPRESSED = 350 * 1024 * 1024
MAX_ARCHIVE_MEMBER = 120 * 1024 * 1024
RASTER_EXTENSIONS = {'.png', '.tga', '.jpg', '.jpeg', '.webp'}


class TemplateStudioError(RuntimeError):
    pass


def _png_b64(image: Image.Image) -> str:
    out = BytesIO()
    image.convert('RGBA').save(out, format='PNG')
    return base64.b64encode(out.getvalue()).decode('ascii')


def _empty_png_b64(width: int, height: int) -> str:
    return _png_b64(Image.new('RGBA', (width, height), (0, 0, 0, 0)))


def _raster_payload(raw: bytes, name: str, *, source_type: str, chosen_entry: str | None = None) -> dict:
    try:
        image = Image.open(BytesIO(raw))
        image.load()
        rgba = image.convert('RGBA')
    except Exception as exc:
        raise TemplateStudioError(f'Could not read template image {name}: {exc}') from exc
    width, height = rgba.size
    if width <= 0 or height <= 0:
        raise TemplateStudioError(f'Template image {name} has invalid dimensions.')
    empty = _empty_png_b64(width, height)
    return {
        'name': name,
        'source_type': source_type,
        'chosen_entry': chosen_entry,
        'width': width,
        'height': height,
        'layers': [],
        'paint_png': _png_b64(rgba),
        'guide_png': empty,
        'overlay_png': empty,
        'has_guide': False,
        'has_overlay': False,
    }


def _paint_has_pixels(payload: dict) -> bool:
    try:
        raw = base64.b64decode(payload.get('paint_png') or '')
        image = Image.open(BytesIO(raw)).convert('RGBA')
        return image.getchannel('A').getbbox() is not None
    except Exception:
        return False


def _flatten_psd(raw: bytes, filename: str) -> dict:
    try:
        payload = parse_psd_template(raw, filename)
        if _paint_has_pixels(payload):
            payload['source_type'] = 'psd'
            payload['chosen_entry'] = None
            return payload
    except PsdStudioError:
        pass

    try:
        from psd_tools import PSDImage
        psd = PSDImage.open(BytesIO(raw))
        image = psd.composite(force=True)
        if image is None:
            raise TemplateStudioError('PSD contains no visible composite artwork.')
        payload = _raster_payload(_image_to_png(image), filename, source_type='psd')
        payload['fallback_flattened'] = True
        return payload
    except TemplateStudioError:
        raise
    except Exception as exc:
        raise TemplateStudioError(f'Could not flatten PSD {filename}: {exc}') from exc


def _image_to_png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.convert('RGBA').save(out, format='PNG')
    return out.getvalue()


def _safe_member(info) -> bool:
    path = PurePosixPath(info.filename)
    if info.is_dir() or info.file_size <= 0:
        return False
    if path.is_absolute() or '..' in path.parts:
        return False
    if any(part.startswith('.') for part in path.parts):
        return False
    if '__MACOSX' in path.parts:
        return False
    return True


def _name_score(name: str) -> int:
    clean = name.lower()
    score = 0
    for word, value in (('template', 80), ('paint', 60), ('body', 40), ('car', 30), ('livery', 20)):
        if word in clean:
            score += value
    if 'preview' in clean or 'thumb' in clean or 'thumbnail' in clean:
        score -= 120
    return score


def _prepare_zip(raw: bytes, filename: str) -> dict:
    try:
        zf = ZipFile(BytesIO(raw))
    except BadZipFile as exc:
        raise TemplateStudioError('That file is not a valid ZIP archive.') from exc

    infos = [info for info in zf.infolist() if _safe_member(info)]
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise TemplateStudioError('Template ZIP contains too many files.')
    if sum(info.file_size for info in infos) > MAX_ARCHIVE_UNCOMPRESSED:
        raise TemplateStudioError('Template ZIP expands beyond the safe size limit.')
    if any(info.file_size > MAX_ARCHIVE_MEMBER for info in infos):
        raise TemplateStudioError('Template ZIP contains an individual file that is too large.')

    raster_candidates: list[tuple[int, int, str, bytes]] = []
    psd_candidates: list[tuple[int, str, bytes]] = []
    for info in infos:
        suffix = PurePosixPath(info.filename).suffix.lower()
        if suffix not in RASTER_EXTENSIONS and suffix != '.psd':
            continue
        member = zf.read(info)
        if suffix == '.psd':
            psd_candidates.append((_name_score(info.filename), info.filename, member))
            continue
        try:
            image = Image.open(BytesIO(member))
            image.load()
            width, height = image.size
        except Exception:
            continue
        area = max(0, width) * max(0, height)
        raster_candidates.append((area, _name_score(info.filename), info.filename, member))

    if raster_candidates:
        raster_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, chosen, member = raster_candidates[0]
        payload = _raster_payload(member, PurePosixPath(chosen).name, source_type='zip', chosen_entry=chosen)
        payload['archive_name'] = filename
        return payload

    if psd_candidates:
        psd_candidates.sort(key=lambda item: item[0], reverse=True)
        _, chosen, member = psd_candidates[0]
        payload = _flatten_psd(member, PurePosixPath(chosen).name)
        payload['source_type'] = 'zip'
        payload['chosen_entry'] = chosen
        payload['archive_name'] = filename
        return payload

    raise TemplateStudioError('This ZIP did not contain a usable PNG, TGA, JPG, WEBP, or PSD template.')


def prepare_template_upload(raw: bytes, filename: str) -> dict:
    name = str(filename or '').strip()
    if not raw:
        raise TemplateStudioError('The selected template file is empty.')
    if len(raw) > MAX_TEMPLATE_BYTES:
        raise TemplateStudioError('Template file must be 150 MB or smaller.')
    lower = name.lower()
    if lower.endswith('.zip'):
        return _prepare_zip(raw, name)
    if lower.endswith('.psd'):
        return _flatten_psd(raw, name)
    if any(lower.endswith(ext) for ext in RASTER_EXTENSIONS):
        return _raster_payload(raw, name, source_type='image')
    raise TemplateStudioError('Choose an iRacing template ZIP, PSD, PNG, TGA, JPG, or WEBP file.')
