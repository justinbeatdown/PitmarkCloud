"""Official partner identity is immutable and not a Pitmark staff permission."""
from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
accounts = (root/"services/race_center_accounts.py").read_text("utf-8")
database = (root/"services/database.py").read_text("utf-8")
profile_js = (root/"api/race_center_profile.js").read_text("utf-8")
profile_html = (root/"api/race_center_profile.html").read_text("utf-8")
css = (root/"api/race_center_refined.css").read_text("utf-8")
staff_api = (root/"api/standings_public.py").read_text("utf-8")

ast.parse(accounts)
ast.parse(database)
assert "class RaceCenterOfficialBadge(Base):" in accounts
assert "class RaceCenterBadgeSeed(Base):" in accounts
assert 'seed_key = "pitmark-tim-chappell-partner-20261018"' in accounts
assert 'RaceCenterProfile.handle == "timmyneutron020"' in accounts
assert '"tim chappell"' in accounts
assert "recipient_id = user.id" in accounts
assert "recipient_user_id=recipient_id" in accounts
assert '"kind": badge.kind' in accounts
assert '"official_badge": _official_badge(db, user.id)' in accounts
assert "race_center_accounts.seed_tim_official_partner_badge()" in database
assert 'id="pitmarkPartnerBadge"' in profile_html
assert "official.kind==='partner'" in profile_js
assert "partnerBadge.hidden=!isPartner" in profile_js
assert ".pitmark-partner-badge" in css
assert "rgba(55,177,255,.63)" in css
assert "partner-badge-20261018" in profile_html
assert "official-partner-20261018" in profile_html

# Crucial: authorization checks staff only, and the partner never appears
# in the privileged PITMARK_STAFF_ACCOUNTS map or its return value.
assert "def _race_staff_or_403(" in staff_api
assert '(profile.get("staff") or {}).get("label")' in staff_api
staff_block=accounts.split("PITMARK_STAFF_ACCOUNTS = {",1)[1].split("def _pitmark_staff_identity",1)[0]
assert "timmyneutron020" not in staff_block
assert "Tim Chappell" not in staff_block
assert "official_badge" not in staff_block
print("Official partner badge structural/privacy/permission regression PASS")
