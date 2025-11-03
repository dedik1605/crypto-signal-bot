import os
import time
import logging
import asyncio
import threading
from flask import Flask
import requests
import json

# Create Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>🤖 Crypto Signals Bot</h1>
    <p>Bot is running and monitoring markets 24/7</p>
    <p>Monitoring: BTC, ETH, SOL</p>
    <p>Check <a href="/health">/health</a> for status</p>
    """

@app.route('/health')
def health():
    return "✅ Healthy - " + time.strftime("%Y-%m-%d %H:%M:%S")

# ===== CONFIGURATION =====
TELEGRAM_BOT_TOKEN = os.environ.get('8343470341:AAHwY8NIaHgHLI2uPHnFQrf3m5F98KkQQBc')
TELEGRAM_CHAT_ID = os.environ.get('601403175')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("❌ Missing Telegram credentials")

SYMBOLS = {
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT', 
    'SOL': 'SOLUSDT',
}

# ===== SIMPLE TECHNICAL ANALYSIS =====
def calculate_rsi(prices, period=14):
    """Simple RSI calculation without pandas"""
    if len(prices) < period + 1:
        return 50
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_sma(prices, period):
    """Simple Moving Average"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    return sum(prices[-period:]) / period

def calculate_ema(prices, period):
    """Exponential Moving Average"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    
    ema = prices[0]
    multiplier = 2 / (period + 1)
    
    for price in prices[1:]:
        ema = (price - ema) * multiplier + ema
    
    return ema

# ===== DATA FETCHING =====
def fetch_binance_data(symbol):
    """Fetch data from Binance API"""
    try:
        url = f"https://api.binance.com/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': '1h',
            'limit': 100
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        closes = [float(candle[4]) for candle in data]  # Close prices
        return closes
    except Exception as e:
        print(f"❌ Error fetching {symbol}: {e}")
        return []

# ===== SIGNAL GENERATION =====
def analyze_symbol(symbol, prices):
    """Analyze symbol and generate signals"""
    if len(prices) < 26:
        return {'signal_type': "NONE", 'score': 0}
    
    current_price = prices[-1]
    
    # Calculate indicators
    rsi = calculate_rsi(prices)
    ema_fast = calculate_ema(prices, 12)
    ema_slow = calculate_ema(prices, 26)
    sma_20 = calculate_sma(prices, 20)
    
    signals = []
    score = 0
    
    # RSI Signals
    if rsi < 30:
        signals.append("RSI OVERSOLD")
        score += 2
    elif rsi > 70:
        signals.append("RSI OVERBOUGHT") 
        score -= 2
    
    # EMA Signals
    if ema_fast > ema_slow:
        signals.append("EMA UPTREND")
        score += 1
    elif ema_fast < ema_slow:
        signals.append("EMA DOWNTREND")
        score -= 1
    
    # Price vs SMA
    if current_price > sma_20 * 1.02:  # 2% above SMA
        signals.append("PRICE ABOVE SMA")
        score -= 1
    elif current_price < sma_20 * 0.98:  # 2% below SMA
        signals.append("PRICE BELOW SMA")
        score += 1
    
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
        'symbol': symbol,
        'price': current_price,
        'rsi': rsi,
        'signals': signals,
        'final_signal': final_signal,
        'signal_type': signal_type,
        'score': score
    }

# ===== TELEGRAM NOTIFICATIONS =====
async def send_telegram_message(message):
    """Send message to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram message sent")
            return True
        else:
            print(f"❌ Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

# ===== MAIN MONITORING LOOP =====
async def monitor_markets():
    """Main monitoring function"""
    print("🤖 Crypto Signals Bot Started on Render!")
    
    # Send startup message
    startup_msg = "🤖 <b>Crypto Signals Bot Activated!</b>\n\n"
    startup_msg += "📊 Monitoring: BTC, ETH, SOL\n"
    startup_msg += "⏰ Interval: 10 minutes\n"
    startup_msg += "🚀 Running on Render 24/7"
    
    await send_telegram_message(startup_msg)
    
    sent_signals = {}
    
    while True:
        try:
            print(f"🔍 Scanning markets... {time.strftime('%Y-%m-%d %H:%M:%S')}")
            signals_found = 0
            
            for coin, symbol in SYMBOLS.items():
                prices = fetch_binance_data(symbol)
                
                if prices:
                    analysis = analyze_symbol(coin, prices)
                    
                    if analysis['signal_type'] != 'NONE':
                        signal_key = f"{coin}_{analysis['signal_type']}"
                        
                        # Avoid spam - send same signal only once per 6 hours
                        if signal_key not in sent_signals or time.time() - sent_signals[signal_key] > 21600:
                            
                            message = f"""
🚨 <b>{analysis['symbol']} SIGNAL</b> 🚨

💰 Price: <b>${analysis['price']:.2f}</b>
📊 Signal: <b>{analysis['final_signal']}</b>
🎯 Score: <b>{analysis['score']}/4</b>

<b>INDICATORS:</b>
📈 RSI: {analysis['rsi']:.1f}

<b>SIGNALS:</b>
"""
                            for signal in analysis['signals']:
                                message += f"• {signal}\n"
                            
                            message += f"\n⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
                            message += f"\n🌐 Hosted on Render"
                            
                            success = await send_telegram_message(message)
                            if success:
                                sent_signals[signal_key] = time.time()
                                signals_found += 1
            
            if signals_found == 0:
                print("✅ No strong signals this cycle")
            
            # Wait 10 minutes before next scan
            print("💤 Waiting 10 minutes...")
            await asyncio.sleep(600)
            
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying

def run_bot():
    """Run the bot"""
    asyncio.run(monitor_markets())

def start_bot_background():
    """Start bot in background thread"""
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    print("🤖 Bot started in background")

# Start bot when app loads
start_bot_background()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
