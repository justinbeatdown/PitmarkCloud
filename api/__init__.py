from urllib.parse import urlencode

from api import early_access_admin as early_access_admin
from api import founders_race as founders_race
from api import prt_ui as prt_ui
from services import founders_race_activation as founders_race_activation  # noqa: F401

# Keep Founder's Race inside the existing PRT surface without creating a
# separate application or deployment. main.py already mounts prt_ui.router.
prt_ui.router.include_router(founders_race.router)


def _gmail_compose_direct(email: str, name: str) -> str:
    """Open Gmail compose directly instead of bouncing through Google AccountChooser.

    The generic /mail/? compose URL can send Workspace/multi-account sessions through
    accounts.google.com and, in some browsers, end up in an ERR_TOO_MANY_REDIRECTS loop.
    Pinning the compose route to the active Gmail slot avoids that account chooser hop.
    """
    query = urlencode(
        {
            "view": "cm",
            "fs": "1",
            "tf": "1",
            "to": email,
            "su": "Pitmark Racing Tools Early Access",
            "body": f"Hi {name},\n\n",
        }
    )
    return f"https://mail.google.com/mail/u/0/?{query}"


# Early Access applicant cards call this module-level helper when rendering.
# Override it here so both the EMAIL IN GMAIL button and applicant email link
# use the direct Gmail compose route without changing the rest of the admin UI.
early_access_admin._gmail_compose = _gmail_compose_direct
