import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from datetime import datetime

# ======= CONFIG FROM SECRETS =======
GOLD_API_KEY = os.environ.get("GOLD_API_KEY")

TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH_TOKEN")
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

# ===== Gmail config =====
GMAIL_EMAIL = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")

GRAMS_PER_TOLA = 11.6638


# ================= GOLD PRICE =================
def get_gold_price_usd():
    url = "https://www.goldapi.io/api/XAU/USD"
    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            print(f"[{datetime.now()}] Fetching gold prices (Attempt {attempt + 1})...")
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            return (
                data.get("price_gram_24k"),
                data.get("price_gram_22k"),
            )
        except Exception as e:
            print(f"Gold price fetch failed: {e}")

    return None, None


def get_usd_to_pkr_rate():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        print(f"[{datetime.now()}] Fetching USD → PKR rate...")
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()["rates"]["PKR"]
    except Exception as e:
        print(f"Exchange rate fetch failed: {e}")
        return 280.0  # safe fallback


def calculate_price_per_tola(price_per_gram_usd, usd_to_pkr):
    if not price_per_gram_usd or not usd_to_pkr:
        return 0.0
    return round(price_per_gram_usd * usd_to_pkr * GRAMS_PER_TOLA, 2)


# ================= WHATSAPP =================
def send_whatsapp_message(price_24k, price_22k):
    if not all([TWILIO_SID, TWILIO_AUTH, MY_WHATSAPP_NUMBER]):
        print("WhatsApp skipped: missing Twilio config.")
        return

    body = (
        f"Gold Price Update (PKR)\n"
        f"📅 {datetime.now().strftime('%d %b %Y')} | "
        f"⏰ {datetime.now().strftime('%I:%M %p')}\n\n"
        f"24K per Tola: Rs. {price_24k:,.2f}\n"
        f"22K per Tola: Rs. {price_22k:,.2f}"
    )

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=MY_WHATSAPP_NUMBER,
            body=body,
        )
        print(f"WhatsApp sent successfully. SID: {msg.sid}")

    except TwilioRestException as e:
        if e.status == 429:
            print("WhatsApp skipped: daily message limit reached.")
        else:
            print(f"WhatsApp Twilio error: {e}")

    except Exception as e:
        print(f"Unexpected WhatsApp error: {e}")


# ================= EMAIL (GMAIL SMTP) =================
def send_email(price_24k, price_22k, usd_to_pkr):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        print("Email skipped: missing Gmail config.")
        return

    html = f"""
    <h2>Gold Price Update (PKR)</h2>
    <p>
      <b>Date:</b> {datetime.now().strftime('%d %b %Y')}<br>
      <b>Time:</b> {datetime.now().strftime('%I:%M %p')}
    </p>
    <ul>
      <li><b>24K per Tola:</b> Rs. {price_24k:,.2f}</li>
      <li><b>22K per Tola:</b> Rs. {price_22k:,.2f}</li>
      <li><b>USD/PKR:</b> {usd_to_pkr:.2f}</li>
    </ul>
    """

    msg = MIMEMultipart()
    msg["From"] = f"Gold Price Notifier <{GMAIL_EMAIL}>"
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = "Gold Price Update (PKR)"
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully via Gmail")

    except Exception as e:
        print(f"Email failed: {e}")


# ================= JOB =================
def job():
    try:
        usd_to_pkr = get_usd_to_pkr_rate()
        price_24k_usd, price_22k_usd = get_gold_price_usd()

        if not price_24k_usd:
            print("Job skipped: gold price unavailable.")
            return

        price_24k = calculate_price_per_tola(price_24k_usd, usd_to_pkr)
        price_22k = calculate_price_per_tola(price_22k_usd, usd_to_pkr)

        print("===================================")
        print(f"24K Tola: Rs. {price_24k:,}")
        print(f"22K Tola: Rs. {price_22k:,}")
        print(f"USD/PKR: {usd_to_pkr:.2f}")
        print("===================================")

        send_whatsapp_message(price_24k, price_22k)
        send_email(price_24k, price_22k, usd_to_pkr)

    except Exception as e:
        print(f"Unexpected job error (safely handled): {e}")


if __name__ == "__main__":
    print(f"[{datetime.now()}] Gold notifier started...")
    job()
