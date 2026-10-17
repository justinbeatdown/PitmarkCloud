from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
bridge = (root / "api" / "prt_race_center_bridge.py").read_text(encoding="utf8")
main = (root / "main.py").read_text(encoding="utf8")
ast.parse(bridge)
ast.parse(main)
for route in (
    "/api/public/race-center/prt/link/start",
    "/api/public/race-center/prt/link/approve",
    "/api/public/race-center/prt/link/token",
    "/api/public/race-center/prt/sessions",
    "/api/public/race-center/prt/device/revoke",
    "/api/public/race-center/prt/my-summary",
    "/api/public/race-center/prt/my-sessions",
):
    assert route in bridge, route
assert "prt_race_center_bridge.router" in main
assert "can_upload_private_history" in bridge
assert "PrtDevice.revoked.is_(False)" in bridge
assert "visibility" in bridge and '"private"' in bridge
assert "race_center_accounts.account_from_request" in bridge
print("PRT Race Center pairing contract and Python syntax PASS")
