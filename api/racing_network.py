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
  <div class="top"><div class="brand"><span class="brand-mark">P</span><span>PITMARK <b>RACING DESK</b></span></div><nav class="nav"><a href="/race-center">Race Center</a><a href="https://pitmarkracing.com">PitmarkRacing.com</a></nav></div>
  <section class="hero"><div class="eyebrow">TRACKS · TEAMS · DRIVERS · SERIES · PROMOTERS</div><h1>Send us<br>the story.</h1><p>Pitmark wants real racing information straight from the people living it. Send schedules, results, press releases, corrections, story leads, photos or video links. This is a coverage lane—not a paid-placement form.</p></section>
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
