import os
import requests
from twilio.rest import Client
from datetime import datetime

# ======= CONFIG FROM SECRETS =======
GOLD_API_KEY = os.environ.get("GOLD_API_KEY")
TWILIO_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH_TOKEN")
MY_WHATSAPP_NUMBER = os.environ.get("MY_WHATSAPP_NUMBER")
TWILIO_WHATSAPP_NUMBER = "whatsapp:+14155238886"

GRAMS_PER_TOLA = 11.6638


def get_gold_price_usd():
    url = "https://www.goldapi.io/api/XAU/USD"
    headers = {"x-access-token": GOLD_API_KEY, "Content-Type": "application/json"}

    for attempt in range(3):
        try:
            print(f"[{datetime.now()}] Fetching gold prices (Attempt {attempt+1})...")
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 403:
                print(f"[{datetime.now()}] ERROR: 403 Forbidden. Check your GOLD_API_KEY.")
                return None, None, None, None
            response.raise_for_status()
            data = response.json()
            return (data.get("price_gram_24k"), data.get("price_gram_22k"),
                    data.get("high_price"), data.get("low_price"))
        except Exception as e:
            print(f"Error fetching gold price: {e}")
            if attempt < 2:
                continue
            return None, None, None, None
    return None, None, None, None


def get_usd_to_pkr_rate():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    for attempt in range(3):
        try:
            print(f"[{datetime.now()}] Fetching USD to PKR rate (Attempt {attempt+1})...")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data["rates"]["PKR"]
        except Exception as e:
            print(f"Error fetching exchange rate: {e}")
            if attempt < 2:
                continue
            return 280.0
    return 280.0


def calculate_price_per_tola_in_pkr(price_per_gram_usd, usd_to_pkr):
    if price_per_gram_usd is None or usd_to_pkr is None:
        return 0.0
    return round(price_per_gram_usd * usd_to_pkr * GRAMS_PER_TOLA, 2)


def send_whatsapp_message(price_24k, price_22k):
    if not all([TWILIO_SID, TWILIO_AUTH, MY_WHATSAPP_NUMBER]):
        print("Missing Twilio configuration. Skipping message.")
        return
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        val_24k = f"{price_24k:,.2f}" if price_24k else "N/A"
        val_22k = f"{price_22k:,.2f}" if price_22k else "N/A"
        now = datetime.now()
        message_body = (
            f"Gold Price Update (PKR)\n"
            f"📅 {now.strftime('%d %b %Y')} | ⏰ {now.strftime('%I:%M %p')}\n\n"
            f"24K per Tola: Rs. {val_24k}\n"
            f"22K per Tola: Rs. {val_22k}"
        )
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=MY_WHATSAPP_NUMBER,
            body=message_body
        )
        print(f"[{now}] WhatsApp message sent. SID: {message.sid}")
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")


def job():
    usd_to_pkr = get_usd_to_pkr_rate()
    price_24k_usd, price_22k_usd, high_price, low_price = get_gold_price_usd()
    if price_24k_usd is None:
        print(f"[{datetime.now()}] Skipping job due to API failure.")
        return
    price_per_tola_24k = calculate_price_per_tola_in_pkr(price_24k_usd, usd_to_pkr)
    price_per_tola_22k = calculate_price_per_tola_in_pkr(price_22k_usd, usd_to_pkr)
    print(f"--- Update {datetime.now()} ---")
    print(f"24K Tola: Rs. {price_per_tola_24k:,}")
    print(f"22K Tola: Rs. {price_per_tola_22k:,}")
    print(f"USD/PKR: {usd_to_pkr:.2f}")
    send_whatsapp_message(price_per_tola_24k, price_per_tola_22k)


if __name__ == "__main__":
    print(f"[{datetime.now()}] Gold price WhatsApp notifier started...")
    job()
