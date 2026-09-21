import os
import sys
import html
import time
import logging
from datetime import datetime, timezone, timedelta

import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
WAQI_TOKEN = os.environ.get("WAQI_TOKEN", "").strip()

for _name, _val in [("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
                    ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
                    ("WAQI_TOKEN", WAQI_TOKEN)]:
    if not _val:
        sys.exit(f"{_name} is empty: check the yml env block and the repo secret name")

# Add or remove locations here. Station IDs come from each aqicn page's "Cloud API" section.
LOCATIONS = [
    {"name": "Putrajaya",                "station_ids": ["@H10485", "putrajaya"]},
    {"name": "Kuantan (Indera Mahkota)", "station_ids": ["@H2592", "kuantan"]},
    {"name": "Singapore East",           "station_ids": ["@H1664"]},
]

MYT = timezone(timedelta(hours=8))


def to_number(value):
    """aqicn returns '-' when a value is missing; convert safely."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_aqi(station_ids):
    """Fetch current AQI from the aqicn (WAQI) API, trying each station ID in turn."""
    for station in station_ids:
        url = f"https://api.waqi.info/feed/{station}/"
        for attempt in range(1, 4):
            try:
                resp = requests.get(url, params={"token": WAQI_TOKEN}, timeout=20)
                logging.info(f"[{station}] attempt {attempt}: HTTP {resp.status_code}")
                resp.raise_for_status()
                payload = resp.json()

                if payload.get("status") != "ok":
                    logging.error(f"[{station}] API said: {payload}")
                    break  # no point retrying this station

                data = payload["data"]
                iaqi = data.get("iaqi", {})
                result = {
                    "aqi": to_number(data.get("aqi")),
                    "pm25": to_number(iaqi.get("pm25", {}).get("v")),
                    "pm10": to_number(iaqi.get("pm10", {}).get("v")),
                    "temp": to_number(iaqi.get("t", {}).get("v")),
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


def format_location(name, r):
    if not r:
        return f"📍 <b>{html.escape(name)}</b>\n⚠️ Could not fetch AQI"

    details = []
    if r["pm25"] is not None:
        details.append(f"PM2.5 {r['pm25']:.0f}")
    if r["pm10"] is not None:
        details.append(f"PM10 {r['pm10']:.0f}")
    if r["temp"] is not None:
        details.append(f"{r['temp']:.0f}°C")

    lines = [
        f"📍 <b>{html.escape(name)}</b>",
        f"📊 AQI <b>{r['aqi']:.0f}</b> · {get_category(r['aqi'])}",
    ]
    if details:
        lines.append(" · ".join(details))
    if r["updated"]:
        lines.append(f"🕐 {html.escape(r['updated'])}")
    return "\n".join(lines)


def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    logging.info("Message sent to Telegram!")


def main():
    now = datetime.now(MYT).strftime("%Y-%m-%d %H:%M")
    blocks = [f"🌤️ <b>AQI Update</b> · {now} MYT"]
    failed = 0

    for loc in LOCATIONS:
        logging.info(f"Fetching AQI for {loc['name']}...")
        r = get_aqi(loc["station_ids"])
        if not r:
            failed += 1
        blocks.append(format_location(loc["name"], r))

    message = "\n\n".join(blocks)

    try:
        send_to_telegram(message)
    except Exception as e:
        logging.error(f"Telegram error: {e}")
        sys.exit(1)

    if failed:
        sys.exit(1)  # makes the GitHub Action show red so you notice


if __name__ == "__main__":
    main()
