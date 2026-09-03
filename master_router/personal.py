from __future__ import annotations
import math
from dataclasses import dataclass
from .models import AccountState, Quality, Signal, Decision, ExternalContribution


@dataclass(frozen=True)
class PersonalDepositPolicyB:
    """
    LOCKED Phase-2 policy:
    - External deposits increase real broker equity.
    - Effective DD is calculated from actual realized broker equity/peak.
    - Deposits can therefore restore Half/Full aggression.
    - Deposits do NOT count as trading profit for the ratchet.
    """
    name: str = "Policy B — Effective-capital DD"


class PersonalV21Governor:
    """
    Exact Personal Aggressive Compound v2.1 sizing behavior, plus the locked
    external-deposit Policy B extension.

    Exact benchmark quirks preserved:
    - Base risk: O 3%, C 4%, E 5%
    - 20–35% DD: half base
    - >=35% DD: 1% regardless of quality
    - Before first ratchet, reserved open risk does NOT reduce risk budget.
    - After ratchet, reserved open risk reduces free capital.
    - Whole-contract floor.
    - No generic MNQ cap. Optional strategy caps can be configured (S4=5).
    """

    BASE = {
        Quality.ORDINARY: 0.03,
        Quality.CONFIRMED: 0.04,
        Quality.EXCEPTIONAL: 0.05,
    }

    def __init__(self, strategy_caps=None):
        self.strategy_caps = dict(strategy_caps or {})

    @staticmethod
    def protected_floor(start: float, trading_peak: float) -> float:
        mult = trading_peak / start
        if mult >= 5:
            return 3.5 * start
        if mult >= 3:
            return 2.0 * start
        if mult >= 2:
            return 1.5 * start
        return 0.0

    @classmethod
    def risk_pct_and_state(cls, quality: Quality, dd: float):
        base = cls.BASE[quality]
        if dd < 0.20:
            return base, "FULL"
        if dd < 0.35:
            return base * 0.5, "HALF"
        return 0.01, "CONSERVATION"

    @staticmethod
    def effective_dd(state: AccountState) -> float:
        # Policy B: actual broker equity vs actual realized peak.
        if state.peak_realized_equity <= 0:
            return 1.0
        return max(0.0, (state.peak_realized_equity - state.balance) /
                   state.peak_realized_equity)

    def decide(self, state: AccountState, signal: Signal) -> Decision:
        signal.validate()

        if not signal.permitted:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0, 0.0,
                "BLOCKED", "MARKET_BRAIN_BLOCKED", signal.rpc,
                self.effective_dd(state), 0.0, state.reserved_open_risk
            )

        dd = self.effective_dd(state)
        pct, risk_state = self.risk_pct_and_state(signal.quality, dd)
        protected = self.protected_floor(
            state.starting_equity,
            float(state.trading_peak)
        )

        if protected > 0:
            free_cap = max(
                0.0,
                state.balance - protected - state.reserved_open_risk
            )
            risk_budget = min(pct * state.balance, pct * free_cap)
        else:
            # Exact benchmark quirk: reserved risk ignored pre-ratchet.
            risk_budget = pct * state.balance

        qty = math.floor(risk_budget / signal.rpc)
        if signal.strategy in self.strategy_caps:
            qty = min(qty, int(self.strategy_caps[signal.strategy]))

        if qty < 1:
            return Decision(
                state.account_id, signal.signal_id, False, 0, 0.0,
                risk_budget, risk_state, "WHOLE_CONTRACT_DOES_NOT_FIT",
                signal.rpc, dd, protected, state.reserved_open_risk
            )

        risk_dollars = qty * signal.rpc
        return Decision(
            state.account_id, signal.signal_id, True, qty, risk_dollars,
            risk_budget, risk_state, "TAKE", signal.rpc, dd, protected,
            state.reserved_open_risk
        )

    @staticmethod
    def reserve_on_entry(state: AccountState, decision: Decision) -> None:
        if decision.take:
            state.reserved_open_risk += decision.risk_dollars

    @staticmethod
    def realize_exit(
        state: AccountState,
        qty: int,
        pnl_per_contract: float,
        reserved_risk: float,
    ) -> float:
        pnl = qty * pnl_per_contract
        state.balance += pnl
        state.trading_nav = float(state.trading_nav) + pnl
        state.peak_realized_equity = max(
            state.peak_realized_equity, state.balance
        )
        state.trading_peak = max(float(state.trading_peak),
                                 float(state.trading_nav))
        state.reserved_open_risk -= reserved_risk
        if abs(state.reserved_open_risk) < 1e-9:
            state.reserved_open_risk = 0.0
        return pnl

    @staticmethod
    def apply_external_contribution(
        state: AccountState,
        contribution: ExternalContribution
    ) -> None:
        if contribution.amount <= 0:
            raise ValueError("external contribution must be > 0")
        state.balance += contribution.amount
        state.external_contributions += contribution.amount
        state.peak_realized_equity = max(
            state.peak_realized_equity, state.balance
        )
        # Intentionally DO NOT modify trading_nav/trading_peak.
