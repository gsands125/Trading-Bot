from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Dict, Optional

from .models import Decision, Signal


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    account_id: str
    signal_id: str
    strategy: str
    symbol: str
    side: str
    qty: int
    intended_entry: Optional[float]
    intended_stop: Optional[float]
    intended_risk: float


@dataclass(frozen=True)
class PaperFill:
    order_id: str
    account_id: str
    signal_id: str
    qty: int
    fill_price: Optional[float]
    status: str = "FILLED"


@dataclass(frozen=True)
class Reconciliation:
    order_id: str
    account_id: str
    signal_id: str
    qty_match: bool
    price_match: bool
    status_match: bool
    ok: bool
    detail: str


class PaperExecutionAdapter:
    """
    Deterministic paper broker simulator.

    Default fill model:
    - TAKE decisions become immediate FILLED paper orders.
    - fill_price == intended entry when entry_price exists.
    - no slippage is invented.
    """

    def __init__(self):
        self.orders: Dict[str, PaperOrder] = {}
        self.fills: Dict[str, PaperFill] = {}

    @staticmethod
    def _order_id(account_id: str, signal_id: str) -> str:
        return f"PAPER::{account_id}::{signal_id}"

    def submit(self, account_id: str, signal: Signal, decision: Decision) -> Optional[PaperFill]:
        if not decision.take:
            return None

        oid = self._order_id(account_id, signal.signal_id)
        if oid in self.orders:
            # Idempotent retry: return the original fill instead of duplicating.
            return self.fills[oid]

        order = PaperOrder(
            order_id=oid,
            account_id=account_id,
            signal_id=signal.signal_id,
            strategy=signal.strategy,
            symbol=signal.symbol,
            side=signal.side,
            qty=decision.qty,
            intended_entry=signal.entry_price,
            intended_stop=signal.technical_stop,
            intended_risk=decision.risk_dollars,
        )
        fill = PaperFill(
            order_id=oid,
            account_id=account_id,
            signal_id=signal.signal_id,
            qty=decision.qty,
            fill_price=signal.entry_price,
            status="FILLED",
        )
        self.orders[oid] = order
        self.fills[oid] = fill
        return fill

    def reconcile(self, fill: PaperFill) -> Reconciliation:
        order = self.orders[fill.order_id]
        qty_match = fill.qty == order.qty
        price_match = (
            order.intended_entry is None
            or fill.fill_price == order.intended_entry
        )
        status_match = fill.status == "FILLED"
        ok = qty_match and price_match and status_match
        detail = "OK" if ok else (
            f"qty_match={qty_match}; price_match={price_match}; "
            f"status_match={status_match}"
        )
        return Reconciliation(
            order.order_id, order.account_id, order.signal_id,
            qty_match, price_match, status_match, ok, detail
        )


class JsonlReconciliationLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, rec: Reconciliation) -> None:
        row = {
            "logged_at_utc": datetime.now(timezone.utc).isoformat(),
            **asdict(rec),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
