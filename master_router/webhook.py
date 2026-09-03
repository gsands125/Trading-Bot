from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

from .models import Signal, Quality


class WebhookAuthError(ValueError):
    pass


class WebhookValidationError(ValueError):
    pass


QUALITY_MAP = {
    "ordinary": Quality.ORDINARY,
    "confirmed": Quality.CONFIRMED,
    "exceptional": Quality.EXCEPTIONAL,
}


@dataclass(frozen=True)
class ParsedWebhook:
    secret: str
    signal: Signal
    raw: Dict[str, Any]


def parse_tradingview_payload(payload: Dict[str, Any], expected_secret: str) -> ParsedWebhook:
    """
    Strict parser for TradingView webhook JSON.

    Required:
      secret, signal_id, strategy, symbol, side, entry_time, rpc, quality

    Optional:
      permitted, technical_stop, entry_price
    """
    if not isinstance(payload, dict):
        raise WebhookValidationError("payload must be a JSON object")

    supplied = str(payload.get("secret", ""))
    if not supplied or supplied != expected_secret:
        raise WebhookAuthError("invalid webhook secret")

    required = [
        "signal_id", "strategy", "symbol", "side",
        "entry_time", "rpc", "quality"
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        raise WebhookValidationError(f"missing required fields: {missing}")

    try:
        dt = datetime.fromisoformat(str(payload["entry_time"]).replace("Z", "+00:00"))
    except Exception as e:
        raise WebhookValidationError("entry_time must be ISO-8601") from e

    qraw = str(payload["quality"]).strip().lower()
    if qraw not in QUALITY_MAP:
        raise WebhookValidationError(
            "quality must be ordinary, confirmed, or exceptional"
        )

    try:
        rpc = float(payload["rpc"])
    except Exception as e:
        raise WebhookValidationError("rpc must be numeric") from e

    sig = Signal(
        signal_id=str(payload["signal_id"]).strip(),
        strategy=str(payload["strategy"]).strip(),
        symbol=str(payload["symbol"]).strip(),
        side=str(payload["side"]).strip().lower(),
        entry_time=dt,
        rpc=rpc,
        quality=QUALITY_MAP[qraw],
        permitted=bool(payload.get("permitted", True)),
        technical_stop=(
            float(payload["technical_stop"])
            if payload.get("technical_stop") is not None else None
        ),
        entry_price=(
            float(payload["entry_price"])
            if payload.get("entry_price") is not None else None
        ),
    )
    sig.validate()
    return ParsedWebhook(secret=supplied, signal=sig, raw=dict(payload))
