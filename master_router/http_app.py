from __future__ import annotations

def create_flask_app(service, status_secret=None, startup_problems=None, s1_token=None, s1_capture_journal=None, s1_rpc_proxy=168.0):
    from flask import Flask, jsonify, request
    from .webhook import WebhookAuthError, WebhookValidationError
    from .events import EventValidationError
    from .s1_adapter import parse_s1_text, S1AdapterValidationError

    app = Flask(__name__)
    startup_problems = list(startup_problems or [])

    @app.get("/health")
    def health():
        return jsonify({
            "ok": len(startup_problems) == 0,
            "service": "master-router-paper",
            "mode": "PAPER",
            "accounts": len(service.router.accounts),
            "open_positions": len(service.router.position_ledger.to_dict()),
            "startup_problems": startup_problems,
        }), (200 if len(startup_problems) == 0 else 503)

    @app.get("/ready")
    def ready():
        return jsonify({
            "ok": len(startup_problems) == 0,
            "ready_for_forward_paper": len(startup_problems) == 0,
            "startup_problems": startup_problems,
        }), (200 if len(startup_problems) == 0 else 503)

    @app.get("/status")
    def status():
        if status_secret:
            supplied = request.headers.get("X-Status-Secret", "")
            if supplied != status_secret:
                return jsonify({"ok": False, "error": "unauthorized"}), 401

        accounts = {}
        for aid, s in service.router.accounts.items():
            accounts[aid] = {
                "stage": s.stage.value,
                "balance": s.balance,
                "peak_realized_equity": s.peak_realized_equity,
                "reserved_open_risk": s.reserved_open_risk,
                "eod_drawdown_floor": s.eod_drawdown_floor,
                "max_contracts": s.max_contracts,
            }
        return jsonify({
            "ok": True,
            "accounts": accounts,
            "open_positions": service.router.position_ledger.to_dict(),
            "processed_signal_count": len(service.router.processed_signal_ids),
        })


    @app.post("/webhook/s1/<token>")
    def s1_webhook(token):
        # Protected ICT Uni emits plain-text alert() payloads and cannot embed
        # the Router JSON secret. Authenticate using a dedicated URL token.
        if not s1_token or token != s1_token:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        if s1_capture_journal is None:
            return jsonify({"ok": False, "error": "S1 capture journal not configured"}), 503
        try:
            raw_text = request.get_data(as_text=True)
            parsed = parse_s1_text(raw_text)
            row = s1_capture_journal.append(parsed, rpc_proxy=s1_rpc_proxy)
            preview = row["normalized_preview"]
            # Capture-only by design. We do NOT mutate Router state until an
            # execution-price source is defined for S1 entry and exit.
            return jsonify({
                "ok": True,
                "mode": "S1_CAPTURE_ONLY",
                "event_type": parsed.event_type,
                "source_id": parsed.source_id,
                "strategy": "S1",
                "symbol": preview["symbol"],
                "route_ready": preview["route_ready"],
                "route_block_reason": preview["route_block_reason"],
            }), 200
        except S1AdapterValidationError as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.post("/webhook")
    def webhook():
        if startup_problems:
            return jsonify({
                "ok": False,
                "error": "router not ready",
                "startup_problems": startup_problems
            }), 503

        try:
            payload = request.get_json(force=True, silent=False)
            result = service.handle_payload(payload)
            return jsonify(result), 200
        except WebhookAuthError as e:
            return jsonify({"ok": False, "error": str(e)}), 401
        except (WebhookValidationError, EventValidationError) as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 409

    return app
