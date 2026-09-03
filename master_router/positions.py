from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict


@dataclass
class PositionRecord:
    account_id: str
    signal_id: str
    strategy: str
    symbol: str
    side: str
    qty: int
    rpc: float
    reserved_risk: float
    entry_time: datetime
    entry_price: float | None = None
    technical_stop: float | None = None


class PositionLedger:
    def __init__(self):
        self._positions: Dict[str, PositionRecord] = {}

    @staticmethod
    def key(account_id: str, signal_id: str) -> str:
        return f"{account_id}::{signal_id}"

    def open(self, p: PositionRecord) -> None:
        k = self.key(p.account_id, p.signal_id)
        if k in self._positions:
            raise ValueError(f"position already open: {k}")
        self._positions[k] = p

    def get(self, account_id: str, signal_id: str) -> PositionRecord:
        k = self.key(account_id, signal_id)
        if k not in self._positions:
            raise KeyError(f"open position not found: {k}")
        return self._positions[k]

    def close(self, account_id: str, signal_id: str) -> PositionRecord:
        k = self.key(account_id, signal_id)
        if k not in self._positions:
            raise KeyError(f"open position not found: {k}")
        return self._positions.pop(k)

    def for_account(self, account_id: str):
        return [p for p in self._positions.values() if p.account_id == account_id]

    def to_dict(self):
        out = {}
        for k, p in self._positions.items():
            raw = asdict(p)
            raw["entry_time"] = p.entry_time.isoformat()
            out[k] = raw
        return out

    def load_dict(self, raw):
        self._positions.clear()
        for k, p in raw.items():
            p = dict(p)
            p["entry_time"] = datetime.fromisoformat(p["entry_time"])
            self._positions[k] = PositionRecord(**p)
