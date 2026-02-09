import os
import time
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from lxml import html

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= CONFIG =================

WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

# ================= SOURCE 1: ABBASI (BLOCKED ON GHA) =================
def get_gold_price_abbasi():
    url = "https://abbasiandcompany.com/today-gold-rate-pakistan"
    xpath = '//*[@id="pkr2"]/div[1]'

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()

        tree = html.fromstring(r.content)
        el = tree.xpath(xpath)

        if not el:
            return None

        price_text = el[0].text_content()
        return int("".join(filter(str.isdigit, price_text)))

    except Exception:
        return None

# ================= SOURCE 2: FALLBACK (WORKS ON GHA) =================
def get_gold_price_fallback():
    """
    Uses international gold price and converts to PKR (approx).
    Reliable on GitHub Actions.
    """
    try:
        # Gold price per ounce (USD)
        gold = requests.get(
            "https://data-asg.goldprice.org/dbXRates/USD",
            timeout=10
        ).json()

        usd_per_ounce = gold["items"][0]["xauPrice"]

        # USD → PKR
        usd_pkr = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=10
        ).json()["rates"]["PKR"]

        # 1 tola = 11.6638038 grams
        # 1 ounce = 31.1035 grams
        tola_price = (usd_per_ounce / 31.1035) * 11.6638038 * usd_pkr

        return int(tola_price)

    except Exception:
        return None

# ================= MASTER PRICE FETCH =================
def get_gold_price_24k_pkr():
    now = datetime.now(PAKISTAN_TZ)
    print(f"[{now}] Fetching gold price")

    price = get_gold_price_abbasi()
    if price:
        print("✔ Source: Abbasi & Company")
        return price

    print("⚠ Abbasi blocked — using fallback source")
    price = get_gold_price_fallback()

    if price:
        print("✔ Source: International fallback")
        return price

    return None

# ================= WHATSAPP =================
def send_whatsapp_message(price):
    if not all([WHAPI_TOKEN, MY_WHATSAPP_NUMBER]):
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
        f"🟡 *24K Gold per Tola:* Rs. {price:,}"
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
        return

    now = datetime.now(PAKISTAN_TZ)

    msg = EmailMessage()
    msg["Subject"] = f"Gold Price Update - {now:%d %b %Y}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT
    msg.set_content(f"24K Gold per Tola: Rs. {price:,}")

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        s.send_message(msg)

# ================= JOB =================
def job():
    price = get_gold_price_24k_pkr()

    if not price:
        print("Job skipped: gold price unavailable")
        return

    print(f"24K Gold per Tola: Rs. {price:,}")
    send_whatsapp_message(price)
    send_email(price)

if __name__ == "__main__":
    job()
