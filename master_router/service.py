from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from typing import Dict, Any

from .webhook import parse_tradingview_payload
from .events import (
    parse_event_type, parse_exit_payload, parse_eod_payload,
    EventValidationError,
)
from .paper_execution import PaperExecutionAdapter
from .invariants import check_router_invariants


class PaperRouterService:
    """
    Hardened unified paper-event service.

    Guarantees:
    - deterministic event IDs
    - entry/exit/EOD idempotency
    - append-only event journal
    - invariant checks after accepted events
    - durable router + lifecycle state
    """

    def __init__(
        self,
        router,
        expected_secret: str,
        state_store=None,
        paper_adapter=None,
        reconciliation_ledger=None,
        lifecycle_machine=None,
        lifecycle_store=None,
        firm_configs=None,
        event_journal=None,
        alert_sink=None,
        deployment_guardrails=None,
    ):
        self.router = router
        self.expected_secret = expected_secret
        self.state_store = state_store
        self.paper_adapter = paper_adapter or PaperExecutionAdapter()
        self.reconciliation_ledger = reconciliation_ledger
        self.lifecycle_machine = lifecycle_machine
        self.lifecycle_store = lifecycle_store
        self.firm_configs = firm_configs or {}
        self.event_journal = event_journal
        self.alert_sink = alert_sink
        self.deployment_guardrails = deployment_guardrails
        self.processed_event_ids = set(
            event_journal.seen_event_ids() if event_journal is not None else []
        )

    @staticmethod
    def _event_id(payload: Dict[str, Any]) -> str:
        typ = parse_event_type(payload)
        if typ == "entry":
            return f"ENTRY::{payload.get('signal_id','')}"
        if typ == "exit":
            acct = payload.get("account_id") or "ALL"
            # Payload hash prevents same exit event from being applied twice.
            body = json.dumps(payload, sort_keys=True, default=str)
            h = hashlib.sha256(body.encode()).hexdigest()[:16]
            return f"EXIT::{acct}::{payload.get('signal_id','')}::{h}"
        acct = payload.get("account_id") or "ALL"
        return f"EOD::{acct}::{payload.get('day','')}"

    def handle_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event_id = self._event_id(payload)

        if event_id in self.processed_event_ids:
            return {
                "ok": True,
                "duplicate": True,
                "event_id": event_id,
                "reason": "IDEMPOTENT_REPLAY_IGNORED",
            }

        typ = parse_event_type(payload)
        if typ == "entry":
            out = self._handle_entry(payload)
        elif typ == "exit":
            out = self._handle_exit(payload)
        else:
            out = self._handle_eod(payload)

        out["event_id"] = event_id
        out["duplicate"] = False

        violations = check_router_invariants(self.router)
        out["invariants_ok"] = len(violations) == 0
        out["invariant_violations"] = [asdict(v) for v in violations]

        if violations and self.alert_sink is not None:
            for v in violations:
                self.alert_sink.send("CRITICAL", v.code, f"{v.account_id}: {v.detail}")

        self.processed_event_ids.add(event_id)
        if self.event_journal is not None:
            safe_payload = dict(payload)
            if "secret" in safe_payload:
                safe_payload["secret"] = "***REDACTED***"
            self.event_journal.append(event_id, safe_payload, out)

        self._persist()
        return out

    def _handle_entry(self, payload):
        parsed = parse_tradingview_payload(payload, self.expected_secret)
        signal = parsed.signal

        if (
            self.deployment_guardrails is not None
            and not self.deployment_guardrails.strategy_allowed(signal.strategy)
        ):
            return {
                "ok": True,
                "event_type": "entry",
                "signal_id": signal.signal_id,
                "strategy": signal.strategy,
                "accounts": {},
                "blocked": True,
                "reason": "STRATEGY_NOT_ENABLED_FOR_FORWARD_PAPER",
            }

        decisions = self.router.route_signal(signal)
        response_accounts = {}

        for account_id, decision in decisions.items():
            fill = self.paper_adapter.submit(account_id, signal, decision)
            rec = None
            if fill is not None:
                rec = self.paper_adapter.reconcile(fill)
                if self.reconciliation_ledger is not None:
                    self.reconciliation_ledger.append(rec)

            response_accounts[account_id] = {
                "decision": {
                    "take": decision.take,
                    "qty": decision.qty,
                    "risk_dollars": decision.risk_dollars,
                    "risk_budget": decision.risk_budget,
                    "risk_state": decision.risk_state,
                    "reason": decision.reason,
                },
                "paper_fill": asdict(fill) if fill is not None else None,
                "reconciliation": asdict(rec) if rec is not None else None,
            }

        return {
            "ok": True,
            "event_type": "entry",
            "signal_id": signal.signal_id,
            "accounts": response_accounts,
        }

    def _handle_exit(self, payload):
        ev = parse_exit_payload(payload, self.expected_secret)

        if ev.account_id is not None:
            target_accounts = [ev.account_id]
        else:
            target_accounts = [
                aid for aid in self.router.accounts
                if self.router.position_ledger.key(aid, ev.signal_id)
                in self.router.position_ledger.to_dict()
            ]

        results = {}
        for aid in target_accounts:
            if aid not in self.router.accounts:
                results[aid] = {"ok": False, "reason": "UNKNOWN_ACCOUNT"}
                continue
            key = self.router.position_ledger.key(aid, ev.signal_id)
            if key not in self.router.position_ledger.to_dict():
                results[aid] = {"ok": False, "reason": "NO_OPEN_POSITION"}
                continue

            pnl = self.router.realize_exit(aid, ev.signal_id, ev.pnl_per_contract)
            if self.lifecycle_machine is not None:
                self.lifecycle_machine.record_realized_pnl(
                    self.router.accounts[aid], pnl, ev.exit_time.date()
                )
            results[aid] = {
                "ok": True,
                "realized_pnl": pnl,
                "new_balance": self.router.accounts[aid].balance,
            }

        return {
            "ok": True,
            "event_type": "exit",
            "signal_id": ev.signal_id,
            "accounts": results,
        }

    def _handle_eod(self, payload):
        ev = parse_eod_payload(payload, self.expected_secret)
        if self.lifecycle_machine is None:
            raise EventValidationError("lifecycle machine not configured")

        account_ids = (
            [ev.account_id] if ev.account_id is not None
            else list(self.router.accounts.keys())
        )

        results = {}
        new_accounts = []

        for aid in list(account_ids):
            if aid not in self.router.accounts:
                results[aid] = {"ok": False, "reason": "UNKNOWN_ACCOUNT"}
                continue

            account = self.router.accounts[aid]
            firm_name = account.metadata.get("firm")
            cfg = self.firm_configs.get(firm_name)

            if cfg is None or account.stage.value not in {"evaluation", "funded"}:
                results[aid] = {
                    "ok": True,
                    "reason": "NO_PROP_EOD_ACTION",
                    "balance": account.balance,
                }
                continue

            r = self.lifecycle_machine.settle_eod(account, cfg, ev.day)
            results[aid] = {
                "ok": True,
                "breached": r.breached,
                "passed": r.passed,
                "payout_eligible": r.payout_eligible,
                "payout_request": r.payout_request,
                "payout_cash": r.payout_cash,
                "reason": r.reason,
                "eod_floor": account.eod_drawdown_floor,
                "balance": account.balance,
            }

            if r.next_stage_account is not None:
                new_accounts.append(r.next_stage_account)

        for a in new_accounts:
            if a.account_id not in self.router.accounts:
                self.router.register_account(a)

        return {
            "ok": True,
            "event_type": "eod",
            "day": ev.day.isoformat(),
            "accounts": results,
            "new_accounts": [a.account_id for a in new_accounts],
        }

    def _persist(self):
        if self.state_store is not None:
            self.state_store.save(self.router)
        if self.lifecycle_store is not None and self.lifecycle_machine is not None:
            self.lifecycle_store.save(self.lifecycle_machine)
