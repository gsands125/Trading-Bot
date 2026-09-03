from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json


class AlertSink:
    def send(self, severity: str, code: str, detail: str):
        raise NotImplementedError


class JsonlAlertSink(AlertSink):
    """
    Paper-forward alert sink.
    Writes alarms locally; later adapters may forward to email/Slack/etc.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, severity: str, code: str, detail: str):
        row = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "code": code,
            "detail": detail,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
