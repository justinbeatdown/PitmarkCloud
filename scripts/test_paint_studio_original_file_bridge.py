from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'api' / 'paint-studio-upload.js').read_text(encoding='utf-8')

assert "new File([original]" not in source, 'Do not copy the selected ZIP into a proxy File; Chrome can expose it as zero bytes.'
assert "originalTemplateFile" in source, 'Transport must retain the real browser-selected file.'
assert "const sourceFile = originalTemplateFile" in source, 'Chunk upload must read bytes from the original selected file.'
assert "new Uint8Array([1])" in source, 'Compatibility proxy should be a tiny non-empty sentinel only.'

print('PAINT_STUDIO_ORIGINAL_FILE_BRIDGE_OK')
