"""Race Center staff workspace and profile ownership regression contract."""
from pathlib import Path
import ast
from html.parser import HTMLParser

root=Path(__file__).resolve().parents[1]
read=lambda p:(root/p).read_text(encoding="utf-8")
api=read("api/standings_public.py")
profile=read("api/race_center_profile.html")
profile_js=read("api/race_center_profile.js")
main=read("api/standings_public.html")
main_js=read("api/standings_public.js")
css=read("api/race_center_refined.css")
admin=read("api/race_center_admin.html")
admin_js=read("api/race_center_admin.js")
admin_css=read("api/race_center_admin.css")
ast.parse(api)
assert '@router.get("/race-center/admin"' in api
assert '@router.get("/race-center-admin.css"' in api
assert '@router.get("/race-center-admin.js"' in api
assert '_race_staff_or_403(request)' in api.split('def race_center_staff_admin(request: Request):')[1].split('@router.get',1)[0]
assert '_race_staff_or_403(request)' in api
assert 'id="raceStaffAdminShortcut"' in main
assert 'id="profileStaffAdminLink"' in profile
assert "state.account.profile.staff.label" in main_js
assert "account.profile.staff.label" in profile_js
assert '#raceStaffAdminShortcut[hidden]' in css
assert '#followerEmailSection[hidden]' in css
assert '#profilePrtPrivateStats[hidden]' in css
assert '#profileFollowerNotifications[hidden]' in css
assert 'Number(account.id)===Number(profile.id)' in profile_js
assert 'id="pitmarkPartnerBadge"' in profile
assert 'class="pitmark-partner-logo" src="/prt-logo.png"' in profile
assert '.pitmark-partner-badge img.pitmark-partner-logo' in css
assert 'pitmark-partner-symbol" aria-hidden' not in profile
assert 'id="seriesQueue"' in admin and 'id="claimQueue"' in admin
assert 'id="editorialForm"' in admin
assert '/api/public/race-center/series-submissions/review' in admin_js
assert '/api/public/race-center/entity-claims/review' in admin_js
assert '/api/public/race-center/editorial-links' in admin_js
assert "credentials:'same-origin'" in admin_js
assert 'window.confirm(' in admin_js
assert 'textContent' in admin_js and 'innerHTML' not in admin_js
assert 'body{' in admin_css and '@media(max-width:720px)' in admin_css

class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set()
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if "id" in d:
            assert d["id"] not in self.ids,d["id"]
            self.ids.add(d["id"])
for page in (profile,main,admin):
    markup=Markup()
    markup.feed(page)
assert "followerEmailSection" in profile
print("Race Center staff interface, partner art, ownership and security contracts PASS")
