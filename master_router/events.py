from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, Optional


class EventValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExitEvent:
    secret: str
    signal_id: str
    exit_time: datetime
    pnl_per_contract: float
    account_id: Optional[str] = None


@dataclass(frozen=True)
class EODEvent:
    secret: str
    day: date
    account_id: Optional[str] = None


def parse_event_type(payload: Dict[str, Any]) -> str:
    typ = str(payload.get("event_type", "entry")).strip().lower()
    if typ not in {"entry", "exit", "eod"}:
        raise EventValidationError("event_type must be entry, exit, or eod")
    return typ


def parse_exit_payload(payload: Dict[str, Any], expected_secret: str) -> ExitEvent:
    supplied = str(payload.get("secret", ""))
    if supplied != expected_secret:
        raise EventValidationError("invalid webhook secret")
    required = ["signal_id", "exit_time", "pnl_per_contract"]
    missing = [k for k in required if k not in payload]
    if missing:
        raise EventValidationError(f"missing required fields: {missing}")
    try:
        dt = datetime.fromisoformat(str(payload["exit_time"]).replace("Z", "+00:00"))
        ppc = float(payload["pnl_per_contract"])
    except Exception as e:
        raise EventValidationError("invalid exit payload") from e
    return ExitEvent(
        secret=supplied,
        signal_id=str(payload["signal_id"]),
        exit_time=dt,
        pnl_per_contract=ppc,
        account_id=payload.get("account_id"),
    )


def parse_eod_payload(payload: Dict[str, Any], expected_secret: str) -> EODEvent:
    supplied = str(payload.get("secret", ""))
    if supplied != expected_secret:
        raise EventValidationError("invalid webhook secret")
    if "day" not in payload:
        raise EventValidationError("missing required field: day")
    try:
        d = date.fromisoformat(str(payload["day"]))
    except Exception as e:
        raise EventValidationError("day must be YYYY-MM-DD") from e
    return EODEvent(
        secret=supplied,
        day=d,
        account_id=payload.get("account_id"),
    )
