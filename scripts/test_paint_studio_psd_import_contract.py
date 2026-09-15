from pathlib import Path


SERVICE = Path("services/paint_studio_psd.py").read_text(encoding="utf-8")
API = Path("api/content_tools.py").read_text(encoding="utf-8")


def run() -> None:
    assert "MAX_PSD_BYTES = 80 * 1024 * 1024" in SERVICE
    assert "PSDImage.open(BytesIO(psd_bytes))" in SERVICE
    assert '"paint_png": _png_b64(paint)' in SERVICE
    assert '"guide_png": _png_b64(guide)' in SERVICE
    assert '"overlay_png": _png_b64(overlay)' in SERVICE
    assert "@router.post(\"/paint-studio/psd/import\"" in API
    assert "@router.post(\"/paint-studio/psd/render\"" in API
    assert "MAX_PSD_BYTES + 1" in API
    print("PAINT_STUDIO_PSD_IMPORT_CONTRACT_OK")


if __name__ == "__main__":
    run()
