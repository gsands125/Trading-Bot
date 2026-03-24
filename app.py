from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

# =============================
# CONFIG
# =============================

SECRET = "PassiveJabba126"

# 🔥 TURN THIS ON FOR TESTING
ALLOW_ALL_HOURS = True

# =============================
# SESSION LOGIC
# =============================

def is_in_session():
    now = datetime.utcnow()
    hour = now.hour
    return 13 <= hour <= 21  # NY session (UTC)

# =============================
# WEBHOOK ENDPOINT
# =============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "reason": "No data"}), 400

    # =============================
    # AUTH CHECK
    # =============================
    if data.get("secret") != SECRET:
        return jsonify({"status": "rejected", "reason": "Invalid secret"}), 403

    # =============================
    # SESSION FILTER
    # =============================
    if not ALLOW_ALL_HOURS and not is_in_session():
        return jsonify({
            "status": "rejected",
            "reason": "Outside allowed session"
        }), 400

    # =============================
    # PARSE SIGNAL
    # =============================
    symbol = data.get("symbol")
    action = data.get("action")
    price = data.get("price")

    if not symbol or not action:
        return jsonify({
            "status": "error",
            "reason": "Missing fields"
        }), 400

    # =============================
    # SIMULATED TRADE EXECUTION
    # =============================
    print(f"📥 SIGNAL RECEIVED: {action.upper()} {symbol} @ {price}")

    # Here is where you will later connect to broker

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
        "status": "ok"
    })

# =============================
# RUN SERVER
# =============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
