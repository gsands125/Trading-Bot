from __future__ import annotations
from dataclasses import dataclass
import os


def _as_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1","true","yes","on"}


@dataclass(frozen=True)
class RouterConfig:
    webhook_secret: str
    state_path: str
    lifecycle_state_path: str
    audit_path: str
    reconciliation_path: str
    event_journal_path: str
    alert_path: str
    accounts_config_path: str
    allowed_strategies: set[str]
    paper_mode: bool
    status_secret: str | None
    port: int

    @classmethod
    def from_env(cls):
        secret = os.environ.get("WEBHOOK_SECRET", "").strip()
        if not secret:
            raise RuntimeError("WEBHOOK_SECRET environment variable is required")

        allowed_raw = os.environ.get("ALLOWED_STRATEGIES", "S3")
        allowed = {
            x.strip().upper()
            for x in allowed_raw.split(",")
            if x.strip()
        }

        status_secret = os.environ.get("STATUS_SECRET", "").strip() or None

        return cls(
            webhook_secret=secret,
            state_path=os.environ.get(
                "ROUTER_STATE_PATH", "/data/master_router_state.json"
            ),
            lifecycle_state_path=os.environ.get(
                "ROUTER_LIFECYCLE_STATE_PATH",
                "/data/master_router_lifecycle.json"
            ),
            audit_path=os.environ.get(
                "ROUTER_AUDIT_PATH", "/data/master_router_audit.jsonl"
            ),
            reconciliation_path=os.environ.get(
                "ROUTER_RECON_PATH", "/data/master_router_reconciliation.jsonl"
            ),
            event_journal_path=os.environ.get(
                "ROUTER_EVENT_JOURNAL_PATH", "/data/master_router_events.jsonl"
            ),
            alert_path=os.environ.get(
                "ROUTER_ALERT_PATH", "/data/master_router_alerts.jsonl"
            ),
            accounts_config_path=os.environ.get(
                "ROUTER_ACCOUNTS_CONFIG", "accounts.example.json"
            ),
            allowed_strategies=allowed,
            paper_mode=_as_bool("PAPER_MODE", True),
            status_secret=status_secret,
            port=int(os.environ.get("PORT", "8080")),
        )
