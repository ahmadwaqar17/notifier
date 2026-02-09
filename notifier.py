import os
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= CONFIG =================

WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

# ================= GOLD PRICE (STABLE SOURCE) =================
def get_gold_price_24k_pkr():
    """
    Uses metals.live (USD/oz) + open.er-api (USD→PKR)
    Fully works on GitHub Actions
    """
    try:
        now = datetime.now(PAKISTAN_TZ)
        print(f"[{now}] Fetching gold price (fallback source)")

        # Gold price per ounce (USD)
        gold_res = requests.get(
            "https://api.metals.live/v1/spot/gold",
            timeout=10
        )
        gold_res.raise_for_status()
        usd_per_ounce = gold_res.json()[0][1]

        # USD → PKR
        fx_res = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=10
        )
        fx_res.raise_for_status()
        usd_to_pkr = fx_res.json()["rates"]["PKR"]

        # Conversions
        OUNCE_TO_GRAM = 31.1035
        TOLA_TO_GRAM = 11.6638038

        price_pkr_tola = (
            usd_per_ounce / OUNCE_TO_GRAM
        ) * TOLA_TO_GRAM * usd_to_pkr

        return int(price_pkr_tola)

    except Exception as e:
        print(f"Gold price fetch failed: {e}")
        return None

# ================= WHATSAPP =================
def send_whatsapp_message(price):
    if not all([WHAPI_TOKEN, MY_WHATSAPP_NUMBER]):
        print("WhatsApp skipped: missing config")
        return

    number = MY_WHATSAPP_NUMBER.strip().replace(" ", "").replace("-", "")
    if number.startswith("+"):
        number = number[1:]
    elif number.startswith("03"):
        number = "92" + number[1:]

    now = datetime.now(PAKISTAN_TZ)

    body = (
        f"📊 *Gold Price Update (PKR)*\n"
        f"📅 {now.strftime('%d %b %Y')} | ⏰ {now.strftime('%I:%M %p')}\n\n"
        f"🟡 *24K Gold per Tola:* Rs. {price:,}\n"
        f"📍 Source: International Market"
    )

    requests.post(
        WHAPI_API_URL,
        json={"to": number, "body": body},
        headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
        timeout=15
    )

# ================= EMAIL =================
def send_email(price):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        print("Email skipped: missing config")
        return

    now = datetime.now(PAKISTAN_TZ)

    msg = EmailMessage()
    msg["Subject"] = f"Gold Price Update (PKR) - {now:%d %b %Y}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT

    msg.set_content(
        f"24K Gold per Tola: Rs. {price:,}\n"
        f"Date: {now:%d %b %Y %I:%M %p}\n"
        f"Source: International Market"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)

# ================= JOB =================
def job():
    price = get_gold_price_24k_pkr()

    if not price:
        print("Job skipped: gold price unavailable")
        return

    now = datetime.now(PAKISTAN_TZ)
    print("===================================")
    print(f"[{now}] 24K Gold per Tola: Rs. {price:,}")
    print("===================================")

    send_whatsapp_message(price)
    send_email(price)

if __name__ == "__main__":
    job()
