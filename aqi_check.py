import requests
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
CITY               = os.environ.get("CITY", "Beijing")
COUNTRY            = os.environ.get("COUNTRY", "cn")


def get_aqi(city: str, country: str):
    url = "https://api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": 39.9 if city == "Beijing" else 34.05,
        "longitude": 116.4 if city == "Beijing" else -118.25,
        "current": "pm2_5",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["current"]["pm2_5"]
    except Exception as e:
        logging.error(f"Error: {e}")
        return None


def send_to_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info("Message sent!")
    except Exception as e:
        logging.error(f"Telegram error: {e}")


def main():
    now = datetime.now().strftime("%Y-%m-%d")
    pm25 = get_aqi(CITY, COUNTRY)

    if pm25 is not None:
        if pm25 <= 12:
            cat = "🟢 Good"
        elif pm25 <= 35.4:
            cat = "🟡 Moderate"
        elif pm25 <= 55.4:
            cat = "🟠 Unhealthy (Sensitive)"
        elif pm25 <= 150.4:
            cat = "🔴 Unhealthy"
        elif pm25 <= 250.4:
            cat = "🟣 Very Unhealthy"
        else:
            cat = "🟤 Hazardous"

        msg = f"🌅 <b>Morning AQI Report</b>\n📍 {CITY}\n📊 PM2.5: {pm25:.1f} µg/m³\n🏷️ {cat}\n🕐 {now}"
    else:
        msg = f"⚠️ Could not fetch AQI for {CITY} on {now}"

    send_to_telegram(msg)


if __name__ == "__main__":
    main()
