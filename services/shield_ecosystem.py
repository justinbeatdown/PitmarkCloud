from __future__ import annotations

import ipaddress
from urllib.parse import urlparse
from sqlalchemy import select

from services.database import SessionLocal
from services.control_center import SecurityAuditEvent, utcnow

ALLOWED_SCHEMES = {'http', 'https'}
BLOCKED_HOSTS = {'localhost', '0.0.0.0', '127.0.0.1', '::1'}


def inspect_external_url(url: str) -> dict:
    """Shield gate for URLs discovered by ecosystem automation.

    Blocks non-web schemes, credentials-in-URL and local/private network targets.
    This is deliberately conservative because Research Agent consumes public URLs.
    """
    try:
        parsed = urlparse((url or '').strip())
        host = (parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return {'safe': False, 'reason': 'non-web URL scheme'}
        if not host:
            return {'safe': False, 'reason': 'missing hostname'}
        if parsed.username or parsed.password:
            return {'safe': False, 'reason': 'embedded URL credentials'}
        if host in BLOCKED_HOSTS or host.endswith('.local'):
            return {'safe': False, 'reason': 'local network target'}
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return {'safe': False, 'reason': 'private/reserved network target'}
        except ValueError:
            pass
        return {'safe': True, 'reason': 'public web target', 'domain': host.removeprefix('www.')}
    except Exception:
        return {'safe': False, 'reason': 'malformed URL'}


def audit_blocked_research_source(url: str, reason: str, job_id: int | None = None) -> None:
    detail = f'Research source blocked by Shield: {reason}. Job #{job_id or "unknown"}. URL={url[:500]}'
    with SessionLocal() as db:
        # Avoid flooding the audit table with the same blocked URL.
        existing = db.scalar(select(SecurityAuditEvent).where(SecurityAuditEvent.event_type == 'research_source_blocked', SecurityAuditEvent.detail == detail))
        if existing:
            return
        db.add(SecurityAuditEvent(event_type='research_source_blocked', severity='warning', actor='autopilot_research', source='shield', detail=detail, created_at=utcnow()))
        db.commit()
