# Pitmark Paint Studio PSD-Aware Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the private Pitmark Paint Studio import original layered iRacing PSD templates, preserve template/guide/protected layers outside the AI paint result, and still export finished PNG/TGA files at the original PSD resolution.

**Architecture:** Add a focused server-side PSD parser/compositor using `psd-tools`; expose owner/admin-only import and re-render endpoints; update the browser editor to show a layer-role tree and compose AI paint + guides + protected overlays + exact logos separately. The image model continues to receive raster images only, while the uploaded PSD remains the authoritative source and is never modified or persisted.

**Tech Stack:** FastAPI, Python 3, `psd-tools`, Pillow, vanilla browser JavaScript/canvas, existing OpenAI image-edit service.

**Spec:** `docs/superpowers/specs/2026-09-15-paint-studio-psd-aware-design.md`

## Global Constraints

- Paint Studio remains private/internal and separate from PRT.
- PSD input limit is 80 MB.
- PSD bytes are processed in memory and not persisted.
- Final exports remain PNG and uncompressed 32-bit TGA at original PSD resolution.
- Guide layers are visible while editing but excluded from export.
- Protected overlay layers are never replaced by AI output.
- Exact logos remain client-side objects and are never sent to AI unless deliberately used as inspiration.
- Owner/admin authentication remains required for all Paint Studio PSD endpoints.

---

### Task 1: PSD parser and role-classification service

**Files:**
- Create: `services/paint_studio_psd.py`
- Modify: `requirements.txt`
- Test: `scripts/test_paint_studio_psd_contract.py`

**Interfaces:**
- Produces `MAX_PSD_BYTES`, `PsdStudioError`, `classify_layer_role(name, inherited_role=None)`, `parse_psd_template(psd_bytes, filename, role_overrides=None)`.
- `parse_psd_template` returns `{name,width,height,layers,paint_png,guide_png,overlay_png}` where PNG values are base64 strings and all composites use the PSD canvas dimensions.

- [ ] **Step 1: Write failing contract tests** for keyword classification, inheritance/override behavior, required return keys, and 80 MB limit constant.
- [ ] **Step 2: Run the contract tests and confirm they fail** because the PSD service does not yet exist.
- [ ] **Step 3: Add `psd-tools>=1.10,<2.0`** to `requirements.txt`.
- [ ] **Step 4: Implement the PSD service** using `PSDImage.open(BytesIO(...))`, a nested manifest walker, conservative role assignment, and transparent RGBA canvas composites.
- [ ] **Step 5: Run compile/contract tests** and confirm the service passes all tests available in the local environment.
- [ ] **Step 6: Commit** with message `feat: add Paint Studio PSD parser`.

### Task 2: Owner/admin PSD import and re-render endpoints

**Files:**
- Modify: `api/content_tools.py`
- Test: `scripts/test_paint_studio_psd_routes_contract.py`

**Interfaces:**
- Consumes `parse_psd_template`, `MAX_PSD_BYTES`, and `PsdStudioError`.
- Produces `POST /api/control/content/paint-studio/psd/import` and `POST /api/control/content/paint-studio/psd/render`.

- [ ] **Step 1: Write failing route contract tests** confirming both route strings exist, both call `_require_paint_studio`, and uploads are bounded to `MAX_PSD_BYTES + 1`.
- [ ] **Step 2: Run tests and confirm failure** before route implementation.
- [ ] **Step 3: Implement import endpoint** accepting one `.psd`, rejecting oversize/non-PSD filenames, parsing in memory, and returning JSON with no-store headers.
- [ ] **Step 4: Implement re-render endpoint** accepting the original PSD plus `role_overrides_json`, validating JSON to a `dict[str,str]`, reparsing without server-side storage, and returning updated composites.
- [ ] **Step 5: Convert parser errors to clear HTTP 400 responses** and unexpected failures to 502.
- [ ] **Step 6: Run route contract tests and Python compilation**.
- [ ] **Step 7: Commit** with message `feat: expose Paint Studio PSD endpoints`.

### Task 3: PSD-first browser import and layer-role UI

