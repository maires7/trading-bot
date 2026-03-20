import requests
import time
import yfinance as yf
import os

# --- KEYS ---
TELEGRAM_TOKEN = "8762235966:AAFPQBViUVDCClT7c3qA2qQQq3HQKKocx_A"
CHAT_ID = "6227906302"
FINNHUB_KEY = "d6uh4hhr01qp1k9ch0c0d6uh4hhr01qp1k9ch0cg"

# --- WATCHLIST ---
WATCHLIST = [
    "BTC-USD", "^VIX", "^IXIC", "^DJI", "^GSPC",
    "MSTR", "QQQ", "AMPX", "DGXX",
    "IREN", "WULF", "NBIS", "ORCL",
    "DJXXF", "QBTS", "IONQ", "RGTI",
    "AMZN", "MSFT", "NVDA", "IBM",
    "TSM", "TSLA", "APM", "RKLB",
    "ASTS", "OPEN"
]

# --- FILE TO STORE SEEN NEWS ---
SEEN_FILE = "seen_news.txt"

# --- LOAD SEEN NEWS ---
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen = set(f.read().splitlines())
else:
    seen = set()

# --- TELEGRAM ---
def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

# --- GET NEWS ---
def get_news(ticker):
    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from=2025-01-01&to=2026-12-31&token={FINNHUB_KEY}"
    try:
        return requests.get(url).json()
    except:
        return []

# --- CLASSIFIER (EXPANDED) ---
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

# --- PRICE CHANGE ---
def get_price_change(ticker):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d", interval="5m")

        if len(data) > 0:
            open_price = data["Open"][0]
            current_price = data["Close"][-1]
            change = ((current_price - open_price) / open_price) * 100
            return round(change, 2)
    except:
        return None

# --- RELEVANCE FILTER (FIXED) ---
def is_relevant(ticker, text):
    text = text.lower()

    names = {
        "AMZN": "amazon",
        "MSFT": "microsoft",
        "NVDA": "nvidia",
        "TSLA": "tesla",
        "META": "meta",
        "GOOGL": "google",
        "IBM": "ibm",
        "ORCL": "oracle",
        "TSM": "taiwan semiconductor",
        "MSTR": "microstrategy",
        "RKLB": "rocket lab",
        "ASTS": "ast spacemobile"
    }

    if ticker in names and names[ticker] in text:
        return True

    return False

# --- MAIN LOOP ---
while True:
    current_time = int(time.time())

    for ticker in WATCHLIST:
        news_list = get_news(ticker)

        for news in news_list:
            news_id = str(news.get("id", ""))

            if not news_id:
                continue

            if news_id in seen:
                continue

            # --- TIME FILTER (FIXED → 6 HOURS) ---
            news_time = news.get("datetime", 0)
            if current_time - news_time > 21600:
                continue

            # --- SAVE TO SEEN ---
            seen.add(news_id)
            with open(SEEN_FILE, "a") as f:
                f.write(news_id + "\n")

            headline = news.get("headline", "")
            summary = news.get("summary", "")
            url = news.get("url", "")

            full_text = headline + " " + summary

            # --- DEBUG (OPTIONAL) ---
            print(f"Checking: {ticker} - {headline}")

            # --- RELEVANCE ---
            if not is_relevant(ticker, full_text):
                continue

            # --- CLASSIFY ---
            category = classify_news(full_text)
            if not category:
                continue

            # --- PRICE ---
            price_change = get_price_change(ticker)

            # --- TRADE FILTER ---
            if category == "📉 NEGATIVE" and price_change is not None and price_change < -5:
                continue

            if category == "📈 POSITIVE" and price_change is not None and price_change > 5:
                continue

            # --- ALERT ---
            message = f"""
{category} NEWS

Ticker: {ticker}
Move: {price_change}%

{headline}

{url}
"""
            send_alert(message)

        time.sleep(1)

    time.sleep(60)
