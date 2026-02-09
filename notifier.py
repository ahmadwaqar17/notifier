import os
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from lxml import html

# ================= CONFIG =================

# ---- WHAPI WhatsApp ----
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

# ---- Gmail ----
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= GOLD PRICE (SCRAPING) =================
def get_gold_price_24k_pkr():
    url = "https://abbasiandcompany.com/today-gold-rate-pakistan"
    xpath = '//*[@id="pkr2"]/div[1]'

    try:
        now = datetime.now(PAKISTAN_TZ)
        print(f"[{now}] Fetching gold price from Abbasi & Company")

        r = requests.get(url, timeout=15)
        r.raise_for_status()

        tree = html.fromstring(r.content)
        element = tree.xpath(xpath)

        if not element:
            raise ValueError("Gold price element not found")

        # Extract digits only (Rs. 214,500 → 214500)
        price_text = element[0].text_content()
        price = int("".join(filter(str.isdigit, price_text)))

        return price

    except Exception as e:
        print(f"Gold price scraping failed: {e}")
        return None

# ================= WHATSAPP =================
def send_whatsapp_message(price_24k):
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
        f"🟡 *24K Gold per Tola:* Rs. {price_24k:,}\n"
        f"📍 Source: Abbasi & Company"
    )

    payload = {
        "to": number,
        "body": body,
        "typing_time": 0
    }

    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(WHAPI_API_URL, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        print(f"[{now}] WhatsApp message sent")
    except Exception as e:
        print(f"WhatsApp error: {e}")

# ================= EMAIL =================
def send_email(price_24k):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        print("Email skipped: missing config")
        return

    now = datetime.now(PAKISTAN_TZ)

    msg = EmailMessage()
    msg["Subject"] = f"Gold Price Update (PKR) - {now.strftime('%d %b %Y')}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT

    text = (
        f"Gold Price Update\n\n"
        f"24K Gold per Tola: Rs. {price_24k:,}\n"
        f"Date: {now.strftime('%d %b %Y %I:%M %p')}\n"
        f"Source: Abbasi & Company"
    )

    msg.set_content(text)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            print(f"[{now}] Email sent")
    except Exception as e:
        print(f"Email error: {e}")

# ================= JOB =================
def job():
    price_24k = get_gold_price_24k_pkr()

    if not price_24k:
        print("Job skipped: gold price unavailable")
        return

    now = datetime.now(PAKISTAN_TZ)
    print("===================================")
    print(f"[{now}] 24K Gold per Tola: Rs. {price_24k:,}")
    print("===================================")

    send_whatsapp_message(price_24k)
    send_email(price_24k)

if __name__ == "__main__":
    job()
