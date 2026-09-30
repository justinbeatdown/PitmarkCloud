from pathlib import Path

SOURCE = Path("services/racing_events.py").read_text(encoding="utf-8")

required = [
    "TRUSTED_SOURCE_EVENT_SEEDS",
    "Start2FinishTV",
    "powri-410-outlaw-sprints",
    "Federated Auto Parts Raceway at I-55",
    "def _trusted_source_event_summaries",
    '"source_kind": "trusted_source"',
    "trusted_summaries = _trusted_source_event_summaries()",
]

missing = [item for item in required if item not in SOURCE]
if missing:
    raise SystemExit(f"Race Center trusted-source contract missing: {missing}")

if "start > now + timedelta(days=45)" not in SOURCE:
    raise SystemExit("Trusted-source seeds must remain freshness-bounded")

print("RACE_CENTER_TRUSTED_SOURCE_CONTRACT_OK")
