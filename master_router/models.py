from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict


class AccountStage(str, Enum):
    EVALUATION = "evaluation"
    FUNDED = "funded"
    LIVE = "live"
    PERSONAL = "personal"


class Quality(str, Enum):
    ORDINARY = "ordinary"
    CONFIRMED = "confirmed"
    EXCEPTIONAL = "exceptional"


@dataclass(frozen=True)
class Signal:
    signal_id: str
    strategy: str
    symbol: str
    side: str
    entry_time: datetime
    rpc: float
    quality: Quality
    permitted: bool = True
    technical_stop: Optional[float] = None
    entry_price: Optional[float] = None

    def validate(self) -> None:
        if not self.signal_id:
            raise ValueError("signal_id is required")
        if self.side.lower() not in {"long", "short"}:
            raise ValueError("side must be 'long' or 'short'")
        if self.rpc <= 0:
            raise ValueError("rpc must be > 0")


@dataclass
class AccountState:
    account_id: str
    stage: AccountStage
    starting_equity: float
    balance: float
    peak_realized_equity: float
    reserved_open_risk: float = 0.0

    # Personal-specific ledgers.
    external_contributions: float = 0.0
    trading_nav: Optional[float] = None
    trading_peak: Optional[float] = None

    # Generic lifecycle/config state.
    eod_drawdown_floor: Optional[float] = None
    max_contracts: Optional[int] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.trading_nav is None:
            self.trading_nav = self.starting_equity
        if self.trading_peak is None:
            self.trading_peak = self.starting_equity


@dataclass(frozen=True)
class ExternalContribution:
    timestamp: datetime
    amount: float
    source: str = "PROP_PAYOUT"


@dataclass(frozen=True)
class Decision:
    account_id: str
    signal_id: str
    take: bool
    qty: int
    risk_dollars: float
    risk_budget: float
    risk_state: str
    reason: str
    rpc: float
    effective_dd: float
    protected_floor: float
    reserved_open_risk_before: float
