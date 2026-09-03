from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, Optional
from .models import AccountState, AccountStage, Quality, Signal, Decision


QUALITY_KEYS = {
    Quality.ORDINARY: "ordinary",
    Quality.CONFIRMED: "confirmed",
    Quality.EXCEPTIONAL: "exceptional",
}


@dataclass(frozen=True)
class FirmConfig:
    name: str
    starting_balance: float = 50000.0
    max_loss: float = 2000.0
    eval_target: float = 3000.0
    eval_consistency: Optional[float] = None
    eval_max_micros: int = 40
    funded_max_micros: int = 40

    # Current funded scaling thresholds from frozen research snapshot.
    funded_scale_2_threshold: float = 1000.0
    funded_scale_3_threshold: float = 2000.0
    funded_scale_qty_1: int = 20
    funded_scale_qty_2: int = 30
    funded_scale_qty_3: int = 40

    # EOD floor lock used by the tested 50K products.
    lock_balance: float = 50100.0
    lock_trigger_peak: float = 52100.0


LUCID_FLEX_50K = FirmConfig(
    name="LucidFlex 50K",
    eval_consistency=0.50,
    funded_scale_2_threshold=1000.0,
    funded_scale_3_threshold=2000.0,
)

TRADEIFY_SELECT_FLEX_50K = FirmConfig(
    name="Tradeify Select Flex 50K",
    eval_consistency=0.40,
    funded_scale_2_threshold=1500.0,
    funded_scale_3_threshold=2000.0,
)


@dataclass
class EvaluationGovernor:
    """
    Frozen evaluation DD governor.

    Risk is a percentage of remaining usable EOD drawdown:
      Healthy (<25% DD consumed): O15 / C20 / E25
      25-50% consumed:           O12.5 / C15 / E20
      50-70% consumed:           O10 / C12.5 / E15
      70-85% consumed:           Ordinary blocked; C/E recovery only
      >=85% consumed:            STOP

    Firm-specific attack profiles can override the healthy tier.
    """
    healthy: Dict[Quality, float] = field(default_factory=lambda: {
        Quality.ORDINARY: .15,
        Quality.CONFIRMED: .20,
        Quality.EXCEPTIONAL: .25,
    })
    recovery_70_85: Dict[Quality, float] = field(default_factory=lambda: {
        Quality.CONFIRMED: .10,
        Quality.EXCEPTIONAL: .125,
    })

    def _risk_pct_state(self, consumed: float, q: Quality):
        if consumed >= .85:
            return 0.0, "STOP_85"
        if consumed >= .70:
            if q == Quality.ORDINARY:
                return 0.0, "RECOVERY_70_85_BLOCK_ORDINARY"
            return self.recovery_70_85[q], "RECOVERY_70_85"
        if consumed >= .50:
            return {
                Quality.ORDINARY:.10,
                Quality.CONFIRMED:.125,
                Quality.EXCEPTIONAL:.15,
            }[q], "REDUCED_50_70"
        if consumed >= .25:
            return {
                Quality.ORDINARY:.125,
                Quality.CONFIRMED:.15,
                Quality.EXCEPTIONAL:.20,
            }[q], "REDUCED_25_50"
        return self.healthy[q], "HEALTHY"

    def decide(self, state: AccountState, signal: Signal) -> Decision:
        signal.validate()
        if not signal.permitted:
            return _blocked(state, signal, "MARKET_BRAIN_BLOCKED")

        floor = _required_floor(state)
        max_loss = float(state.metadata.get("max_loss", 2000.0))
        cushion = max(0.0, state.balance - floor)
        consumed = min(1.0, max(0.0, 1.0 - cushion / max_loss))
        pct, risk_state = self._risk_pct_state(consumed, signal.quality)

        if pct <= 0:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0, 0.0,
                risk_state, risk_state, signal.rpc, consumed, 0.0,
                state.reserved_open_risk
            )

        # Account architecture reserves existing technical open risk.
        available_cushion = max(0.0, cushion - state.reserved_open_risk)
        budget = pct * available_cushion
        qty = math.floor(budget / signal.rpc)
        qty = _apply_max_qty(state, qty)

        if qty < 1:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0, budget,
                risk_state, "WHOLE_CONTRACT_DOES_NOT_FIT", signal.rpc,
                consumed, 0.0, state.reserved_open_risk
            )

        return Decision(
            state.account_id, signal.signal_id, True, qty, qty*signal.rpc,
            budget, risk_state, "TAKE", signal.rpc, consumed, 0.0,
            state.reserved_open_risk
        )


@dataclass
class FundedGovernor:
    """
    Frozen Funded PUSH objective:
      Ordinary 20%, Confirmed 25%, Exceptional 30%
    of remaining usable funded DD, after reserved open risk.
    """
    risk: Dict[Quality, float] = field(default_factory=lambda: {
        Quality.ORDINARY:.20,
        Quality.CONFIRMED:.25,
        Quality.EXCEPTIONAL:.30,
    })

    def decide(self, state: AccountState, signal: Signal) -> Decision:
        signal.validate()
        if not signal.permitted:
            return _blocked(state, signal, "MARKET_BRAIN_BLOCKED")
        floor = _required_floor(state)
        cushion = max(0.0, state.balance - floor)
        available = max(0.0, cushion - state.reserved_open_risk)
        pct = self.risk[signal.quality]
        budget = pct * available
        qty = _apply_max_qty(state, math.floor(budget / signal.rpc))
        if qty < 1:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0, budget,
                "FUNDED_PUSH", "WHOLE_CONTRACT_DOES_NOT_FIT", signal.rpc,
                _dd_fraction(state), 0.0, state.reserved_open_risk
            )
        return Decision(
            state.account_id, signal.signal_id, True, qty, qty*signal.rpc,
            budget, "FUNDED_PUSH", "TAKE", signal.rpc, _dd_fraction(state),
            0.0, state.reserved_open_risk
        )


