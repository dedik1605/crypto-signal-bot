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

# Create Flask app for health checks
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Crypto Signals Bot is running!"

@app.route('/health')
def health():
    return "✅ Bot is healthy!"

# ===== CONFIGURATION =====
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', 'your_bot_token_here')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', 'your_chat_id_here')

# Список монет для мониторинга
SYMBOLS = {
    'BTC': 'BTC/USDT:USDT',
    'ETH': 'ETH/USDT:USDT', 
    'SOL': 'SOL/USDT:USDT',
    'DASH': 'DASH/USDT:USDT',
    'ZEC': 'ZEC/USDT:USDT',
}

# Настройки индикаторов
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ===== TECHNICAL INDICATORS =====
def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    if len(prices) < period:
        return 50
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gains = pd.Series(gains).rolling(period).mean()
    avg_losses = pd.Series(losses).rolling(period).mean()
    
    # Avoid division by zero
    avg_losses = avg_losses.replace(0, 0.001)
    
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""
    if len(prices) < slow:
        return 0, 0, 0
    
    exp1 = pd.Series(prices).ewm(span=fast).mean()
    exp2 = pd.Series(prices).ewm(span=slow).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line
    
    macd_val = macd.iloc[-1] if not macd.empty else 0
    signal_val = signal_line.iloc[-1] if not signal_line.empty else 0
    hist_val = histogram.iloc[-1] if not histogram.empty else 0
    
    return macd_val, signal_val, hist_val

def calculate_ema(prices, period=20):
    """Calculate EMA indicator"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    return pd.Series(prices).ewm(span=period).mean().iloc[-1]

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return prices[-1], prices[-1], prices[-1]
    
    sma = pd.Series(prices).rolling(period).mean()
    std = pd.Series(prices).rolling(period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    
    upper = upper_band.iloc[-1] if not upper_band.empty else prices[-1]
    middle = sma.iloc[-1] if not sma.empty else prices[-1]
    lower = lower_band.iloc[-1] if not lower_band.empty else prices[-1]
    
    return upper, middle, lower

# ===== SIGNAL GENERATION =====
def generate_signal(symbol_data):
    """Generate trading signals based on multiple indicators"""
    prices = symbol_data['close']
    current_price = prices[-1] if prices else 0
    
    if len(prices) < 26:  # Minimum data required
        return {
            'symbol': symbol_data['symbol'],
            'price': current_price,
            'rsi': 50,
            'macd_histogram': 0,
            'ema_fast': current_price,
            'ema_slow': current_price,
            'upper_bb': current_price,
            'lower_bb': current_price,
            'signals': ["Insufficient data"],
            'final_signal': "⚪ INSUFFICIENT DATA",
            'signal_type': "NONE",
            'score': 0
        }
    
    # Calculate indicators
    rsi = calculate_rsi(prices)
    macd, macd_signal, macd_histogram = calculate_macd(prices)
    ema_fast = calculate_ema(prices, 12)
    ema_slow = calculate_ema(prices, 26)
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(prices)
    
    signals = []
    score = 0
    
    # RSI Signals
    if rsi < RSI_OVERSOLD:
        signals.append("📈 RSI OVERSOLD")
        score += 2
    elif rsi > RSI_OVERBOUGHT:
        signals.append("📉 RSI OVERBOUGHT") 
        score -= 2
    
    # MACD Signals
    if macd > macd_signal and macd_histogram > 0:
        signals.append("🟢 MACD BULLISH")
        score += 1
    elif macd < macd_signal and macd_histogram < 0:
        signals.append("🔴 MACD BEARISH")
        score -= 1
    
    # EMA Signals
    if ema_fast > ema_slow:
        signals.append("⬆️ EMA UPTREND")
        score += 1
    elif ema_fast < ema_slow:
        signals.append("⬇️ EMA DOWNTREND")
        score -= 1
    
    # Bollinger Bands Signals
    if current_price < lower_bb:
        signals.append("💰 PRICE NEAR LOWER BB")
        score += 1
    elif current_price > upper_bb:
        signals.append("💸 PRICE NEAR UPPER BB") 
        score -= 1
    
    # Determine final signal
    if score >= 3:
        final_signal = "🚀 STRONG LONG SIGNAL"
        signal_type = "LONG"
    elif score >= 2:
        final_signal = "🟢 LONG SIGNAL"
        signal_type = "LONG"
    elif score <= -3:
        final_signal = "🎯 STRONG SHORT SIGNAL" 
        signal_type = "SHORT"
    elif score <= -2:
        final_signal = "🔴 SHORT SIGNAL"
        signal_type = "SHORT"
    else:
        final_signal = "⚪ NO CLEAR SIGNAL"
        signal_type = "NONE"
    
    return {
        'symbol': symbol_data['symbol'],
        'price': current_price,
        'rsi': rsi,
        'macd_histogram': macd_histogram,
        'ema_fast': ema_fast,
        'ema_slow': ema_slow,
        'upper_bb': upper_bb,
        'lower_bb': lower_bb,
        'signals': signals,
        'final_signal': final_signal,
        'signal_type': signal_type,
        'score': score
    }

# ===== DATA FETCHING =====
def fetch_market_data():
    """Fetch current market data for all symbols"""
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'enableRateLimit': True,
    })
    
    market_data = {}
    
    for coin, symbol in SYMBOLS.items():
        try:
            # Fetch OHLCV data (1-hour timeframe, last 100 candles)
            ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['close'] = df['close'].astype(float)
            
            market_data[coin] = {
                'symbol': symbol,
                'close': df['close'].tolist(),
                'high': df['high'].max(),
                'low': df['low'].min()
            }
            
            time.sleep(0.2)  # Rate limit
                
        except Exception as e:
            print(f"Error fetching data for {coin}: {e}")
            # Return empty data to avoid crash
            market_data[coin] = {
                'symbol': symbol,
                'close': [],
                'high': 0,
                'low': 0
            }
    
    return market_data

# ===== TELEGRAM NOTIFICATIONS =====
async def send_telegram_message(message):
    """Send message to Telegram"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
        print(f"✅ Message sent: {message[:50]}...")
        return True
    except TelegramError as e:
        print(f"❌ Telegram error: {e}")
        return False

