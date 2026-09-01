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
PITMARK_GMAIL_BUSINESS_ADDRESSES=justin@pitmarkracing.com,sales@pitmarkracing.com,support@pitmarkracing.com,partnerships@pitmarkracing.com,prt@pitmarkracing.com,marketing@pitmarkracing.com,outreach@pitmarkracing.com,orders@pitmarkracing.com,hello@pitmarkracing.com
PITMARK_GMAIL_SYNC_QUERY=
```

Keep `DATABASE_URL` pointed at the existing Render PostgreSQL database. The
automatic-response dedupe log is stored there so a restart or redeploy cannot send
a second acknowledgment for the same conversation.

Create the refresh token from a Google Cloud OAuth Desktop client on a trusted PC:

```powershell
python scripts/google_gmail_oauth_setup.py --client-id "YOUR_CLIENT_ID"
```

The helper asks for the client secret without displaying it, opens the Google consent
screen, captures the one-time localhost callback, and prints the refresh token for
Render. It does not save the client secret or token.

The Workspace user must have these aliases before deployment: `sales`, `support`,
`partnerships`, `prt`, `marketing`, `outreach`, `orders`, and `hello` at
`pitmarkracing.com`. Pitmark Cloud discovers the approved Gmail send-as list
automatically, so the composer only exposes identities Gmail knows about.

Leave `PITMARK_GMAIL_SYNC_QUERY` blank unless a custom Gmail search is required.
Pitmark Cloud then builds a business-only mailbox query from the explicit address
list and approved `@pitmarkracing.com` send-as identities. The query includes Gmail
Spam for Shield auditing, while excluding sent mail, drafts, trash, and messages
delivered only to a personal Gmail address.

## One-time Google Cloud / Render connection

1. In Google Cloud, enable the Gmail API for the Pitmark project.
2. In Google Auth Platform, use an Internal consent audience for the Workspace
   organization.
3. Create an OAuth client with application type **Desktop app**.
4. Run the helper above on the trusted PC, sign in as
   `justin@pitmarkracing.com`, and approve the three Gmail scopes.
5. Copy the client ID, client secret, and printed refresh token into the matching
   Render environment variables. Never commit any of the three values.
6. Add the remaining non-secret variables exactly as shown above and redeploy.

## First-run Control Center setup

1. Open **Control Center > Mail > Auto Replies**.
2. Select **Provision Gmail Labels & Filters**. The operation is idempotent and
   creates eight `Pitmark/<Department>` routing labels, four `Pitmark/Shield ...`
   verdict labels, and eight `deliveredto:` routing filters.
3. Review the eight acknowledgment templates and disable or edit any department
   before live testing.
4. Select **Run Safe Reply Check** after sending a fresh test message from an
   external address to one alias.

Automatic acknowledgments run 24/7, at most once per department/conversation. They
are sent only after Shield classifies the message as Legit or Unverified. Review,
Spam, bulk/list mail, automated senders, no-reply addresses, and Pitmark's own domain
are blocked from automatic response. First deployment does not reply to older inbox
history; only messages arriving after the settings initialize are eligible.

After Render deploys, open Control Center > Mail. The status must read `GMAIL
CONNECTED`, and the setup panel must report labels and filters ready. Send a test
message from an external mailbox to `sales@pitmarkracing.com`, verify the Sales and
Shield labels in Gmail, confirm exactly one acknowledgment arrives, then open the
thread in Control Center. Mark a second disposable message as spam and delete a test
thread to verify two-way Gmail actions and Shield classification.

The old `RESEND_API_KEY`, `RESEND_INBOUND_API_KEY`, `RESEND_WEBHOOK_SECRET` and
`mail.pitmarkracing.com` records are no longer read by Pitmark Cloud. Remove
them only after the Gmail connection test passes.
