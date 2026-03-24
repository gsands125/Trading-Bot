import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

app = Flask(__name__)

# ==================================================
# CONFIG
# ==================================================
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
TIMEZONE = ZoneInfo("America/New_York")

MAX_CONTRACTS = 1
MAX_TRADES_PER_DAY = 3
MAX_LOSING_TRADES_PER_DAY = 2
DAILY_PROFIT_LOCK_R = 3.0

SESSION_START_HOUR = 9
SESSION_START_MINUTE = 30
SESSION_END_HOUR = 12
SESSION_END_MINUTE = 0

MNQ_DOLLARS_PER_POINT = 2.0
DEFAULT_RISK_PER_TRADE_DOLLARS = 100.0

# ==================================================
# IN-MEMORY STATE
# ==================================================
state = {
    "current_day": None,
    "trades_today": 0,
    "losing_trades_today": 0,
    "daily_realized_r": 0.0,
    "position_open": False,
    "position_side": None,
    "position_symbol": None,
    "position_entry_price": None,
    "position_contracts": 0,
    "position_opened_at": None,
}


# ==================================================
# HELPERS
# ==================================================
def now_et() -> datetime:
    return datetime.now(TIMEZONE)


def today_str() -> str:
    return now_et().date().isoformat()


def reset_daily_state_if_needed() -> None:
    today = today_str()
    if state["current_day"] != today:
        state["current_day"] = today
        state["trades_today"] = 0
        state["losing_trades_today"] = 0
        state["daily_realized_r"] = 0.0
        # Position state is intentionally NOT reset here.
        # If a position is open across midnight, keep it tracked.


def in_allowed_session() -> bool:
    current = now_et()
    start_minutes = SESSION_START_HOUR * 60 + SESSION_START_MINUTE
    end_minutes = SESSION_END_HOUR * 60 + SESSION_END_MINUTE
    current_minutes = current.hour * 60 + current.minute
    return start_minutes <= current_minutes < end_minutes


def daily_loss_lock_hit() -> bool:
    return state["losing_trades_today"] >= MAX_LOSING_TRADES_PER_DAY


def daily_profit_lock_hit() -> bool:
    return state["daily_realized_r"] >= DAILY_PROFIT_LOCK_R


def parse_price(value) -> float:
    if value is None:
        raise ValueError("Missing price")
    return float(value)


def calculate_contracts(price: float, stop: float, risk_amount: float) -> int:
    stop_distance_points = abs(price - stop)
    if stop_distance_points <= 0:
        return 1
    contracts = int(risk_amount / (stop_distance_points * MNQ_DOLLARS_PER_POINT))
    contracts = max(1, contracts)
    contracts = min(contracts, MAX_CONTRACTS)
    return contracts


def reject(reason: str, code: int = 400):
    return jsonify({"status": "rejected", "reason": reason}), code


def accept(payload: dict):
    return jsonify(payload), 200


# ==================================================
# ROUTES
# ==================================================
@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "service": "MNQ bot"}), 200


