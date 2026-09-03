from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class InvariantViolation:
    code: str
    account_id: str
    detail: str


def check_router_invariants(router) -> List[InvariantViolation]:
    v = []

    # Account-level invariants.
    for aid, s in router.accounts.items():
        if s.reserved_open_risk < -1e-9:
            v.append(InvariantViolation(
                "NEGATIVE_RESERVED_RISK", aid,
                f"reserved_open_risk={s.reserved_open_risk}"
            ))

        # Sum ledger risk must match account reserved risk.
        ledger_risk = sum(p.reserved_risk for p in router.position_ledger.for_account(aid))
        if abs(ledger_risk - s.reserved_open_risk) > 1e-6:
            v.append(InvariantViolation(
                "RESERVED_RISK_MISMATCH", aid,
                f"account={s.reserved_open_risk}; ledger={ledger_risk}"
            ))

        if s.stage.value in {"evaluation", "funded"} and s.eod_drawdown_floor is not None:
            if s.balance <= s.eod_drawdown_floor:
                v.append(InvariantViolation(
                    "ACCOUNT_AT_OR_BELOW_EOD_FLOOR", aid,
                    f"balance={s.balance}; floor={s.eod_drawdown_floor}"
                ))

        if s.stage.value == "personal":
            if s.external_contributions < -1e-9:
                v.append(InvariantViolation(
                    "NEGATIVE_EXTERNAL_CONTRIBUTIONS", aid,
                    f"external_contributions={s.external_contributions}"
                ))
            if float(s.trading_peak) + 1e-9 < float(s.trading_nav):
                v.append(InvariantViolation(
                    "TRADING_PEAK_BELOW_NAV", aid,
                    f"trading_peak={s.trading_peak}; trading_nav={s.trading_nav}"
                ))

    # Position keys must point to known accounts.
    for p in router.position_ledger.to_dict().values():
        if p["account_id"] not in router.accounts:
            v.append(InvariantViolation(
                "POSITION_UNKNOWN_ACCOUNT", p["account_id"],
                f"signal_id={p['signal_id']}"
            ))

    return v
