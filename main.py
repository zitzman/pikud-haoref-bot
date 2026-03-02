import os
import time
import json
import logging
import requests
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

ALERTS_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "2"))
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

REQUEST_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
}

CATEGORY_EMOJI = {
    "1": "🚀",
    "2": "🛸",
    "3": "🌍",
    "4": "☣️",
    "6": "🌊",
    "7": "✈️",
    "13": "☢️",
    "101": "🔫",
}

CATEGORY_TITLE_EN = {
    "1": "Missile/Rocket Fire",
    "2": "UAV/Drone Intrusion",
    "3": "Earthquake",
    "4": "Hazardous Materials",
    "6": "Tsunami",
    "7": "Hostile Aircraft",
    "13": "Nuclear Threat",
    "101": "Terrorist Infiltration",
}

CATEGORY_INSTRUCTION_EN = {
    "1": "Enter a protected space and remain for 10 minutes.",
    "2": "Enter a protected space and remain for 10 minutes.",
    "3": "Move away from buildings, avoid elevators, and take cover under a sturdy table.",
    "4": "Enter a building, close windows and doors, and await further instructions.",
    "6": "Move immediately to high ground or upper floors of a building.",
    "7": "Enter a protected space and remain until further notice.",
    "13": "Enter a building, close windows and doors, and await further instructions.",
    "101": "Enter a building, lock doors, and await further instructions.",
}

# Common Israeli city/area names: Hebrew → English
CITY_NAME_EN = {
    "אשקלון": "Ashkelon",
    "אשדוד": "Ashdod",
    "באר שבע": "Be'er Sheva",
    "תל אביב": "Tel Aviv",
    "ירושלים": "Jerusalem",
    "חיפה": "Haifa",
    "ראשון לציון": "Rishon LeZion",
    "פתח תקווה": "Petah Tikva",
    "נתניה": "Netanya",
    "רמת גן": "Ramat Gan",
    "בני ברק": "Bnei Brak",
    "הרצליה": "Herzliya",
    "חולון": "Holon",
    "בת ים": "Bat Yam",
    "רחובות": "Rehovot",
    "לוד": "Lod",
    "רמלה": "Ramla",
    "קריית גת": "Kiryat Gat",
    "קריית שמונה": "Kiryat Shmona",
    "נהריה": "Nahariya",
    "עכו": "Acre",
    "צפת": "Safed",
    "טבריה": "Tiberias",
    "אילת": "Eilat",
    "דימונה": "Dimona",
    "ערד": "Arad",
    "מודיעין": "Modi'in",
    "כפר סבא": "Kfar Saba",
    "רעננה": "Ra'anana",
    "הוד השרון": "Hod HaSharon",
    "רמת השרון": "Ramat HaSharon",
    "גבעתיים": "Givatayim",
    "קריית אונו": "Kiryat Ono",
    "אור יהודה": "Or Yehuda",
    "יהוד": "Yehud",
    "מזכרת בתיה": "Mazkeret Batya",
    "גדרה": "Gedera",
    "קריית מלאכי": "Kiryat Malakhi",
    "שדרות": "Sderot",
    "נתיבות": "Netivot",
    "אופקים": "Ofakim",
    "מגן": "Magen",
    "כפר עזה": "Kfar Aza",
    "נחל עוז": "Nahal Oz",
    "ניר עוז": "Nir Oz",
    "בארי": "Be'eri",
    "זיקים": "Zikim",
    "אשכול": "Eshkol",
    "שאר הנגב": "She'ar HaNegev",
    "חוף אשקלון": "Ashkelon Coast",
    "לכיש": "Lachish",
    "יואב": "Yo'av",
    "גן יבנה": "Gan Yavne",
    "יבנה": "Yavne",
    "גדרות": "Gedarot",
    "ברנר": "Brenner",
    "נען": "Na'an",
}

BACKOFF_INITIAL_SECONDS = 5
BACKOFF_MAX_SECONDS = 60


def fetch_active_alert() -> Optional[dict]:
    """Fetch the current alert from the Oref API. Returns parsed JSON or None if no active alert."""
    response = requests.get(ALERTS_URL, headers=REQUEST_HEADERS, timeout=10)
    decoded_content = response.content.decode("utf-8-sig").strip()
    if not decoded_content:
        return None
    return json.loads(decoded_content)


def format_slack_message(alert: dict) -> dict:
    """Build a Slack Block Kit payload from an alert dict."""
    category_id = str(alert.get("cat", "1"))
    emoji = CATEGORY_EMOJI.get(category_id, "⚠️")
    alert_title = CATEGORY_TITLE_EN.get(category_id, alert.get("title", "Alert"))
    shelter_instruction = CATEGORY_INSTRUCTION_EN.get(category_id, alert.get("desc", ""))

    hebrew_cities = alert.get("data", [])
    english_cities = [CITY_NAME_EN.get(city, city) for city in hebrew_cities]
    cities_text = " • ".join(english_cities) if english_cities else "Unknown location"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {alert_title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Affected areas:*\n{cities_text}",
            },
        },
    ]

    if shelter_instruction:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Instructions:* {shelter_instruction}",
                },
            }
        )

    return {"blocks": blocks}


def post_to_slack(slack_message_payload: dict) -> None:
    """POST a message payload to the configured Slack webhook."""
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json=slack_message_payload,
        timeout=10,
    )
    if response.status_code != 200:
        logger.error(
            "Slack webhook returned %s: %s",
            response.status_code,
            response.text,
        )
    else:
        logger.info("Alert posted to Slack successfully.")


def run_poll_loop() -> None:
    """Main polling loop. Runs indefinitely, posting new alerts to Slack."""
    logger.info("Monitoring for alerts... (polling every %ds)", POLL_INTERVAL)

    seen_alert_id: Optional[str] = None
    backoff_seconds = BACKOFF_INITIAL_SECONDS

    while True:
        try:
            alert = fetch_active_alert()

            if alert is None:
                # No active alert — reset dedup state so the next real alert always fires
                if seen_alert_id is not None:
                    logger.info("Alert cleared. Resetting dedup state.")
                    seen_alert_id = None
            else:
                current_alert_id = str(alert.get("id", ""))
                if current_alert_id != seen_alert_id:
                    logger.info(
                        "New alert detected (id=%s): %s",
                        current_alert_id,
                        alert.get("title"),
                    )
                    seen_alert_id = current_alert_id
                    slack_payload = format_slack_message(alert)
                    post_to_slack(slack_payload)
                else:
                    logger.debug("Alert id=%s already posted, skipping.", current_alert_id)

            # Successful poll — reset backoff
            backoff_seconds = BACKOFF_INITIAL_SECONDS
            time.sleep(POLL_INTERVAL)

        except requests.exceptions.ConnectionError as connection_error:
            logger.warning(
                "Connection error, retrying in %ds: %s",
                backoff_seconds,
                connection_error,
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, BACKOFF_MAX_SECONDS)

        except requests.exceptions.Timeout as timeout_error:
            logger.warning(
                "Request timed out, retrying in %ds: %s",
                backoff_seconds,
                timeout_error,
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, BACKOFF_MAX_SECONDS)

        except Exception as unexpected_error:
            logger.error(
                "Unexpected error, retrying in %ds: %s",
                backoff_seconds,
                unexpected_error,
                exc_info=True,
            )
            time.sleep(backoff_seconds)
            backoff_seconds = min(backoff_seconds * 2, BACKOFF_MAX_SECONDS)


if __name__ == "__main__":
    run_poll_loop()
