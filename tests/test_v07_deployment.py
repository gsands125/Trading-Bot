from pathlib import Path

from master_router import (
    MasterRouter, AccountState, AccountStage,
    PaperRouterService, DeploymentGuardrails,
    create_flask_app,
)

SECRET="v07"

def payload(strategy="S3", sid="D1"):
    return {
        "event_type":"entry","secret":SECRET,
        "signal_id":sid,"strategy":strategy,"symbol":"MNQ","side":"long",
        "entry_time":"2026-09-03T10:00:00-04:00",
        "rpc":100.0,"quality":"confirmed",
        "entry_price":24000,"technical_stop":23950,
    }

def test_s3_only_allowlist_blocks_s4_without_creating_position():
    r=MasterRouter()
    r.register_account(AccountState(
        "P",AccountStage.PERSONAL,5000,5000,5000
    ))
    g=DeploymentGuardrails(True,{"S3"})
    svc=PaperRouterService(r,SECRET,deployment_guardrails=g)

    blocked=svc.handle_payload(payload("S4","S4-X"))
    assert blocked["blocked"] is True
    assert len(r.position_ledger.to_dict()) == 0

    allowed=svc.handle_payload(payload("S3","S3-X"))
    assert allowed["blocked"] if "blocked" in allowed else False is False
    assert len(r.position_ledger.to_dict()) == 1

def test_paper_mode_false_fails_startup_guardrail(tmp_path):
    cfg=tmp_path/"accounts.json"
    cfg.write_text('{"accounts":[]}')
    g=DeploymentGuardrails(False,{"S3"})
    problems=g.validate_startup(str(tmp_path/"state.json"),str(cfg))
    assert any("PAPER_MODE" in x for x in problems)

def test_missing_accounts_and_state_fails_startup(tmp_path):
    g=DeploymentGuardrails(True,{"S3"})
    problems=g.validate_startup(
        str(tmp_path/"state.json"),
        str(tmp_path/"missing_accounts.json")
    )
    assert any("accounts config" in x for x in problems)

def test_ready_endpoint_and_protected_status(tmp_path):
    pytest = __import__("pytest")
    pytest.importorskip("flask")

    r=MasterRouter()
    r.register_account(AccountState(
        "P",AccountStage.PERSONAL,5000,5000,5000
    ))
    svc=PaperRouterService(r,SECRET)
    app=create_flask_app(svc,status_secret="STATUS",startup_problems=[])
    c=app.test_client()

    assert c.get("/ready").status_code==200
    assert c.get("/status").status_code==401
    assert c.get("/status",headers={"X-Status-Secret":"STATUS"}).status_code==200

def test_not_ready_blocks_webhook():
    pytest = __import__("pytest")
    pytest.importorskip("flask")

    r=MasterRouter()
    svc=PaperRouterService(r,SECRET)
    app=create_flask_app(
        svc,startup_problems=["example deployment problem"]
    )
    c=app.test_client()
    w=c.post("/webhook",json=payload())
    assert w.status_code==503
