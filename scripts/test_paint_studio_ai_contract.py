from pathlib import Path


SERVICE = Path("services/paint_studio.py").read_text(encoding="utf-8")
API = Path("api/content_tools.py").read_text(encoding="utf-8")
JS = Path("api/paint-studio.js").read_text(encoding="utf-8")


def run() -> None:
    assert "guide_bytes: bytes | None = None" in SERVICE
    assert '"The SECOND supplied image is a protected UV/template guide' in SERVICE
    assert 'guide_name or "guide.png"' in SERVICE
    assert "if guide_bytes:" in SERVICE
    assert "guide: UploadFile | None" in API
    assert "guide_bytes=guide_bytes" in API
    assert "form.append('guide'" in JS
    assert "state.baseImage = asset" in JS
    assert "state.guideImage" in JS and "state.overlayImage" in JS
    print("PAINT_STUDIO_AI_CONTRACT_OK")


if __name__ == "__main__":
    run()
