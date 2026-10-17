"""PRT linked profile regression contracts: navigation, privacy and no-data UX."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
api=(ROOT/"api/prt_race_center_bridge.py").read_text(encoding="utf-8")
page=(ROOT/"api/race_center_profile.html").read_text(encoding="utf-8")
profile=(ROOT/"api/race_center_profile.js").read_text(encoding="utf-8")
home=(ROOT/"api/standings_public.html").read_text(encoding="utf-8")
home_js=(ROOT/"api/standings_public.js").read_text(encoding="utf-8")
style=(ROOT/"api/race_center_prt_profile.css").read_text(encoding="utf-8")
ast.parse(api)
assert '@router.get("/race-center/me"' in api
assert 'race_center_accounts.ensure_profile(account.id)' in api
assert 'url="/race-center/u/" + profile["handle"]' in api
assert '"connected_devices": int(device_count)' in api
assert 'PrtDevice.revoked.is_(False)' in api
assert '@router.get("/race-center-prt-profile.css"' in api
assert 'id="viewMyProfile"' in api
assert 'id="myRacerProfileShortcut"' in home
assert 'href="/race-center/me"' in home
assert "quickProfile.hidden=!authed" in home_js
assert 'id="profilePrtPrivateStats" hidden' in page
assert 'id="profilePrtRecentRaces"' in page
assert '/race-center-prt-profile.css' in page
assert 'const ownPrt = Boolean(account.authenticated && account.profile && account.profile.handle === profile.handle)' in profile
assert 'if(ownPrt)await renderPrtOwnerDashboard()' in profile
assert "/api/public/race-center/prt/my-summary" in profile
assert "/api/public/race-center/prt/my-sessions" in profile
assert "history.visibility!=='private'" in profile
assert "No connected PRT computers" in profile
assert "Sync Now" in profile
assert "Auto-sync" in profile
assert "trackCell.textContent=" in profile
assert "recentHost.appendChild(table)" in profile
assert "textContent" in profile
assert len(style)>1800
print("PRT racer profile dashboard contracts pass")
