from pathlib import Path


SOURCE = Path("api/content_tools.py").read_text(encoding="utf-8")


def run() -> None:
    assert '@router.post("/paint-studio/psd/import"' in SOURCE
    assert '@router.post("/paint-studio/psd/render"' in SOURCE
    assert SOURCE.count("_require_paint_studio(request)") >= 5
    assert "MAX_PSD_BYTES + 1" in SOURCE
    assert "role_overrides_json" in SOURCE
    assert "parse_psd_template(raw, filename)" in SOURCE
    assert "parse_psd_template(raw, filename, overrides)" in SOURCE
    print("PAINT_STUDIO_PSD_ROUTES_CONTRACT_OK")


if __name__ == "__main__":
    run()
