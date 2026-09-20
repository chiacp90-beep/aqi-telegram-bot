import os
import sys
import html
import time
import logging
from datetime import datetime, timezone, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
WAQI_TOKEN = os.environ["WAQI_TOKEN"]

# Putrajaya station on aqicn.org (Malaysia DOE). Fallback: search by city name.
STATION_CANDIDATES = ["@H10485", "putrajaya"]

MYT = timezone(timedelta(hours=8))


def to_number(value):
    """aqicn returns '-' when a value is missing; convert safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_aqi():
    """Fetch current AQI for Putrajaya from the aqicn (WAQI) API."""
    for station in STATION_CANDIDATES:
        url = f"https://api.waqi.info/feed/{station}/"
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, params={"token": WAQI_TOKEN}, timeout=20)
                logging.info(f"[{station}] attempt {attempt}: HTTP {resp.status_code}")
                resp.raise_for_status()
                payload = resp.json()

                if payload.get("status") != "ok":
                    # e.g. {"status":"error","data":"Invalid key"} or "Unknown station"
                    logging.error(f"[{station}] API said: {payload}")
                    break  # no point retrying this station

                data = payload["data"]
                iaqi = data.get("iaqi", {})
                result = {
                    "aqi": to_number(data.get("aqi")),
                    "pm25": to_number(iaqi.get("pm25", {}).get("v")),
                    "pm10": to_number(iaqi.get("pm10", {}).get("v")),
                    "temp": to_number(iaqi.get("t", {}).get("v")),
                    "station": data.get("city", {}).get("name", "Putrajaya"),
                    "updated": data.get("time", {}).get("s", ""),
                }
                if result["aqi"] is None:
                    logging.error(f"[{station}] no AQI value in response: {payload}")
                    break
                logging.info(f"[{station}] OK: {result}")
                return result

            except requests.exceptions.RequestException as e:
                logging.error(f"[{station}] request failed: {e}")
                time.sleep(3)
            except Exception as e:
                logging.error(f"[{station}] unexpected error: {e}")
                break
    return None


def get_category(aqi):
    """US EPA AQI categories (aqicn values are on this scale)."""
    if aqi <= 50:
        return "🟢 Good"
    elif aqi <= 100:
        return "🟡 Moderate"
    elif aqi <= 150:
        return "🟠 Unhealthy for Sensitive Groups"
    elif aqi <= 200:
        return "🔴 Unhealthy"
    elif aqi <= 300:
        return "🟣 Very Unhealthy"
    else:
        return "🟤 Hazardous"


def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    logging.info("Message sent to Telegram!")


def main():
    today = datetime.now(MYT).strftime("%Y-%m-%d")
    logging.info("Fetching AQI for Putrajaya...")
    r = get_aqi()

    if r:
        lines = [
            "🌅 <b>Morning AQI Report</b>",
            f"📍 <b>{html.escape(r['station'])}</b>",
            f"📊 <b>Overall AQI:</b> {r['aqi']:.0f}",
            f"🏷️ <b>{get_category(r['aqi'])}</b>",
        ]
        if r["pm25"] is not None:
            lines.append(f"🌫️ PM2.5 AQI: {r['pm25']:.0f}")
        if r["pm10"] is not None:
            lines.append(f"💨 PM10 AQI: {r['pm10']:.0f}")
        if r["temp"] is not None:
            lines.append(f"🌡️ Temp: {r['temp']:.0f}°C")
        if r["updated"]:
            lines.append(f"🕐 Station update: {html.escape(r['updated'])}")
        else:
            lines.append(f"🕐 {today}")
        msg = "\n".join(lines)
    else:
        msg = f"⚠️ Could not fetch AQI for Putrajaya on {today}"

    try:
        send_to_telegram(msg)
    except Exception as e:
        logging.error(f"Telegram error: {e}")
        sys.exit(1)

    if not r:
        sys.exit(1)  # makes the GitHub Action show red so you notice


if __name__ == "__main__":
    main()
