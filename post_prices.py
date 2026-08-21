"""
ربات ارسال قیمت دلار، یورو، طلا، سکه و کریپتو به کانال تلگرام
منبع قیمت‌ها: brsapi.ir (یک API واحد برای همه چیز)
اجرا: python post_prices.py

تنظیمات لازم از طریق متغیرهای محیطی (Environment Variables) خونده می‌شن:
  TELEGRAM_BOT_TOKEN   -> توکن رباتی که از BotFather گرفتی
  TELEGRAM_CHAT_ID     -> آیدی کانال (مثلا @LivePriceCurrency)
  BRSAPI_KEY           -> کلید API که از brsapi.ir گرفتی

فایل last_prices.json کنار همین اسکریپت ذخیره می‌شه تا قیمتِ اجرای قبلی
رو به خاطر بسپاریم و بشه دایره‌ی سبز (صعود) و قرمز (نزول) رو نشون داد.
"""
import os
import sys
import json
import requests
import jdatetime
from datetime import datetime
from zoneinfo import ZoneInfo

jdatetime.set_locale("fa_IR")

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

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

# فایلی که قیمت اجرای قبلی رو نگه می‌داره تا بشه صعود/نزول رو تشخیص داد
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_prices.json")

# ---------------------------------------------------------------------------
# نمادهایی که توی پیام نمایش داده می‌شن (به همین ترتیب و با همین برچسب فارسی)
# ---------------------------------------------------------------------------
CURRENCY_SYMBOLS = [
    ("USD", "دلار آمریکا"),
    ("USDT_IRT", "دلار تتر"),
    ("EUR", "یورو"),
    ("GBP", "پوند انگلیس"),
    ("AED", "درهم امارات"),
]

GOLD_SYMBOLS = [
    ("IR_GOLD_18K", "طلای ۱۸ عیار"),
    ("IR_GOLD_24K", "طلای ۲۴ عیار"),
    ("IR_GOLD_MELTED", "طلای آب‌شده نقدی"),
    ("XAUUSD", "انس طلای جهانی"),
]

COIN_SYMBOLS = [
    ("IR_COIN_1G", "سکه یک گرمی"),
    ("IR_COIN_QUARTER", "ربع سکه"),
    ("IR_COIN_HALF", "نیم سکه"),
    ("IR_COIN_EMAMI", "سکه امامی"),
    ("IR_COIN_BAHAR", "سکه بهار آزادی"),
]

CRYPTO_SYMBOLS = [
    ("BTC", "بیت‌کوین"),
    ("ETH", "اتریوم"),
    ("XRP", "ایکس‌آر‌پی"),
    ("SOL", "سولانا"),
]

DIVIDER = "──────────────"


def fa_number(n):
    """تبدیل عدد به رشته با جداکننده هزارگان (بدون اعشار) - برای تومان/دلار بزرگ"""
    try:
        return f"{float(n):,.0f}"
    except (ValueError, TypeError):
        return "نامشخص"


def fa_crypto_number(n):
    """قیمت کریپتو رو با جداکننده هزارگان فرمت می‌کنه؛ برای اعداد کوچیک (زیر ۱۰۰) دو رقم اعشار نگه می‌داره"""
    try:
        value = float(n)
    except (ValueError, TypeError):
        return "نامشخص"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


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


