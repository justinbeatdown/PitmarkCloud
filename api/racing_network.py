from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse

from services.pitmark_mail_identities import send_message as send_mail
from utils.security import enforce_rate_limit

router = APIRouter()
_HERE = Path(__file__).resolve().parent

_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#090b0e">
  <title>Pitmark Racing Desk | Send Racing News</title>
  <link rel="stylesheet" href="/racing-network.css?v=20260920b">
</head>
<body><main class="wrap">
  <div class="top"><a class="brand" href="https://pitmarkracing.com" aria-label="Pitmark Racing Co. home"><img class="brand-logo" src="/prt-logo.png" alt="Pitmark Racing Co."><span class="desk-label">RACING DESK</span></a><nav class="nav"><a href="/race-center">Race Center</a><a href="https://pitmarkracing.com">PitmarkRacing.com</a></nav></div>
  <section class="hero"><div class="eyebrow">TRACKS · TEAMS · DRIVERS · SERIES · PROMOTERS</div><h1>Send us<br>the story.</h1><p>Pitmark wants real racing information straight from the people living it. Send schedules, results, press releases, corrections, story leads, photos or video links. This is a coverage lane—not a paid-placement form.</p></section>
  <section class="network-ways" aria-label="Ways to connect with Pitmark">
    <a class="network-card primary" href="#racing-desk-form"><span class="network-icon">▤</span><div><small>RACING NEWS</small><strong>Send the Racing Desk a lead</strong><p>Results, schedules, press releases, corrections, photos, video, or something Pitmark should cover.</p></div><b>Use Racing Desk →</b></a>
    <a class="network-card" href="https://docs.google.com/forms/d/e/1FAIpQLScWmRdjn3BcFLY1vhpPpW0n0h2biXgM6WMwKe0zICrf-AsKLA/viewform" target="_blank" rel="noopener"><span class="network-icon">✦</span><div><small>DRIVERS + TEAMS</small><strong>Tell Pitmark your story</strong><p>Rookie year, new class, family team, comeback, race updates, Q&A interest, or a program we should follow.</p></div><b>Submit your story ↗</b></a>
    <a class="network-card" href="https://docs.google.com/forms/d/e/1FAIpQLSfJEJAAhYdfPfqD5qGSktbFmK8acwytd_Clx2tMDNMcDrVkhg/viewform" target="_blank" rel="noopener"><span class="network-icon">◎</span><div><small>COMMUNITY RADAR</small><strong>Nominate a grassroots racer</strong><p>Know a rookie, small team, family-built program, comeback story, or racer people should be watching? Put them on our radar.</p></div><b>Nominate someone ↗</b></a>
    <a class="network-card" href="https://docs.google.com/forms/d/e/1FAIpQLSdblkMOvPFtz0y2_3WK9X2C3330zXqzqTaqFC5cHx81e1E0MA/viewform" target="_blank" rel="noopener"><span class="network-icon">↔</span><div><small>WORK WITH PITMARK</small><strong>Start the right conversation</strong><p>Tracks, series, leagues, broadcasters, creators, teams and brands can route partnership, PRT, merch, media, or 2027 ideas here.</p></div><b>Work with Pitmark ↗</b></a>
  </section>
  <div id="racing-desk-form" class="anchor-target" aria-hidden="true"></div>
  <section class="panel">
    <div class="panel-head"><div><div class="eyebrow">SUBMIT TO PITMARK</div><h2>Racing Desk Intake</h2></div><p>Give us the facts and the best official source you have. We would rather leave something blank than invent it.</p></div>
    <form method="post" action="/submit-racing-news">
      <label>Your role<select name="submitter_role" required><option value="">Choose one</option><option>Track / Speedway</option><option>Driver / Team</option><option>Racing Series</option><option>Promoter / Organizer</option><option>Media / Photographer</option><option>Fan / Community</option><option>Other</option></select></label>
      <label>Submission type<select name="submission_type" required><option value="">Choose one</option><option>Schedule / Event</option><option>Race Result</option><option>Press Release / News</option><option>Story Lead</option><option>Correction / Update</option><option>Photo / Video</option><option>Other</option></select></label>
      <label>Track / team / driver / series<input name="organization" maxlength="180" required></label>
      <label>Contact name<input name="contact_name" maxlength="140" required></label>
      <label>Email<input name="email" type="email" maxlength="254" required></label>
      <label>Event date <span class="fine">(optional)</span><input name="event_date" maxlength="80" placeholder="Example: Sept. 26, 2026"></label>
      <label class="full">Headline / what happened<input name="title" maxlength="240" required></label>
      <label class="full">Official/source URL <span class="fine">(strongly preferred)</span><input name="official_url" type="url" maxlength="700" placeholder="https://..."></label>
      <label class="full">Photo/video/media URL <span class="fine">(optional)</span><input name="media_url" type="url" maxlength="700" placeholder="Drive, Dropbox, official media page, etc."></label>
      <label class="full">Details<textarea name="details" maxlength="6000" required placeholder="Give us the useful facts: series/class, location, winner/result, schedule details, quotes, context, corrections, or what makes the story matter."></textarea></label>
      <label class="full check"><input type="checkbox" name="rights_confirmed" value="yes" required><span>I have permission to send any media or material linked here for Pitmark to review and potentially use in coverage, or I am only linking to publicly available official material.</span></label>
      <input class="honeypot" name="company_website" tabindex="-1" autocomplete="off" aria-hidden="true">
      <div class="full actions"><button class="btn" type="submit">Send to Pitmark Racing Desk</button><span class="fine">No paid placement. No guarantee of coverage. <strong>Useful, verifiable racing information wins.</strong></span></div>
    </form>
    <p class="fine">Pitmark verifies factual claims before publication when practical. Submitting something does not guarantee coverage, and missing information may be left out rather than guessed.</p>
  </section>
