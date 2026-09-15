from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

utils_pkg = types.ModuleType("utils")
config_mod = types.ModuleType("utils.config")
config_mod.settings = types.SimpleNamespace(
    openai_api_key="test",
    pitmark_image_model="gpt-image-2",
    pitmark_image_timeout_seconds=60,
)
sys.modules.setdefault("utils", utils_pkg)
sys.modules["utils.config"] = config_mod

spec = importlib.util.spec_from_file_location("paint_studio_test_target", ROOT / "services" / "paint_studio.py")
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)

prompt = module._paint_prompt(
    "Create a grassroots Pitmark livery.",
    has_guide=True,
    attachment_roles=["logo", "reference"],
)

assert "Image 3 is a user-supplied LOGO asset" in prompt
assert "Image 4 is a REFERENCE image" in prompt
assert "do not invent a variation" in prompt
assert "User livery brief: Create a grassroots Pitmark livery." in prompt
print("PAINT_STUDIO_ATTACHMENT_PROMPT_OK")
