from __future__ import annotations

from urllib.parse import urlencode

import api.early_access_admin as early_access_admin


def _gmail_compose(email: str, name: str) -> str:
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
    # Pin the compose route to Gmail account slot 0. The generic /mail/? route
    # can bounce multi-account/Workspace sessions through accounts.google.com
    # and trigger ERR_TOO_MANY_REDIRECTS in Chrome.
    return f"https://mail.google.com/mail/u/0/?{query}"


early_access_admin._gmail_compose = _gmail_compose
