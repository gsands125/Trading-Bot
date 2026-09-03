from __future__ import annotations
from pathlib import Path
import json

from .models import AccountState, AccountStage
from .lifecycle import (
    new_prop_account, LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K
)

FIRMS = {
    LUCID_FLEX_50K.name: LUCID_FLEX_50K,
    TRADEIFY_SELECT_FLEX_50K.name: TRADEIFY_SELECT_FLEX_50K,
}


def load_accounts_from_json(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    accounts = []

    for item in raw.get("accounts", []):
        stage = AccountStage(item["stage"])
        if stage == AccountStage.PERSONAL:
            start = float(item["starting_equity"])
            accounts.append(AccountState(
                account_id=item["account_id"],
                stage=stage,
                starting_equity=start,
                balance=float(item.get("balance", start)),
                peak_realized_equity=float(item.get("peak_realized_equity", start)),
                max_contracts=item.get("max_contracts"),
                metadata=item.get("metadata", {}),
            ))
            continue

        firm_name = item["firm"]
        if firm_name not in FIRMS:
            raise ValueError(f"unknown firm config: {firm_name}")
        s = new_prop_account(item["account_id"], stage, FIRMS[firm_name])

        # Optional runtime overrides only; frozen risk logic remains unchanged.
        if "payout_cap" in item:
            s.metadata["payout_cap"] = float(item["payout_cap"])
        if "min_payout_request" in item:
            s.metadata["min_payout_request"] = float(item["min_payout_request"])
        if "trader_split" in item:
            s.metadata["trader_split"] = float(item["trader_split"])
        accounts.append(s)

    return accounts
