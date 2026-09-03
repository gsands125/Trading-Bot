from datetime import datetime
import json

from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K,
    JsonStateStore, JsonLifecycleStore,
    LifecycleStateMachine, PaperRouterService,
    JsonlEventJournal, check_router_invariants,
    load_accounts_from_json
)

SECRET="v06"

def base_service(tmp_path):
    r=MasterRouter()
    r.register_account(new_prop_account(
        "LUCID-EVAL",AccountStage.EVALUATION,LUCID_FLEX_50K
    ))
    r.register_account(AccountState(
        "PERSONAL",AccountStage.PERSONAL,5000,5000,5000
    ))
    lm=LifecycleStateMachine()
    return PaperRouterService(
        r,SECRET,
        state_store=JsonStateStore(tmp_path/"state.json"),
        lifecycle_machine=lm,
        lifecycle_store=JsonLifecycleStore(tmp_path/"life.json"),
        firm_configs={LUCID_FLEX_50K.name:LUCID_FLEX_50K},
        event_journal=JsonlEventJournal(tmp_path/"events.jsonl"),
    )

def entry(sid):
    return {
        "event_type":"entry","secret":SECRET,
        "signal_id":sid,"strategy":"S3","symbol":"MNQ","side":"long",
        "entry_time":"2026-09-03T10:00:00-04:00",
        "rpc":100.0,"quality":"confirmed",
        "entry_price":24000,"technical_stop":23950
    }

def test_duplicate_exit_is_idempotent(tmp_path):
    svc=base_service(tmp_path)
    svc.handle_payload(entry("X1"))
    ex={
        "event_type":"exit","secret":SECRET,
        "signal_id":"X1","exit_time":"2026-09-03T11:00:00-04:00",
        "pnl_per_contract":50
    }
    first=svc.handle_payload(ex)
    bal=svc.router.accounts["PERSONAL"].balance
    second=svc.handle_payload(ex)
    assert second["duplicate"] is True
    assert svc.router.accounts["PERSONAL"].balance == bal

def test_duplicate_eod_is_idempotent(tmp_path):
    svc=base_service(tmp_path)
    eod={"event_type":"eod","secret":SECRET,"day":"2026-09-03"}
    a=svc.handle_payload(eod)
    b=svc.handle_payload(eod)
    assert b["duplicate"] is True

def test_lifecycle_state_survives_restart(tmp_path):
    lm=LifecycleStateMachine()
    a=new_prop_account("E",AccountStage.EVALUATION,LUCID_FLEX_50K)
    lm.record_realized_pnl(a,250.0,datetime(2026,9,3).date())
    store=JsonLifecycleStore(tmp_path/"life.json")
    store.save(lm)

    lm2=LifecycleStateMachine()
    store.load_into(lm2)
    assert lm2.daily_pnl[("E","2026-09-03")] == 250.0

def test_invariants_clean_after_entry(tmp_path):
    svc=base_service(tmp_path)
    out=svc.handle_payload(entry("INV1"))
    assert out["invariants_ok"] is True
    assert check_router_invariants(svc.router) == []

def test_account_config_externalized(tmp_path):
    p=tmp_path/"accounts.json"
    p.write_text(json.dumps({
        "accounts":[
            {"account_id":"E1","stage":"evaluation","firm":"LucidFlex 50K"},
            {"account_id":"P1","stage":"personal","starting_equity":5000}
        ]
    }))
    acc=load_accounts_from_json(p)
    assert len(acc)==2
    assert {a.account_id for a in acc}=={"E1","P1"}
