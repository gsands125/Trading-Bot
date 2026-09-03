from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import json
from typing import Dict

from .models import AccountState, AccountStage


class JsonStateStore:
    """
    Simple durable JSON state store for paper-router restart recovery.

    Stores:
    - account states
    - open positions
    - processed signal IDs
    - lifecycle metadata
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, router) -> None:
        payload = {
            "accounts": {
                aid: {
                    "account_id": s.account_id,
                    "stage": s.stage.value,
                    "starting_equity": s.starting_equity,
                    "balance": s.balance,
                    "peak_realized_equity": s.peak_realized_equity,
                    "reserved_open_risk": s.reserved_open_risk,
                    "external_contributions": s.external_contributions,
                    "trading_nav": s.trading_nav,
                    "trading_peak": s.trading_peak,
                    "eod_drawdown_floor": s.eod_drawdown_floor,
                    "max_contracts": s.max_contracts,
                    "metadata": s.metadata,
                }
                for aid, s in router.accounts.items()
            },
            "open_positions": router.position_ledger.to_dict(),
            "processed_signal_ids": sorted(router.processed_signal_ids),
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str),
                       encoding="utf-8")
        tmp.replace(self.path)

    def load_into(self, router) -> None:
        if not self.path.exists():
            return

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        router.accounts.clear()
        for aid, raw in payload.get("accounts", {}).items():
            router.accounts[aid] = AccountState(
                account_id=raw["account_id"],
                stage=AccountStage(raw["stage"]),
                starting_equity=float(raw["starting_equity"]),
                balance=float(raw["balance"]),
                peak_realized_equity=float(raw["peak_realized_equity"]),
                reserved_open_risk=float(raw.get("reserved_open_risk", 0.0)),
                external_contributions=float(raw.get("external_contributions", 0.0)),
                trading_nav=raw.get("trading_nav"),
                trading_peak=raw.get("trading_peak"),
                eod_drawdown_floor=raw.get("eod_drawdown_floor"),
                max_contracts=raw.get("max_contracts"),
                metadata=raw.get("metadata", {}),
            )
        router.position_ledger.load_dict(payload.get("open_positions", {}))
        router.processed_signal_ids = set(payload.get("processed_signal_ids", []))
