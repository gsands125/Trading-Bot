import pytest
pytest.importorskip("flask")

from master_router import (
    MasterRouter, AccountState, AccountStage,
    PaperRouterService, create_flask_app
)

SECRET="http-secret"

def test_http_health_and_webhook():
    r=MasterRouter()
    r.register_account(AccountState(
        "PERSONAL",AccountStage.PERSONAL,5000,5000,5000
    ))
    app=create_flask_app(PaperRouterService(r,SECRET))
    c=app.test_client()

    h=c.get("/health")
    assert h.status_code==200
    assert h.get_json()["ok"] is True

    p={
        "secret":SECRET,
        "signal_id":"HTTP-1",
        "strategy":"S3",
        "symbol":"MNQ",
        "side":"long",
        "entry_time":"2026-09-03T10:15:00-04:00",
        "rpc":100.0,
        "quality":"confirmed",
        "entry_price":24000.0,
        "technical_stop":23950.0
    }
    w=c.post("/webhook",json=p)
    assert w.status_code==200
    body=w.get_json()
    assert body["ok"] is True
    assert body["accounts"]["PERSONAL"]["reconciliation"]["ok"] is True

    # Exact retry is rejected by Router-level deduplication.
    w2=c.post("/webhook",json=p)
    assert w2.status_code==409
