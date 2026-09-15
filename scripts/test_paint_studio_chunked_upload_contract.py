from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / "api" / "paint-studio.js").read_text(encoding="utf-8")
api = (ROOT / "api" / "content_tools.py").read_text(encoding="utf-8")
helper_path = ROOT / "services" / "paint_studio_uploads.py"

assert helper_path.exists(), "Paint Studio must have a server-side staged PSD upload helper"
helper = helper_path.read_text(encoding="utf-8")

assert "PSD_CHUNK_BYTES" in js, "Browser must split PSDs into small chunks"
assert "uploadPsdInChunks" in js, "PSD load path must use chunked upload"
assert "/paint-studio/psd/chunk" in js, "Browser must send staged PSD chunks"
assert "/paint-studio/psd/complete" in js, "Browser must finalize staged PSD uploads"
assert "/paint-studio/psd/render-upload" in js, "Advanced role changes must reuse the staged PSD"
assert "form.append('psd', file" not in js, "Initial PSD load must not send one giant multipart body"

assert '@router.post("/paint-studio/psd/chunk"' in api
assert '@router.post("/paint-studio/psd/complete"' in api
assert '@router.post("/paint-studio/psd/render-upload"' in api
assert "stage_psd_chunk" in api and "complete_psd_upload" in api and "read_staged_psd" in api

assert "MAX_CHUNK_BYTES" in helper
assert "MAX_PSD_BYTES" in helper
assert "cleanup_stale_uploads" in helper
assert "UploadSessionError" in helper

print("PAINT_STUDIO_CHUNKED_UPLOAD_CONTRACT_OK")
