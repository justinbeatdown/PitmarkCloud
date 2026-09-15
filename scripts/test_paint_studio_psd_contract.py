from __future__ import annotations

import base64
import sys
import types
from io import BytesIO

from PIL import Image

from services.paint_studio_psd import MAX_PSD_BYTES, classify_layer_role, parse_psd_template


class FakeLayer:
    def __init__(self, name: str, *, kind: str = "pixel", children=None, visible: bool = True):
        self.name = name
        self.kind = kind
        self.visible = visible
        self.opacity = 255
        self.blend_mode = "normal"
        self.bbox = (0, 0, 4, 4)
        self._children = list(children or [])

    def __iter__(self):
        if self.kind not in {"group", "artboard"}:
            raise TypeError("not a group")
        return iter(self._children)


class FakePSD(list):
    width = 4
    height = 4

    def composite(self, *, viewport, layer_filter, **kwargs):
        assert viewport == (0, 0, 4, 4)
        image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))

        def visit(nodes):
            for layer in nodes:
                if layer_filter(layer) and layer.kind == "pixel" and layer.visible:
                    image.putpixel((0, 0), (255, 255, 255, 255))
                if layer.kind in {"group", "artboard"}:
                    visit(layer._children)

        visit(self)
        return image


class FakePSDImage:
    @staticmethod
    def open(_file):
        return FakePSD(
            [
                FakeLayer("Base Paint"),
                FakeLayer("Wireframe", kind="group", children=[FakeLayer("UV mesh")]),
                FakeLayer("Mandatory Logos"),
                FakeLayer("Spec Map"),
            ]
        )


def png_size(encoded: str) -> tuple[int, int]:
    return Image.open(BytesIO(base64.b64decode(encoded))).size


def run() -> None:
    assert MAX_PSD_BYTES == 80 * 1024 * 1024
    assert classify_layer_role("Wireframe") == "guide"
    assert classify_layer_role("Mandatory Logos") == "overlay"
    assert classify_layer_role("Specular Map") == "ignore"
    assert classify_layer_role("Body Color") == "paint"
    assert classify_layer_role("Body Color", "guide") == "guide"

    fake_module = types.ModuleType("psd_tools")
    fake_module.PSDImage = FakePSDImage
    prior = sys.modules.get("psd_tools")
    sys.modules["psd_tools"] = fake_module
    try:
        result = parse_psd_template(b"fake-psd", "car.psd")
        assert result["name"] == "car.psd"
        assert result["width"] == 4 and result["height"] == 4
        assert [node["role"] for node in result["layers"]] == ["paint", "guide", "overlay", "ignore"]
        assert result["layers"][1]["children"][0]["role"] == "guide"
        assert png_size(result["paint_png"]) == (4, 4)
        assert png_size(result["guide_png"]) == (4, 4)
        assert png_size(result["overlay_png"]) == (4, 4)

        overridden = parse_psd_template(b"fake-psd", "car.psd", {"1": "ignore", "1/0": "paint"})
        assert overridden["layers"][1]["role"] == "ignore"
        assert overridden["layers"][1]["children"][0]["role"] == "paint"
    finally:
        if prior is None:
            sys.modules.pop("psd_tools", None)
        else:
            sys.modules["psd_tools"] = prior

    print("PAINT_STUDIO_PSD_CONTRACT_OK")


if __name__ == "__main__":
    run()
