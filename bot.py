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
    "MSTR","QQQ","AMPX","DGXX",
    "IREN","WULF","NBIS","ORCL",
    "QBTS","IONQ","RGTI",
    "AMZN","MSFT","NVDA","IBM",
    "TSM","TSLA","RKLB",
    "ASTS","OPEN"
]

# --- FILES ---
SEEN_FILE = "seen_news.txt"
SPIKE_FILE = "seen_spikes.txt"

# --- LOAD SEEN ---
def load_seen(file):
    if os.path.exists(file):
        with open(file,"r") as f:
            return set(f.read().splitlines())
    return set()

seen = load_seen(SEEN_FILE)
seen_spikes = load_seen(SPIKE_FILE)

# --- TELEGRAM ---
def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url,data={"chat_id":CHAT_ID,"text":message})

# --- API ---
def finnhub_get(endpoint,params=None):
    url=f"https://finnhub.io/api/v1/{endpoint}"
    params=params or {}
    params["token"]=FINNHUB_KEY

    try:
        res=requests.get(url,params=params,timeout=10)
        if res.status_code!=200:
            return None
        return res.json()
    except:
        return None

# --- COMPANY NEWS ---
def get_news(ticker):
    return finnhub_get(
        "company-news",
        {
            "symbol":ticker,
            "from":"2025-01-01",
            "to":"2026-12-31"
        }
    ) or []

# --- RELEVANCE ---
def is_relevant(ticker,text):

    text=text.lower()

    names={
        "RKLB":["rocket lab","rocketlab"],
        "NVDA":["nvidia"],
        "TSLA":["tesla"],
        "AMZN":["amazon"],
        "MSFT":["microsoft"],
        "ORCL":["oracle"],
        "TSM":["tsmc","taiwan semiconductor"],
        "ASTS":["ast spacemobile"],
        "MSTR":["microstrategy"],
    }

    # ticker symbol
    if ticker.lower() in text:
        return True

    # company name
    if ticker in names:
        for name in names[ticker]:
            if name in text:
                return True

    return False

# --- CLASSIFIER ---
def classify_news(text):

    text=text.lower()

    if any(k in text for k in [
        "offering","dilution","bankruptcy",
        "acquisition","merger","guidance",
        "lawsuit","investigation"
    ]):
        return "🚨 IMPORTANT"

    if any(k in text for k in [
        "beats","growth","partnership",
        "contract","record","launch",
        "expansion","ai","deal"
    ]):
        return "📈 POSITIVE"

    if any(k in text for k in [
        "misses","decline","loss",
        "downgrade","cuts","layoffs"
    ]):
        return "📉 NEGATIVE"

    return "📰 NEWS"

# --- SPIKE DETECTION ---
def get_spike(ticker):

    try:
        stock=yf.Ticker(ticker)
        data=stock.history(period="1d",interval="5m")

        if len(data)<10:
            return None

        last_close=data["Close"][-1]
        prev_close=data["Close"][-2]

        change=((last_close-prev_close)/prev_close)*100

        avg_volume=data["Volume"].mean()
        last_volume=data["Volume"][-1]

        if abs(change)>2 and last_volume>avg_volume*3:
            return round(change,2)

    except:
        return None

    return None

# --- MAIN LOOP ---
while True:

    now=int(time.time())

    for ticker in WATCHLIST:

        # ----- PRICE SPIKE -----
        spike=get_spike(ticker)

        if spike:

            spike_id=f"{ticker}_{round(time.time()/300)}"

            if spike_id not in seen_spikes:

                seen_spikes.add(spike_id)

                with open(SPIKE_FILE,"a") as f:
                    f.write(spike_id+"\n")

                direction="📈 SPIKE UP" if spike>0 else "📉 SPIKE DOWN"

                send_alert(
                    f"{direction} | {ticker}\n"
                    f"5m move: {spike}%"
                )

        # ----- NEWS -----
        news_list=get_news(ticker)

        for news in news_list:

            nid=str(news.get("id",""))

            if not nid or nid in seen:
                continue

            news_time=news.get("datetime",0)

            # ignore old news
            if now-news_time>21600:
                continue

            headline=news.get("headline","")
            summary=news.get("summary","")
            url=news.get("url","")

            text=headline+" "+summary

            if not is_relevant(ticker,text):
                continue

            seen.add(nid)

            with open(SEEN_FILE,"a") as f:
                f.write(nid+"\n")

            category=classify_news(text)

            send_alert(
                f"{category} | {ticker}\n"
                f"{headline}\n"
                f"{url}"
            )

        time.sleep(1)

    time.sleep(30)
