from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from .models import Decision, Signal, AccountState


class JsonlAuditLedger:
    """Append-only deterministic TAKE/SKIP audit log."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, signal: Signal, state: AccountState,
               decision: Decision) -> None:
        row = {
            "logged_at_utc": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal.signal_id,
            "strategy": signal.strategy,
            "symbol": signal.symbol,
            "side": signal.side,
            "entry_time": signal.entry_time.isoformat(),
            "account_id": state.account_id,
            "account_stage": state.stage.value,
            "balance": state.balance,
            "peak_realized_equity": state.peak_realized_equity,
            "reserved_open_risk": state.reserved_open_risk,
            **asdict(decision),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str, sort_keys=True) + "\n")
