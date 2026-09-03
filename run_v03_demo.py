from datetime import datetime, date
from pathlib import Path

from master_router import (
    MasterRouter, JsonStateStore, LifecycleStateMachine,
    AccountState, AccountStage, Quality, Signal,
    new_prop_account, LUCID_FLEX_50K
)

statefile=Path("/mnt/data/master_router_phase3_v03_demo_state.json")
if statefile.exists():
    statefile.unlink()

router=MasterRouter()
personal=AccountState(
    "PERSONAL-1",AccountStage.PERSONAL,
    starting_equity=5000,balance=5000,peak_realized_equity=5000
)
funded=new_prop_account(
    "LUCID-FUNDED-1",AccountStage.FUNDED,LUCID_FLEX_50K
)
funded.metadata["payout_cap"]=2000.0
funded.metadata["min_payout_request"]=500.0
funded.metadata["trader_split"]=0.90

router.register_account(personal)
router.register_account(funded)

s=Signal(
    "LIVE-DEMO-001","S3","MNQ","long",
    datetime(2026,9,3,10,15),95.668,Quality.CONFIRMED
)

decisions=router.route_signal(s)
print("ENTRY FAN-OUT")
for aid,d in decisions.items():
    print(aid, "TAKE" if d.take else "SKIP", "qty", d.qty, "risk", round(d.risk_dollars,2))

print("\nOPEN POSITIONS BEFORE RESTART:", len(router.position_ledger.to_dict()))

store=JsonStateStore(statefile)
store.save(router)

restored=MasterRouter()
store.load_into(restored)
print("OPEN POSITIONS AFTER RESTART:", len(restored.position_ledger.to_dict()))
print("PROCESSED SIGNAL RESTORED:", "LIVE-DEMO-001" in restored.processed_signal_ids)

for aid in ["PERSONAL-1","LUCID-FUNDED-1"]:
    if restored.position_ledger.for_account(aid):
        pnl=restored.realize_exit(aid,"LIVE-DEMO-001",50.0)
        print(aid,"realized pnl",round(pnl,2),"new balance",round(restored.accounts[aid].balance,2))

store.save(restored)
