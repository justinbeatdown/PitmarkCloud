from pathlib import Path
import re

repo = Path(__file__).resolve().parent
research = repo / "services" / "research_agent.py"
config = repo / "utils" / "config.py"

if not research.exists() or not config.exists():
    raise SystemExit("Run this from the PitmarkCloud repository root.")

text = research.read_text(encoding="utf-8")

# Import the verification/page-reading layer.
needle = "from services.racing_community import CommunityEntity, ResearchJob, CampaignParticipant, ResearchEvidence\n"
replacement = needle + "from services.research_page_reader import enrich_ranked_sources\n"
if "from services.research_page_reader import enrich_ranked_sources" not in text:
    if needle not in text:
        raise SystemExit("research_agent.py import anchor not found")
    text = text.replace(needle, replacement, 1)

# Wikipedia is a useful secondary profile source. Official racing sources still rank higher.
old = "official = ('nascar.com','imsa.com','indycar.com','worldofoutlaws.com','dirtcar.com','myracepass.com','racemonitor.com')"
new = "official = ('nascar.com','imsa.com','indycar.com','worldofoutlaws.com','dirtcar.com','myracepass.com','racemonitor.com')\n    reference = ('wikipedia.org',)"
if old in text and "reference = ('wikipedia.org',)" not in text:
    text = text.replace(old, new, 1)

old2 = "if any(domain == d or domain.endswith('.'+d) or d in source for d in official):\n        return 3\n"
new2 = old2 + "    if any(domain == d or domain.endswith('.'+d) for d in reference):\n        return 2\n"
if old2 in text and "for d in reference" not in text:
    text = text.replace(old2, new2, 1)

# Explicit profile/reference discovery.
q_anchor = "f'{n} official driver stats', f'{n} official driver profile'"
if q_anchor in text and "site:wikipedia.org" not in text:
    text = text.replace(
        q_anchor,
        q_anchor + ",\n            f'site:wikipedia.org {n} racing driver', f'{n} biography racing driver'",
        1,
    )

# Feed full-page excerpts to the AI evidence packet.
packet_anchor = "'identity_score': item.get('identity_score',0),"
if packet_anchor not in text:
    raise SystemExit("AI packet anchor not found")
if "'page_excerpt': item.get('page_excerpt','')" not in text:
    text = text.replace(
        packet_anchor,
        packet_anchor + "\n            'page_excerpt': item.get('page_excerpt',''),",
        1,
    )

# Strengthen synthesis instructions so page content is the verification layer.
inst_anchor = "Use ONLY the supplied public-search evidence. Never guess."
if inst_anchor in text and "page excerpts" not in text[text.find(inst_anchor):text.find(inst_anchor)+600].lower():
    text = text.replace(
        inst_anchor,
        "Use ONLY the supplied evidence, including fetched page excerpts. Never guess. "
        "Prefer facts stated directly in page excerpts from official racing sources; "
        "use Wikipedia or reputable racing coverage as secondary corroboration.",
        1,
    )

# Read top-ranked pages after scoring and before AI synthesis.
score_anchor = "scored.sort(key=lambda x: x['identity_score'], reverse=True)\n"
if score_anchor not in text:
    raise SystemExit("scored.sort anchor not found")
enrich_block = """scored.sort(key=lambda x: (_source_authority(x), x['identity_score']), reverse=True)

    # v0.15.8 verification layer: discovery finds candidates; this step actually
    # reads the best safe pages so profile extraction is not limited to snippets.
    if job.research_type == 'rookie_deep_dive' and scored:
        scored = enrich_ranked_sources(scored, limit=8)
"""
text = text.replace(score_anchor, enrich_block, 1)

# Deterministic fallback should also see page excerpts.
old_text_join = "text = _clean(' '.join([item.get('title',''), item.get('snippet','')]))"
new_text_join = "text = _clean(' '.join([item.get('title',''), item.get('snippet',''), item.get('page_excerpt','')]))"
text = text.replace(old_text_join, new_text_join)

# Don't persist giant excerpts into source ledgers / API brief payloads.
sources_anchor = "'sources': scored[:12],"
if sources_anchor in text:
    text = text.replace(
        sources_anchor,
        "'sources': [{k:v for k,v in x.items() if k != 'page_excerpt'} for x in scored[:12]],",
        1,
    )

# Source URLs remain compact too; no change needed there.
research.write_text(text, encoding="utf-8")

cfg = config.read_text(encoding="utf-8")
cfg2, n = re.subn(r'PITMARK_RELEASE_VERSION\s*=\s*"0\.15\.7"', 'PITMARK_RELEASE_VERSION = "0.15.8"', cfg, count=1)
if n == 0:
    cfg2, n = re.subn(r'PITMARK_RELEASE_VERSION\s*=\s*"0\.15\.6"', 'PITMARK_RELEASE_VERSION = "0.15.8"', cfg, count=1)
if n == 0 and 'PITMARK_RELEASE_VERSION = "0.15.8"' not in cfg:
    raise SystemExit("config.py version anchor not found")
config.write_text(cfg2, encoding="utf-8")

print("v0.15.8 applied: research_agent.py + config.py + research_page_reader.py")
