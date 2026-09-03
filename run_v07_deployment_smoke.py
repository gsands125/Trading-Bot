from pathlib import Path
from master_router import (
    DeploymentGuardrails, MasterRouter, AccountState, AccountStage,
    PaperRouterService
)

guard=DeploymentGuardrails(
    paper_mode=True,
    allowed_strategies={"S3"}
)

tmp=Path("/mnt/data/v07_deploy_smoke")
tmp.mkdir(exist_ok=True)
accounts=tmp/"accounts.json"
accounts.write_text('{"accounts":[{"account_id":"P","stage":"personal","starting_equity":5000}]}')

problems=guard.validate_startup(
    str(tmp/"state.json"), str(accounts)
)
print("startup problems:",problems)
assert problems == []

router=MasterRouter()
router.register_account(AccountState(
    "P",AccountStage.PERSONAL,5000,5000,5000
))
svc=PaperRouterService(
    router,"SMOKE",
    deployment_guardrails=guard
)

s4={
    "event_type":"entry","secret":"SMOKE",
    "signal_id":"SMOKE-S4","strategy":"S4","symbol":"MNQ","side":"short",
    "entry_time":"2026-09-03T14:00:00-04:00",
    "rpc":40,"quality":"ordinary","entry_price":24000,"technical_stop":24020
}
s3=dict(s4)
s3.update({
    "signal_id":"SMOKE-S3",
    "strategy":"S3",
    "side":"long",
    "rpc":100,
    "quality":"confirmed",
    "technical_stop":23950
})

print("S4:",svc.handle_payload(s4))
print("S3:",svc.handle_payload(s3))
print("open positions:",len(router.position_ledger.to_dict()))
assert len(router.position_ledger.to_dict()) == 1
print("PASS — deployment smoke test.")