</main></body></html>"""


_MEDIA_KIT_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#090b0e">
  <title>Pitmark Racing Co. | Media & Partner Kit</title>
  <link rel="stylesheet" href="/racing-network.css?v=20260921mediakit1">
</head>
<body><main class="wrap">
  <div class="top"><a class="brand" href="https://pitmarkracing.com" aria-label="Pitmark Racing Co. home"><img class="brand-logo" src="/prt-logo.png" alt="Pitmark Racing Co."><span class="desk-label">MEDIA + PARTNER KIT</span></a><nav class="nav"><a href="/racing-desk">Racing Desk</a><a href="/race-center">Race Center</a><a href="https://pitmarkracing.com">Store</a></nav></div>

  <section class="hero media-hero">
    <div class="eyebrow">GRASSROOTS RACING · MEDIA · TECHNOLOGY · COMMUNITY</div>
    <h1>Built around<br>the people racing.</h1>
    <p>Pitmark Racing Co. is an independent motorsports brand rooted in western Pennsylvania. We build racing media, community relationships, apparel, and Pitmark Racing Tools (PRT) around a simple idea: the people, teams, tracks and communities doing the work deserve useful coverage and useful tools.</p>
    <div class="media-actions"><a class="btn" href="https://docs.google.com/forms/d/e/1FAIpQLSdblkMOvPFtz0y2_3WK9X2C3330zXqzqTaqFC5cHx81e1E0MA/viewform" target="_blank" rel="noopener">Work With Pitmark</a><a class="btn secondary" href="/racing-desk">Send Racing News</a></div>
  </section>

  <section class="media-grid">
    <article class="media-card"><div class="eyebrow">RACING MEDIA</div><h2>Racing Desk</h2><p>Race results, schedules, track news, driver and team stories, corrections, interviews and racing-culture coverage. Pitmark prefers direct, verifiable information from the people actually involved.</p></article>
    <article class="media-card"><div class="eyebrow">RACING TECHNOLOGY</div><h2>PRT</h2><p>Pitmark Racing Tools is our independent iRacing companion platform. Early Access development spans race-night overlays, telemetry, driver analysis, league tools and broadcast workflows.</p></article>
    <article class="media-card"><div class="eyebrow">GRASSROOTS RELATIONSHIPS</div><h2>Drivers + Teams</h2><p>We actively look for rookie seasons, new-class moves, family teams, comeback stories and smaller programs worth following before everybody already knows their name.</p></article>
    <article class="media-card"><div class="eyebrow">RACING CULTURE</div><h2>Brand + Store</h2><p>Pitmark apparel and products are built around racing identity, local-track culture and the people who keep showing up. “Leave your mark.” is the core idea behind the brand.</p></article>
  </section>

  <section class="panel media-panel">
    <div class="panel-head"><div><div class="eyebrow">WHAT PITMARK COVERS</div><h2>From local pits to sim grids.</h2></div><p>Pitmark starts with grassroots racing, but the audience is not boxed into one class or one discipline.</p></div>
    <div class="media-pill-grid"><span>Dirt Late Models</span><span>Sprint Cars</span><span>Modifieds</span><span>Stock Cars</span><span>Short Track</span><span>Sports Cars</span><span>iRacing</span><span>Leagues</span><span>Broadcasting</span><span>Tracks + Series</span></div>
  </section>

  <section class="panel media-panel">
    <div class="panel-head"><div><div class="eyebrow">HOW WE WORK</div><h2>Useful beats flashy.</h2></div></div>
    <div class="media-principles">
      <div><strong>People first.</strong><p>We care about the story behind the car, team, track or project — not just the logo sheet.</p></div>
      <div><strong>Real information.</strong><p>We verify facts when practical and would rather leave something out than invent a detail.</p></div>
      <div><strong>Real media.</strong><p>For race coverage, verified real photos and official assets come first. We do not fabricate fake driver or race-action imagery.</p></div>
      <div><strong>No forced partnership.</strong><p>Most relationships begin with conversation, coverage, feedback or simply staying connected.</p></div>
    </div>
  </section>

  <section class="panel media-panel">
    <div class="panel-head"><div><div class="eyebrow">FASTEST PATH</div><h2>Tell us what lane you’re in.</h2></div><p>Structured intake means less back-and-forth and gets the right opportunity into Pitmark’s pipeline quickly.</p></div>
    <div class="media-links">
      <a href="https://docs.google.com/forms/d/e/1FAIpQLScWmRdjn3BcFLY1vhpPpW0n0h2biXgM6WMwKe0zICrf-AsKLA/viewform" target="_blank" rel="noopener"><strong>Driver / Team Story</strong><span>Introduce your program or season story ↗</span></a>
      <a href="https://docs.google.com/forms/d/e/1FAIpQLSfJEJAAhYdfPfqD5qGSktbFmK8acwytd_Clx2tMDNMcDrVkhg/viewform" target="_blank" rel="noopener"><strong>Nominate a Racer</strong><span>Put somebody on Pitmark’s radar ↗</span></a>
      <a href="https://docs.google.com/forms/d/e/1FAIpQLSdblkMOvPFtz0y2_3WK9X2C3330zXqzqTaqFC5cHx81e1E0MA/viewform" target="_blank" rel="noopener"><strong>Partnership / Collaboration</strong><span>Tracks, series, leagues, broadcasters, creators and brands ↗</span></a>
      <a href="/racing-desk"><strong>Racing Desk</strong><span>Send results, news, schedules, media or corrections →</span></a>
    </div>
  </section>

  <section class="panel media-panel media-contact">
    <div><div class="eyebrow">CONTACT</div><h2>Justin Olson · Pitmark Racing Co.</h2><p>Western Pennsylvania · <a href="mailto:justin@pitmarkracing.com">justin@pitmarkracing.com</a> · <a href="https://pitmarkracing.com">pitmarkracing.com</a></p></div>
    <div class="media-tagline">LEAVE YOUR MARK.</div>
  </section>
</main></body></html>"""