@app.route("/health", methods=["GET"])
def health():
    reset_daily_state_if_needed()
    return jsonify(
        {
            "status": "ok",
            "current_day": state["current_day"],
            "trades_today": state["trades_today"],
            "losing_trades_today": state["losing_trades_today"],
            "daily_realized_r": state["daily_realized_r"],
            "position_open": state["position_open"],
            "position_side": state["position_side"],
            "position_symbol": state["position_symbol"],
        }
    ), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    reset_daily_state_if_needed()

    data = request.get_json(silent=True)
    if not data:
        return reject("Invalid or missing JSON")

    secret = data.get("secret")
    symbol = data.get("symbol", "MNQ")
    action = str(data.get("action", "")).lower().strip()

    if secret != WEBHOOK_SECRET:
        return reject("Invalid secret", 401)

    if action not in {"buy", "sell"}:
        return reject("Invalid action. Must be 'buy' or 'sell'")

    if not in_allowed_session():
        return reject("Outside allowed session")

    if daily_loss_lock_hit():
        return reject("Daily loss lock hit")

    if daily_profit_lock_hit():
        return reject("Daily profit lock hit")

    if state["trades_today"] >= MAX_TRADES_PER_DAY:
        return reject("Max trades per day hit")

    if state["position_open"]:
        return reject("Position already open")

    try:
        price = parse_price(data.get("price"))
    except ValueError as exc:
        return reject(str(exc))

    # Optional fields from webhook
    stop = data.get("stop")
    risk_amount = float(data.get("risk_amount", DEFAULT_RISK_PER_TRADE_DOLLARS))

    if stop is not None:
        try:
            stop = float(stop)
        except ValueError:
            return reject("Invalid stop price")
        contracts = calculate_contracts(price=price, stop=stop, risk_amount=risk_amount)
    else:
        contracts = 1

    contracts = min(max(1, contracts), MAX_CONTRACTS)

    # Simulated execution / placeholder for broker execution
    # Replace this block later with real broker API logic.
    state["position_open"] = True
    state["position_side"] = "long" if action == "buy" else "short"
    state["position_symbol"] = symbol
    state["position_entry_price"] = price
    state["position_contracts"] = contracts
    state["position_opened_at"] = now_et().isoformat()
    state["trades_today"] += 1

    print(
        f"ALERT RECEIVED: {data} | EXECUTED: {action.upper()} "
        f"{contracts} {symbol} @ {price}"
    )

    return accept(
        {
            "status": "executed",
            "symbol": symbol,
            "action": action,
            "price": price,
            "contracts": contracts,
            "trades_today": state["trades_today"],
            "losing_trades_today": state["losing_trades_today"],
            "daily_realized_r": state["daily_realized_r"],
        }
    )


@app.route("/close_trade", methods=["POST"])
def close_trade():
    """
    Manual endpoint to close the currently tracked position and record outcome.
    Use this while paper testing until broker integration is added.

    Example JSON:
    {
      "secret": "your_secret",
      "exit_price": 23980.5,
      "result_r": 1.2
    }

    result_r:
      positive for winners, negative for losers, 0 for break-even
    """
    reset_daily_state_if_needed()

    data = request.get_json(silent=True)
    if not data:
        return reject("Invalid or missing JSON")

    if data.get("secret") != WEBHOOK_SECRET:
        return reject("Invalid secret", 401)

    if not state["position_open"]:
        return reject("No open position to close")

    exit_price = data.get("exit_price")
    result_r = data.get("result_r")

    if exit_price is None or result_r is None:
        return reject("exit_price and result_r are required")

    try:
        exit_price = float(exit_price)
        result_r = float(result_r)
    except ValueError:
        return reject("Invalid exit_price or result_r")

    closed_position = {
        "side": state["position_side"],
        "symbol": state["position_symbol"],
        "entry_price": state["position_entry_price"],
        "exit_price": exit_price,
        "contracts": state["position_contracts"],
        "opened_at": state["position_opened_at"],
        "closed_at": now_et().isoformat(),
        "result_r": result_r,
    }

    state["daily_realized_r"] += result_r
    if result_r < 0:
        state["losing_trades_today"] += 1

    state["position_open"] = False
    state["position_side"] = None
    state["position_symbol"] = None
    state["position_entry_price"] = None
    state["position_contracts"] = 0
    state["position_opened_at"] = None

    print(f"TRADE CLOSED: {closed_position}")

    return accept(
        {
            "status": "closed",
            "trade": closed_position,
            "trades_today": state["trades_today"],
            "losing_trades_today": state["losing_trades_today"],
            "daily_realized_r": state["daily_realized_r"],
            "daily_loss_lock_hit": daily_loss_lock_hit(),
            "daily_profit_lock_hit": daily_profit_lock_hit(),
        }
    )


@app.route("/force_flatten", methods=["POST"])
def force_flatten():
    """
    Emergency kill switch to flatten tracked state.
    This does NOT close a broker position unless you later wire it to a broker API.
    """
    data = request.get_json(silent=True)
    if not data:
        return reject("Invalid or missing JSON")

    if data.get("secret") != WEBHOOK_SECRET:
        return reject("Invalid secret", 401)

    state["position_open"] = False
    state["position_side"] = None
    state["position_symbol"] = None
    state["position_entry_price"] = None
    state["position_contracts"] = 0
    state["position_opened_at"] = None

    print("FORCE FLATTEN: position state cleared")

    return accept({"status": "flattened"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
