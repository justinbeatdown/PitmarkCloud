"""Race Center Social V2 structure, navigation and permission guard contract."""
from pathlib import Path
import ast

root=Path(__file__).resolve().parents[1]
read=lambda p:(root/p).read_text(encoding="utf-8")
api=read("api/standings_public.py")
service=read("services/race_center_social_v2.py")
accounts=read("services/race_center_accounts.py")
html=read("api/race_center_social.html")
js=read("api/race_center_social.js")
css=read("api/race_center_social.css")
admin=read("api/race_center_admin.html")
admin_js=read("api/race_center_social_moderation.js")
main=read("api/standings_public.html")
profile=read("api/race_center_profile.html")
db=read("services/database.py")
for src in (api,service,accounts,db):ast.parse(src)
for path in (main,profile):
    assert 'href="/race-center/social"' in path
assert 'href="/race-center/social?notifications=1"' in main
assert 'href="/race-center/social?notifications=1"' in profile
assert 'id="followingTab"' in html and 'id="discoverTab"' in html
assert 'id="socialComposer"' in html
assert 'id="socialMediaInput"' in html
assert 'id="socialNotifications"' in html
assert 'id="socialReportDialog"' in html
assert 'id="socialFeed"' in html
assert 'id="social-moderation"' in admin
assert 'id="socialReportsQueue"' in admin
assert 'race-center-social-moderation.js' in admin
assert '"/race-center-social-moderation.js"' in api
assert '"/api/public/race-center/social/timeline"' in api
assert '"/api/public/race-center/social/notifications"' in api
assert '"/api/public/race-center/social/notifications/read"' in api
assert '"/api/public/race-center/social/report"' in api
assert '"/api/public/race-center/social/reports/review"' in api
assert '"/api/public/race-center/feed/{post_id}/media"' in api
assert '_race_staff_or_403(request)' in api
assert '_race_account_or_401(request)' in api
assert 'MAX_IMAGE=5*1024*1024' in service
assert 'MAX_VIDEO=12*1024*1024' in service
assert '"video/mp4"' in service and '"video/webm"' in service
assert 'RaceSocialNotification' in service
assert 'RaceSocialReport' in service
assert 'RaceSocialReply' in service
assert 'RaceSocialMedia' in service
assert 'accounts.list_posts(' in service
assert 'following_only=mode=="following"' in service
assert 'discover_all=mode=="discover"' in service
assert 'race_center_owner_hub.followed_updates' in service
assert 'race_center_entities.my_racing_brief' in service
assert 'RaceCenterPost.series_key.in_(series_keys)' in accounts
assert 'RaceCenterPost.driver_key.in_(driver_keys)' in accounts
assert 'RaceCenterPost.user_id.in_(followed_people)' in accounts
assert 'RaceCenterPost.series_key == ""' not in accounts.split("if following_only and not author_user_id:",1)[1].split("elif not discover_all",1)[0]
assert "showModal()" in js
assert "renderEntityUpdate(" in js
assert "renderPost(" in js
assert "renderPost(item.record):renderEntityUpdate(item.record)" in js
assert "new FormData()" in js
assert "parent_comment_id" in js
assert "reportTarget={target_type:type,target_id:id}" in js
assert "innerHTML" not in js and "innerHTML" not in admin_js
assert '"/api/public/race-center/social/reports/"' not in admin_js  # actual path built from JS string below
assert "'/api/public/race-center/social/reports/'" in admin_js
assert "textContent" in js
assert ".rc-post-media" in css
assert "@media(max-width:670px)" in css
assert "from services import race_center_social_v2  # noqa: F401" in db
print("Race Center social markup, routes, feed privacy and safe rendering PASS")