@router.get("/media-kit", response_class=HTMLResponse, include_in_schema=False)
@router.get("/press", response_class=HTMLResponse, include_in_schema=False)
def media_kit():
    return HTMLResponse(_MEDIA_KIT_PAGE, headers={"Cache-Control": "no-store"})


def _success() -> HTMLResponse:
    return HTMLResponse(
        _PAGE.replace(
            '<section class="panel">',
            '<section class="panel success"><div class="eyebrow">SUBMISSION RECEIVED</div><h2>Received. 🏁</h2><p>Your submission is in the Pitmark Racing Desk inbox. If we need more detail, we can reply directly to the email you provided.</p></section><section class="panel hidden-panel">',
            1,
        ),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/racing-network.css", include_in_schema=False)
def racing_network_css():
    return FileResponse(_HERE / "racing_network.css", media_type="text/css", headers={"Cache-Control": "public, max-age=300"})


@router.get("/submit-racing-news", response_class=HTMLResponse, include_in_schema=False)
@router.get("/racing-desk", response_class=HTMLResponse, include_in_schema=False)
def racing_desk():
    return HTMLResponse(_PAGE, headers={"Cache-Control": "no-store"})


@router.post("/submit-racing-news", response_class=HTMLResponse, include_in_schema=False)
def submit_racing_news(
    request: Request,
    submitter_role: str = Form(...),
    submission_type: str = Form(...),
    organization: str = Form(...),
    contact_name: str = Form(...),
    email: str = Form(...),
    event_date: str = Form(default=""),
    title: str = Form(...),
    official_url: str = Form(default=""),
    media_url: str = Form(default=""),
    details: str = Form(...),
    rights_confirmed: str = Form(default=""),
    company_website: str = Form(default=""),
):
    enforce_rate_limit(request, "racing-desk-submit", 12, 300)
    if company_website.strip():
        return _success()

    email = email.strip()[:254]
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return HTMLResponse("A valid contact email is required.", status_code=400)
    if rights_confirmed != "yes":
        return HTMLResponse("Permission confirmation is required.", status_code=400)

    role = submitter_role.strip()[:100]
    kind = submission_type.strip()[:100]
    org = organization.strip()[:180]
    contact = contact_name.strip()[:140]
    headline = title.strip()[:240]
    detail = details.strip()[:6000]
    if not all((role, kind, org, contact, headline, detail)):
        return HTMLResponse("Please complete the required fields.", status_code=400)

    text = (
        "PITMARK RACING DESK SUBMISSION\n\n"
        f"Role: {role}\n"
        f"Type: {kind}\n"
        f"Organization / identity: {org}\n"
        f"Contact: {contact} <{email}>\n"
        f"Event date: {(event_date or '').strip()[:80] or '—'}\n"
        f"Headline: {headline}\n"
        f"Official/source URL: {(official_url or '').strip()[:700] or '—'}\n"
        f"Media URL: {(media_url or '').strip()[:700] or '—'}\n\n"
        f"DETAILS\n{detail}\n\n"
        "Rights confirmation: YES\n"
        "Submitted through links.pitmarkracing.com / Pitmark Race Center."
    )
    subject = f"[Racing Desk] {kind}: {org} — {headline}"[:500]
    try:
        send_mail(
            to=["justin@pitmarkracing.com"],
            from_identity="outreach",
            reply_to=[email],
            subject=subject,
            text=text,
            message_headers={"X-Pitmark-Purpose": "racing-desk-submission"},
        )
    except ValueError:
        send_mail(
            to=["justin@pitmarkracing.com"],
            reply_to=[email],
            subject=subject,
            text=text,
            message_headers={"X-Pitmark-Purpose": "racing-desk-submission"},
        )
    except RuntimeError:
        return HTMLResponse(
            "Pitmark Racing Desk could not accept the submission right now. Please email outreach@pitmarkracing.com.",
            status_code=503,
        )
    return _success()
