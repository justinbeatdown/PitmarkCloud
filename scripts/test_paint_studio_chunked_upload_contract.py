from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
api = (ROOT / "api" / "content_tools.py").read_text(encoding="utf-8")
shim_path = ROOT / "api" / "paint-studio-upload.js"
helper_path = ROOT / "services" / "paint_studio_uploads.py"

assert shim_path.exists(), "Paint Studio must load a dedicated upload transport shim"
assert helper_path.exists(), "Paint Studio must have a server-side staged PSD upload helper"

shim = shim_path.read_text(encoding="utf-8")
helper = helper_path.read_text(encoding="utf-8")

assert "PSD_CHUNK_BYTES" in shim, "Browser must split PSDs into small chunks"
assert "nativeFetch" in shim and "window.fetch" in shim, "Shim must transparently intercept PSD fetches"
assert "/paint-studio/psd/chunk" in shim, "Browser must send staged PSD chunks"
assert "/paint-studio/psd/complete" in shim, "Browser must finalize staged PSD uploads"
assert "/paint-studio/psd/render-upload" in shim, "Advanced role changes must reuse the staged PSD"
assert "file.slice" in shim, "Chunk upload must slice the original File instead of buffering the whole PSD"

assert '@router.get("/paint-studio-upload.js"' in api
assert '@router.post("/paint-studio/psd/chunk"' in api
assert '@router.post("/paint-studio/psd/complete"' in api
assert '@router.post("/paint-studio/psd/render-upload"' in api
assert "stage_psd_chunk" in api and "complete_psd_upload" in api and "read_staged_psd" in api
assert "paint-studio-upload.js" in api and "paint-studio.js?v=4" in api

assert "MAX_CHUNK_BYTES" in helper
assert "MAX_PSD_BYTES" in helper
assert "cleanup_stale_uploads" in helper
assert "UploadSessionError" in helper
assert "read_staged_psd" in helper

print("PAINT_STUDIO_CHUNKED_UPLOAD_CONTRACT_OK")
