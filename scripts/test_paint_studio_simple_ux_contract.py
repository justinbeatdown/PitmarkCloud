from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / 'api' / 'paint-studio.html').read_text(encoding='utf-8')
js = (ROOT / 'api' / 'paint-studio.js').read_text(encoding='utf-8')
routes = (ROOT / 'api' / 'content_tools.py').read_text(encoding='utf-8')
service = (ROOT / 'services' / 'paint_studio.py').read_text(encoding='utf-8')

checks = {
    'asset tray exists': 'id="assetInput"' in html and 'id="assetList"' in html,
    'conversation history exists': 'id="conversationHistory"' in html,
    'advanced template controls are collapsed': 'id="advancedTemplateSettings"' in html and '<details' in html,
    'engine is injected into authenticated html': 'PAINT_STUDIO_ENGINE' in html and 'paint-studio.js?v=' not in html and 'replace("<!-- PAINT_STUDIO_ENGINE -->"' in routes,
    'boot status is not falsely ready': '>Starting engine…<' in html and "setStatus('Ready')" in js,
    'attachments can be added before template': 'Load a template before adding logos' not in js,
    'generation sends attachment roles': "form.append('asset_roles_json'" in js and "form.append('assets'" in js,
    'backend accepts multiple attachments': 'assets: list[UploadFile]' in routes and 'attachments=attachments' in routes,
    'service accepts multiple attachments': 'attachments: list[PaintAttachment]' in service and 'attachment_roles' in service,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise AssertionError('Missing simple UX contract: ' + ', '.join(failed))
print('PAINT_STUDIO_SIMPLE_UX_CONTRACT_OK')
