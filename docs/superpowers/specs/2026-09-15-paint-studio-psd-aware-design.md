# Pitmark Paint Studio PSD-Aware Import Design

## Goal

Upgrade the private Pitmark Paint Studio so the authoritative iRacing source file can be a layered `.psd`, while the finished paint is still exported as `.tga` or `.png` at the PSD's original canvas size.

## Scope

This is an internal Pitmark production tool only. It remains separate from PRT and from any future Trading Paints-style PRT feature.

The new workflow is:

`iRacing layered PSD -> PSD parser -> layer/group manifest + role-based composites -> AI paint pass -> preserved template overlays/guides + exact logos -> PNG/TGA export`

The PSD remains the authoritative template. Paint Studio must not modify or overwrite the uploaded PSD.

## Architecture

### 1. PSD parsing service

Add a focused backend service using `psd-tools` to read an uploaded PSD in memory. The service returns:

- original canvas width/height
- PSD filename
- nested layer/group structure
- each layer's visible state, opacity, blend mode, bounds, and path/name
- an automatically assigned Paint Studio role for every layer/group
- raster composites needed by the browser

The service must not persist the PSD to disk or external storage.

### 2. Layer roles

Paint Studio will reason about four roles:

- `paint`: editable visual content that the AI is allowed to change and that belongs in the final paint
- `guide`: template information used for alignment/UV context, such as wireframes or UV guides; shown in the editor and supplied as AI context, but excluded from final export
- `overlay`: protected visual content that remains exact and is composited above the AI paint in the final export
- `ignore`: instructions, notes, spec-map helpers, or other content not needed for the working paint

The parser performs conservative role classification from layer/group names. Initial keyword behavior:

- guide hints: `wire`, `wireframe`, `uv`, `mesh`, `outline`, `guide`, `template`
- ignore hints: `spec`, `specular`, `rough`, `metal`, `normal`, `instructions`, `read me`, `readme`, `notes`
- overlay hints: `decal`, `contingency`, `mandatory`, `stamp`, `logo`, `logos`
- everything else defaults to `paint` unless inherited from a classified parent group

Group classification applies to descendants unless a child receives a stronger explicit classification.

Because iRacing PSD naming varies by car, the UI must allow the user to override a layer/group role before generation.

### 3. PSD import endpoint

Add an owner/admin-only endpoint under the existing Paint Studio route:

`POST /api/control/content/paint-studio/psd/import`

Input:

- multipart PSD file

Validation:

- filename must end in `.psd`
- content must parse as a PSD
- size limit: 80 MB for the internal MVP
- canvas dimensions must be nonzero

Response JSON:

- `name`
- `width`
- `height`
- `layers`: nested manifest with stable per-import layer paths/IDs and assigned roles
- `paint_png`: base64 PNG data for the current paint-role composite
- `guide_png`: base64 PNG data for guide-role content
- `overlay_png`: base64 PNG data for protected final overlays

Transparent composites must match the original PSD dimensions exactly.

### 4. Role re-render endpoint

Add:

`POST /api/control/content/paint-studio/psd/render`

Input:

- the original PSD file
- JSON role overrides keyed by layer path/ID

The endpoint reparses the PSD and returns updated `paint_png`, `guide_png`, and `overlay_png` composites. This avoids server-side PSD session storage while still allowing role changes.

### 5. Browser editor changes

The template picker becomes PSD-first:

- primary accepted source: `.psd`
- optional legacy raster import may remain available as a secondary fallback, but it must be visually labeled as a flattened/legacy source

After PSD import the left panel shows a compact `PSD Layers` tree. Each visible layer/group shows:

- name
- role dropdown: Paint / Guide / Overlay / Ignore

Changing a role triggers re-render using the original PSD file and the updated role map.

The canvas composes, in order:

1. AI/current paint raster
2. guide raster while editing only
3. protected overlay raster
4. exact client-side sponsor/logo objects
5. selection chrome while editing only

Final PNG/TGA export omits guide content and selection chrome.

### 6. AI generation behavior

The image model still receives raster images; it does not receive the PSD binary directly.

For each generation:

- editable input image = current paint raster
- guide image = separate reference image when non-empty
- optional user inspiration image = additional reference image
- prompt explicitly states that the guide image is authoritative UV/template geometry and must not be redrawn or rearranged

After the AI result returns, the browser replaces only the editable paint raster. Guide and overlay composites remain unchanged and exact.

This is the key difference from the current flattened workflow: AI output can no longer destroy protected PSD content because protected layers are composited separately after generation.

### 7. Exact logos

Existing exact-logo behavior remains client-side and separate from AI generation. Uploaded sponsor/logo artwork must never be rasterized into the AI request unless the user deliberately chooses it as an inspiration image.

### 8. Export

Export stays exactly as the current iRacing-facing workflow requires:

- PNG at original PSD resolution
- uncompressed 32-bit TGA at original PSD resolution

The exported composite is:

`AI paint + protected overlay + exact logos`

Guide and ignored layers are excluded.

The original PSD is never exported as a modified PSD in this phase.

## Error handling

The UI must show a clear message for:

- corrupt or unsupported PSD
- file over 80 MB
- PSD with no usable composite/layers
- parser failure on an unsupported PSD feature
- role re-render failure
- AI generation failure

A parser failure must leave the previously loaded working state untouched.

## Security and privacy

All PSD endpoints remain owner/admin-only behind the existing Paint Studio authentication flow.

PSD bytes are processed in memory and are not persisted by Paint Studio.

No PRT customer-facing endpoint, licensing, installer integration, or public paint-sharing behavior is added.

## Dependencies

Add `psd-tools>=1.10,<2.0` to the Python runtime. Use its Pillow-compatible raster output for composites.

Do not add a client-side PSD parser for this phase; parsing stays server-side so behavior is consistent and testable.

## Testing

Backend tests must cover:

- valid PSD metadata extraction
- nested groups/layers in the manifest
- conservative automatic role classification
- role override re-rendering
- all returned composites preserving exact source dimensions
- invalid/non-PSD input rejection
- 80 MB size enforcement
- owner/admin access remains required

Frontend contract tests must cover:

- PSD is accepted by the source picker
- imported layer manifest renders into the layer-role UI
- role changes request a re-render
- guide content appears in the editor but not PNG/TGA export
- overlay content remains in export after an AI paint replacement
- legacy raster fallback, if retained, still behaves as a flattened source

The live smoke test must use a real iRacing PSD and verify: import, layer tree, at least one role override, AI paint generation, exact-logo placement, undo/reset, PNG export, and TGA export.

## Success criteria

The change is successful when Justin can select an original layered iRacing PSD directly, see that Paint Studio understands its layer/group structure, keep wireframe/template/protected content separate from AI painting, generate a paint pass without losing those protected layers, and export an iRacing-ready PNG or TGA at the original template resolution.