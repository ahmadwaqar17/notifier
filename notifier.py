import os
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+ for timezone support

# ================= CONFIG =================
GOLD_API_KEY = os.environ.get("GOLD_API_KEY")

# ---- WHAPI WhatsApp ----
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_API_URL = "https://gate.whapi.cloud/messages/text"
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")

# ---- Gmail ----
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

GRAMS_PER_TOLA = 11.6638
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")

# ================= GOLD PRICE =================
def get_gold_price_usd():
    url = "https://www.goldapi.io/api/XAU/USD"
    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            now = datetime.now(PAKISTAN_TZ)
            print(f"[{now}] Fetching gold prices (Attempt {attempt + 1})")
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get("price_gram_24k"), data.get("price_gram_22k")
        except Exception as e:
            print(f"Gold price fetch failed: {e}")

    return None, None


def get_usd_to_pkr_rate():
    try:
        now = datetime.now(PAKISTAN_TZ)
        print(f"[{now}] Fetching USD → PKR rate")
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=10)
        r.raise_for_status()
        return r.json()["rates"]["PKR"]
    except Exception as e:
        print(f"Exchange rate fetch failed: {e}")
        return 280.0  # fallback


def calculate_price_per_tola(price_per_gram_usd, usd_to_pkr):
    if not price_per_gram_usd or not usd_to_pkr:
        return 0.0
    return round(price_per_gram_usd * usd_to_pkr * GRAMS_PER_TOLA, 2)


def format_price(price):
    return "{:,.2f}".format(price)

# ================= WHATSAPP (WHAPI) =================
def send_whatsapp_message(price_24k, price_22k):
    if not all([WHAPI_TOKEN, MY_WHATSAPP_NUMBER]):
        print("WhatsApp skipped: missing Whapi config")
        return

    # Normalize Pakistani number → 92xxxxxxxxxx
    number = MY_WHATSAPP_NUMBER.strip().replace(" ", "").replace("-", "")
    if number.startswith("+"):
        number = number[1:]
    elif number.startswith("03"):
        number = "92" + number[1:]

    now = datetime.now(PAKISTAN_TZ)
    body = (
        f"📊 *Gold Price Update (PKR)*\n"
        f"📅 {now.strftime('%d %b %Y')} | "
        f"⏰ {now.strftime('%I:%M %p')}\n\n"
        f"🟡 *24K per Tola:* Rs. {format_price(price_24k)}\n"
        f"🟠 *22K per Tola:* Rs. {format_price(price_22k)}"
    )

    payload = {
        "to": number,
        "body": body,
        "typing_time": 0
    }

    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(WHAPI_API_URL, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        print(f"[{now}] WhatsApp message sent successfully via Whapi")
    except Exception as e:
        print(f"WhatsApp error: {e} | {r.text if 'r' in locals() else ''}")

# ================= EMAIL =================
def send_email(price_24k, price_22k, usd_to_pkr):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        print("Email skipped: missing Gmail config")
        return

    now = datetime.now(PAKISTAN_TZ)
    date_str = now.strftime('%d %b %Y')
    time_str = now.strftime('%I:%M %p')

    msg = EmailMessage()
    msg["Subject"] = f"Gold Price Update (PKR) - {date_str}"
    msg["From"] = GMAIL_EMAIL
    msg["To"] = EMAIL_RECIPIENT

    text = (
        f"Gold Price Update\n"
        f"Date: {date_str} {time_str}\n"
        f"24K: Rs. {format_price(price_24k)}\n"
        f"22K: Rs. {format_price(price_22k)}\n"
        f"USD/PKR: {usd_to_pkr:.2f}"
    )

    html = f"""
    <html>
      <body>
        <h2 style="color:#D4AF37;">Gold Price Update (PKR)</h2>
        <p><b>Date:</b> {date_str}<br><b>Time:</b> {time_str}</p>
        <ul>
          <li><b>24K per Tola:</b> Rs. {format_price(price_24k)}</li>
          <li><b>22K per Tola:</b> Rs. {format_price(price_22k)}</li>
          <li><b>USD/PKR:</b> {usd_to_pkr:.2f}</li>
        </ul>
      </body>
    </html>
    """

    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            print(f"[{now}] Email sent successfully")
    except Exception as e:
        print(f"Email error: {e}")

# ================= JOB =================
def job():
    usd_to_pkr = get_usd_to_pkr_rate()
    price_24k_usd, price_22k_usd = get_gold_price_usd()

    if not price_24k_usd:
        print("Job skipped: gold price unavailable")
        return

    price_24k = calculate_price_per_tola(price_24k_usd, usd_to_pkr)
    price_22k = calculate_price_per_tola(price_22k_usd, usd_to_pkr)

    now = datetime.now(PAKISTAN_TZ)
    print("===================================")
    print(f"[{now}] 24K Tola: Rs. {format_price(price_24k)}")
    print(f"[{now}] 22K Tola: Rs. {format_price(price_22k)}")
    print(f"[{now}] USD/PKR: {usd_to_pkr:.2f}")
    print("===================================")

    send_whatsapp_message(price_24k, price_22k)
    send_email(price_24k, price_22k, usd_to_pkr)


if __name__ == "__main__":
    job()
