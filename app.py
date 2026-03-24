from flask import Flask, request, jsonify
from datetime import datetime, time
from zoneinfo import ZoneInfo

app = Flask(__name__)

# =============================
# CONFIG
# =============================

SECRET = "PassiveJabba126"

# TEST MODE OFF
ALLOW_ALL_HOURS = False

# Exact best-performing window
NY_TZ = ZoneInfo("America/New_York")
SESSION_START = time(9, 30)   # 9:30 AM ET
SESSION_END = time(12, 0)     # 12:00 PM ET

# =============================
# SESSION LOGIC
# =============================

def is_in_session():
    now_ny = datetime.now(NY_TZ).time()
    return SESSION_START <= now_ny <= SESSION_END

# =============================
# WEBHOOK ENDPOINT
# =============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"status": "error", "reason": "No data"}), 400

    if data.get("secret") != SECRET:
        return jsonify({"status": "rejected", "reason": "Invalid secret"}), 403

    if not ALLOW_ALL_HOURS and not is_in_session():
        return jsonify({
            "status": "rejected",
            "reason": "Outside allowed session"
        }), 400

    symbol = data.get("symbol")
    action = data.get("action")
    price = data.get("price")

    if not symbol or not action:
        return jsonify({
            "status": "error",
            "reason": "Missing fields"
        }), 400

    if action not in ["buy", "sell"]:
        return jsonify({
            "status": "error",
            "reason": "Invalid action"
        }), 400

    print(f"SIGNAL RECEIVED: {action.upper()} {symbol} @ {price}")

    return jsonify({
        "status": "accepted",
        "symbol": symbol,
        "action": action,
        "price": price
    }), 200

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
        "session_end": "12:00"
    })

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
# RUN SERVER
# =============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
