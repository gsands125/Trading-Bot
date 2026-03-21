from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)

    print("🔥 ALERT RECEIVED:", data)

    # ---- DATA ----
    symbol = data.get("symbol")
    action = data.get("action")
    price = float(data.get("price"))
    confidence = int(data.get("confidence", 5))

    # ---- SESSION FILTER ----
    hour = datetime.utcnow().hour

    if hour < 13 or hour >= 16:
        return jsonify({"status": "outside session"}), 200

    # ---- TRADE QUALITY FILTER ----
    if confidence < 7:
        return jsonify({"status": "low quality trade"}), 200

    # ---- RISK SETTINGS ----
    ACCOUNT_SIZE = 10000
    RISK_PER_TRADE = 0.01
    MNQ_TICK_VALUE = 2

    # ---- STOP LOGIC ----
    if action == "BUY":
        stop = price - 20
    else:
        stop = price + 20

    # ---- POSITION SIZE ----
    risk_amount = ACCOUNT_SIZE * RISK_PER_TRADE
    stop_distance = abs(price - stop)

    if stop_distance == 0:
        contracts = 1
    else:
        contracts = int(risk_amount / (stop_distance * MNQ_TICK_VALUE))

    contracts = max(1, contracts)

    print(f"{action} {contracts} {symbol} @ {price}")
    print(f"Stop: {stop}")

    return jsonify({
        "status": "executed",
        "contracts": contracts
    }), 200
