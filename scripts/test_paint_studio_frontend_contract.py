from pathlib import Path


HTML = Path("api/paint-studio.html").read_text(encoding="utf-8")
JS = Path("api/paint-studio.js").read_text(encoding="utf-8")


def run() -> None:
    assert 'accept=".psd,application/vnd.adobe.photoshop"' in HTML
    assert 'id="psdLayersSection"' in HTML
    assert 'id="layerTree"' in HTML
    assert 'Legacy flattened image' in HTML
    assert '/paint-studio/psd/import' in JS
    assert '/paint-studio/psd/render' in JS
    assert "roleOverrides" in JS
    assert "guideImage" in JS
    assert "overlayImage" in JS
    assert "['paint', 'guide', 'overlay', 'ignore']" in JS
    assert "form.append('role_overrides_json'" in JS
    print("PAINT_STUDIO_FRONTEND_CONTRACT_OK")


if __name__ == "__main__":
    run()
