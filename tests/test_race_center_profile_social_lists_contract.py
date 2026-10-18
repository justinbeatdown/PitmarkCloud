"""Regression: non-owner profile management is not exposed; social totals open useful lists."""
from pathlib import Path
import ast

root=Path(__file__).resolve().parents[1]
read=lambda path:(root/path).read_text(encoding="utf-8")
page=read("api/race_center_profile.html")
js=read("api/race_center_profile.js")
css=read("api/race_center_refined.css")
backend=read("api/standings_public.py")
accounts=read("services/race_center_accounts.py")
ast.parse(backend);ast.parse(accounts)
assert 'id="prtOwnerActions" hidden' in page
assert '#prtOwnerActions[hidden]' in css
assert 'if(ownerActions)ownerActions.hidden=!ownPrt' in js
assert "if($('#prtOwnerActions'))$('#prtOwnerActions').hidden=true" in js
assert 'Number(account.id)===Number(profile.id)' in js
assert 'data-profile-list="followers"' in page
assert 'data-profile-list="following"' in page
assert 'data-profile-list="series"' in page
assert 'id="profileConnectionsDialog"' in page
assert 'id="profileConnectionsResults"' in page
assert 'id="profileConnectionsMore"' in page
assert 'profileConnectionsDialog' in js and 'showModal()' in js
assert "dialog.open" in js
assert "'/connections?kind='" in js or "'/connections?kind='" in js
assert "mode==='series'" in js and 'profile.series' in js
assert "connectionsLink(item,true)" in js
assert "connectionsLink(item,false)" in js
assert "@router.get(\"/api/public/race-center/people/{handle}/connections\"" in backend
assert 'public_profile_connections(' in accounts
assert '"email":' not in accounts.split("def public_profile_connections(",1)[1].split("def discover_people(",1)[0]
assert '[hidden]' in css
assert 'social-stats-owner-20261018' in page
print("Owner-only controls and clickable social statistics contracts PASS")
