import requests
import time

TOKEN = "8343470341:AAHwY8NIaHgHLI2uPHnFQrf3m5F98KkQQBc"
CHAT_ID = "601403175"

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

while True:
    # тут пока просто пример — бот каждые 10 секунд шлёт сообщение
    send_message("📈 Проверка связи, бот работает!")
    time.sleep(10)
