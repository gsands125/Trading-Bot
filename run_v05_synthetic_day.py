from pathlib import Path
from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K,
    JsonStateStore, LifecycleStateMachine, PaperRouterService
)

SECRET="SYNTHETIC_DAY_SECRET"
state=Path("/mnt/data/master_router_v05_synthetic_day_state.json")
if state.exists():
    state.unlink()

router=MasterRouter()
router.register_account(new_prop_account(
    "LUCID-EVAL-1",AccountStage.EVALUATION,LUCID_FLEX_50K
))
router.register_account(new_prop_account(
    "TRADEIFY-EVAL-1",AccountStage.EVALUATION,TRADEIFY_SELECT_FLEX_50K
))
router.register_account(AccountState(
    "PERSONAL-1",AccountStage.PERSONAL,5000,5000,5000
))

svc=PaperRouterService(
    router,SECRET,
    state_store=JsonStateStore(state),
    lifecycle_machine=LifecycleStateMachine(),
    firm_configs={
        LUCID_FLEX_50K.name:LUCID_FLEX_50K,
        TRADEIFY_SELECT_FLEX_50K.name:TRADEIFY_SELECT_FLEX_50K,
    }
)

events=[
    {
        "event_type":"entry","secret":SECRET,
        "signal_id":"SYN-S3-001","strategy":"S3","symbol":"MNQ","side":"long",
        "entry_time":"2026-09-03T10:15:00-04:00","rpc":95.668,
        "quality":"confirmed","entry_price":24000.0,"technical_stop":23952.166
    },
    {
        "event_type":"exit","secret":SECRET,
        "signal_id":"SYN-S3-001",
        "exit_time":"2026-09-03T11:05:00-04:00",
        "pnl_per_contract":75.0
    },
    {
        "event_type":"entry","secret":SECRET,
        "signal_id":"SYN-S4-001","strategy":"S4","symbol":"MNQ","side":"short",
        "entry_time":"2026-09-03T14:10:00-04:00","rpc":40.0,
        "quality":"ordinary","entry_price":24100.0,"technical_stop":24120.0
    },
    {
        "event_type":"exit","secret":SECRET,
        "signal_id":"SYN-S4-001",
        "exit_time":"2026-09-03T15:40:00-04:00",
        "pnl_per_contract":-40.0
    },
    {
        "event_type":"eod","secret":SECRET,"day":"2026-09-03"
    }
]

for i,e in enumerate(events,1):
    out=svc.handle_payload(e)
    print(f"\nEVENT {i}: {e['event_type'].upper()}")
    print(out)

print("\nFINAL ACCOUNT STATE")
for aid,s in sorted(router.accounts.items()):
    print(
        aid,
        "stage",s.stage.value,
        "balance",round(s.balance,2),
        "reserved",round(s.reserved_open_risk,2),
        "floor",s.eod_drawdown_floor
    )
