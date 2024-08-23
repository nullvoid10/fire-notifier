import json
import logging
import os
import time
import typing

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

USER_AGENT = "https://github.com/nulldot0/fire-notifier"
SEARCH_TERM = os.environ.get("SEARCH_TERM", "")
DELAY = int(os.environ.get("DELAY", 30))  # Delay in seconds
JSON_DB_FILENAME = os.environ.get("JSON_DB_FILENAME", "fire_alerts.json")
JSON_DB_PATH = os.path.join("db", JSON_DB_FILENAME)
if not os.path.exists("db"):
    os.makedirs("db")

# Website: https://txtfire.net
# Source Data URL
TARGET_URL = "https://id.txtfire.net/qqq3"

# Alert Types
SECOND_ALARM = "2ND ALARM"
POSSITIVE_ALARM = "POSSITIVE ALARM"
GAS_STOVE_FIRE = "GAS STOVE FIRE"
FOURTH_ALARM = "4TH ALARM"
ELECTRICAL_FIRE = "ELECTRICAL FIRE"
VEHICULAR_FIRE = "VEHICULAR FIRE"
FIRE_UNDER_CONTROL = "FIRE UNDER CONTROL"
RUBBISH_FIRE = "RUBBISH FIRE"
CEILING_FIRE = "CEILING FIRE"
THIRD_ALARM = "3RD ALARM"
FOR_VERIFICATION = "FOR VERIFICATION"
VISIBLE_SMOKE = "VISIBLE SMOKE"
FALSE_ALARM = "FALSE ALARM"
FIRE_OUT = "FIRE OUT"
POSITIVE_ALARM = "POSITIVE ALARM"
NEGATIVE_ALARM = "NEGATIVE ALARM"
POST_FIRE = "POST FIRE"
FIRST_ALARM = "1ST ALARM"
KITCHEN_FIRE = "KITCHEN FIRE"

# Alarm Types that are considered dangerous
WARN_ALARMS = [
    SECOND_ALARM,
    POSSITIVE_ALARM,
    GAS_STOVE_FIRE,
    FOURTH_ALARM,
    ELECTRICAL_FIRE,
    VEHICULAR_FIRE,
    RUBBISH_FIRE,
    CEILING_FIRE,
    THIRD_ALARM,
    VISIBLE_SMOKE,
    POSITIVE_ALARM,
    POST_FIRE,
    FIRST_ALARM,
    KITCHEN_FIRE,
    FOR_VERIFICATION,  # Consider as dangerous
]

# Pushover API
# Handles sending push notifications to devices
# Docs: https://pushover.net/api
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN")
PUSHOVER_USER = os.environ.get("PUSHOVER_USER")
PUSHOVER_ENDPOINT = os.environ.get(
    "PUSHOVER_ENDPOINT", "https://api.pushover.net/1/messages.json"
)
assert PUSHOVER_TOKEN, "Please set PUSHOVER_TOKEN in .env"
assert PUSHOVER_USER, "Please set PUSHOVER_USER in .env"


def send_pushover_message(message: str) -> typing.Union[requests.Response, None]:
    url = PUSHOVER_ENDPOINT
    data = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "message": message,
        "sound": "alien",
        "priority": "2",
        "retry": "30",
        "expire": "3600",
        "ttl": "60",
    }

    try:
        response = requests.post(url, data=data)
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send pushover message! {e}")
        return None


def check_fire_alert_in_db(alert_data: dict) -> bool:
    if not os.path.exists(JSON_DB_PATH):
        return False

    with open(JSON_DB_PATH, "r") as f:
        data = json.load(f)

    for alert in data:
        if alert["alert_time"] == alert_data["alert_time"]:
            return True

    return False


def add_fire_alert_to_db(alert_data: dict) -> None:
    if not os.path.exists(JSON_DB_PATH):
        with open(JSON_DB_PATH, "w") as f:
            json.dump([alert_data], f, indent=4)
        return

    with open(JSON_DB_PATH, "r") as f:
        data = json.load(f)

    data.append(alert_data)

    with open(JSON_DB_PATH, "w") as f:
        json.dump(data, f, indent=4)


def clean_text(text: str) -> str:
    return text.strip().replace("\n", "").replace("\t", "").replace("\r", "")


def capitalize_per_word(text: str) -> str:
    return " ".join([word.capitalize() for word in text.split()])


