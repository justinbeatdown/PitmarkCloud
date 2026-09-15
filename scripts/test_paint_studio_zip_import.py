import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.paint_studio_template import prepare_template_upload


def png_bytes(size=(1024, 1024), color=(20, 30, 40, 255)):
    out = BytesIO()
    Image.new('RGBA', size, color).save(out, format='PNG')
    return out.getvalue()


archive = BytesIO()
with ZipFile(archive, 'w') as zf:
    zf.writestr('readme.txt', 'ignore me')
    zf.writestr('preview.png', png_bytes((512, 512)))
    zf.writestr('car_template.png', png_bytes((2048, 2048)))

result = prepare_template_upload(archive.getvalue(), 'iracing-template.zip')
assert result['source_type'] == 'zip'
assert result['chosen_entry'] == 'car_template.png'
assert result['width'] == 2048 and result['height'] == 2048
assert result['paint_png']
assert result['has_guide'] is False
assert result['has_overlay'] is False

print('PAINT_STUDIO_ZIP_IMPORT_OK')
