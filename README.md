# Futures Master Router — Phase 3 v0.7

v0.7 is the Railway forward-paper deployment gate.

## Deployment policy

The first forward deployment intentionally enables **S3 only** by default.

This is not a strategy change. It is an operational rollout guardrail so we
can verify the full live-alert path with one known strategy before enabling
S1, S2 and S4.

Default:
- `PAPER_MODE=true`
- `ALLOWED_STRATEGIES=S3`

Once the live TradingView → Railway → Router → paper-fill → reconciliation
path is clean, expand the env value to `S1,S2,S3,S4`.

## Added in v0.7

- Hard paper-mode startup guardrail.
- Configurable strategy allowlist.
- S3-only default forward-paper rollout.
- `/ready` deployment-readiness endpoint.
- Protected `/status` endpoint using `X-Status-Secret`.
- Startup diagnostics that block `/webhook` if configuration is unsafe.
- Railway deployment config (`railway.json`).
- `.env.example`.
- Single-worker Gunicorn configuration to preserve deterministic local-state
  behavior while using the Railway persistent volume.
- All historical Personal benchmark and v0.1–v0.6 tests remain in the suite.

## Railway setup

Mount a persistent volume at:

`/data`

Set variables:

```text
WEBHOOK_SECRET=<long random secret>
STATUS_SECRET=<different long random secret>
PAPER_MODE=true
ALLOWED_STRATEGIES=S3
ROUTER_ACCOUNTS_CONFIG=accounts.example.json
```

The other durable paths already default to `/data/...`.

## First deployment validation

After Railway deploys:

1. Open `/health`.
2. Confirm `"ok": true`, `"mode": "PAPER"`.
3. Open `/ready`.
4. Confirm `"ready_for_forward_paper": true`.
5. Send one manual S3 test webhook.
6. Check `/status` with the `X-Status-Secret` header.
7. Confirm one paper position/fill and no invariant violations.
8. Only then point the real TradingView S3 alert at `/webhook`.

Do **not** enable S1/S2/S4 on day one.

## Local validation

```bash
cd /mnt/data/master_router_phase3_v0_7
PYTHONPATH=. python -m pytest -q
python run_regression.py
python run_v06_restart_demo.py
python run_v07_deployment_smoke.py
```
