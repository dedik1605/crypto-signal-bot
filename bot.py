import requests
import time
import pandas as pd
from datetime import datetime
from threading import Thread
from flask import Flask

# === TELEGRAM + BYBIT НАСТРОЙКИ ===
TELEGRAM_TOKEN = "8343470341:AAHwY8NIaHgHLI2uPHnFQrf3m5F98KkQQBc"
CHAT_ID = "601403175"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

BYBIT_API_URL = "https://api.bybit.com"
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# === САМ БОТ ===
def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, json=payload)

def get_klines(symbol, interval):
    url = f"{BYBIT_API_URL}/v5/market/kline?category=linear&symbol={symbol}&interval={interval}&limit=200"
    data = requests.get(url).json()
    df = pd.DataFrame(data['result']['list'], columns=['open_time','open','high','low','close','volume'])
    df = df.astype({'close':'float'})
    return df

def rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(df, short=12, long=26, signal=9):
    ema_short = df['close'].ewm(span=short, adjust=False).mean()
    ema_long = df['close'].ewm(span=long, adjust=False).mean()
    macd_line = ema_short - ema_long
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

def bot_worker():
    last_signal = None
    intervals = ["1", "5", "15", "30", "60", "240", "D"]
    while True:
        try:
            for symbol in SYMBOLS:
                for interval in intervals:
                    df = get_klines(symbol, interval)
                    df["RSI"] = rsi(df)
                    df["MACD"], df["SIGNAL"] = macd(df)
                    rsi_now = df["RSI"].iloc[-1]
                    macd_now = df["MACD"].iloc[-1]
                    signal_now = df["SIGNAL"].iloc[-1]

                    text = None
                    if rsi_now < RSI_OVERSOLD and macd_now > signal_now:
                        text = f"🟢 LONG {symbol} ({interval}) RSI={rsi_now:.2f}"
                    elif rsi_now > RSI_OVERBOUGHT and macd_now < signal_now:
                        text = f"🔴 SHORT {symbol} ({interval}) RSI={rsi_now:.2f}"

                    if text and text != last_signal:
                        send_message(f"{datetime.now().strftime('%H:%M:%S')} {text}")
                        last_signal = text

            time.sleep(60)
        except Exception as e:
            print("Ошибка:", e)
            time.sleep(10)

# === Flask-сервер для Render ===
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running OK 👌"

if __name__ == '__main__':
    t = Thread(target=bot_worker)
    t.start()
    app.run(host='0.0.0.0', port=10000)
