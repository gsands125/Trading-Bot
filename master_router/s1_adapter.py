from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any, Dict, Optional


class S1AdapterValidationError(ValueError):
    pass


@dataclass(frozen=True)
class S1ParsedEvent:
    source_id: str
    action: str
    symbol: str
    received_at: str
    raw_text: str
    risk: Optional[float] = None
    stop_loss: Optional[float] = None
    tp: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    reason: Optional[str] = None

    @property
    def event_type(self) -> str:
        return "exit" if self.action == "close" else "entry"

    @property
    def side(self) -> Optional[str]:
        if self.action == "buy":
            return "long"
        if self.action == "sell":
            return "short"
        return None

    def normalized_preview(self, rpc_proxy: float = 168.0) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "source": "ICT_UNI_PROTECTED_ALERT",
            "source_id": self.source_id,
            "event_type": self.event_type,
            "strategy": "S1",
            "symbol": normalize_symbol(self.symbol),
            "received_at": self.received_at,
            "raw_action": self.action,
        }
        if self.event_type == "entry":
            base.update({
                "side": self.side,
                "quality": "ordinary",
                "rpc_proxy": float(rpc_proxy),
                "technical_stop": self.stop_loss,
                "entry_price": None,
                "source_risk": self.risk,
                "tp": self.tp,
                "tp1": self.tp1,
                "tp2": self.tp2,
                "route_ready": False,
                "route_block_reason": "S1_ALERT_HAS_NO_ENTRY_PRICE",
            })
        else:
            base.update({
                "reason": self.reason,
                "exit_price": None,
                "pnl_per_contract": None,
                "route_ready": False,
                "route_block_reason": "S1_ALERT_HAS_NO_EXIT_PRICE_OR_PNL",
            })
        return base


def normalize_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper()
    if s.startswith("MNQ"):
        return "MNQ"
    return s


def _to_float(value: str, field: str) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise S1AdapterValidationError(f"{field} must be numeric") from exc


def parse_s1_text(raw_text: str, received_at: Optional[datetime] = None) -> S1ParsedEvent:
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise S1AdapterValidationError("S1 payload must be non-empty text")

    raw = raw_text.strip()
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) < 3:
        raise S1AdapterValidationError("S1 payload requires source_id, action, symbol")

    source_id, action, symbol = parts[:3]
    action = action.lower()
    if not source_id:
        raise S1AdapterValidationError("S1 source_id is required")
    if action not in {"buy", "sell", "close"}:
        raise S1AdapterValidationError("S1 action must be buy, sell, or close")
    if not symbol:
        raise S1AdapterValidationError("S1 symbol is required")

    fields: Dict[str, str] = {}
    for token in parts[3:]:
        if not token:
            continue
        if "=" not in token:
            raise S1AdapterValidationError(f"invalid S1 field: {token}")
        k, v = token.split("=", 1)
        fields[k.strip().lower()] = v.strip()

    ts = received_at or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if action in {"buy", "sell"}:
        if "sl" not in fields:
            raise S1AdapterValidationError("S1 entry payload is missing sl")
        return S1ParsedEvent(
            source_id=source_id,
            action=action,
            symbol=symbol,
            received_at=ts.isoformat(),
            raw_text=raw,
            risk=_to_float(fields["risk"], "risk") if "risk" in fields else None,
            stop_loss=_to_float(fields["sl"], "sl"),
            tp=_to_float(fields["tp"], "tp") if "tp" in fields else None,
            tp1=_to_float(fields["tp1"], "tp1") if "tp1" in fields else None,
            tp2=_to_float(fields["tp2"], "tp2") if "tp2" in fields else None,
        )

    return S1ParsedEvent(
        source_id=source_id,
        action=action,
        symbol=symbol,
        received_at=ts.isoformat(),
        raw_text=raw,
        reason=fields.get("reason"),
    )


class S1CaptureJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: S1ParsedEvent, rpc_proxy: float = 168.0) -> Dict[str, Any]:
        row = {
            "logged_at_utc": datetime.now(timezone.utc).isoformat(),
            "parsed": asdict(event),
            "normalized_preview": event.normalized_preview(rpc_proxy=rpc_proxy),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        return row
