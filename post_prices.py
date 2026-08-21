"""
ربات ارسال قیمت دلار، یورو، طلا، سکه و کریپتو به کانال تلگرام
اجرا: python post_prices.py
تنظیمات لازم از طریق متغیرهای محیطی (Environment Variables) خونده می‌شن:
  TELEGRAM_BOT_TOKEN   -> توکن رباتی که از BotFather گرفتی
  TELEGRAM_CHAT_ID     -> آیدی کانال (مثلا @mychannel یا عدد -100...)
  NAVASAN_API_KEY      -> کلید API که از navasan.tech گرفتی
"""

import os
import sys
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NAVASAN_API_KEY = os.environ.get("NAVASAN_API_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("خطا: TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID تنظیم نشده.")
    sys.exit(1)


def fa_number(n):
    """تبدیل عدد به رشته با جداکننده هزارگان"""
    try:
        return f"{float(n):,.0f}"
    except (ValueError, TypeError):
        return "نامشخص"


def get_navasan_prices():
    """دریافت قیمت دلار، یورو، طلا و سکه از navasan.tech"""
    if not NAVASAN_API_KEY:
        return {}
    url = f"http://api.navasan.tech/latest/?api_key={NAVASAN_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "دلار": data.get("usd_sell", {}).get("value") or data.get("usd", {}).get("value"),
            "یورو": data.get("eur_sell", {}).get("value") or data.get("eur", {}).get("value"),
            "طلای ۱۸ عیار": data.get("18ayar", {}).get("value") or data.get("gold_18k", {}).get("value"),
            "سکه امامی": data.get("emami1", {}).get("value") or data.get("sekee", {}).get("value"),
        }
    except Exception as e:
        print(f"خطا در دریافت قیمت‌های navasan: {e}")
        return {}


def get_crypto_prices():
    """دریافت قیمت بیت‌کوین و اتریوم از CoinGecko (رایگان و بدون نیاز به کلید)"""
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin,ethereum", "vs_currencies": "usd"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return {
            "بیت‌کوین (BTC)": data.get("bitcoin", {}).get("usd"),
            "اتریوم (ETH)": data.get("ethereum", {}).get("usd"),
        }
    except Exception as e:
        print(f"خطا در دریافت قیمت‌های کریپتو: {e}")
        return {}


def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 بروزرسانی قیمت‌ها\n🕒 {now}\n"]

    fiat_gold = get_navasan_prices()
    if fiat_gold:
        lines.append("💵 ارز و طلا:")
        for name, value in fiat_gold.items():
            if value:
                lines.append(f"{name}: {fa_number(value)} تومان")
        lines.append("")

    crypto = get_crypto_prices()
    if crypto:
        lines.append("🪙 کریپتو:")
        for name, value in crypto.items():
            if value:
                lines.append(f"{name}: ${fa_number(value)}")

    return "\n".join(lines)


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    resp = requests.post(url, data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"خطا در ارسال به تلگرام: {resp.status_code} - {resp.text}")
        sys.exit(1)
    print("پیام با موفقیت ارسال شد.")


if __name__ == "__main__":
    message = build_message()
    print(message)
    send_to_telegram(message)
