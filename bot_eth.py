import requests
import time
import csv
import os
from datetime import datetime

# ===== CONFIG =====
API_URL = "https://api.coingecko.com/api/v3/simple/price"
SYMBOL = "ethereum"
VS_CURRENCY = "usd"

CHECK_INTERVAL = 30
HISTORY_SIZE = 10
FEE = 0.001
START_USD_BALANCE = 1000.0

CSV_FILE = "bot_history.csv"
TRADES_LOG_FILE = "trades_log.txt"

# ===== TELEGRAM =====
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"


# ===== TELEGRAM FUNCTION =====
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": text
    }

    try:
        response = requests.post(url, data=data, timeout=10)
       
        response.raise_for_status()
    except Exception as e:
        print(f"Telegram error: {e}")


# ===== CSV INIT =====
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "timestamp",
                "price",
                "change_percent",
                "action",
                "reason",
                "usd_balance",
                "eth_balance",
                "total_balance",
                "profit"
            ])


# ===== LOGGING =====
def log_csv(timestamp, price, change_percent, action, reason,
            usd_balance, eth_balance, total_balance, profit):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            timestamp,
            round(price, 2),
            round(change_percent, 4),
            action,
            reason,
            round(usd_balance, 2),
            round(eth_balance, 6),
            round(total_balance, 2),
            round(profit, 2)
        ])


def log_trade(timestamp, action, price, amount, usd_balance, eth_balance, reason, profit=None):
    with open(TRADES_LOG_FILE, "a", encoding="utf-8") as file:
        line = (
            f"[{timestamp}] {action} | "
            f"price={price:.2f} | "
            f"amount={amount:.6f} ETH | "
            f"usd_balance={usd_balance:.2f} | "
            f"eth_balance={eth_balance:.6f} | "
            f"reason={reason}"
        )

        if profit is not None:
            line += f" | profit={profit:.2f} USD"

        file.write(line + "\n")


# ===== API =====
def get_eth_price():
    params = {
        "ids": SYMBOL,
        "vs_currencies": VS_CURRENCY
    }

    response = requests.get(API_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    return data[SYMBOL][VS_CURRENCY]


# ===== STRATEGY =====
def analyze_market(price_history, usd_balance, eth_balance):
    if len(price_history) < 2:
        return "WAIT", "NOT_ENOUGH_DATA", 0.0

    current_price = price_history[-1]
    previous_price = price_history[-2]

    change_percent = ((current_price - previous_price) / previous_price) * 100

    local_min = min(price_history)
    local_max = max(price_history)
    range_value = local_max - local_min

    if range_value <= 0:
        return "WAIT", "FLAT_RANGE", change_percent

    position_in_range = (current_price - local_min) / range_value

    if position_in_range <= 0.2 and usd_balance > 0:
        return "BUY", "LOW_RANGE", change_percent

    if position_in_range >= 0.8 and eth_balance > 0:
        return "SELL", "HIGH_RANGE", change_percent

    return "WAIT", "NO_SIGNAL", change_percent


# ===== MAIN =====
def main():
    init_csv()
    send_telegram_message("Bot started in group 🚀")

    usd_balance = START_USD_BALANCE
    eth_balance = 0.0
    start_balance = START_USD_BALANCE

    price_history = []

    print("ETH Telegram bot started...")

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            price = get_eth_price()

            price_history.append(price)
            if len(price_history) > HISTORY_SIZE:
                price_history.pop(0)

            action, reason, change_percent = analyze_market(
                price_history,
                usd_balance,
                eth_balance
            )
            

            if action == "BUY" and usd_balance > 0:
                
                usd_to_spend = usd_balance
                eth_bought = (usd_to_spend * (1 - FEE)) / price

                eth_balance += eth_bought
                usd_balance = 0.0

                log_trade(timestamp, "BUY", price, eth_bought,
                          usd_balance, eth_balance, reason)

               
                send_telegram_message(
                    f"🟢 BUY SIGNAL\n"
                    f"Price: {price:.2f} USD\n"
                    f"Reason: {reason}\n"
                    f"USD Balance: {usd_balance:.2f}\n"
                    f"Time: {timestamp}"
                )

            elif action == "SELL" and eth_balance > 0:
               
                eth_to_sell = eth_balance
                usd_received = (eth_to_sell * price) * (1 - FEE)

                eth_balance = 0.0
                usd_balance += usd_received

                total_balance = usd_balance + eth_balance * price
                profit = total_balance - start_balance

                log_trade(timestamp, "SELL", price, eth_to_sell,
                          usd_balance, eth_balance, reason, profit)

               
                send_telegram_message(
                    f"🔴 SELL SIGNAL\n"
                    f"Price: {price:.2f} USD\n"
                    f"Profit: {profit:.2f} USD\n"
                    f"Reason: {reason}\n"
                    f"Time: {timestamp}"
                )

            total_balance = usd_balance + eth_balance * price
            profit = total_balance - start_balance

            log_csv(timestamp, price, change_percent, action, reason,
                    usd_balance, eth_balance, total_balance, profit)

            print(
                f"{timestamp} | {price:.2f} | {action} | {reason} | profit={profit:.2f}"
            )

        except Exception as e:
            print(f"{timestamp} | ERROR: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        send_telegram_message("Bot stopped ❌")
        print("Bot stopped")
   