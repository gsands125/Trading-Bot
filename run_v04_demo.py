from pathlib import Path
from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K,
    JsonStateStore, JsonlReconciliationLedger, PaperRouterService
)

secret="DEMO_SECRET"

router=MasterRouter()
router.register_account(new_prop_account(
    "LUCID-EVAL-1",AccountStage.EVALUATION,LUCID_FLEX_50K
))
router.register_account(new_prop_account(
    "TRADEIFY-FUNDED-1",AccountStage.FUNDED,TRADEIFY_SELECT_FLEX_50K
))
router.register_account(AccountState(
    "PERSONAL-1",AccountStage.PERSONAL,5000,5000,5000
))

svc=PaperRouterService(
    router,
    secret,
    state_store=JsonStateStore("/mnt/data/master_router_phase3_v04_demo_state.json"),
    reconciliation_ledger=JsonlReconciliationLedger(
        "/mnt/data/master_router_phase3_v04_demo_reconciliation.jsonl"
    )
)

payload={
    "secret":secret,
    "signal_id":"TV-DEMO-S3-001",
    "strategy":"S3",
    "symbol":"MNQ",
    "side":"long",
    "entry_time":"2026-09-03T10:15:00-04:00",
    "rpc":95.668,
    "quality":"confirmed",
    "permitted":True,
    "entry_price":24000.0,
    "technical_stop":23952.166
}

out=svc.handle_payload(payload)
print("SIGNAL:",out["signal_id"])
for aid,x in out["accounts"].items():
    d=x["decision"]
    f=x["paper_fill"]
    rec=x["reconciliation"]
    print(
        aid,
        "TAKE" if d["take"] else "SKIP",
        "qty",d["qty"],
        "risk",round(d["risk_dollars"],2),
        "fill", None if f is None else f["status"],
        "reconciled", None if rec is None else rec["ok"],
    )
