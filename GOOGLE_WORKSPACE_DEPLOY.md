# Google Workspace deployment

## Required Gmail OAuth scopes

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.send`
- `https://www.googleapis.com/auth/gmail.settings.basic`

## Required Render environment variables

```text
GOOGLE_GMAIL_CLIENT_ID=
GOOGLE_GMAIL_CLIENT_SECRET=
GOOGLE_GMAIL_REFRESH_TOKEN=
GOOGLE_GMAIL_USER=justin@pitmarkracing.com
PITMARK_EMAIL_FROM=Pitmark Racing Co. <justin@pitmarkracing.com>
PITMARK_EMAIL_REPLY_TO=justin@pitmarkracing.com
PITMARK_EMAIL_DOMAIN=pitmarkracing.com
PITMARK_GMAIL_SYNC_SECONDS=60
PITMARK_GMAIL_SYNC_LIMIT=100
PITMARK_GMAIL_BUSINESS_DOMAIN=pitmarkracing.com
PITMARK_GMAIL_BUSINESS_ADDRESSES=
PITMARK_GMAIL_SYNC_QUERY=
```

Create the refresh token from a Google Cloud OAuth Desktop client on a trusted PC:

```powershell
python scripts/google_gmail_oauth_setup.py --client-id "YOUR_CLIENT_ID"
```

The helper asks for the client secret without displaying it, opens the Google consent
screen, captures the one-time localhost callback, and prints the refresh token for
Render. It does not save the client secret or token.

Configure department addresses as Gmail aliases / send-as identities in Google
Workspace. Pitmark Cloud discovers the approved send-as list automatically, so the
composer only exposes identities Gmail knows about.

Leave `PITMARK_GMAIL_SYNC_QUERY` blank unless a custom Gmail search is required.
Pitmark Cloud then builds a business-only inbox query from approved
`@pitmarkracing.com` send-as identities. Mail delivered only to a personal Gmail
address is intentionally excluded from Pitmark Mail and Shield.

After Render deploys, open Control Center > Email. The status must read `GMAIL
CONNECTED`. Send a test message from Gmail to the Pitmark Workspace address, refresh
Pitmark Mail, open the thread, mark it as spam, and delete a disposable test thread
to verify the two-way Gmail actions and Shield classification.

The old `RESEND_API_KEY`, `RESEND_INBOUND_API_KEY`, `RESEND_WEBHOOK_SECRET` and
`mail.pitmarkracing.com` records are no longer read by Pitmark Cloud v0.20.0. Remove
them only after the Gmail connection test passes.
