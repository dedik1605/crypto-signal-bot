import requests
import time
import numpy as np

TOKEN = "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН"
CHAT_ID = "ВСТАВЬ_СЮДА_СВОЙ_CHAT_ID"

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DASHUSDT", "ZECUSDT"]

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

def get_klines(symbol, interval="15"):
    url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={symbol}&interval={interval}"
    r = requests.get(url).json()
    closes = [float(c[4]) for c in r["result"]["list"]]
    closes.reverse()
    return closes

def calc_rsi(data, period=14):
    deltas = np.diff(data)
    up = deltas.clip(min=0)
    down = -1 * deltas.clip(max=0)
    avg_gain = np.mean(up[:period])
    avg_loss = np.mean(down[:period])
    rsi_values = []
    for i in range(period, len(data)):
        avg_gain = (avg_gain * (period - 1) + up[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + down[i - 1]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)
    return rsi_values[-1]

def calc_ema(data, period):
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    a = np.convolve(data, weights, mode='full')[:len(data)]
    a[:period] = a[period]
    return a[-1]

def calc_macd(data):
    ema12 = calc_ema(data, 12)
    ema26 = calc_ema(data, 26)
    macd = ema12 - ema26
    return macd

while True:
    for sym in symbols:
        try:
            closes = get_klines(sym)
            rsi = calc_rsi(closes)
            macd = calc_macd(closes)
            ema = calc_ema(closes, 50)
            price = closes[-1]

            signal = None
            if rsi < 30 and price > ema and macd > 0:
                signal = f"🟢 LONG сигнал по {sym}\nRSI: {rsi:.2f}"
            elif rsi > 70 and price < ema and macd < 0:
                signal = f"🔴 SHORT сигнал по {sym}\nRSI: {rsi:.2f}"

            if signal:
                send_message(signal)

            time.sleep(3)
        except Exception as e:
            print(e)
            time.sleep(3)

    # проверка каждые 15 минут
    time.sleep(900)
