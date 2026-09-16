from pathlib import Path

path = Path("api/early_access_admin.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "from services.prt_application_admin import delete_application, set_application_status",
        "from services.prt_application_admin import delete_application, set_application_status, update_application_identity",
    ),
    (
        '''        acceptance_action = ""\n        if raw_status == "accepted":\n            acceptance_action = f"""\n              <form method="post" action="/control/early-access/{application_id}/send-acceptance">\n                <button class="btn accept-mail" type="submit">SEND ACCEPTANCE EMAIL</button>\n              </form>\n            """\n''',
        '''        acceptance_action = ""\n        if raw_status == "accepted":\n            acceptance_action = f"""\n              <form method="post" action="/control/early-access/{application_id}/send-acceptance">\n                <button class="btn accept-mail" type="submit">SEND ACCEPTANCE EMAIL</button>\n              </form>\n            """\n\n        identity_edit_action = ""\n        if raw_status in {"new", "hold"}:\n            identity_edit_action = f"""\n              <details class="delete-menu">\n                <summary>CORRECT NAME / EMAIL</summary>\n                <div class="delete-popover">\n                  <strong>Correct applicant identity</strong>\n                  <p>Available only before acceptance. Duplicate or invalid emails are rejected.</p>\n                  <form method="post" action="/control/early-access/{application_id}/identity">\n                    <label style="display:block;margin:8px 0;color:#98a0a6;font-size:8px;font-weight:900;letter-spacing:.07em">NAME<input style="display:block;width:100%;margin-top:5px;padding:9px;border-radius:7px;border:1px solid rgba(255,255,255,.12);background:#0b0e12;color:#eef0f1" type="text" name="full_name" value="{name}" maxlength="120" required></label>\n                    <label style="display:block;margin:8px 0;color:#98a0a6;font-size:8px;font-weight:900;letter-spacing:.07em">EMAIL<input style="display:block;width:100%;margin-top:5px;padding:9px;border-radius:7px;border:1px solid rgba(255,255,255,.12);background:#0b0e12;color:#eef0f1" type="email" name="email" value="{email}" maxlength="200" required></label>\n                    <button class="action-btn neutral" type="submit">SAVE CORRECTION</button>\n                  </form>\n                </div>\n              </details>\n            """\n''',
    ),
    (
        '''                <div class="footer-tools">\n                  <span>APPLICATION #{application_id}</span>''',
        '''                <div class="footer-tools">\n                  {identity_edit_action}\n                  <span>APPLICATION #{application_id}</span>''',
    ),
    (
        '''    if request.query_params.get("sent") == "1":\n        notice = '<div class="notice good">Acceptance email sent and a fresh PRT Early Access code was issued.</div>'\n    elif request.query_params.get("error") == "invite-exists":''',
        '''    if request.query_params.get("sent") == "1":\n        notice = '<div class="notice good">Acceptance email sent and a fresh PRT Early Access code was issued.</div>'\n    elif request.query_params.get("identity-updated") == "1":\n        notice = '<div class="notice good">Applicant name and email were corrected. Review the updated identity before accepting.</div>'\n    elif request.query_params.get("error") == "identity":\n        notice = '<div class="notice bad">Applicant identity was not changed. Corrections are limited to New / On Hold applications and must use a valid, non-duplicate email.</div>'\n    elif request.query_params.get("error") == "missing":\n        notice = '<div class="notice bad">The requested application could not be found.</div>'\n    elif request.query_params.get("error") == "invite-exists":''',
    ),
    (
        '''@router.post("/control/early-access/{application_id}/send-acceptance", include_in_schema=False)\ndef send_early_access_acceptance(''',
        '''@router.post("/control/early-access/{application_id}/identity", include_in_schema=False)\ndef update_early_access_identity(\n    application_id: int,\n    request: Request,\n    full_name: str = Form(...),\n    email: str = Form(...),\n    x_pitmark_admin_key: str | None = Header(default=None),\n):\n    require_control_user(request, x_pitmark_admin_key)\n    try:\n        update_application_identity(application_id, full_name, email)\n    except LookupError:\n        return RedirectResponse(url="/control/early-access?error=missing", status_code=303)\n    except ValueError:\n        return RedirectResponse(url="/control/early-access?error=identity", status_code=303)\n    return RedirectResponse(url="/control/early-access?identity-updated=1", status_code=303)\n\n\n@router.post("/control/early-access/{application_id}/send-acceptance", include_in_schema=False)\ndef send_early_access_acceptance(''',
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected patch anchor not found:\n{old[:180]}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Applied Applicant Center identity correction UI/route patch")