**Files:**
- Modify: `api/paint-studio.html`
- Modify: `api/paint-studio.css`
- Modify: `api/paint-studio.js`
- Test: `scripts/test_paint_studio_frontend_contract.py`

**Interfaces:**
- Consumes PSD import/re-render JSON from Task 2.
- Browser state adds `sourceMode`, `psdFile`, `layerManifest`, `roleOverrides`, `paintImage`, `guideImage`, and `overlayImage` while preserving exact-logo state.

- [ ] **Step 1: Write failing frontend contract tests** for `.psd` acceptance, a `PSD Layers` section, role dropdown values `paint/guide/overlay/ignore`, PSD import endpoint string, PSD render endpoint string, and separate guide/overlay state.
- [ ] **Step 2: Run tests and confirm failure**.
- [ ] **Step 3: Change the source picker to PSD-first** with `.psd` accepted and legacy raster input clearly labeled secondary/flattened.
- [ ] **Step 4: Render the nested PSD layer manifest** as an indented list/tree with per-node role dropdowns and useful metadata.
- [ ] **Step 5: On role changes, POST original PSD + role overrides** to the re-render endpoint and replace only the PSD composites on success.
- [ ] **Step 6: Keep current state intact on failed import/re-render** and surface the server error in the status pill.
- [ ] **Step 7: Add CSS for the layer tree** without altering the existing Pitmark visual identity.
- [ ] **Step 8: Run frontend contract tests**.
- [ ] **Step 9: Commit** with message `feat: add PSD layer controls to Paint Studio`.

### Task 4: AI generation and canvas composition separation

**Files:**
- Modify: `services/paint_studio.py`
- Modify: `api/paint-studio.js`
- Test: `scripts/test_paint_studio_ai_contract.py`

**Interfaces:**
- `generate_livery_edit` continues to take one editable raster as the first image but now supports a dedicated optional `guide` raster before user inspiration.
- Browser editor draws `paint -> guide(edit-only) -> overlay -> exact logos -> selection chrome` and exports `paint -> overlay -> exact logos`.

- [ ] **Step 1: Write failing tests** confirming the AI service accepts a guide image and sends it as a distinct `image[]` reference when supplied.
- [ ] **Step 2: Update the AI prompt** so the separate guide image is authoritative UV/template geometry that must not be rearranged or painted into the final scheme.
- [ ] **Step 3: Update multipart assembly** to include guide and inspiration references in deterministic order.
- [ ] **Step 4: Refactor browser drawing** so guide and overlay composites are separate from the editable paint image.
- [ ] **Step 5: Update AI generation** to send only current editable paint plus guide context and optional inspiration, then replace only the paint image with the AI result.
- [ ] **Step 6: Preserve undo/reset history for paint only** while guide/overlay/role selections remain unchanged.
- [ ] **Step 7: Run contract tests and JS syntax check where available**.
- [ ] **Step 8: Commit** with message `feat: preserve PSD guides and overlays during AI paint`.

### Task 5: Export, regression checks, and deployment readiness

**Files:**
- Modify as needed: `api/paint-studio.js`
- Test: `scripts/test_paint_studio_export_contract.py`

**Interfaces:**
- PNG and TGA exports include paint + protected overlay + exact logos and explicitly exclude guide content and editor selection chrome.

- [ ] **Step 1: Write failing export contract tests** for explicit export composition behavior and original-dimension preservation.
- [ ] **Step 2: Ensure PNG export uses the export-only scene compositor** without guide content.
- [ ] **Step 3: Ensure TGA export uses the same export-only compositor** and keeps existing 32-bit BGRA encoding.
- [ ] **Step 4: Run all Paint Studio contract tests plus `py_compile`** over touched Python files.
- [ ] **Step 5: Review the feature diff against the PSD-aware design spec** for auth, privacy, role separation, export behavior, and PRT isolation.
- [ ] **Step 6: Open a PR from `feature/paint-studio-psd-aware` to `main`** and verify mergeability/CI status.
- [ ] **Step 7: After merge, verify the Render deployment reaches application startup complete**.
- [ ] **Step 8: Update the Pitmark Master Checklist** with deployed status and the remaining live real-iRacing-PSD smoke test.
