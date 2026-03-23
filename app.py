from flask import Flask, jsonify
import yfinance as yf
import pandas as pd
import time
import os

app = Flask(__name__)

TROY_OUNCE_TO_GRAM = 31.1035
IMPORT_DUTY_EFFECTIVE = 0.06
GST_RATE = 0.03
CHENNAI_PREMIUM_GOLD = 120.50
CHENNAI_PREMIUM_SILVER = 5.25

cache = {}
last_fetch = 0

def fetch_data(ticker):
    data = yf.download(ticker, period="3y", interval="1d", progress=False, auto_adjust=True)
    return data["Close"]

def get_rsi(prices, period=14):
    delta = prices.diff().dropna()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return (100 - (100 / (1 + rs))).iloc[-1]

def analyze(prices):
    returns = prices.pct_change()

    sma50 = prices.rolling(50).mean().iloc[-1]
    sma200 = prices.rolling(200).mean().iloc[-1]

    spikes = returns[returns > 0.05].count()
    drops = returns[returns < -0.05].count()

    ath = prices.max()
    current = prices.iloc[-1]
    drawdown = ((current - ath) / ath) * 100

    return sma50, sma200, spikes, drops, ath, drawdown

def local_price(usd, fx, metal):
    base = (usd * fx) / TROY_OUNCE_TO_GRAM
    base *= (1 + IMPORT_DUTY_EFFECTIVE)
    base *= (1 + GST_RATE)
    premium = CHENNAI_PREMIUM_GOLD if metal == "GOLD" else CHENNAI_PREMIUM_SILVER
    return base + premium

def strategy(prices, fx, metal):
    sma50, sma200, spikes, drops, ath, drawdown = analyze(prices)
    rsi = get_rsi(prices)

    price = local_price(prices.iloc[-1], fx, metal)

    if sma50 > sma200 and rsi < 40:
        signal = "⭐ STRONG BUY"
        advice = "Dip in bull trend. Accumulate."
    elif rsi > 70:
        signal = "🚨 SELL"
        advice = "Overbought. Correction likely."
    elif drawdown < -15 and rsi < 30:
        signal = "✅ BUY"
        advice = "Crash zone. High reward."
    else:
        signal = "➡️ WAIT"
        advice = "Sideways market."

    return {
        "price": round(price, 2),
        "ath": round(local_price(ath, fx, metal), 2),
        "drawdown": round(drawdown, 2),
        "spikes": int(spikes),
        "drops": int(drops),
        "rsi": round(rsi, 2),
        "signal": signal,
        "advice": advice
    }

def get_data():
    global cache, last_fetch

    if time.time() - last_fetch > 60:
        fx = fetch_data("USDINR=X")
        fx_rate = float(fx.iloc[-1])

        gold_prices = fetch_data("GC=F")
        silver_prices = fetch_data("SI=F")

        cache = {
            "gold": strategy(gold_prices, fx_rate, "GOLD"),
            "silver": strategy(silver_prices, fx_rate, "SILVER")
        }

        last_fetch = time.time()

    return cache

@app.route("/")
def home():
    return "API Running 🚀"

@app.route("/price")
def price():
    return jsonify(get_data())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
