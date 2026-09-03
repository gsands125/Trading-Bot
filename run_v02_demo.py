from datetime import datetime
from master_router import (
    MasterRouter, AccountState, AccountStage, Quality, Signal,
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K
)

r = MasterRouter()
r.register_account(new_prop_account(
    "LUCID-EVAL-1", AccountStage.EVALUATION, LUCID_FLEX_50K
))
r.register_account(new_prop_account(
    "TRADEIFY-FUNDED-1", AccountStage.FUNDED, TRADEIFY_SELECT_FLEX_50K
))
r.register_account(AccountState(
    "PERSONAL-1", AccountStage.PERSONAL,
    starting_equity=5000, balance=5000, peak_realized_equity=5000
))

signal = Signal(
    signal_id="DEMO-S3-001", strategy="S3", symbol="MNQ", side="long",
    entry_time=datetime(2026,9,3,10,15), rpc=95.668,
    quality=Quality.CONFIRMED
)

for account_id, d in r.route_signal(signal).items():
    print(
        account_id,
        "TAKE" if d.take else "SKIP",
        "qty=", d.qty,
        "risk=$", round(d.risk_dollars,2),
        "state=", d.risk_state,
        "reason=", d.reason,
    )
