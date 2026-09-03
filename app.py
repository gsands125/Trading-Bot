from pathlib import Path

from master_router import (
    MasterRouter,
    LUCID_FLEX_50K, TRADEIFY_SELECT_FLEX_50K,
    JsonStateStore, JsonlAuditLedger, JsonlReconciliationLedger,
    LifecycleStateMachine, PaperRouterService, create_flask_app,
    JsonLifecycleStore, JsonlEventJournal, JsonlAlertSink,
    load_accounts_from_json, DeploymentGuardrails,
)
from master_router.config import RouterConfig

cfg = RouterConfig.from_env()

guardrails = DeploymentGuardrails(
    paper_mode=cfg.paper_mode,
    allowed_strategies=cfg.allowed_strategies,
    status_secret=cfg.status_secret,
)

startup_problems = guardrails.validate_startup(
    cfg.state_path, cfg.accounts_config_path
)
if startup_problems:
    # App still starts so Railway health diagnostics are visible.
    # /webhook remains blocked until configuration is corrected.
    pass

router = MasterRouter(
    audit_ledger=JsonlAuditLedger(cfg.audit_path)
)
state_store = JsonStateStore(cfg.state_path)
state_store.load_into(router)

lifecycle = LifecycleStateMachine()
lifecycle_store = JsonLifecycleStore(cfg.lifecycle_state_path)
lifecycle_store.load_into(lifecycle)

if not router.accounts and not startup_problems:
    for account in load_accounts_from_json(cfg.accounts_config_path):
        router.register_account(account)
    state_store.save(router)

service = PaperRouterService(
    router=router,
    expected_secret=cfg.webhook_secret,
    state_store=state_store,
    reconciliation_ledger=JsonlReconciliationLedger(cfg.reconciliation_path),
    lifecycle_machine=lifecycle,
    lifecycle_store=lifecycle_store,
    firm_configs={
        LUCID_FLEX_50K.name: LUCID_FLEX_50K,
        TRADEIFY_SELECT_FLEX_50K.name: TRADEIFY_SELECT_FLEX_50K,
    },
    event_journal=JsonlEventJournal(cfg.event_journal_path),
    alert_sink=JsonlAlertSink(cfg.alert_path),
    deployment_guardrails=guardrails,
)

app = create_flask_app(
    service,
    status_secret=cfg.status_secret,
    startup_problems=startup_problems
)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.port)
