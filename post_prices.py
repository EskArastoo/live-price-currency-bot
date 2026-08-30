"""
ربات ارسال قیمت ارز، طلا و سکه به کانال تلگرام

منبع قیمت‌ها:
    Servix

Environment Variables:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    SERVIX_API_KEY

قیمت‌های ریالی Servix به ریال دریافت می‌شوند
و برای نمایش در کانال به تومان تبدیل می‌شوند.

فایل last_prices.json برای مقایسه قیمت قبلی
و نمایش افزایش / کاهش استفاده می‌شود.
"""

import os
import sys
import json
import requests
import jdatetime

from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# تنظیمات اصلی
# ============================================================

jdatetime.set_locale("fa_IR")

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERVIX_API_KEY = os.environ.get("SERVIX_API_KEY")


if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not SERVIX_API_KEY:
    print(
        "خطا: یکی از متغیرهای زیر تنظیم نشده است:\n"
        "TELEGRAM_BOT_TOKEN\n"
        "TELEGRAM_CHAT_ID\n"
        "SERVIX_API_KEY"
    )
    sys.exit(1)


# ============================================================
# Servix
# ============================================================

SERVIX_URL = "https://servix.cc/api/v1/assets"

HEADERS = {
    "X-API-Key": SERVIX_API_KEY,
    "Accept": "application/json",
    "User-Agent": "LivePriceCurrencyBot/1.0"
}


# ============================================================
# فایل تاریخچه
# ============================================================

HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "last_prices.json"
)

CHANNEL_USERNAME = "@LivePriceCurrency"

DAILY_STATS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "daily_stats.json"
)

PINNED_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "last_pinned.json"
)

# نمادهایی که در خلاصه‌ی نیمه‌شب گزارش می‌شوند
DAILY_SUMMARY_SYMBOLS = [
    ("USD_RLS", "دلار آمریکا"),
    ("GOLD_18_RLS", "طلای ۱۸ عیار"),
    ("SEKKEH_RLS", "سکه امامی"),
]


# ============================================================
# نمادهای ارز
# ============================================================

CURRENCY_SYMBOLS = [
    ("USD_RLS", "دلار آمریکا"),
    ("USDT_RLS", "دلار تتر"),
    ("EUR_RLS", "یورو"),
    ("GBP_RLS", "پوند انگلیس"),
    ("AED_RLS", "درهم امارات"),
    ("CNY_RLS", "یوان چین"),
    ("TRY_RLS", "لیر ترکیه"),
]


# ============================================================
# نمادهای طلا
# ============================================================

GOLD_SYMBOLS = [
    ("GOLD_18_RLS", "طلای ۱۸ عیار"),
    ("GOLD_24_RLS", "طلای ۲۴ عیار"),
    ("GOLD_MESGHAL_RLS", "مثقال طلا"),
    ("GOLD_OUNCE_USD", "انس جهانی طلا"),
]


# ============================================================
# نمادهای سکه
# ============================================================

COIN_SYMBOLS = [
    ("SEKKEH_RLS", "سکه امامی"),
    ("BAHAR_RLS", "سکه بهار آزادی"),
    ("NIM_SEKKEH_RLS", "نیم سکه"),
    ("ROB_SEKKEH_RLS", "ربع سکه"),
]


# ============================================================
# تبدیل اعداد به فارسی
# ============================================================

EN_TO_FA_DIGITS = str.maketrans(
    "0123456789",
    "۰۱۲۳۴۵۶۷۸۹"
)


def to_fa_digits(text):
    return str(text).translate(EN_TO_FA_DIGITS)


def fa_number(value):
    """نمایش عدد با جداکننده هزارگان."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "نامشخص"

    return to_fa_digits(
        f"{value:,.0f}"
    )


def fa_decimal_number(value):
    """نمایش عدد اعشاری برای انس جهانی (بدون علامت +/-)."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "نامشخص"

    return to_fa_digits(
        f"{abs(value):,.2f}"
    )


def fa_change_number(value):
    """
    نمایش مقدار تغییر قیمت به تومان (شامل علامت +/- به‌صورت خودکار).
    همیشه به عدد صحیح گرد می‌شود چون تومان واحد اعشاری ندارد
    (مثلاً 4.99 -> 5، نه 4.99).
    """

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "۰"

    text = f"{value:+,.0f}"

    return to_fa_digits(text)