def get_fire_alerts() -> typing.List[dict]:
    try:
        response = requests.get(TARGET_URL, headers={"User-Agent": USER_AGENT})
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to get response from {TARGET_URL}! {e}")
        return []

    if not response.ok:
        logger.warning(f"Failed to get response from {TARGET_URL}!")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    fire_alerts = soup.find_all("div", class_="cardfire")

    data = []
    for fire_alert in fire_alerts:
        fire_alert_info = clean_text(fire_alert.find_all("p")[0].text)
        fire_alert_info = fire_alert_info.replace("->", "")
        fire_alert_parts = fire_alert_info.split(":")
        alert_info = fire_alert_parts[0].strip()

        if len(fire_alert_parts) == 2:
            alert_info = fire_alert_parts[0].split("!")[1]
            alert_type = fire_alert_parts[1]

        fire_alert_time = clean_text(fire_alert.find_all("p")[1].text)
        fire_alert_time = fire_alert_time.split("As of ")[1]

        alert_info = alert_info.strip()
        alert_info = alert_info.replace("FIRE ALERT!", "")
        alert_type = alert_type.strip()
        alert_time = fire_alert_time.strip()

        data.append(
            {
                "alert_info": alert_info.upper(),
                "alert_type": alert_type.upper(),
                "alert_time": alert_time.upper(),
            }
        )

    return data


def break_down_search_term(search_term: str) -> typing.List[str]:
    search_terms = search_term.split(",")
    search_terms = [term.strip().capitalize() for term in search_terms]
    return search_terms


def fire_alert_match(search_term: str, alert_info: str) -> bool:
    search_terms = break_down_search_term(search_term)

    for term in search_terms:
        if term.lower() in alert_info.strip().lower():
            return True

    return False


def run_fire_alert():
    while True:
        time.sleep(DELAY)
        fire_alerts = get_fire_alerts()
        if not fire_alerts:
            logger.warning("No fire alerts found!")
            continue

        recent_fire_alert = fire_alerts[0]
        alert_type = recent_fire_alert["alert_type"]
        alert_info = recent_fire_alert["alert_info"]
        alert_time = recent_fire_alert["alert_time"]

        alert_type_clean = capitalize_per_word(alert_type)
        alert_info_clean = capitalize_per_word(alert_info)

        logger.info(
            f"Recent Fire Alert: {alert_type_clean} "
            f"from {alert_info_clean} on {alert_time}"
        )

        if not fire_alert_match(SEARCH_TERM, alert_info):
            search_terms = break_down_search_term(SEARCH_TERM)
            search_terms_readable = ", ".join(search_terms)
            if len(search_terms) > 1:
                logger.info(
                    f"Search terms `{search_terms_readable}` not found in {alert_info}!"
                )
                continue

            search_term = search_terms[0].capitalize()
            logger.info(f"Search term '{search_term}' not found in {alert_info}!")
            continue

        if alert_type not in WARN_ALARMS:
            logger.info(f"Alert type {alert_type_clean} is not dangerous!")
            continue

        if check_fire_alert_in_db(recent_fire_alert):
            logger.info(
                f"Alert {alert_type_clean} "
                f"from {alert_info_clean} on {alert_time} already sent!"
            )
            continue

        response = send_pushover_message(
            f"{alert_type_clean}\n{alert_info_clean}\n{alert_time}"
        )
        if response and response.ok:
            logger.info(
                f"Notified! {alert_type_clean} "
                f"from {alert_info_clean} on {alert_time}"
            )
            add_fire_alert_to_db(recent_fire_alert)
        else:
            logger.warning(f"Failed to send notification! {response.text}")


def main():
    logger.info("Starting Fire Alert Service!")
    logger.debug("=" * 70)
    logger.debug("Configurations")
    logger.debug(f"Search Term: {SEARCH_TERM}")
    logger.debug(f"Delay: {DELAY} seconds")
    logger.debug(f"JSON DB Path: {JSON_DB_PATH}")
    logger.debug(f"Target URL: {TARGET_URL}")
    logger.debug(f"Pushover Token: {PUSHOVER_TOKEN[:6]}...")
    logger.debug(f"Pushover User: {PUSHOVER_USER[:6]}...")
    logger.debug(f"Pushover Endpoint: {PUSHOVER_ENDPOINT}")
    logger.debug("=" * 70)

    run_fire_alert()


if __name__ == "__main__":
    main()
