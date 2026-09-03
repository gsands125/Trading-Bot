from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .models import AccountState, AccountStage
from .lifecycle import FirmConfig, new_prop_account, update_eod_floor, funded_max_micros


@dataclass(frozen=True)
class EODResult:
    account_id: str
    breached: bool
    passed: bool
    payout_eligible: bool
    payout_request: float
    payout_cash: float
    next_stage_account: Optional[AccountState]
    reason: str


class LifecycleStateMachine:
    """
    Paper-router lifecycle controller for the frozen 50K EOD products.

    Evaluation:
    - target from FirmConfig
    - consistency from FirmConfig
    - EOD drawdown breach
    - pass creates a NEW Funded account instance

    Funded:
    - EOD drawdown
    - 5 winning days with >= $150
    - positive cycle profit
    - 90/10 payout
    - current payout cap supplied in account metadata/config
    - payout creates no fake trading profit on Personal; routing of cash is external
    """

    def __init__(self):
        self.daily_pnl = {}

    def record_realized_pnl(self, account: AccountState, pnl: float, day: date):
        key = (account.account_id, day.isoformat())
        self.daily_pnl[key] = self.daily_pnl.get(key, 0.0) + float(pnl)

    def settle_eod(self, account: AccountState, config: FirmConfig, day: date) -> EODResult:
        day_key = (account.account_id, day.isoformat())
        pnl_today = float(self.daily_pnl.get(day_key, 0.0))

        # EOD trailing floor updates only after the day's trading is done.
        update_eod_floor(account)

        if account.balance <= float(account.eod_drawdown_floor):
            return EODResult(
                account.account_id, True, False, False, 0.0, 0.0, None,
                "EOD_DRAWDOWN_BREACH"
            )

        if account.stage == AccountStage.EVALUATION:
            return self._settle_eval(account, config, day, pnl_today)

        if account.stage == AccountStage.FUNDED:
            return self._settle_funded(account, config, day, pnl_today)

        return EODResult(
            account.account_id, False, False, False, 0.0, 0.0, None,
            "NO_STAGE_ACTION"
        )

    def _settle_eval(self, account, config, day, pnl_today):
        days = account.metadata.setdefault("eval_daily_pnl", {})
        days[day.isoformat()] = pnl_today

        total_profit = account.balance - account.starting_equity
        best_day = max(days.values(), default=0.0)
        consistency_ok = True
        if config.eval_consistency is not None and total_profit > 0:
            consistency_ok = best_day <= config.eval_consistency * total_profit + 1e-9

        if total_profit >= config.eval_target and consistency_ok:
            funded_id = f"{account.account_id}::FUNDED"
            nxt = new_prop_account(funded_id, AccountStage.FUNDED, config)
            nxt.metadata["origin_eval_account_id"] = account.account_id
            return EODResult(
                account.account_id, False, True, False, 0.0, 0.0, nxt,
                "EVALUATION_PASSED_NEW_FUNDED_INSTANCE"
            )

        reason = "EVAL_TARGET_NOT_REACHED"
        if total_profit >= config.eval_target and not consistency_ok:
            reason = "EVAL_CONSISTENCY_NOT_MET"

        return EODResult(
            account.account_id, False, False, False, 0.0, 0.0, None, reason
        )

    def _settle_funded(self, account, config, day, pnl_today):
        if pnl_today >= 150.0:
            account.metadata["qualifying_days"] = int(
                account.metadata.get("qualifying_days", 0)
            ) + 1

        cycle_start_balance = float(
            account.metadata.setdefault("cycle_start_balance", account.starting_equity)
        )
        cycle_profit = account.balance - cycle_start_balance

        eod_profit = account.balance - account.starting_equity
        account.max_contracts = funded_max_micros(config, eod_profit)

        qdays = int(account.metadata.get("qualifying_days", 0))
        payout_cap = float(account.metadata.get("payout_cap", 0.0))
        min_request = float(account.metadata.get("min_payout_request", 500.0))
        split = float(account.metadata.get("trader_split", 0.90))

        if qdays >= 5 and cycle_profit > 0 and payout_cap > 0:
            total_profit = max(0.0, account.balance - account.starting_equity)
            request = min(0.5 * total_profit, payout_cap)

            if request >= min_request:
                cash = request * split
                account.balance -= request
                account.metadata["qualifying_days"] = 0
                account.metadata["cycle_start_balance"] = account.balance
                account.metadata["payout_count"] = int(
                    account.metadata.get("payout_count", 0)
                ) + 1

                # Tested 50K funded products lock to 50,100 after payout.
                account.metadata["floor_locked"] = True
                account.eod_drawdown_floor = float(
                    account.metadata.get("lock_balance", 50100.0)
                )

                return EODResult(
                    account.account_id, False, False, True,
                    request, cash, None, "FUNDED_PAYOUT_ELIGIBLE_AND_PROCESSED"
                )

        return EODResult(
            account.account_id, False, False, False, 0.0, 0.0, None,
            "FUNDED_NO_PAYOUT"
        )
