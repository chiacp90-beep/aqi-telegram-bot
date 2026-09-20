import requests
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# Beijing coordinates
LAT = 39.9042
LON = 116.4074


def get_aqi():
    """Fetch PM2.5 using Open-Meteo Air Quality API."""
    url = "https://api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "current_air_quality": "true",   # ← String "true", not Python True!
        "timezone": "Asia/Shanghai",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Debug: print raw response to see the structure
        logging.info(f"Raw response keys: {data.keys()}")

        air_quality = data.get("current_air_quality", {})
        pm25 = air_quality.get("pm2_5")
        return pm25

    except requests.exceptions.RequestException as e:
        logging.error(f"API request failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return None


def get_category(pm25):
    if pm25 is None:
        return "❓ Unavailable"
    elif pm25 <= 12:
        return "🟢 Good"
    elif pm25 <= 35.4:
        return "🟡 Moderate"
    elif pm25 <= 55.4:
        return "🟠 Unhealthy (Sensitive)"
    elif pm25 <= 150.4:
        return "🔴 Unhealthy"
    elif pm25 <= 250.4:
        return "🟣 Very Unhealthy"
    else:
        return "🟤 Hazardous"


def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info("Message sent to Telegram!")
    except Exception as e:
        logging.error(f"Telegram error: {e}")


def main():
    now = datetime.now().strftime("%Y-%m-%d")
    logging.info("Fetching AQI for Beijing...")
    pm25 = get_aqi()

    if pm25 is not None:
        category = get_category(pm25)
        msg = (
            f"🌅 <b>Morning AQI Report</b>\n"
            f"📍 <b>Beijing</b>\n"
            f"📊 <b>PM2.5:</b> {pm25:.1f} µg/m³\n"
            f"🏷️ <b>{category}</b>\n"
            f"🕐 <b>{now}</b>"
        )
    else:
        msg = f"⚠️ Could not fetch AQI for Beijing on {now}"

    send_to_telegram(msg)


if __name__ == "__main__":
    main()
