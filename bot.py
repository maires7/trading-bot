import requests
import time
import yfinance as yf
import os
from datetime import datetime
import pytz

# --- KEYS ---
TELEGRAM_TOKEN = "8762235966:AAFPQBViUVDCClT7c3qA2qQQq3HQKKocx_A"
CHAT_ID = "6227906302"
FINNHUB_KEY = "d6uh4hhr01qp1k9ch0c0d6uh4hhr01qp1k9ch0cg"

# --- WATCHLIST ---
WATCHLIST = [
    "MSTR", "QQQ", "AMPX", "DGXX",
    "IREN", "WULF", "NBIS", "ORCL",
    "QBTS", "IONQ", "RGTI",
    "AMZN", "MSFT", "NVDA", "IBM",
    "TSM", "TSLA", "RKLB",
    "ASTS", "OPEN"
]

# --- FILES ---
SEEN_FILE = "seen_news.txt"
MACRO_FILE = "seen_macro.txt"
SPIKE_FILE = "seen_spikes.txt"

# --- LOAD SEEN ---
def load_seen(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return set(f.read().splitlines())
    return set()

seen = load_seen(SEEN_FILE)
seen_macro = load_seen(MACRO_FILE)
seen_spikes = load_seen(SPIKE_FILE)

# --- TELEGRAM ---
def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# --- TIME ---
def is_premarket():
    ny = pytz.timezone("US/Eastern")
    now = datetime.now(ny)
    return (4 <= now.hour < 9) or (now.hour == 9 and now.minute < 30)

# --- API ---
def finnhub_get(endpoint, params=None):
    url = f"https://finnhub.io/api/v1/{endpoint}"
    params = params or {}
    params["token"] = FINNHUB_KEY

    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return None
        return res.json()
    except:
        return None

# --- NEWS ---
def get_news(ticker):
    return finnhub_get("company-news", {
        "symbol": ticker,
        "from": "2025-01-01",
        "to": "2026-12-31"
    }) or []

def get_macro_news():
    return finnhub_get("news", {"category": "merger"}) or []

# --- SENTIMENT ---
def get_sentiment(ticker):
    data = finnhub_get("news-sentiment", {"symbol": ticker})
    if not data:
        return None

    sentiment = data.get("sentiment", {})
    bullish = sentiment.get("bullishPercent", 0)
    bearish = sentiment.get("bearishPercent", 0)

    return round(bullish - bearish, 2)

# --- CLASSIFIER ---
def classify_news(text):
    text = text.lower()

    if any(k in text for k in [
        "offering", "dilution", "bankruptcy",
        "acquisition", "merger", "guidance",
        "lawsuit", "investigation"
    ]):
        return "🚨 VERY IMPORTANT"

    if any(k in text for k in [
        "beats", "growth", "partnership",
        "contract", "record", "launch",
        "expansion", "ai", "deal"
    ]):
        return "📈 POSITIVE"

    if any(k in text for k in [
        "misses", "decline", "loss",
        "downgrade", "cuts", "layoffs"
    ]):
        return "📉 NEGATIVE"

    return None

# --- RELEVANCE ---
def is_relevant(ticker, text):
    text = text.lower()

    names = {
        "AMZN": "amazon",
        "MSFT": "microsoft",
        "NVDA": "nvidia",
        "TSLA": "tesla",
        "IBM": "ibm",
        "ORCL": "oracle",
        "TSM": "taiwan semiconductor",
        "MSTR": "microstrategy",
        "RKLB": "rocket lab",
        "ASTS": "ast spacemobile"
    }

    return ticker in names and names[ticker] in text

# --- PRICE ---
def get_price_change(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="5m")
        if len(data) > 0:
            open_price = data["Open"][0]
            current_price = data["Close"][-1]
            return round(((current_price - open_price) / open_price) * 100, 2)
    except:
        return None

# --- SPIKE DETECTION ---
def get_spike(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="5m")

        if len(data) < 10:
            return None

        last_close = data["Close"][-1]
        prev_close = data["Close"][-2]
        change = ((last_close - prev_close) / prev_close) * 100

        avg_volume = data["Volume"].mean()
        last_volume = data["Volume"][-1]

        if abs(change) > 2 and last_volume > avg_volume * 3:
            return round(change, 2)

    except:
        return None

    return None

# --- MAIN LOOP ---
while True:
    now = int(time.time())

    # 🌍 MACRO NEWS
    for article in get_macro_news():
        aid = str(article.get("id", ""))
        if not aid or aid in seen_macro:
            continue

        seen_macro.add(aid)
        with open(MACRO_FILE, "a") as f:
            f.write(aid + "\n")

        headline = article.get("headline", "")
        url = article.get("url", "")

        tag = "🌍 PRE-MARKET MACRO" if is_premarket() else "🌍 MARKET NEWS"
        send_alert(f"{tag}\n\n{headline}\n\n{url}")

    time.sleep(2)

    # 🎯 WATCHLIST
    for ticker in WATCHLIST:

        # --- SPIKE FIRST ---
        spike = get_spike(ticker)

        if spike:
            spike_id = f"{ticker}_{round(time.time()/300)}"

            if spike_id not in seen_spikes:
                seen_spikes.add(spike_id)
                with open(SPIKE_FILE, "a") as f:
                    f.write(spike_id + "\n")

                direction = "📈 SPIKE UP" if spike > 0 else "📉 SPIKE DOWN"

                send_alert(f"""
⚡ {direction}

Ticker: {ticker}
5m Move: {spike}%

Unusual price + volume activity
""")

        # --- NEWS ---
        news_list = get_news(ticker)

        for news in news_list:
            nid = str(news.get("id", ""))
            if not nid or nid in seen:
                continue

            news_time = news.get("datetime", 0)
            if now - news_time > 21600:
                continue

            seen.add(nid)
            with open(SEEN_FILE, "a") as f:
                f.write(nid + "\n")

            headline = news.get("headline", "")
            summary = news.get("summary", "")
            url = news.get("url", "")
            text = headline + " " + summary

            if not is_relevant(ticker, text):
                continue

            category = classify_news(text)
            if not category:
                continue

            price = get_price_change(ticker)
            sentiment = get_sentiment(ticker)

            # --- SCORE ---
            score = "C"
            if sentiment and sentiment > 20:
                score = "A+"
            elif sentiment and sentiment > 5:
                score = "B"

            if score == "C":
                continue  # remove low-quality noise

            tag = "🚨 PRE-MARKET" if is_premarket() else category

            send_alert(f"""
{tag} | Score: {score}

{ticker} | {price}% | Sent: {sentiment}

{headline}

{url}
""")

        time.sleep(1)

    time.sleep(30)
