from pathlib import Path

from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K,
    JsonStateStore, JsonLifecycleStore, LifecycleStateMachine,
    JsonlEventJournal, PaperRouterService
)

SECRET="RESTART_DEMO"
base=Path("/mnt/data/v06_demo")
base.mkdir(exist_ok=True)
for f in base.glob("*"):
    f.unlink()

def make_service(load_existing=False):
    r=MasterRouter()
    state=JsonStateStore(base/"state.json")
    state.load_into(r)
    lm=LifecycleStateMachine()
    life=JsonLifecycleStore(base/"life.json")
    life.load_into(lm)

    if not r.accounts:
        r.register_account(new_prop_account(
            "LUCID-EVAL",AccountStage.EVALUATION,LUCID_FLEX_50K
        ))
        r.register_account(AccountState(
            "PERSONAL",AccountStage.PERSONAL,5000,5000,5000
        ))

    return PaperRouterService(
        r,SECRET,state_store=state,
        lifecycle_machine=lm,lifecycle_store=life,
        firm_configs={LUCID_FLEX_50K.name:LUCID_FLEX_50K},
        event_journal=JsonlEventJournal(base/"events.jsonl"),
    )

svc=make_service()
entry={
    "event_type":"entry","secret":SECRET,
    "signal_id":"RST-1","strategy":"S3","symbol":"MNQ","side":"long",
    "entry_time":"2026-09-03T10:00:00-04:00","rpc":100.0,
    "quality":"confirmed","entry_price":24000,"technical_stop":23950
}
print("ENTRY:",svc.handle_payload(entry))
print("open positions before restart:",len(svc.router.position_ledger.to_dict()))

svc2=make_service(load_existing=True)
print("open positions after restart:",len(svc2.router.position_ledger.to_dict()))

exit_event={
    "event_type":"exit","secret":SECRET,"signal_id":"RST-1",
    "exit_time":"2026-09-03T11:00:00-04:00","pnl_per_contract":50
}
print("EXIT #1:",svc2.handle_payload(exit_event))
balances={k:v.balance for k,v in svc2.router.accounts.items()}
print("balances after exit:",balances)

svc3=make_service(load_existing=True)
print("EXIT RETRY AFTER SECOND RESTART:",svc3.handle_payload(exit_event))
balances2={k:v.balance for k,v in svc3.router.accounts.items()}
print("balances after retry:",balances2)
assert balances2 == balances
print("PASS — duplicate exit after restart did not alter equity.")
