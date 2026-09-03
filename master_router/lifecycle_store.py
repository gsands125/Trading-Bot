from __future__ import annotations
from pathlib import Path
import json


class JsonLifecycleStore:
    """Durable storage for lifecycle-machine daily realized-P&L state."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, lifecycle_machine) -> None:
        payload = {
            "daily_pnl": {
                f"{aid}||{day}": pnl
                for (aid, day), pnl in lifecycle_machine.daily_pnl.items()
            }
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(self.path)

    def load_into(self, lifecycle_machine) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        lifecycle_machine.daily_pnl = {}
        for k, pnl in raw.get("daily_pnl", {}).items():
            aid, day = k.split("||", 1)
            lifecycle_machine.daily_pnl[(aid, day)] = float(pnl)
