from datetime import datetime, date
from master_router import (
    MasterRouter, AccountState, AccountStage, Quality, Signal,
    JsonStateStore, LifecycleStateMachine,
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K
)


def signal(sid="S1", rpc=100.0):
    return Signal(
        sid, "S3", "MNQ", "long", datetime(2026,9,3,10,0),
        rpc, Quality.CONFIRMED
    )


def test_position_reserve_and_exit_release():
    r=MasterRouter()
    p=AccountState(
        "P", AccountStage.PERSONAL, 5000, 5000, 5000
    )
    r.register_account(p)
    d=r.route_signal(signal("P1"))["P"]
    assert d.take
    assert p.reserved_open_risk == d.risk_dollars
    pnl=r.realize_exit("P","P1",50.0)
    assert pnl == d.qty*50.0
    assert p.reserved_open_risk == 0.0
    assert len(r.position_ledger.for_account("P")) == 0


def test_state_store_restart_recovery(tmp_path):
    store=JsonStateStore(tmp_path/"state.json")
    r=MasterRouter()
    p=AccountState(
        "P", AccountStage.PERSONAL, 5000, 5000, 5000
    )
    r.register_account(p)
    d=r.route_signal(signal("RESTART"))["P"]
    store.save(r)

    r2=MasterRouter()
    store.load_into(r2)
    assert "P" in r2.accounts
    assert "RESTART" in r2.processed_signal_ids
    assert len(r2.position_ledger.for_account("P")) == 1
    assert r2.accounts["P"].reserved_open_risk == d.risk_dollars


def test_eval_pass_creates_new_funded_instance():
    sm=LifecycleStateMachine()
    a=new_prop_account("EVAL1",AccountStage.EVALUATION,LUCID_FLEX_50K)
    # 4 equal days of +750 = +3000; best day is 25%, passes 50% consistency.
    a.balance=53000
    for d in [date(2026,9,1),date(2026,9,2),date(2026,9,3),date(2026,9,4)]:
        sm.record_realized_pnl(a,750,d)
        res=sm.settle_eod(a,LUCID_FLEX_50K,d)
    assert res.passed
    assert res.next_stage_account is not None
    assert res.next_stage_account.stage == AccountStage.FUNDED
    assert res.next_stage_account.balance == 50000
    assert res.next_stage_account.account_id != a.account_id


def test_eval_consistency_can_delay_pass():
    sm=LifecycleStateMachine()
    a=new_prop_account("EVAL2",AccountStage.EVALUATION,TRADEIFY_SELECT_FLEX_50K)
    a.balance=53000
    # One +2000 day plus two +500 days => total 3000; 2000 > 40% of 3000.
    vals=[2000,500,500]
    out=None
    for i,v in enumerate(vals,1):
        d=date(2026,9,i)
        sm.record_realized_pnl(a,v,d)
        out=sm.settle_eod(a,TRADEIFY_SELECT_FLEX_50K,d)
    assert not out.passed
    assert out.reason=="EVAL_CONSISTENCY_NOT_MET"


def test_funded_payout_after_five_qualifying_days():
    sm=LifecycleStateMachine()
    a=new_prop_account("F1",AccountStage.FUNDED,LUCID_FLEX_50K)
    a.metadata["payout_cap"]=2000.0
    a.metadata["min_payout_request"]=500.0
    a.metadata["trader_split"]=0.90

    # 5 qualifying days, account now +2500.
    a.balance=52500
    res=None
    for i in range(1,6):
        d=date(2026,9,i)
        sm.record_realized_pnl(a,500,d)
        res=sm.settle_eod(a,LUCID_FLEX_50K,d)

    assert res.payout_eligible
    assert res.payout_request == 1250.0
    assert res.payout_cash == 1125.0
    assert a.balance == 51250.0
    assert a.eod_drawdown_floor == 50100.0
    assert a.metadata["qualifying_days"] == 0
