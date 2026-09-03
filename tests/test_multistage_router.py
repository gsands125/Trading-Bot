from datetime import datetime
import pytest

from master_router import (
    AccountState, AccountStage, Quality, Signal, MasterRouter,
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K,
    EvaluationGovernor, funded_max_micros,
)


def sig(sid="X1", rpc=100.0, q=Quality.CONFIRMED):
    return Signal(
        signal_id=sid, strategy="S3", symbol="MNQ", side="long",
        entry_time=datetime(2026, 9, 3, 10, 0), rpc=rpc, quality=q
    )


def test_multi_account_fanout_is_independent():
    r = MasterRouter()

    ev = new_prop_account("LUCID-EVAL", AccountStage.EVALUATION,
                          LUCID_FLEX_50K)
    fu = new_prop_account("TRADEIFY-FUNDED", AccountStage.FUNDED,
                          TRADEIFY_SELECT_FLEX_50K)
    pe = AccountState(
        "PERSONAL", AccountStage.PERSONAL,
        starting_equity=5000, balance=5000, peak_realized_equity=5000
    )

    # Same market signal, intentionally different account risk states.
    ev.balance = 49000
    fu.balance = 51000
    pe.balance = 5000

    r.register_account(ev)
    r.register_account(fu)
    r.register_account(pe)

    out = r.route_signal(sig())
    assert set(out) == {"LUCID-EVAL","TRADEIFY-FUNDED","PERSONAL"}
    assert out["LUCID-EVAL"].qty != out["TRADEIFY-FUNDED"].qty
    assert out["PERSONAL"].qty != out["TRADEIFY-FUNDED"].qty


def test_duplicate_signal_rejected():
    r = MasterRouter()
    r.register_account(new_prop_account(
        "E1", AccountStage.EVALUATION, LUCID_FLEX_50K
    ))
    r.route_signal(sig("DUP"))
    with pytest.raises(ValueError):
        r.route_signal(sig("DUP"))


def test_eval_70_85_blocks_ordinary():
    s = new_prop_account("E1", AccountStage.EVALUATION, LUCID_FLEX_50K)
    # Initial floor 48,000; balance 48,500 = $500 cushion = 75% consumed.
    s.balance = 48500
    d = EvaluationGovernor().decide(
        s, sig("RISK", rpc=50, q=Quality.ORDINARY)
    )
    assert not d.take
    assert d.risk_state == "RECOVERY_70_85_BLOCK_ORDINARY"


def test_funded_scaling_thresholds():
    assert funded_max_micros(LUCID_FLEX_50K, 999) == 20
    assert funded_max_micros(LUCID_FLEX_50K, 1000) == 30
    assert funded_max_micros(LUCID_FLEX_50K, 2000) == 40

    assert funded_max_micros(TRADEIFY_SELECT_FLEX_50K, 1499) == 20
    assert funded_max_micros(TRADEIFY_SELECT_FLEX_50K, 1500) == 30
    assert funded_max_micros(TRADEIFY_SELECT_FLEX_50K, 2000) == 40