def load_previous_prices():
    """قیمت‌های اجرای قبلی رو از فایل می‌خونه؛ اگه فایل نبود یا خراب بود، دیکشنری خالی برمی‌گردونه"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_current_prices(prices):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


def trend_text(symbol, current_price, previous_prices):
    """بر اساس مقایسه با اجرای قبلی، دایره رنگی + درصد تغییر رو برمی‌گردونه (مثلا ' 🟢 +۰.۴۳٪')"""
    prev = previous_prices.get(symbol)
    if prev is None:
        return ""
    try:
        prev = float(prev)
        current_price = float(current_price)
    except (TypeError, ValueError):
        return ""
    if prev == 0:
        return ""
    diff = current_price - prev
    percent = (diff / prev) * 100
    if diff > 0:
        icon = "🟢"
    elif diff < 0:
        icon = "🔴"
    else:
        icon = "⚪️"
    percent_text = to_fa_digits(f"{percent:+.2f}") + "٪"
    return f" {icon} {percent_text}"


EN_TO_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa_digits(text):
    """اعداد انگلیسی رو به رقم فارسی تبدیل می‌کنه (فقط برای نمایش تاریخ/ساعت)"""
    return text.translate(EN_TO_FA_DIGITS)


def jalali_now_str():
    """تاریخ و ساعت شمسیِ ایران رو (نه ساعت سرور) به فارسی و خوانا برمی‌گردونه"""
    tehran_now = datetime.now(TEHRAN_TZ)
    now = jdatetime.datetime.fromgregorian(datetime=tehran_now)
    text = now.strftime("%A %d %B %Y  -  ساعت %H:%M")
    return to_fa_digits(text)


def render_section(title, icon, symbol_list, items, current_prices, previous_prices, unit_fallback="تومان", is_usd=False, number_fn=fa_number):
    """یه بخش از پیام (مثلا ارز یا طلا) رو می‌سازه؛ اگه هیچ نمادی پیدا نشه خط خالی برمی‌گردونه"""
    rows = []
    for symbol, label in symbol_list:
        item = find_by_symbol(items, symbol)
        if not item:
            continue
        price = item["price"]
        current_prices[symbol] = price
        icon_trend = trend_text(symbol, price, previous_prices)
        unit = item.get("unit", unit_fallback)
        prefix = "$" if is_usd else ""
        price_text = number_fn(price)
        if is_usd:
            rows.append(f"▫️ {label}: {prefix}{price_text}{icon_trend}")
        else:
            rows.append(f"▫️ {label}: {price_text} {unit}{icon_trend}")
    if not rows:
        return ""
    return f"{icon} <b>{title}</b>\n" + "\n".join(rows)


def build_message():
    data = get_all_prices()
    previous_prices = load_previous_prices()
    current_prices = {}

    currency_items = data.get("currency", [])
    gold_items = data.get("gold", [])
    crypto_items = data.get("cryptocurrency", [])

    blocks = [
        f"📊 <b>گزارش لحظه‌ای قیمت‌ها</b>",
        f"🗓 {jalali_now_str()}",
    ]

    currency_block = render_section("نرخ ارز", "💵", CURRENCY_SYMBOLS, currency_items, current_prices, previous_prices)
    if currency_block:
        blocks.append(currency_block)

    gold_block = render_section("طلا", "🪙", GOLD_SYMBOLS, gold_items, current_prices, previous_prices)
    coin_block = render_section("سکه", "🪙", COIN_SYMBOLS, gold_items, current_prices, previous_prices)
    if gold_block or coin_block:
        combined = []
        if gold_block:
            combined.append(gold_block)
        if gold_block and coin_block:
            combined.append(DIVIDER)
        if coin_block:
            combined.append(coin_block)
        blocks.append("\n".join(combined))

    crypto_block = render_section(
        "ارز دیجیتال", "₿", CRYPTO_SYMBOLS, crypto_items, current_prices, previous_prices,
        is_usd=True, number_fn=fa_crypto_number,
    )
    if crypto_block:
        blocks.append(crypto_block)

    save_current_prices(current_prices)
    return "\n\n".join(blocks)


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    resp = requests.post(url, data=payload, timeout=15)
    if resp.status_code != 200:
        print(f"خطا در ارسال به تلگرام: {resp.status_code} - {resp.text}")
        sys.exit(1)
    print("پیام با موفقیت ارسال شد.")


def list_all_symbols():
    """
    این تابع برای اینه که خودت لیست کامل نمادهای در دسترس API رو با کلید واقعی
    خودت ببینی. کافیه اسکریپت رو این‌طوری اجرا کنی:
        python post_prices.py list
    """
    data = get_all_prices()
    for section_name, section_key in [("ارز", "currency"), ("طلا و سکه", "gold"), ("ارز دیجیتال", "cryptocurrency")]:
        items = data.get(section_key, [])
        print(f"\n=== {section_name} ({len(items)} نماد) ===")
        for it in items:
            print(f"  symbol={it.get('symbol')!r}  name={it.get('name') or it.get('name_en')}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_all_symbols()
    else:
        message = build_message()
        print(message)
        send_to_telegram(message)
