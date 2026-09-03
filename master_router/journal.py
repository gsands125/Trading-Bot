from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Dict, Any, Iterable


class JsonlEventJournal:
    """
    Append-only accepted-event journal.

    Purposes:
    - crash recovery / replay
    - audit trail
    - duplicate exit / duplicate EOD protection
    - forward-test reconciliation
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_id: str, payload: Dict[str, Any],
               outcome: Dict[str, Any]) -> None:
        row = {
            "logged_at_utc": datetime.now(timezone.utc).isoformat(),
            "event_id": event_id,
            "payload": payload,
            "outcome": outcome,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    def read_all(self):
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def seen_event_ids(self):
        return {r["event_id"] for r in self.read_all()}