@dataclass
class LiveGovernor:
    """
    Frozen working Live PUSH candidate:
      Ordinary 10%, Confirmed 12.5%, Exceptional 15%
    The exact Live withdrawal policy remains intentionally separate.
    """
    risk: Dict[Quality, float] = field(default_factory=lambda: {
        Quality.ORDINARY:.10,
        Quality.CONFIRMED:.125,
        Quality.EXCEPTIONAL:.15,
    })

    def decide(self, state: AccountState, signal: Signal) -> Decision:
        signal.validate()
        if not signal.permitted:
            return _blocked(state, signal, "MARKET_BRAIN_BLOCKED")
        floor = _required_floor(state)
        cushion = max(0.0, state.balance - floor)
        available = max(0.0, cushion - state.reserved_open_risk)
        budget = self.risk[signal.quality] * available
        qty = _apply_max_qty(state, math.floor(budget / signal.rpc))
        if qty < 1:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0, budget,
                "LIVE_PUSH_CANDIDATE", "WHOLE_CONTRACT_DOES_NOT_FIT",
                signal.rpc, _dd_fraction(state), 0.0,
                state.reserved_open_risk
            )
        return Decision(
            state.account_id, signal.signal_id, True, qty, qty*signal.rpc,
            budget, "LIVE_PUSH_CANDIDATE", "TAKE", signal.rpc,
            _dd_fraction(state), 0.0, state.reserved_open_risk
        )


def reserve_on_entry(state: AccountState, decision: Decision) -> None:
    if decision.take:
        state.reserved_open_risk += decision.risk_dollars


def release_reserved_risk(state: AccountState, amount: float) -> None:
    state.reserved_open_risk = max(0.0, state.reserved_open_risk - amount)


def update_eod_floor(state: AccountState) -> None:
    """
    Generic EOD floor updater for the tested 50K EOD products.
    Requires metadata:
      max_loss, lock_balance, lock_trigger_peak, floor_locked
    """
    max_loss = float(state.metadata.get("max_loss", 2000.0))
    lock_balance = float(state.metadata.get("lock_balance", 50100.0))
    lock_trigger = float(state.metadata.get("lock_trigger_peak", 52100.0))
    locked = bool(state.metadata.get("floor_locked", False))

    state.peak_realized_equity = max(state.peak_realized_equity, state.balance)
    if locked or state.peak_realized_equity >= lock_trigger:
        state.metadata["floor_locked"] = True
        state.eod_drawdown_floor = lock_balance
    else:
        state.eod_drawdown_floor = min(
            lock_balance,
            state.peak_realized_equity - max_loss
        )


def _required_floor(state: AccountState) -> float:
    if state.eod_drawdown_floor is not None:
        return float(state.eod_drawdown_floor)
    max_loss = float(state.metadata.get("max_loss", 2000.0))
    return state.starting_equity - max_loss


def _apply_max_qty(state: AccountState, qty: int) -> int:
    if state.max_contracts is None:
        return max(0, qty)
    return min(max(0, qty), int(state.max_contracts))


def _dd_fraction(state: AccountState) -> float:
    if state.peak_realized_equity <= 0:
        return 1.0
    return max(0.0, (state.peak_realized_equity-state.balance) /
               state.peak_realized_equity)


def _blocked(state, signal, reason):
    return Decision(
        state.account_id, signal.signal_id, False, 0, 0.0, 0.0,
        "BLOCKED", reason, signal.rpc, _dd_fraction(state), 0.0,
        state.reserved_open_risk
    )


def funded_max_micros(config: FirmConfig, eod_profit: float) -> int:
    if eod_profit >= config.funded_scale_3_threshold:
        return config.funded_scale_qty_3
    if eod_profit >= config.funded_scale_2_threshold:
        return config.funded_scale_qty_2
    return config.funded_scale_qty_1


def new_prop_account(account_id: str, stage: AccountStage,
                     config: FirmConfig) -> AccountState:
    max_qty = (config.eval_max_micros if stage == AccountStage.EVALUATION
               else config.funded_max_micros)
    return AccountState(
        account_id=account_id,
        stage=stage,
        starting_equity=config.starting_balance,
        balance=config.starting_balance,
        peak_realized_equity=config.starting_balance,
        eod_drawdown_floor=config.starting_balance-config.max_loss,
        max_contracts=max_qty,
        metadata={
            "firm": config.name,
            "max_loss": config.max_loss,
            "lock_balance": config.lock_balance,
            "lock_trigger_peak": config.lock_trigger_peak,
            "floor_locked": False,
            "eval_target": config.eval_target,
            "eval_consistency": config.eval_consistency,
        },
    )