def format_signal_message(analysis):
    """Format analysis results into a nice message"""
    if analysis['signal_type'] == 'NONE':
        return None
    
    message = f"""
🚨 <b>{analysis['symbol']} TRADING SIGNAL</b> 🚨

💰 Price: <b>${analysis['price']:.2f}</b>
📊 Signal: <b>{analysis['final_signal']}</b>
🎯 Score: <b>{analysis['score']}/5</b>

<b>INDICATORS:</b>
📈 RSI: {analysis['rsi']:.1f}
📊 MACD Hist: {analysis['macd_histogram']:.4f}
📉 Fast EMA: {analysis['ema_fast']:.2f}
📈 Slow EMA: {analysis['ema_slow']:.2f}

<b>SIGNALS:</b>
"""
    for signal in analysis['signals']:
        message += f"• {signal}\n"
    
    message += f"\n⏰ Time: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}"
    message += f"\n🌐 Hosted on Render"
    
    return message

# ===== MAIN MONITORING LOOP =====
async def monitor_markets():
    """Main function to monitor markets and send signals"""
    print("🤖 Crypto Signals Bot Started on Render!")
    print("📊 Monitoring: BTC, ETH, SOL, DASH, ZEC")
    print("⏰ Interval: 5 minutes")
    
    # Track sent signals to avoid spam
    sent_signals = {}
    
    # Send startup message
    startup_msg = "🤖 <b>Crypto Auto Signals Bot Activated on Render!</b>\n\n"
    startup_msg += "📊 Monitoring: BTC, ETH, SOL, DASH, ZEC\n"
    startup_msg += "⏰ Interval: 5 minutes\n"
    startup_msg += "🚀 Bot is now running 24/7!"
    
    await send_telegram_message(startup_msg)
    
    error_count = 0
    max_errors = 5
    
    while True:
        try:
            print(f"\n🔍 Scanning markets... {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch market data
            market_data = fetch_market_data()
            signals_found = 0
            
            # Analyze each symbol
            for coin, data in market_data.items():
                if data['close']:
                    analysis = generate_signal(data)
                    
                    # Only send signal if it's strong enough and not recently sent
                    if analysis['signal_type'] != 'NONE':
                        signal_key = f"{coin}_{analysis['signal_type']}"
                        
                        # Check if we already sent similar signal recently (within 6 hours)
                        if signal_key not in sent_signals or time.time() - sent_signals[signal_key] > 21600:
                            
                            message = format_signal_message(analysis)
                            if message:
                                success = await send_telegram_message(message)
                                if success:
                                    sent_signals[signal_key] = time.time()
                                    signals_found += 1
                                    print(f"✅ Signal sent for {coin}: {analysis['final_signal']}")
            
            if signals_found == 0:
                print("✅ No strong signals detected this cycle")
            
            error_count = 0  # Reset error count on successful cycle
            
            # Wait 5 minutes before next scan
            print("💤 Waiting 5 minutes for next scan...")
            await asyncio.sleep(300)
            
        except Exception as e:
            error_count += 1
            print(f"❌ Error in main loop (attempt {error_count}/{max_errors}): {e}")
            
            if error_count >= max_errors:
                crash_msg = f"🚨 <b>Bot Crash Alert!</b>\nMultiple errors detected: {e}\nBot may need restart."
                await send_telegram_message(crash_msg)
                break
            
            await asyncio.sleep(60)  # Wait 1 minute before retrying

async def main():
    """Main async function"""
    await monitor_markets()

def run_bot():
    """Run the bot in asyncio"""
    asyncio.run(main())

# Start the bot when imported
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run Flask app in separate thread
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the bot
    print("🚀 Starting Crypto Signals Bot on Render...")
    run_bot()
