from urllib.parse import urlencode, quote

from api import early_access_admin as early_access_admin
from api import founders_race as founders_race
from api import prt_ui as prt_ui
from services import founders_race_activation as founders_race_activation  # noqa: F401

# Keep Founder's Race inside the existing PRT surface without creating a
# separate application or deployment. main.py already mounts prt_ui.router.
prt_ui.router.include_router(founders_race.router)


def _gmail_compose_direct(email: str, name: str) -> str:
    """Open a compose draft without depending on Gmail web-account redirects.

    Google Workspace/multi-account browser sessions can redirect mail.google.com
    through accounts.google.com and hit ERR_TOO_MANY_REDIRECTS. A mailto link hands
    the compose request to the user's configured mail handler instead and keeps the
    applicant address, subject, and greeting prefilled.
    """
    query = urlencode(
        {
            "subject": "Pitmark Racing Tools Early Access",
            "body": f"Hi {name},\n\n",
        },
        quote_via=quote,
    )
    return f"mailto:{quote(email)}?{query}"


# Early Access applicant cards call this module-level helper when rendering.
# Override it here so both the contact button and applicant email link avoid
# Google's account-chooser redirect loop entirely.
early_access_admin._gmail_compose = _gmail_compose_direct
