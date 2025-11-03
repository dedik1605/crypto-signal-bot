import os
import time
import requests
import schedule
from threading import Thread
from flask import Flask

app = Flask(__name__)

# Конфигурация
TELEGRAM_BOT_TOKEN = os.environ.get('8343470341:AAHwY8NIaHgHLI2uPHnFQrf3m5F98KkQQBc')
TELEGRAM_CHAT_ID = os.environ.get('601403175')

@app.route('/')
def home():
    return "🤖 Crypto Bot WORKING!"

@app.route('/health')
def health():
    return f"✅ OK - {time.strftime('%H:%M:%S')}"

def send_telegram(msg):
    """Отправка сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': msg,
            'parse_mode': 'HTML'
        }
        requests.post(url, data=data, timeout=10)
        print(f"✅ Sent: {msg[:50]}...")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

def check_market():
    """Проверка рынка и отправка сигнала"""
    try:
        # Простая проверка цены BTC
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        response = requests.get(url, timeout=10)
        data = response.json()
        price = float(data['price'])
        
        # Простой сигнал на основе цены
        if price > 50000:
            signal = "🔴 SHORT - Price high"
        elif price < 40000:
            signal = "🟢 LONG - Price low"
        else:
            signal = "⚪ HOLD - Neutral"
        
        message = f"""
🚨 <b>BTC Signal</b>
💰 Price: ${price:,.2f}
📊 {signal}
⏰ {time.strftime('%H:%M:%S')}
        """
        
        send_telegram(message)
        
    except Exception as e:
        print(f"❌ Market error: {e}")
        send_telegram(f"❌ Bot error: {e}")

def run_scheduler():
    """Запуск планировщика"""
    # Проверка каждые 10 минут
    schedule.every(10).minutes.do(check_market)
    
    # Первая проверка через 10 секунд после старта
    time.sleep(10)
    check_market()
    
    print("🕐 Scheduler started - checking every 10 minutes")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# Запуск при старте приложения
send_telegram("🚀 <b>Bot STARTED on Render!</b>")
print("🤖 Bot initialized!")

# Запуск планировщика в отдельном потоке
scheduler_thread = Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
