@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)

    print("🔥 ALERT RECEIVED:", data)

    symbol = data.get("symbol")
    action = data.get("action")
    price = float(data.get("price"))

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

    print(f"📊 {action} {contracts} {symbol} @ {price}")
    print(f"🛑 Stop: {stop}")

    return jsonify({
        "status": "executed",
        "contracts": contracts
    }), 200