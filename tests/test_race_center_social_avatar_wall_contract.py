"""Social avatars and functional profile-wall controls regression contract."""
from pathlib import Path
import ast
root=Path(__file__).resolve().parents[1]
read=lambda path:(root/path).read_text(encoding="utf-8")
js=read("api/race_center_profile.js")
css=read("api/race_center_refined.css")
page=read("api/race_center_profile.html")
accounts=read("services/race_center_accounts.py")
ast.parse(accounts)
assert "function racerAvatar(" in js
avatar=js.split("function racerAvatar(",1)[1].split("function connectionsLink(",1)[0]
assert "img.loading='eager'" in avatar
assert "avatar.appendChild(img);" in avatar
assert "img.src='/api/public/race-center/profile-photo/'" in avatar
assert avatar.index("avatar.appendChild(img);") < avatar.index("img.src=")
assert "img.addEventListener('error'" in avatar
assert "avatar.classList.add('has-photo')" in avatar
assert "fallback.textContent=initials(name)" in avatar
list_body=js.split("function connectionsLink(",1)[1].split("async function openConnections(",1)[0]
assert "a.appendChild(racerAvatar(item))" in list_body
assert "img.loading='lazy'" not in list_body
assert "async function refreshProfileWall(" in js
wall=js.split("function renderWall(",1)[1].split("async function prepareProfilePhoto(",1)[0]
assert "profile-post-author-link" in wall and "racerAvatar(" in wall
assert "profile-post-comment" in wall and "commentHandle" in wall
assert "profile-wall-post" in wall and "textContent=String(post.body||'')" in wall
assert "post.viewer_reactions" in wall
assert "'/reaction'" in wall
assert "'/comments'" in wall
assert "method:'DELETE'" in wall
assert "if(!account.authenticated)" in wall
assert "confirm('Delete this Race Center post?')" in wall
assert "img.onerror" not in list_body
assert 'profile-connection-fallback.has-photo img' in css
assert 'profile-connection-fallback.has-photo .profile-avatar-initials' in css
assert 'profile-post-comment-thread' in css
assert 'profile-post-reaction.is-active' in css
assert 'real-social-avatars-20261018' in page
assert '"photo_url": "/api/public/race-center/profile-photo/" + profile.handle if profile else ""' in accounts
print("Race Center image loading, fallbacks and post actions contract PASS")
