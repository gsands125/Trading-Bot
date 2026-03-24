from flask import Flask, request, jsonify
from datetime import datetime, time
from zoneinfo import ZoneInfo

app = Flask(__name__)

# =============================
# CONFIG
# =============================

SECRET = "PassiveJabba126"
ALLOW_ALL_HOURS = False

NY_TZ = ZoneInfo("America/New_York")
SESSION_START = time(9, 30)   # 9:30 AM ET
SESSION_END = time(12, 0)     # 12:00 PM ET

# =============================
# SIMPLE POSITION STATE
# =============================

position_open = False
open_position = {
    "symbol": None,
    "side": None,        # "long" or "short"
    "entry_price": None,
    "opened_at": None
}

last_closed_position = {
    "symbol": None,
    "side": None,
    "entry_price": None,
    "exit_price": None,
    "opened_at": None,
    "closed_at": None
}

# =============================
# SESSION LOGIC
# =============================

def is_in_session():
    now_ny = datetime.now(NY_TZ).time()
    return SESSION_START <= now_ny <= SESSION_END

# =============================
# HOME
# =============================

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "service": "MNQ bot",
        "status": "ok"
    })

# =============================
# HEALTH CHECK
# =============================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "MNQ bot",
        "status": "ok",
        "test_mode": ALLOW_ALL_HOURS,
        "session_timezone": "America/New_York",
        "session_start": "09:30",
        "session_end": "12:00",
        "position_open": position_open,
        "open_position": open_position,
        "last_closed_position": last_closed_position
    })

# =============================
# WEBHOOK ENDPOINT
# =============================

@app.route("/webhook", methods=["POST"])
def webhook():
    global position_open, open_position, last_closed_position

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "error", "reason": "No data"}), 400

    if data.get("secret") != SECRET:
        return jsonify({"status": "rejected", "reason": "Invalid secret"}), 403

    symbol = data.get("symbol")
    action = data.get("action")
    price = data.get("price")

    if not symbol or not action:
        return jsonify({
            "status": "error",
            "reason": "Missing fields"
        }), 400

    if action not in ["buy", "sell", "close_long", "close_short"]:
        return jsonify({
            "status": "error",
            "reason": "Invalid action"
        }), 400

    # -----------------------------
    # ENTRY SIGNALS
    # -----------------------------
    if action in ["buy", "sell"]:
        if not ALLOW_ALL_HOURS and not is_in_session():
            return jsonify({
                "status": "rejected",
                "reason": "Outside allowed session"
            }), 400

        if position_open:
            return jsonify({
                "status": "rejected",
                "reason": "Position already open",
                "open_position": open_position
            }), 400

        side = "long" if action == "buy" else "short"

        position_open = True
        open_position = {
            "symbol": symbol,
            "side": side,
            "entry_price": price,
            "opened_at": datetime.now(NY_TZ).isoformat()
        }

        print(f"ENTRY ACCEPTED: {side.upper()} {symbol} @ {price}")

        return jsonify({
            "status": "accepted",
            "type": "entry",
            "symbol": symbol,
            "side": side,
            "price": price,
            "position_open": position_open,
            "open_position": open_position
        }), 200

    # -----------------------------
    # EXIT SIGNALS
    # -----------------------------
    if action in ["close_long", "close_short"]:
        exit_side = "long" if action == "close_long" else "short"

        if not position_open:
            return jsonify({
                "status": "ignored",
                "reason": "No open position to close"
            }), 200

        if open_position["side"] != exit_side:
            return jsonify({
                "status": "ignored",
                "reason": "Exit side does not match open position",
                "open_position": open_position
            }), 200

        last_closed_position = {
            "symbol": open_position["symbol"],
            "side": open_position["side"],
            "entry_price": open_position["entry_price"],
            "exit_price": price,
            "opened_at": open_position["opened_at"],
            "closed_at": datetime.now(NY_TZ).isoformat()
        }

        print(f"EXIT ACCEPTED: {exit_side.upper()} {symbol} @ {price}")

        position_open = False
        open_position = {
            "symbol": None,
            "side": None,
            "entry_price": None,
            "opened_at": None
        }

        return jsonify({
            "status": "accepted",
            "type": "exit",
            "symbol": symbol,
            "side": exit_side,
            "price": price,
            "position_open": position_open,
            "last_closed_position": last_closed_position
        }), 200

    return jsonify({"status": "error", "reason": "Unhandled action"}), 400

# =============================
# RUN SERVER
# =============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
