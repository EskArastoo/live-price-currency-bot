"""
ربات ارسال قیمت دلار، یورو، طلا، سکه و کریپتو به کانال تلگرام
منبع قیمت‌ها: brsapi.ir (یک API واحد برای همه چیز)
اجرا: python post_prices.py
تنظیمات لازم از طریق متغیرهای محیطی (Environment Variables) خونده می‌شن:
  TELEGRAM_BOT_TOKEN   -> توکن رباتی که از BotFather گرفتی
  TELEGRAM_CHAT_ID     -> آیدی کانال (مثلا @LivePriceCurrency)
  BRSAPI_KEY           -> کلید API که از brsapi.ir گرفتی
"""

import os
import sys
import requests
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BRSAPI_KEY = os.environ.get("BRSAPI_KEY")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not BRSAPI_KEY:
    print("خطا: یکی از TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID / BRSAPI_KEY تنظیم نشده.")
    sys.exit(1)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def fa_number(n):
    """تبدیل عدد به رشته با جداکننده هزارگان"""
    try:
        return f"{float(n):,.0f}"
    except (ValueError, TypeError):
        return "نامشخص"


def find_by_symbol(items, symbol):
    for it in items or []:
        if it.get("symbol") == symbol:
            return it
    return None


def get_all_prices():
    url = f"https://Api.BrsApi.ir/Market/Gold_Currency.php?key={BRSAPI_KEY}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def build_message():
    data = get_all_prices()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 بروزرسانی قیمت‌ها\n🕒 {now}\n"]

    currency_items = data.get("currency", [])
    gold_items = data.get("gold", [])
    crypto_items = data.get("cryptocurrency", [])

    # ارز
    usd = find_by_symbol(currency_items, "USD")
    eur = find_by_symbol(currency_items, "EUR")
    if usd or eur:
        lines.append("💵 ارز:")
        if usd:
            lines.append(f"دلار: {fa_number(usd['price'])} {usd.get('unit', 'تومان')}")
        if eur:
            lines.append(f"یورو: {fa_number(eur['price'])} {eur.get('unit', 'تومان')}")
        lines.append("")

    # طلا و سکه
    gold18 = find_by_symbol(gold_items, "IR_GOLD_18K")
    coin_emami = find_by_symbol(gold_items, "IR_COIN_EMAMI")
    if gold18 or coin_emami:
        lines.append("🪙 طلا و سکه:")
        if gold18:
            lines.append(f"طلای ۱۸ عیار: {fa_number(gold18['price'])} {gold18.get('unit', 'تومان')}")
        if coin_emami:
            lines.append(f"سکه امامی: {fa_number(coin_emami['price'])} {coin_emami.get('unit', 'تومان')}")
        lines.append("")

    # کریپتو
    btc = find_by_symbol(crypto_items, "BTC")
    eth = find_by_symbol(crypto_items, "ETH")
    if btc or eth:
        lines.append("₿ کریپتو:")
        if btc:
            lines.append(f"بیت‌کوین: ${fa_number(btc['price'])}")
        if eth:
            lines.append(f"اتریوم: ${fa_number(eth['price'])}")

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
