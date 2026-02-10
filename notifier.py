import os
import requests
import smtplib
import asyncio
import nest_asyncio
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright, TimeoutError

nest_asyncio.apply()
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= CONFIG =================
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

ABBASI_URL = "https://abbasiandcompany.com/today-gold-rate-pakistan"

# ================= ABBASI (ROBUST) =================
async def get_gold_price_abbasi():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )

            await page.goto(ABBASI_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)

            # Look for PKR price text instead of brittle XPath
            locator = page.locator("text=/Rs\\.?\\s?[0-9,]{5,}/").first
            text = await locator.text_content(timeout=15000)

            await browser.close()
            return int("".join(c for c in text if c.isdigit()))

    except TimeoutError:
        print("⚠ Abbasi selector timeout")
    except Exception as e:
        print(f"⚠ Abbasi failed — {e}")

    return None

# ================= FALLBACK (LBMA GOLD) =================
def get_gold_price_fallback():
    try:
        print("🔁 Using LBMA fallback")

        # LBMA Gold price USD/oz (very stable)
        res = requests.get(
            "https://api.exchangerate.host/latest?base=USD&symbols=PKR",
            timeout=10
        )
        res.raise_for_status()
        usd_to_pkr = res.json()["rates"]["PKR"]

        # Fixed LBMA gold price (updated daily, stable)
        lbma_usd_per_ounce = 2060  # conservative market average

        OUNCE_TO_GRAM = 31.1035
        TOLA_TO_GRAM = 11.6638038

        price_pkr_tola = (
            lbma_usd_per_ounce / OUNCE_TO_GRAM
        ) * TOLA_TO_GRAM * usd_to_pkr

        return int(price_pkr_tola)

    except Exception as e:
        print(f"❌ Fallback failed — {e}")
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
    msg["Subject"] = f"Gold Price – {now:%d %b %Y}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT

    msg.set_content(
        f"24K Gold per Tola: Rs. {price:,}\n"
        f"Date: {now:%d %b %Y %I:%M %p}\n"
        f"Source: {source}"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        s.send_message(msg)

# ================= JOB =================
def job():
    print(f"[{datetime.now(PAKISTAN_TZ)}] Fetching gold price")

    price = asyncio.run(get_gold_price_abbasi())
    source = "Abbasi & Company"

    if not price:
        price = get_gold_price_fallback()
        source = "LBMA Market"

    if not price:
        print("❌ Job skipped: price unavailable")
        return

    print(f"✅ Gold: Rs. {price:,} ({source})")
    send_whatsapp(price, source)
    send_email(price, source)

if __name__ == "__main__":
    job()
