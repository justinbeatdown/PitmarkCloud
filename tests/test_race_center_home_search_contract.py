"""Contract check for Race Center home search layout and functionality."""
import ast
from pathlib import Path
from html.parser import HTMLParser

root=Path(__file__).resolve().parents[1]
page=(root/"api/standings_public.html").read_text(encoding="utf8")
css=(root/"api/race_center_refined.css").read_text(encoding="utf8")
search_js=(root/"api/race_center_consumer.js").read_text(encoding="utf8")
base_css=(root/"api/standings_public.css").read_text(encoding="utf8")
backend=(root/"api/standings_public.py").read_text(encoding="utf8")
ast.parse(backend)
assert page.count('id="raceSearchDock"')==1
assert page.count('id="raceSearchInput"')==1
assert page.count('id="raceSearchResults"')==1
assert 'role="search"' in page
assert 'class="rc-search-heading"' in page
assert 'for="raceSearchInput"' in page
assert 'id="raceSearchHelp"' in page
assert 'aria-describedby="raceSearchHelp"' in page
assert 'class="rc-search-icon"' in page
assert 'class="race-search-box"' in page
assert 'id="raceSearchResults" hidden' in page
assert 'class="rc-search-heading"' in page
assert 'class="race-search-dock" id="raceSearchDock"' in page
assert 'Press / to focus search' in page
assert 'raceSearchInput' in search_js
assert 'raceSearchResults' in search_js
assert '.race-search-dock>label span::after' in base_css  # legacy no longer matches actual markup
assert '#raceSearchDock .rc-search-heading label span::after{content:none!important}' in css
assert '#raceSearchDock .rc-search-heading>span' in css
assert 'row-gap:3px' in css
assert 'overflow:visible' in css
assert 'focus-within' in css
assert '@media(max-width:680px)' in css

class ElementIds(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids={}
    def handle_starttag(self, tag, attrs):
        attr=dict(attrs)
        if "id" in attr:
            assert attr["id"] not in self.ids,attr["id"]
            self.ids[attr["id"]]=(tag,attr)

doc=ElementIds()
doc.feed(page)
assert doc.ids["raceSearchDock"][1]["role"]=="search"
assert doc.ids["raceSearchInput"][0]=="input"
assert doc.ids["raceSearchHelp"][0]=="span"
print("Race Center search UI markup, styling and JS integration PASS")
