import pytest
pytest.importorskip("flask")

from master_router import MasterRouter, AccountState, AccountStage, PaperRouterService, create_flask_app
from master_router.s1_adapter import (
    parse_s1_text, S1AdapterValidationError, S1CaptureJournal,
)

S1_TOKEN = "s1-secret-token"


def build_app(tmp_path, s1_token=S1_TOKEN):
    r = MasterRouter()
    r.register_account(AccountState(
        "PERSONAL", AccountStage.PERSONAL, 5000, 5000, 5000
    ))
    svc = PaperRouterService(r, "router-secret")
    journal = S1CaptureJournal(tmp_path / "s1_capture.jsonl")
    app = create_flask_app(
        svc, s1_token=s1_token, s1_capture_journal=journal, s1_rpc_proxy=168.0
    )
    return app, journal


def test_parse_s1_text_buy_entry_normalizes_fields():
    event = parse_s1_text("ICT-UNI-1,buy,MNQZ2026,sl=23950,risk=1.5,tp=24100")

    assert event.source_id == "ICT-UNI-1"
    assert event.action == "buy"
    assert event.side == "long"
    assert event.event_type == "entry"
    assert event.stop_loss == 23950.0
    assert event.risk == 1.5
    assert event.tp == 24100.0

    preview = event.normalized_preview()
    assert preview["symbol"] == "MNQ"
    assert preview["strategy"] == "S1"
    assert preview["route_ready"] is False
    assert preview["route_block_reason"] == "S1_ALERT_HAS_NO_ENTRY_PRICE"


def test_parse_s1_text_close_exit_captures_reason():
    event = parse_s1_text("ICT-UNI-1,close,MNQ,reason=stop_hit")

    assert event.action == "close"
    assert event.event_type == "exit"
    assert event.side is None
    assert event.reason == "stop_hit"

    preview = event.normalized_preview()
    assert preview["event_type"] == "exit"
    assert preview["reason"] == "stop_hit"
    assert preview["route_ready"] is False
    assert preview["route_block_reason"] == "S1_ALERT_HAS_NO_EXIT_PRICE_OR_PNL"


def test_parse_s1_text_rejects_invalid_action():
    with pytest.raises(S1AdapterValidationError):
        parse_s1_text("ICT-UNI-1,hold,MNQ,sl=23950")


def test_parse_s1_text_entry_requires_stop_loss():
    with pytest.raises(S1AdapterValidationError):
        parse_s1_text("ICT-UNI-1,buy,MNQ,risk=1.5")


def test_s1_webhook_rejects_wrong_or_missing_token(tmp_path):
    app, journal = build_app(tmp_path)
    c = app.test_client()

    r = c.post("/webhook/s1/wrong-token", data="ICT-UNI-1,buy,MNQ,sl=23950")
    assert r.status_code == 401
    assert r.get_json()["ok"] is False
    assert not journal.path.exists() or journal.path.read_text() == ""


def test_s1_webhook_accepts_valid_token_and_journals_capture_only(tmp_path):
    app, journal = build_app(tmp_path)
    c = app.test_client()

    r = c.post(f"/webhook/s1/{S1_TOKEN}", data="ICT-UNI-1,buy,MNQ,sl=23950,risk=1.5")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["mode"] == "S1_CAPTURE_ONLY"
    assert body["strategy"] == "S1"
    assert body["symbol"] == "MNQ"
    assert body["route_ready"] is False

    rows = journal.path.read_text().strip().splitlines()
    assert len(rows) == 1
