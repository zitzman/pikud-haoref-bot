import json
import logging
import os
import requests
import boto3
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALERTS_URL = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
SSM_PARAMETER_NAME = "/pikud-haoref-bot/last-alert-id"

REQUEST_HEADERS = {
    "Referer": "https://www.oref.org.il/",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Emoji by category (best-effort visual cue only)
CATEGORY_EMOJI = {
    "1": "🚀",
    "2": "🛸",
    "3": "🌍",
    "4": "☣️",
    "6": "⚠️",
    "7": "✈️",
    "13": "☢️",
    "101": "🔫",
}

# Translate the Hebrew title string the API returns — more reliable than category numbers.
# Substrings are matched so partial titles (e.g. with "- האירוע הסתיים" appended) still match.
TITLE_TRANSLATIONS = {
    "ירי רקטות וטילים": "Missile/Rocket Fire",
    "חדירת כלי טיס עויין": "UAV/Drone Intrusion",
    "חדירת כטב\"מ": "UAV/Drone Intrusion",
    "כלי טיס עויין": "Hostile Aircraft",
    "רעידת אדמה": "Earthquake",
    "חומרים מסוכנים": "Hazardous Materials",
    "צונאמי": "Tsunami",
    "נשק בלתי קונבנציונלי": "Unconventional Weapon",
    "חדירת מחבלים": "Terrorist Infiltration",
}

# English shelter instructions keyed by Hebrew desc substring
DESC_TRANSLATIONS = {
    "מרחב המוגן": "Enter a protected space and remain for 10 minutes.",
    "רעידת אדמה": "Move away from buildings, avoid elevators, and take cover under a sturdy table.",
    "חומרים מסוכנים": "Enter a building, close windows and doors, and await further instructions.",
    "צונאמי": "Move immediately to high ground or upper floors of a building.",
    "מחבלים": "Enter a building, lock doors, and await further instructions.",
}

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
    "ברנר": "Brenner",
    "ניר גלים": "Nir Galim",
    "פלמחים": "Palmachim",
    "בית אלעזרי": "Beit Elazari",
    "בית חלקיה": "Beit Halakiya",
    "בני ראם": "Bnei Ra'em",
    "גני טל": "Ganei Tal",
    "חפץ חיים": "Hafetz Hayyim",
    "יד בנימין": "Yad Binyamin",
    "כפר הנגיד": "Kfar HaNagid",
    "קדרון": "Kedron",
    "בית גמליאל": "Beit Gamliel",
    "בן זכאי": "Ben Zakai",
    "גבעת ברנר": "Givat Brenner",
    "כפר מרדכי": "Kfar Mordechai",
    "עשרת": "Aseret",
    "קבוצת יבנה": "Kvutzat Yavne",
}

ssm_client = boto3.client("ssm")


def fetch_active_alert() -> Optional[dict]:
    response = requests.get(ALERTS_URL, headers=REQUEST_HEADERS, timeout=10)
    decoded_content = response.content.decode("utf-8-sig").strip()
    if not decoded_content:
        return None
    try:
        return json.loads(decoded_content)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response from API (len=%d): %r", len(decoded_content), decoded_content[:120])
        return None


def translate_hebrew_field(hebrew_text: str, translations: dict) -> Optional[str]:
    """Return the English translation whose key appears as a substring of hebrew_text, or None."""
    for hebrew_key, english_value in translations.items():
        if hebrew_key in hebrew_text:
            return english_value
    return None


def format_slack_message(alert: dict) -> dict:
    category_id = str(alert.get("cat", "1"))
    hebrew_title = alert.get("title", "")
    hebrew_desc = alert.get("desc", "")

    emoji = CATEGORY_EMOJI.get(category_id, "⚠️")
    alert_title = translate_hebrew_field(hebrew_title, TITLE_TRANSLATIONS) or hebrew_title or "Alert"
    shelter_instruction = translate_hebrew_field(hebrew_desc, DESC_TRANSLATIONS) or ""

    logger.info("Formatting alert: cat=%s title=%r -> %r", category_id, hebrew_title, alert_title)

    hebrew_cities = alert.get("data", [])
    english_cities = [CITY_NAME_EN.get(city, city) for city in hebrew_cities]
    cities_text = " • ".join(english_cities) if english_cities else "Unknown location"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{emoji} {alert_title}", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Affected areas:*\n{cities_text}"},
        },
    ]

    if shelter_instruction:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Instructions:* {shelter_instruction}"},
            }
        )

    return {"blocks": blocks}


def post_to_slack(slack_message_payload: dict) -> None:
    response = requests.post(SLACK_WEBHOOK_URL, json=slack_message_payload, timeout=10)
    if response.status_code != 200:
        logger.error("Slack webhook returned %s: %s", response.status_code, response.text)
    else:
        logger.info("Alert posted to Slack successfully.")


def get_last_alert_id() -> str:
    try:
        response = ssm_client.get_parameter(Name=SSM_PARAMETER_NAME)
        return response["Parameter"]["Value"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "ParameterNotFound":
            return ""
        raise


def set_last_alert_id(alert_id: str) -> None:
    ssm_client.put_parameter(
        Name=SSM_PARAMETER_NAME,
        Value=alert_id,
        Type="String",
        Overwrite=True,
    )


def clear_last_alert_id() -> None:
    try:
        ssm_client.delete_parameter(Name=SSM_PARAMETER_NAME)
    except ClientError as error:
        if error.response["Error"]["Code"] != "ParameterNotFound":
            raise


def handler(event, context):
    try:
        active_alert = fetch_active_alert()
        last_alert_id = get_last_alert_id()

        if active_alert is None:
            if last_alert_id:
                logger.info("Alert cleared. Resetting dedup state.")
                clear_last_alert_id()
            return {"statusCode": 200, "body": "No active alert"}

        current_alert_id = str(active_alert.get("id", ""))
        if current_alert_id != last_alert_id:
            logger.info("New alert detected (id=%s): %s", current_alert_id, active_alert.get("title"))
            post_to_slack(format_slack_message(active_alert))
            set_last_alert_id(current_alert_id)
        else:
            logger.info("Alert id=%s already posted, skipping.", current_alert_id)

        return {"statusCode": 200, "body": "OK"}

    except Exception as unexpected_error:
        logger.error("Unexpected error: %s", unexpected_error, exc_info=True)
        raise
