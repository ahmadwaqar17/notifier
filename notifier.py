import os
import requests
import smtplib
import asyncio
import nest_asyncio
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

nest_asyncio.apply()

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= CONFIG =================

WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

URL = "https://abbasiandcompany.com/today-gold-rate-pakistan"
XPATH_24K = "/html/body/div/section/div/div/div/div/div/div[2]/div[2]/div[1]/div/div[1]/div[1]"

# ================= PRIMARY SOURCE (ABBASI) =================
async def get_gold_price_abbasi():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            await page.goto(URL, timeout=60000)
            await page.wait_for_selector(f"xpath={XPATH_24K}", timeout=20000)

            text = await page.locator(f"xpath={XPATH_24K}").text_content()
            await browser.close()

            # Extract numeric PKR value
            price = int(
                "".join(c for c in text if c.isdigit())
            )
            return price

    except Exception as e:
        print(f"⚠ Abbasi blocked — {e}")
        return None

# ================= FALLBACK SOURCE =================
def get_gold_price_fallback():
    try:
        now = datetime.now(PAKISTAN_TZ)
        print(f"[{now}] Fetching gold price (fallback)")

        gold_res = requests.get(
            "https://api.metals.live/v1/spot/gold",
            timeout=10
        )
        gold_res.raise_for_status()
        usd_per_ounce = gold_res.json()[0][1]

        fx_res = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=10
        )
        fx_res.raise_for_status()
        usd_to_pkr = fx_res.json()["rates"]["PKR"]

        OUNCE_TO_GRAM = 31.1035
        TOLA_TO_GRAM = 11.6638038

        price_pkr_tola = (
            usd_per_ounce / OUNCE_TO_GRAM
        ) * TOLA_TO_GRAM * usd_to_pkr

        return int(price_pkr_tola)

    except Exception as e:
        print(f"Fallback failed: {e}")
        return None

# ================= WHATSAPP =================
def send_whatsapp(price, source):
    if not all([WHAPI_TOKEN, MY_WHATSAPP_NUMBER]):
        return

    number = MY_WHATSAPP_NUMBER.replace("+", "").replace("-", "").replace(" ", "")
    if number.startswith("03"):
        number = "92" + number[1:]

    now = datetime.now(PAKISTAN_TZ)

    body = (
        f"📊 *Gold Price Update (PKR)*\n"
        f"📅 {now:%d %b %Y} | ⏰ {now:%I:%M %p}\n\n"
        f"🟡 *24K Gold per Tola:* Rs. {price:,}\n"
        f"📍 Source: {source}"
    )

    requests.post(
        WHAPI_API_URL,
        headers={"Authorization": f"Bearer {WHAPI_TOKEN}"},
        json={"to": number, "body": body},
        timeout=15
    )

# ================= EMAIL =================
def send_email(price, source):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        return

    now = datetime.now(PAKISTAN_TZ)

    msg = EmailMessage()
    msg["Subject"] = f"Gold Price Update – {now:%d %b %Y}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT

    msg.set_content(
        f"24K Gold per Tola: Rs. {price:,}\n"
        f"Date: {now:%d %b %Y %I:%M %p}\n"
        f"Source: {source}"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)

# ================= JOB =================
def job():
    now = datetime.now(PAKISTAN_TZ)
    print(f"[{now}] Fetching gold price")

    price = asyncio.run(get_gold_price_abbasi())
    source = "Abbasi & Company"

    if not price:
        price = get_gold_price_fallback()
        source = "International Market"

    if not price:
        print("❌ Job skipped: gold price unavailable")
        return

    print(f"✅ 24K Gold per Tola: Rs. {price:,} ({source})")

    send_whatsapp(price, source)
    send_email(price, source)

if __name__ == "__main__":
    job()
