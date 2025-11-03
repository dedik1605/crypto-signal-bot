import ccxt
import pandas as pd
import numpy as np
import asyncio
import time
import logging
import os
from telegram import Bot
from telegram.error import TelegramError
from flask import Flask
import threading

# Create Flask app for health checks
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🤖 Crypto Signals Bot</h1>
    <p>Bot is running and monitoring markets 24/7</p>
    <p>Monitoring: BTC, ETH, SOL, DASH, ZEC</p>
    <p>Check <a href="/health">/health</a> for status</p>
    """

@app.route('/health')
def health():
    return "✅ Healthy - " + time.strftime("%Y-%m-%d %H:%M:%S")

# ===== CONFIGURATION =====
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Validate required environment variables
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables")

SYMBOLS = {
    'BTC': 'BTC/USDT:USDT',
    'ETH': 'ETH/USDT:USDT', 
    'SOL': 'SOL/USDT:USDT',
    'DASH': 'DASH/USDT:USDT',
    'ZEC': 'ZEC/USDT:USDT',
}

# ===== TECHNICAL INDICATORS =====
def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return 50
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gains = pd.Series(gains).rolling(period).mean()
    avg_losses = pd.Series(losses).rolling(period).mean()
    avg_losses = avg_losses.replace(0, 0.001)
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50

def calculate_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow:
        return 0, 0, 0
    exp1 = pd.Series(prices).ewm(span=fast).mean()
    exp2 = pd.Series(prices).ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    return macd.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def calculate_ema(prices, period=20):
    if len(prices) < period:
        return prices[-1] if prices else 0
    return pd.Series(prices).ewm(span=period).mean().iloc[-1]

# ===== SIGNAL GENERATION =====
def generate_signal(symbol_data):
    prices = symbol_data['close']
    current_price = prices[-1] if prices else 0
    
    if len(prices) < 26:
        return {'signal_type': "NONE", 'score': 0}
    
    rsi = calculate_rsi(prices)
    macd, macd_signal, macd_histogram = calculate_macd(prices)
    ema_fast = calculate_ema(prices, 12)
    ema_slow = calculate_ema(prices, 26)
    
    signals = []
    score = 0
    
    # RSI Signals
    if rsi < 30:
        signals.append("RSI OVERSOLD")
        score += 2
    elif rsi > 70:
        signals.append("RSI OVERBOUGHT") 
        score -= 2
    
    # MACD Signals
    if macd > macd_signal and macd_histogram > 0:
        signals.append("MACD BULLISH")
        score += 1
    elif macd < macd_signal and macd_histogram < 0:
        signals.append("MACD BEARISH")
        score -= 1
    
    # EMA Signals
    if ema_fast > ema_slow:
        signals.append("EMA UPTREND")
        score += 1
    elif ema_fast < ema_slow:
        signals.append("EMA DOWNTREND")
        score -= 1
    
    # Determine final signal
    if score >= 3:
        final_signal = "🚀 STRONG LONG"
        signal_type = "LONG"
    elif score >= 2:
        final_signal = "🟢 LONG"
        signal_type = "LONG"
    elif score <= -3:
        final_signal = "🎯 STRONG SHORT" 
        signal_type = "SHORT"
    elif score <= -2:
        final_signal = "🔴 SHORT"
        signal_type = "SHORT"
    else:
        final_signal = "⚪ NO SIGNAL"
        signal_type = "NONE"
    
    return {
        'symbol': symbol_data['symbol'],
        'price': current_price,
        'rsi': rsi,
        'signals': signals,
        'final_signal': final_signal,
        'signal_type': signal_type,
        'score': score
    }

# ===== DATA FETCHING =====
def fetch_market_data():
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'enableRateLimit': True,
    })
    
    market_data = {}
    for coin, symbol in SYMBOLS.items():
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['close'] = df['close'].astype(float)
            
            market_data[coin] = {
                'symbol': symbol,
                'close': df['close'].tolist(),
            }
            time.sleep(0.2)
        except Exception as e:
            print(f"Error fetching {coin}: {e}")
            market_data[coin] = {'symbol': symbol, 'close': []}
    
    return market_data

# ===== TELEGRAM NOTIFICATIONS =====
async def send_telegram_message(message):
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
        print(f"✅ Message sent")
        return True
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

# ===== MAIN MONITORING LOOP =====
async def monitor_markets():
    print("🤖 Crypto Signals Bot Started!")
    
    # Send startup message
    startup_msg = "🤖 <b>Bot Activated on Render!</b>\nMonitoring: BTC, ETH, SOL, DASH, ZEC\nInterval: 5 min"
    await send_telegram_message(startup_msg)
    
    sent_signals = {}
    
    while True:
        try:
            print(f"🔍 Scanning... {time.strftime('%H:%M:%S')}")
            market_data = fetch_market_data()
            signals_found = 0
            
            for coin, data in market_data.items():
                if data['close']:
                    analysis = generate_signal(data)
                    
                    if analysis['signal_type'] != 'NONE':
                        signal_key = f"{coin}_{analysis['signal_type']}"
                        
                        if signal_key not in sent_signals or time.time() - sent_signals[signal_key] > 21600:
                            message = f"""
🚨 <b>{analysis['symbol']} SIGNAL</b>
💰 Price: ${analysis['price']:.2f}
📊 {analysis['final_signal']}
🎯 Score: {analysis['score']}/4
📈 RSI: {analysis['rsi']:.1f}
⏰ {time.strftime('%H:%M:%S')}
                            """
                            success = await send_telegram_message(message)
                            if success:
                                sent_signals[signal_key] = time.time()
                                signals_found += 1
            
            print(f"✅ Cycle complete. Signals found: {signals_found}")
            await asyncio.sleep(300)  # 5 minutes
            
        except Exception as e:
            print(f"❌ Error: {e}")
            await asyncio.sleep(60)

def run_bot():
    asyncio.run(monitor_markets())

def start_background_bot():
    """Start bot in background thread"""
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🤖 Bot started in background thread")

# Start bot when module loads
start_background_bot()

# For Gunicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
