from datetime import datetime
import json
from master_router import (
    MasterRouter, JsonlAuditLedger, AccountStage, Quality, Signal,
    new_prop_account, LUCID_FLEX_50K
)

def test_audit_writes_take_or_skip(tmp_path):
    p = tmp_path / "audit.jsonl"
    r = MasterRouter(audit_ledger=JsonlAuditLedger(p))
    r.register_account(new_prop_account(
        "E1", AccountStage.EVALUATION, LUCID_FLEX_50K
    ))
    r.route_signal(Signal(
        "A1","S3","MNQ","long",datetime(2026,9,3,10),100,
        Quality.CONFIRMED
    ))
    rows = [json.loads(x) for x in p.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["signal_id"] == "A1"
    assert rows[0]["account_id"] == "E1"
    assert rows[0]["reason"] in {"TAKE","WHOLE_CONTRACT_DOES_NOT_FIT"}
