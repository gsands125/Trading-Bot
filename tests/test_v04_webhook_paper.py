from datetime import datetime
import json
import pytest

from master_router import (
    MasterRouter, AccountState, AccountStage,
    new_prop_account, LUCID_FLEX_50K,
    JsonStateStore, PaperRouterService,
    PaperExecutionAdapter, JsonlReconciliationLedger,
    parse_tradingview_payload, WebhookAuthError, WebhookValidationError,
)


SECRET = "test-secret"

def payload(signal_id="SIG-1"):
    return {
        "secret": SECRET,
        "signal_id": signal_id,
        "strategy": "S3",
        "symbol": "MNQ",
        "side": "long",
        "entry_time": "2026-09-03T10:15:00-04:00",
        "rpc": 95.668,
        "quality": "confirmed",
        "permitted": True,
        "entry_price": 24000.0,
        "technical_stop": 23952.166,
    }


def build_router():
    r = MasterRouter()
    r.register_account(new_prop_account(
        "LUCID-EVAL", AccountStage.EVALUATION, LUCID_FLEX_50K
    ))
    r.register_account(AccountState(
        "PERSONAL", AccountStage.PERSONAL, 5000, 5000, 5000
    ))
    return r


def test_webhook_auth_and_validation():
    good = parse_tradingview_payload(payload(), SECRET)
    assert good.signal.rpc == 95.668
    assert good.signal.signal_id == "SIG-1"

    bad = payload()
    bad["secret"] = "wrong"
    with pytest.raises(WebhookAuthError):
        parse_tradingview_payload(bad, SECRET)

    bad2 = payload()
    del bad2["rpc"]
    with pytest.raises(WebhookValidationError):
        parse_tradingview_payload(bad2, SECRET)


def test_end_to_end_payload_to_paper_fill_and_reconciliation(tmp_path):
    r = build_router()
    state = JsonStateStore(tmp_path/"state.json")
    rec_ledger = JsonlReconciliationLedger(tmp_path/"recon.jsonl")
    svc = PaperRouterService(
        r, SECRET, state_store=state,
        reconciliation_ledger=rec_ledger
    )

    out = svc.handle_payload(payload("E2E-1"))
    assert out["ok"] is True
    assert set(out["accounts"]) == {"LUCID-EVAL","PERSONAL"}

    for aid, item in out["accounts"].items():
        if item["decision"]["take"]:
            assert item["paper_fill"]["status"] == "FILLED"
            assert item["reconciliation"]["ok"] is True

    assert state.path.exists()
    rows = rec_ledger.path.read_text().strip().splitlines()
    assert len(rows) >= 1


def test_duplicate_signal_is_idempotent_and_does_not_duplicate_orders(tmp_path):
    r = build_router()
    adapter = PaperExecutionAdapter()
    svc = PaperRouterService(r, SECRET, paper_adapter=adapter)

    first = svc.handle_payload(payload("DUP-1"))
    order_count = len(adapter.orders)
    second = svc.handle_payload(payload("DUP-1"))

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["reason"] == "IDEMPOTENT_REPLAY_IGNORED"
    assert len(adapter.orders) == order_count


def test_paper_adapter_submit_is_idempotent():
    r = build_router()
    p = payload("IDEMP-1")
    parsed = parse_tradingview_payload(p, SECRET)
    decisions = r.route_signal(parsed.signal)
    adapter = PaperExecutionAdapter()

    d = decisions["PERSONAL"]
    f1 = adapter.submit("PERSONAL", parsed.signal, d)
    f2 = adapter.submit("PERSONAL", parsed.signal, d)
    assert f1 == f2
    assert len(adapter.orders) == 1
