from datetime import date
from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K,
    JsonStateStore, LifecycleStateMachine, PaperRouterService,
)

SECRET="v05-secret"

def service(tmp_path):
    r=MasterRouter()
    r.register_account(new_prop_account(
        "LUCID-EVAL",AccountStage.EVALUATION,LUCID_FLEX_50K
    ))
    r.register_account(AccountState(
        "PERSONAL",AccountStage.PERSONAL,5000,5000,5000
    ))
    return PaperRouterService(
        r, SECRET,
        state_store=JsonStateStore(tmp_path/"state.json"),
        lifecycle_machine=LifecycleStateMachine(),
        firm_configs={LUCID_FLEX_50K.name:LUCID_FLEX_50K},
    )

def entry_payload(sid="S1"):
    return {
        "event_type":"entry",
        "secret":SECRET,
        "signal_id":sid,
        "strategy":"S3",
        "symbol":"MNQ",
        "side":"long",
        "entry_time":"2026-09-03T10:15:00-04:00",
        "rpc":100.0,
        "quality":"confirmed",
        "entry_price":24000.0,
        "technical_stop":23950.0,
    }

def test_full_entry_exit_eod_cycle(tmp_path):
    svc=service(tmp_path)
    out=svc.handle_payload(entry_payload("DAY1"))
    assert out["event_type"]=="entry"

    ex=svc.handle_payload({
        "event_type":"exit",
        "secret":SECRET,
        "signal_id":"DAY1",
        "exit_time":"2026-09-03T14:00:00-04:00",
        "pnl_per_contract":50.0
    })
    assert ex["event_type"]=="exit"
    assert ex["accounts"]["PERSONAL"]["ok"] is True

    eod=svc.handle_payload({
        "event_type":"eod",
        "secret":SECRET,
        "day":"2026-09-03"
    })
    assert eod["event_type"]=="eod"
    assert "LUCID-EVAL" in eod["accounts"]


def test_eval_pass_creates_new_funded_account_via_eod(tmp_path):
    svc=service(tmp_path)
    a=svc.router.accounts["LUCID-EVAL"]
    a.balance=53000.0

    sm=svc.lifecycle_machine
    for i in range(1,5):
        d=date(2026,9,i)
        sm.record_realized_pnl(a,750.0,d)
        out=svc.handle_payload({
            "event_type":"eod",
            "secret":SECRET,
            "day":d.isoformat(),
            "account_id":"LUCID-EVAL"
        })

    assert out["accounts"]["LUCID-EVAL"]["passed"] is True
    assert "LUCID-EVAL::FUNDED" in svc.router.accounts
    assert svc.router.accounts["LUCID-EVAL::FUNDED"].balance==50000.0
