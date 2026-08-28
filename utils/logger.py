import logging
import re

_SECRET_RE = re.compile(
    r"(?i)((?:authorization|token|secret|password|admin[_-]?key|client[_-]?secret)\s*[=:]\s*)([^\s,;]+)"
)
_QUERY_RE = re.compile(r"(?i)([?&](?:code|state|device_secret|access_token|refresh_token)=)[^&\s]+")


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            message = _SECRET_RE.sub(r"\1[REDACTED]", message)
            message = _QUERY_RE.sub(r"\1[REDACTED]", message)
            record.msg = message[:12000]
            record.args = ()
        except Exception:
            pass
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(_RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
