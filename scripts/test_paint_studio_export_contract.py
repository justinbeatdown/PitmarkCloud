from pathlib import Path


JS = Path("api/paint-studio.js").read_text(encoding="utf-8")


def run() -> None:
    assert "function drawScene(forExport = false)" in JS
    assert "if (!forExport && state.hasGuide && state.guideVisible)" in JS
    assert "if (state.hasOverlay) drawAsset(state.overlayImage);" in JS
    assert "drawScene(true);" in JS
    assert "canvas.toBlob" in JS
    assert "function encodeTga" in JS
    assert "out[16] = 32" in JS
    assert "out[o++] = data[i + 2]" in JS
    print("PAINT_STUDIO_EXPORT_CONTRACT_OK")


if __name__ == "__main__":
    run()
