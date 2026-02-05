import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from datetime import datetime

# ======= CONFIG FROM ENVIRONMENT =======
GOLD_API_KEY        = os.environ.get("GOLD_API_KEY")
TWILIO_SID          = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH         = os.environ.get("TWILIO_AUTH_TOKEN")
MY_WHATSAPP_NUMBER  = os.environ.get("MY_WHATSAPP_NUMBER")
TWILIO_WHATSAPP     = "whatsapp:+14155238886"

GMAIL_EMAIL         = os.environ.get("GMAIL_EMAIL")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT     = os.environ.get("EMAIL_RECIPIENT")

GRAMS_PER_TOLA = 11.6638038   # more precise value

# ================= HELPERS =================
def get_gold_price_usd():
    """Returns (price_gram_24k, price_gram_22k) in USD or (None, None)"""
    url = "https://www.goldapi.io/api/XAU/USD"
    headers = {
        "x-access-token": GOLD_API_KEY,
        "Content-Type": "application/json",
    }

    for attempt in range(1, 4):
        try:
            print(f"[{datetime.now()}] Fetching gold prices (Attempt {attempt})...")
            r = requests.get(url, headers=headers, timeout=12)
            r.raise_for_status()
            data = r.json()

            p24 = data.get("price_gram_24k")
            p22 = data.get("price_gram_22k")

            if p24 is None or p22 is None:
                raise ValueError("Missing price data in response")

            return float(p24), float(p22)

        except Exception as e:
            print(f"Gold fetch failed: {e}")
            if attempt == 3:
                return None, None

    return None, None


def get_usd_to_pkr_rate():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        print(f"[{datetime.now()}] Fetching USD → PKR rate...")
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rate = r.json()["rates"].get("PKR")
        if not rate:
            raise ValueError("PKR rate not found")
        return float(rate)
    except Exception as e:
        print(f"Exchange rate fetch failed: {e}")
        return 280.0  # fallback


def calculate_price_per_tola(price_per_gram_usd: float | None, usd_to_pkr: float) -> float:
    if price_per_gram_usd is None or usd_to_pkr is None:
        return 0.0
    return round(price_per_gram_usd * usd_to_pkr * GRAMS_PER_TOLA, 2)


def format_price(value: float) -> str:
    """Comma separated, no non-ASCII characters"""
    return f"{value:,.0f}"          # whole rupees - cleaner for gold prices


# ================= NOTIFICATION CHANNELS =================
def send_whatsapp_message(price_24k: float, price_22k: float):
    if not all([TWILIO_SID, TWILIO_AUTH, MY_WHATSAPP_NUMBER]):
        print("WhatsApp skipped: missing Twilio credentials")
        return

    body = (
        f"Gold Price Update (PKR)\n"
        f"Date: {datetime.now().strftime('%d %b %Y')}\n"
        f"Time: {datetime.now().strftime('%I:%M %p')}\n\n"
        f"24K per Tola : Rs. {format_price(price_24k)}\n"
        f"22K per Tola : Rs. {format_price(price_22k)}"
    )

    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        message = client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP,
            to=MY_WHATSAPP_NUMBER
        )
        print(f"WhatsApp sent → SID: {message.sid}")
    except TwilioRestException as e:
        if e.status == 429:
            print("WhatsApp skipped: daily message limit reached.")
        else:
            print(f"Twilio error: {e}")
    except Exception as e:
        print(f"WhatsApp failed: {e}")


def send_email(price_24k: float, price_22k: float, usd_to_pkr: float):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT]):
        print("Email skipped: missing Gmail config")
        return

    date_str   = datetime.now().strftime("%d %b %Y")
    time_str   = datetime.now().strftime("%I:%M %p")
    p24_str    = format_price(price_24k)
    p22_str    = format_price(price_22k)
    usd_pkr_str = f"{usd_to_pkr:,.2f}"

    html_content = f"""\
<html>
  <body>
    <h2>Gold Price Update (PKR)</h2>
    <p><b>Date:</b> {date_str}<br>
       <b>Time:</b> {time_str}</p>
    <ul>
      <li><b>24K per Tola:</b> Rs. {p24_str}</li>
      <li><b>22K per Tola:</b> Rs. {p22_str}</li>
      <li><b>USD/PKR:</b> {usd_pkr_str}</li>
    </ul>
  </body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["From"]    = GMAIL_EMAIL
    msg["To"]      = EMAIL_RECIPIENT
    msg["Subject"] = f"Gold Price Update {date_str}"

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
            server.starttls()
            server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)               # ← modern & clean way
        print("Email sent successfully")
    except Exception as e:
        print(f"Email failed: {type(e).__name__} → {e}")


# ================= MAIN LOGIC =================
def main():
    print(f"[{datetime.now()}] Gold notifier started...")

    usd_to_pkr = get_usd_to_pkr_rate()
    price_24k_usd, price_22k_usd = get_gold_price_usd()

    if price_24k_usd is None:
        print("Cannot continue — gold price unavailable.")
        return

    price_24k = calculate_price_per_tola(price_24k_usd, usd_to_pkr)
    price_22k = calculate_price_per_tola(price_22k_usd, usd_to_pkr)

    print("===================================")
    print(f"24K Tola: Rs. {format_price(price_24k)}")
    print(f"22K Tola: Rs. {format_price(price_22k)}")
    print(f"USD/PKR: {usd_to_pkr:,.2f}")
    print("===================================")

    send_whatsapp_message(price_24k, price_22k)
    send_email(price_24k, price_22k, usd_to_pkr)


if __name__ == "__main__":
    main()
