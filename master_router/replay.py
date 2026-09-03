from __future__ import annotations
import numpy as np
import pandas as pd
from dataclasses import dataclass
from .models import AccountState, AccountStage, Quality, Signal
from .personal import PersonalV21Governor


@dataclass
class ReplayResult:
    ending_equity: float
    peak_equity: float
    trades_taken: int
    signals_skipped: int
    max_eod_dd: float
    event_log: pd.DataFrame


def replay_personal_core640_exact(csv_path: str, start: float = 5000.0):
    """
    Reproduces the exact 640-trade Personal v2.1 benchmark from the frozen
    eligible stream. ENTRY sorts before EXIT on the same timestamp.
    """
    df = pd.read_csv(csv_path, parse_dates=["entry_dt", "exit_dt"])
    governor = PersonalV21Governor()

    state = AccountState(
        account_id="PERSONAL_BENCHMARK",
        stage=AccountStage.PERSONAL,
        starting_equity=start,
        balance=start,
        peak_realized_equity=start,
    )

    events = []
    for i, r in df.iterrows():
        # Exact benchmark: entry sort key 0; exit sort key 1.
        events.append((r.entry_dt, 0, "ENTRY", i, r))
        events.append((r.exit_dt, 1, "EXIT", i, r))
    events.sort(key=lambda x: (x[0], x[1]))

    openpos = {}
    logs = []
    daybal = {}
    curday = None
    taken = skipped = 0

    for dt, _, typ, i, r in events:
        day = pd.Timestamp(dt).normalize()
        if curday is None:
            curday = day
        if day != curday:
            daybal[curday] = state.balance
            curday = day

        if typ == "ENTRY":
            q = Quality(str(r.quality).lower())
            sig = Signal(
                signal_id=f"{r.strategy}-{int(r['Trade number'])}-{i}",
                strategy=str(r.strategy),
                symbol="MNQ",
                side="long",  # direction is irrelevant to risk sizing here
                entry_time=pd.Timestamp(r.entry_dt).to_pydatetime(),
                rpc=float(r.rpc),
                quality=q,
                permitted=True,
            )
            d = governor.decide(state, sig)
            if d.take:
                governor.reserve_on_entry(state, d)
                openpos[i] = (d.qty, d.risk_dollars)
                taken += 1
                logs.append({
                    "timestamp": dt, "event": "ENTRY", "strategy": r.strategy,
                    "qty": d.qty, "balance": state.balance,
                    "peak": state.peak_realized_equity,
                    "dd": d.effective_dd, "risk_state": d.risk_state,
                    "risk_budget": d.risk_budget, "rpc": d.rpc,
                    "protected_floor": d.protected_floor,
                    "reserved_after": state.reserved_open_risk,
                })
            else:
                skipped += 1
                logs.append({
                    "timestamp": dt, "event": "SKIP", "strategy": r.strategy,
                    "qty": 0, "balance": state.balance,
                    "peak": state.peak_realized_equity,
                    "dd": d.effective_dd, "risk_state": d.risk_state,
                    "risk_budget": d.risk_budget, "rpc": d.rpc,
                    "protected_floor": d.protected_floor,
                    "reserved_after": state.reserved_open_risk,
                })
        else:
            if i in openpos:
                qty, rr = openpos.pop(i)
                pnl = governor.realize_exit(
                    state, qty, float(r.pnl_per_contract), rr
                )
                logs.append({
                    "timestamp": dt, "event": "EXIT", "strategy": r.strategy,
                    "qty": qty, "pnl": pnl, "balance": state.balance,
                    "peak": state.peak_realized_equity,
                    "reserved_after": state.reserved_open_risk,
                })

    if curday is not None:
        daybal[curday] = state.balance

    vals = np.array(list(daybal.values()), dtype=float)
    peaks = np.maximum.accumulate(vals)
    maxdd = float(np.max((peaks - vals) / peaks)) if len(vals) else 0.0

    return ReplayResult(
        ending_equity=state.balance,
        peak_equity=state.peak_realized_equity,
        trades_taken=taken,
        signals_skipped=skipped,
        max_eod_dd=maxdd,
        event_log=pd.DataFrame(logs),
    )
