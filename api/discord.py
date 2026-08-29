from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from services import device_auth_service, discord_service
from utils.security import enforce_rate_limit, safe_html, validate_device_id

router = APIRouter()


@router.get("/status")
async def status() -> dict:
    return discord_service.status()


@router.get("/install")
async def install() -> dict:
    url = discord_service.install_url()
    if not url:
        raise HTTPException(status_code=503, detail="DISCORD_CLIENT_ID is not configured.")
    return {"install_url": url, "scope": ["bot", "applications.commands"], "permissions": "View Channels, Send Messages, Embed Links, Attach Files, Read Message History"}


@router.post("/link/start")
async def link_start(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-start", 20)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    try:
        return discord_service.create_link(device_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/link/status")
async def link_status(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-status", 120)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    return discord_service.link_status(device_id)


@router.post("/link/disconnect")
async def link_disconnect(request: Request, device_id: str = Query(..., min_length=16, max_length=64), x_pitmark_device_token: str | None = Header(default=None)) -> dict:
    enforce_rate_limit(request, "discord-link-disconnect", 30)
    device_id = validate_device_id(device_id)
    if not device_auth_service.authenticate(device_id, x_pitmark_device_token):
        raise HTTPException(status_code=401, detail="Invalid device credential.")
    return discord_service.disconnect(device_id)


@router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(request: Request, code: str = Query(..., min_length=1, max_length=4096), state: str = Query(..., min_length=10, max_length=4096)) -> HTMLResponse:
    enforce_rate_limit(request, "discord-oauth-callback", 60)
    try:
        result = await discord_service.complete_link(code, state)
    except ValueError as exc:
        return HTMLResponse(_oauth_page(
            title="Connection failed",
            headline="DISCORD CONNECTION FAILED",
            message=safe_html(str(exc)),
            success=False,
        ), status_code=400)

    if result.status != "connected":
        return HTMLResponse(_oauth_page(
            title="Connection failed",
            headline="DISCORD CONNECTION FAILED",
            message=safe_html(result.error or "Discord could not be connected."),
            success=False,
        ), status_code=400)

    display = safe_html(result.global_name or result.username or "your Discord account")
    return HTMLResponse(_oauth_page(
        title="Discord connected",
        headline="DISCORD CONNECTED",
        message=f"Pitmark Racing Tools is connected to <strong>{display}</strong>.",
        success=True,
    ))


def _oauth_page(*, title: str, headline: str, message: str, success: bool) -> str:
    state_label = "CONNECTED" if success else "TRY AGAIN"
    state_class = "ok" if success else "error"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Pitmark Racing Tools - {safe_html(title)}</title>
  <style>
    :root {{ color-scheme: dark; --orange:#ff5500; --bg:#08090a; --panel:#111315; --line:#292d31; --text:#f4f1eb; --muted:#8f959c; --green:#36d36b; --red:#ff5f56; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:28px; background:radial-gradient(circle at 50% 0%,#1a1c1f 0,#0b0c0d 42%,var(--bg) 75%); color:var(--text); font-family:Segoe UI,Arial,sans-serif; }}
    .card {{ width:min(560px,100%); background:rgba(17,19,21,.96); border:1px solid var(--line); border-radius:14px; box-shadow:0 24px 80px rgba(0,0,0,.48); overflow:hidden; }}
    .stripe {{ height:5px; background:var(--orange); }}
    .content {{ padding:34px; }}
    .brand {{ color:var(--orange); font-size:12px; font-weight:900; letter-spacing:1.6px; text-transform:uppercase; margin-bottom:26px; }}
    .status {{ display:inline-flex; align-items:center; gap:8px; color:var(--muted); font-size:11px; font-weight:800; letter-spacing:1px; margin-bottom:10px; }}
    .dot {{ width:9px; height:9px; border-radius:50%; background:var(--green); box-shadow:0 0 15px rgba(54,211,107,.45); }}
    .error .dot {{ background:var(--red); box-shadow:0 0 15px rgba(255,95,86,.4); }}
    h1 {{ margin:0; font-size:30px; line-height:1.05; letter-spacing:.4px; }}
    p {{ color:var(--muted); line-height:1.65; margin:18px 0 0; }}
    strong {{ color:var(--text); }}
    .return {{ margin-top:28px; padding-top:20px; border-top:1px solid var(--line); font-size:13px; color:#b6bbc0; }}
    .mark {{ margin-top:24px; color:var(--orange); font-size:11px; font-weight:900; letter-spacing:.8px; }}
  </style>
</head>
<body>
  <main class="card {state_class}">
    <div class="stripe"></div>
    <div class="content">
      <div class="brand">PITMARK RACING TOOLS</div>
      <div class="status"><span class="dot"></span>{state_label}</div>
      <h1>{safe_html(headline)}</h1>
      <p>{message}</p>
      <div class="return">You can close this window and return to Pitmark Racing Tools.</div>
      <div class="mark">LEAVE YOUR MARK.</div>
    </div>
  </main>
</body>
</html>"""
