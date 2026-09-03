from datetime import datetime
from master_router.models import AccountState, AccountStage, ExternalContribution
from master_router.personal import PersonalV21Governor

def test_policy_b_deposit_improves_effective_dd_without_changing_trading_peak():
    g = PersonalV21Governor()
    s = AccountState(
        account_id="P1",
        stage=AccountStage.PERSONAL,
        starting_equity=5000,
        balance=6500,
        peak_realized_equity=10000,
        trading_nav=6500,
        trading_peak=10000,
    )
    before = g.effective_dd(s)
    assert abs(before - .35) < 1e-12

    g.apply_external_contribution(
        s, ExternalContribution(datetime(2026,9,3), 1500)
    )

    after = g.effective_dd(s)
    assert after < .35
    assert s.trading_peak == 10000
    assert s.trading_nav == 6500
    assert s.external_contributions == 1500