def fa_percent_number(value):
    """نمایش درصد تغییر با دو رقم اعشار و علامت +/- خودکار."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return None

    text = f"{value:+.2f}"

    return to_fa_digits(text)


# ============================================================
# دریافت قیمت‌ها از Servix
# ============================================================

def get_all_prices():
    """
    دریافت تمام قیمت‌های مورد نیاز با یک درخواست API.
    """

    codes = [
        "USD_RLS",
        "USDT_RLS",
        "EUR_RLS",
        "GBP_RLS",
        "AED_RLS",
        "CNY_RLS",
        "TRY_RLS",
        "GOLD_18_RLS",
        "GOLD_24_RLS",
        "GOLD_MESGHAL_RLS",
        "GOLD_OUNCE_USD",
        "SEKKEH_RLS",
        "BAHAR_RLS",
        "NIM_SEKKEH_RLS",
        "ROB_SEKKEH_RLS",
    ]

    params = {
        "codes": ",".join(codes)
    }

    response = requests.get(
        SERVIX_URL,
        headers=HEADERS,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            "پاسخ Servix فرمت مورد انتظار را ندارد."
        )

    return data


# ============================================================
# تبدیل پاسخ API به دیکشنری
# ============================================================

def make_price_map(items):

    result = {}

    for item in items:

        if not isinstance(item, dict):
            continue

        code = item.get("code")

        if code:
            result[code] = item

    return result


# ============================================================
# مدیریت تاریخچه
# ============================================================

def load_previous_prices():

    if not os.path.exists(HISTORY_FILE):
        return {}

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

    except (
        json.JSONDecodeError,
        OSError
    ):
        pass

    return {}


def save_current_prices(prices):

    temp_file = HISTORY_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            prices,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        HISTORY_FILE
    )


# ============================================================
# تغییر قیمت
# ============================================================

def get_price_change(
    symbol,
    current_price,
    previous_prices
):

    previous_price = previous_prices.get(
        symbol
    )

    if previous_price is None:
        return None, None

    try:

        previous_price = float(
            previous_price
        )

        current_price = float(
            current_price
        )

    except (
        ValueError,
        TypeError
    ):

        return None, None

    change = current_price - previous_price

    if change > 0:
        return "up", change

    if change < 0:
        return "down", change

    return "same", 0


def trend_html(
    symbol,
    current_price,
    previous_prices,
    is_ounce=False
):
    """
    نمایش تغییر قیمت: فلش، مقدار تغییر، و درصد تغییر.

    فلش‌ها: 🔼 برای افزایش، 🔽 برای کاهش
    (این دو ایموجی خودشان رنگ سبز/قرمز دارند).

    نکته: fa_change_number خودش علامت +/- را اضافه می‌کند،
    پس اینجا دیگر نباید دوباره + دستی اضافه شود.
    """

    direction, change = get_price_change(
        symbol,
        current_price,
        previous_prices
    )

    if direction not in ("up", "down"):
        return ""

    if is_ounce:

        if direction == "up":
            change_text = "+" + fa_decimal_number(change)
        else:
            change_text = "-" + fa_decimal_number(change)

    else:
        # fa_change_number خودش علامت +/- را دارد
        change_text = fa_change_number(change)

    # --------------------------------------------------------
    # درصد تغییر نسبت به قیمت قبلی
    # --------------------------------------------------------

    previous_price = previous_prices.get(symbol)

    percent_text = ""

    try:

        percent = (
            change / float(previous_price)
        ) * 100

        percent_fa = fa_percent_number(percent)

        if percent_fa is not None:
            percent_text = f" / {percent_fa}٪"

    except (
        TypeError,
        ValueError,
        ZeroDivisionError
    ):
        pass

    arrow = "🔼" if direction == "up" else "🔽"

    return (
        f" {arrow} "
        f"(<b>{change_text}{percent_text}</b>)"
    )


# ============================================================
# تاریخ و ساعت تهران
# ============================================================

def jalali_date():

    tehran_now = datetime.now(
        TEHRAN_TZ
    )

    jalali_now = jdatetime.datetime.fromgregorian(
        datetime=tehran_now
    )

    text = jalali_now.strftime(
        "%A %d %B %Y"
    )

    return to_fa_digits(text)


def tehran_time():

    tehran_now = datetime.now(
        TEHRAN_TZ
    )

    return to_fa_digits(
        tehran_now.strftime("%H:%M")
    )


# ============================================================
# تبدیل ریال به تومان
# ============================================================

def rial_to_toman(value):

    try:
        return float(value) / 10
    except (
        ValueError,
        TypeError
    ):
        return None


# ============================================================
# مدیریت آمار روزانه (بیشترین/کمترین)
# ============================================================

def _today_key():
    """کلید روز جاری بر اساس تاریخ تهران (میلادی، برای سادگی مقایسه)."""

    return datetime.now(TEHRAN_TZ).date().isoformat()


def load_daily_stats():

    if not os.path.exists(DAILY_STATS_FILE):
        return {"date": _today_key(), "symbols": {}}

    try:

        with open(
            DAILY_STATS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict) and "symbols" in data:
            return data

    except (
        json.JSONDecodeError,
        OSError
    ):
        pass

    return {"date": _today_key(), "symbols": {}}


def save_daily_stats(stats):

    temp_file = DAILY_STATS_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            stats,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        DAILY_STATS_FILE
    )


def track_daily_stats(current_prices):
    """
    بیشترین و کمترین قیمت هرکدام از نمادهای مورد نظر خلاصه‌ی
    شبانه را در طول روز جاری به‌روزرسانی می‌کند.

    اگر روز عوض شده باشد (یعنی هنوز خلاصه‌ی دیروز خوانده نشده)
    آمار به‌طور خودکار برای روز جدید از صفر شروع می‌شود.
    """

    today = _today_key()

    stats = load_daily_stats()

    if stats.get("date") != today:
        stats = {"date": today, "symbols": {}}

    for symbol, _label in DAILY_SUMMARY_SYMBOLS:

        price = current_prices.get(symbol)

        if price is None:
            continue

        entry = stats["symbols"].get(symbol)

        if entry is None:
            stats["symbols"][symbol] = {
                "min": price,
                "max": price
            }
        else:
            entry["min"] = min(entry["min"], price)
            entry["max"] = max(entry["max"], price)

    save_daily_stats(stats)


# ============================================================
# ساخت ردیف قیمت
# ============================================================

def render_price_row(
    symbol,
    label,
    price_map,
    current_prices,
    previous_prices
):

    item = price_map.get(symbol)

    if not item:

        print(
            f"هشدار: نماد {symbol} در پاسخ Servix وجود ندارد."
        )

        return None

    raw_value = item.get("value")

    if raw_value is None:

        print(
            f"هشدار: مقدار {symbol} موجود نیست."
        )

        return None

    # --------------------------------------------------------
    # اونس جهانی
    # --------------------------------------------------------

    if symbol == "GOLD_OUNCE_USD":

        try:
            price = float(raw_value)
        except (
            ValueError,
            TypeError
        ):
            return None

        current_prices[symbol] = price

        change_html = trend_html(
            symbol,
            price,
            previous_prices,
            is_ounce=True
        )

        price_text = fa_decimal_number(
            price
        )

        return (
            f"▫️ {label}: "
            f"<b>{price_text}</b> دلار"
            f"{change_html}"
        )

    # --------------------------------------------------------
    # قیمت‌های ریالی
    # --------------------------------------------------------

    price = rial_to_toman(
        raw_value
    )

    if price is None:
        return None

    current_prices[symbol] = price

    change_html = trend_html(
        symbol,
        price,
        previous_prices
    )

    price_text = fa_number(
        price
    )

    return (
        f"▫️ {label}: "
        f"<b>{price_text}</b> تومان"
        f"{change_html}"
    )


# ============================================================
# ساخت بخش
# ============================================================

def render_section(
    title,
    icon,
    symbol_list,
    price_map,
    current_prices,
    previous_prices
):

    rows = []

    for symbol, label in symbol_list:

        row = render_price_row(
            symbol=symbol,
            label=label,
            price_map=price_map,
            current_prices=current_prices,
            previous_prices=previous_prices
        )

        if row:
            rows.append(row)

    if not rows:
        return ""

    return (
        f"{icon} <b>{title}</b>\n"
        + "\n".join(rows)
    )


# ============================================================
# ساخت پیام نهایی
# ============================================================

def build_message():

    data = get_all_prices()

    price_map = make_price_map(
        data
    )

    previous_prices = load_previous_prices()

    current_prices = {}

    blocks = []

    blocks.append(
        "💹 <b>نبض بازار</b>\n"
        f"🗓 {jalali_date()}  •  "
        f"⏱ {tehran_time()}"
    )

    currency_block = render_section(
        title="ارز",
        icon="💵",
        symbol_list=CURRENCY_SYMBOLS,
        price_map=price_map,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if currency_block:
        blocks.append(currency_block)

    gold_block = render_section(
        title="طلا",
        icon="🥇",
        symbol_list=GOLD_SYMBOLS,
        price_map=price_map,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if gold_block:
        blocks.append(gold_block)

    coin_block = render_section(
        title="سکه",
        icon="🪙",
        symbol_list=COIN_SYMBOLS,
        price_map=price_map,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if coin_block:
        blocks.append(coin_block)

    footer = [
        "──────────────",
        f"📢 {CHANNEL_USERNAME}"
    ]

    blocks.append("\n".join(footer))

    save_current_prices(current_prices)
    track_daily_stats(current_prices)

    return "\n\n".join(blocks)


# ============================================================
# ساخت پیام خلاصه‌ی نیمه‌شب
# ============================================================

def build_summary_message():
    """
    خلاصه‌ی بیشترین/کمترین قیمت دلار، طلا و سکه در طول روزی
    که تازه تمام شده است؛ بر اساس داده‌های daily_stats.json.
    """

    stats = load_daily_stats()
    symbols = stats.get("symbols", {})

    blocks = [
        "📅 <b>خلاصه‌ی شبانه‌ی بازار</b>\n"
        f"🗓 {jalali_date()}"
    ]

    rows = []

    for symbol, label in DAILY_SUMMARY_SYMBOLS:

        entry = symbols.get(symbol)

        if not entry:
            continue

        rows.append(
            f"▫️ <b>{label}</b>\n"
            f"   کمترین: {fa_number(entry['min'])} تومان\n"
            f"   بیشترین: {fa_number(entry['max'])} تومان"
        )

    if not rows:
        rows.append("داده‌ای برای امروز ثبت نشده است.")

    blocks.append("\n\n".join(rows))

    blocks.append(
        "──────────────\n"
        f"📢 {CHANNEL_USERNAME}"
    )

    return "\n\n".join(blocks)


# ============================================================
# ارسال به تلگرام
# ============================================================

def send_to_telegram(text):

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    response = requests.post(
        url,
        data=payload,
        timeout=15
    )

    if response.status_code != 200:

        print(
            "خطا در ارسال به تلگرام:\n"
            f"{response.status_code}\n"
            f"{response.text}"
        )

        sys.exit(1)

    print("پیام با موفقیت ارسال شد.")


# ============================================================
# ارسال و پین‌کردن خلاصه‌ی نیمه‌شب
# ============================================================

def load_pinned_message_id():

    if not os.path.exists(PINNED_FILE):
        return None

    try:

        with open(
            PINNED_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        return data.get("message_id")

    except (
        json.JSONDecodeError,
        OSError
    ):
        return None


def save_pinned_message_id(message_id):

    temp_file = PINNED_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            {"message_id": message_id},
            file
        )

    os.replace(temp_file, PINNED_FILE)


def unpin_previous_summary():

    previous_id = load_pinned_message_id()

    if previous_id is None:
        return

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/unpinChatMessage"
    )

    try:
        requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": previous_id
            },
            timeout=15
        )
    except requests.RequestException:
        # اگر پیام قبلی قبلاً آن‌پین شده یا پاک شده، مشکلی نیست
        pass


def send_and_pin_to_telegram(text):
    """
    خلاصه‌ی شبانه را ارسال، پیام قبلی را آن‌پین، و پیام تازه
    را پین می‌کند تا همیشه فقط آخرین خلاصه در بالای کانال باشد.
    """

    unpin_previous_summary()

    url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    response = requests.post(
        url,
        data=payload,
        timeout=15
    )

    if response.status_code != 200:

        print(
            "خطا در ارسال خلاصه به تلگرام:\n"
            f"{response.status_code}\n"
            f"{response.text}"
        )

        sys.exit(1)

    message_id = response.json()["result"]["message_id"]

    pin_url = (
        "https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
    )

    pin_response = requests.post(
        pin_url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "disable_notification": False
        },
        timeout=15
    )

    if pin_response.status_code == 200:
        save_pinned_message_id(message_id)
    else:
        print(
            "هشدار: پین‌کردن پیام خلاصه ناموفق بود:\n"
            f"{pin_response.status_code}\n"
            f"{pin_response.text}"
        )

    print("پیام خلاصه با موفقیت ارسال شد.")


# ============================================================
# نمایش نمادهای دریافت‌شده
# ============================================================

def list_all_symbols():

    data = get_all_prices()

    print(f"\n=== {len(data)} نماد دریافت شد ===")

    for item in data:

        code = item.get("code")
        name = item.get("labelFa")
        value = item.get("value")
        business_time = item.get("businessTime")

        print(
            f"{code} | {name} | {value} | {business_time}"
        )


# ============================================================
# اجرای برنامه
# ============================================================

if __name__ == "__main__":

    mode = sys.argv[1] if len(sys.argv) > 1 else "regular"

    if mode == "list":

        try:
            list_all_symbols()

        except requests.RequestException as error:
            print(f"خطا در دریافت اطلاعات Servix: {error}")
            sys.exit(1)

    elif mode == "summary":

        try:
            summary = build_summary_message()
            print("\n" + summary)
            send_and_pin_to_telegram(summary)

        except Exception as error:
            print(f"خطای غیرمنتظره در خلاصه‌ی نیمه‌شب: {error}")
            sys.exit(1)

    else:

        try:
            message = build_message()
            print("\n" + message)
            send_to_telegram(message)

        except requests.RequestException as error:
            print(f"خطا در دریافت اطلاعات Servix: {error}")
            sys.exit(1)

        except Exception as error:
            print(f"خطای غیرمنتظره: {error}")
            sys.exit(1)
