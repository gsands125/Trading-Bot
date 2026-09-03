from __future__ import annotations
from typing import Dict

from .models import AccountState, AccountStage, Signal, Decision
from .personal import PersonalV21Governor
from .lifecycle import EvaluationGovernor, FundedGovernor, LiveGovernor, reserve_on_entry
from .positions import PositionLedger, PositionRecord


class MasterRouter:
    """
    Phase 3 v0.3 deterministic multi-account router.

    Adds:
    - position ledger
    - entry reservation
    - realized exits
    - restart-safe state serialization hooks
    """

    def __init__(
        self,
        personal_governor=None,
        evaluation_governor=None,
        funded_governor=None,
        live_governor=None,
        audit_ledger=None,
    ):
        self.accounts: Dict[str, AccountState] = {}
        self.processed_signal_ids = set()
        self.personal_governor = personal_governor or PersonalV21Governor(
            strategy_caps={"S4": 5}
        )
        self.evaluation_governor = evaluation_governor or EvaluationGovernor()
        self.funded_governor = funded_governor or FundedGovernor()
        self.live_governor = live_governor or LiveGovernor()
        self.audit_ledger = audit_ledger
        self.position_ledger = PositionLedger()

    def register_account(self, state: AccountState) -> None:
        if state.account_id in self.accounts:
            raise ValueError(f"duplicate account_id: {state.account_id}")
        self.accounts[state.account_id] = state

    def decide_for_account(self, account_id: str, signal: Signal) -> Decision:
        state = self.accounts[account_id]
        if state.stage == AccountStage.PERSONAL:
            return self.personal_governor.decide(state, signal)
        if state.stage == AccountStage.EVALUATION:
            return self.evaluation_governor.decide(state, signal)
        if state.stage == AccountStage.FUNDED:
            return self.funded_governor.decide(state, signal)
        if state.stage == AccountStage.LIVE:
            return self.live_governor.decide(state, signal)
        raise ValueError(f"unsupported stage: {state.stage}")

    def route_signal(self, signal: Signal) -> Dict[str, Decision]:
        if signal.signal_id in self.processed_signal_ids:
            raise ValueError(f"duplicate signal_id: {signal.signal_id}")

        out = {}
        for account_id in sorted(self.accounts):
            state = self.accounts[account_id]
            d = self.decide_for_account(account_id, signal)
            out[account_id] = d

            if d.take:
                if state.stage == AccountStage.PERSONAL:
                    self.personal_governor.reserve_on_entry(state, d)
                else:
                    reserve_on_entry(state, d)

                self.position_ledger.open(PositionRecord(
                    account_id=account_id,
                    signal_id=signal.signal_id,
                    strategy=signal.strategy,
                    symbol=signal.symbol,
                    side=signal.side,
                    qty=d.qty,
                    rpc=d.rpc,
                    reserved_risk=d.risk_dollars,
                    entry_time=signal.entry_time,
                    entry_price=signal.entry_price,
                    technical_stop=signal.technical_stop,
                ))

            if self.audit_ledger is not None:
                self.audit_ledger.append(signal, state, d)

        self.processed_signal_ids.add(signal.signal_id)
        return out

    def realize_exit(self, account_id: str, signal_id: str,
                     pnl_per_contract: float) -> float:
        state = self.accounts[account_id]
        p = self.position_ledger.close(account_id, signal_id)

        pnl = p.qty * float(pnl_per_contract)
        state.balance += pnl
        state.peak_realized_equity = max(state.peak_realized_equity, state.balance)

        if state.stage == AccountStage.PERSONAL:
            state.trading_nav = float(state.trading_nav) + pnl
            state.trading_peak = max(float(state.trading_peak), float(state.trading_nav))

        state.reserved_open_risk = max(
            0.0, state.reserved_open_risk - p.reserved_risk
        )
        return pnl
