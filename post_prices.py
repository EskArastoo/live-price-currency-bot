"""
ربات ارسال قیمت ارز، طلا و سکه به کانال تلگرام

منبع قیمت‌ها:
    Servix

Environment Variables:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    SERVIX_API_KEY

فایل last_prices.json کنار اسکریپت ذخیره می‌شود
تا قیمت اجرای قبلی برای نمایش افزایش یا کاهش در دسترس باشد.
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
# تنظیمات API
# ============================================================

SERVIX_BASE_URL = "https://servix.cc/api/v1"

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


# ============================================================
# نمادهای مورد استفاده
# ============================================================

CURRENCY_SYMBOLS = [
    ("USD", "دلار آمریکا"),
    ("EUR", "یورو"),
    ("GBP", "پوند انگلیس"),
    ("AED", "درهم امارات"),
    ("CNY", "یوان چین"),
    ("TRY", "لیر ترکیه"),
]


GOLD_SYMBOLS = [
    ("18K", "طلای ۱۸ عیار"),
    ("24K", "طلای ۲۴ عیار"),
    ("MES", "مثقال طلا"),
]


COIN_SYMBOLS = [
    ("SEK", "سکه امامی"),
    ("AZ", "سکه بهار آزادی"),
    ("1/2", "نیم سکه"),
    ("1/4", "ربع سکه"),
]


# ============================================================
# تبدیل اعداد به فارسی
# ============================================================

EN_TO_FA_DIGITS = str.maketrans(
    "0123456789",
    "۰۱۲۳۴۵۶۷۸۹"
)


def to_fa_digits(text):
    """تبدیل اعداد انگلیسی به اعداد فارسی."""
    return str(text).translate(EN_TO_FA_DIGITS)


def fa_number(value):
    """فرمت قیمت‌های ریالی."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "نامشخص"

    return to_fa_digits(
        f"{value:,.0f}"
    )


def fa_change_number(value):
    """فرمت مقدار تغییر قیمت."""

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "۰"

    if abs(value) >= 100:
        text = f"{value:+,.0f}"
    else:
        text = f"{value:+,.2f}"

    return to_fa_digits(text)


# ============================================================
# دریافت قیمت‌ها از Servix
# ============================================================

def get_all_prices():
    """
    دریافت تمام قیمت‌های مورد نیاز از Servix.

    همه نمادهای مورد نیاز در یک درخواست دریافت می‌شوند.
    """

    codes = [
        "USD",
        "EUR",
        "GBP",
        "AED",
        "CNY",
        "TRY",
        "18K",
        "24K",
        "MES",
        "SEK",
        "AZ",
        "1/2",
        "1/4",
    ]

    url = f"{SERVIX_BASE_URL}/assets"

    params = {
        "codes": ",".join(codes)
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# مدیریت تاریخچه قیمت
# ============================================================

def load_previous_prices():
    """خواندن قیمت‌های اجرای قبلی."""

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
    """ذخیره قیمت‌های فعلی به‌صورت امن."""

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
# پیدا کردن نماد
# ============================================================

def find_by_symbol(items, symbol):
    """پیدا کردن نماد در پاسخ Servix."""

    if isinstance(items, dict):
        item = items.get(symbol)

        if isinstance(item, dict):
            return item

    for item in items or []:

        if not isinstance(item, dict):
            continue

        if item.get("symbol") == symbol:
            return item

        if item.get("code") == symbol:
            return item

    return None


# ============================================================
# استخراج لیست دارایی‌ها
# ============================================================

def extract_items(data):
    """
    تبدیل پاسخ‌های مختلف API به یک لیست واحد.

    بسته به ساختار پاسخ API ممکن است داده‌ها
    داخل assets / data / results باشند.
    """

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in (
        "assets",
        "data",
        "results",
        "items"
    ):
        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            return value

    return data


# ============================================================
# استخراج قیمت
# ============================================================

def extract_price(item):
    """استخراج قیمت از آبجکت Servix."""

    if not isinstance(item, dict):
        return None

    for key in (
        "price",
        "value",
        "last",
        "lastPrice",
        "currentPrice"
    ):
        value = item.get(key)

        if value is not None:
            return value

    return None


# ============================================================
# تشخیص تغییر قیمت
# ============================================================

def get_price_change(
    symbol,
    current_price,
    previous_prices
):
    """
    مقایسه قیمت فعلی با اجرای قبلی.

    خروجی:

        ("up", change)
        ("down", change)
        ("same", 0)
        (None, None)
    """

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
    previous_prices
):
    """نمایش تغییر قیمت."""

    direction, change = get_price_change(
        symbol,
        current_price,
        previous_prices
    )

    if direction == "up":

        return (
            f"  🟢 "
            f"(<b>{fa_change_number(change)}</b>)"
        )

    if direction == "down":

        return (
            f"  🔴 "
            f"(<b>{fa_change_number(change)}</b>)"
        )

    return ""


# ============================================================
# تاریخ و ساعت تهران
# ============================================================

def jalali_date():
    """تاریخ شمسی ایران."""

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
    """ساعت تهران."""

    tehran_now = datetime.now(
        TEHRAN_TZ
    )

    return to_fa_digits(
        tehran_now.strftime("%H:%M")
    )


# ============================================================
# ساخت ردیف قیمت
# ============================================================

def render_price_row(
    symbol,
    label,
    items,
    current_prices,
    previous_prices
):
    """ساخت یک ردیف قیمت."""

    item = find_by_symbol(
        items,
        symbol
    )

    if not item:
        print(
            f"هشدار: نماد {symbol} پیدا نشد."
        )
        return None

    price = extract_price(item)

    if price is None:
        print(
            f"هشدار: قیمت {symbol} پیدا نشد."
        )
        return None

    # ذخیره قیمت فعلی
    current_prices[symbol] = price

    # تغییر قیمت
    change_html = trend_html(
        symbol,
        price,
        previous_prices
    )

    price_text = fa_number(
        price
    )

    # --------------------------------------------------------
    # واحد
    # --------------------------------------------------------

    unit = item.get(
        "unit",
        "تومان"
    )

    # اگر API ریال برگرداند،
    # آن را به تومان تبدیل نمی‌کنیم مگر اینکه
    # خود API unit را مشخص کرده باشد.
    row = (
        f"▫️ {label}: "
        f"<b>{price_text}</b> "
        f"{unit}"
        f"{change_html}"
    )

    return row


# ============================================================
# ساخت بخش
# ============================================================

def render_section(
    title,
    icon,
    symbol_list,
    items,
    current_prices,
    previous_prices
):
    """ساخت یک بخش مثل ارز، طلا یا سکه."""

    rows = []

    for symbol, label in symbol_list:

        row = render_price_row(
            symbol=symbol,
            label=label,
            items=items,
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

    # --------------------------------------------------------
    # دریافت اطلاعات
    # --------------------------------------------------------

    data = get_all_prices()

    previous_prices = load_previous_prices()

    current_prices = {}

    items = extract_items(data)

    blocks = []

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    blocks.append(
        "💹 <b>نبض بازار</b>\n"
        f"🗓 {jalali_date()}  •  "
        f"⏱ {tehran_time()}"
    )

    # --------------------------------------------------------
    # ارز
    # --------------------------------------------------------

    currency_block = render_section(
        title="ارز",
        icon="💵",
        symbol_list=CURRENCY_SYMBOLS,
        items=items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if currency_block:
        blocks.append(
            currency_block
        )

    # --------------------------------------------------------
    # طلا
    # --------------------------------------------------------

    gold_block = render_section(
        title="طلا",
        icon="🥇",
        symbol_list=GOLD_SYMBOLS,
        items=items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if gold_block:
        blocks.append(
            gold_block
        )

    # --------------------------------------------------------
    # سکه
    # --------------------------------------------------------

    coin_block = render_section(
        title="سکه",
        icon="🪙",
        symbol_list=COIN_SYMBOLS,
        items=items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if coin_block:
        blocks.append(
            coin_block
        )

    # --------------------------------------------------------
    # خط پایانی
    # --------------------------------------------------------

    blocks.append(
        "──────────────\n"
        f"📡 {CHANNEL_USERNAME}"
    )

    # --------------------------------------------------------
    # ذخیره قیمت‌های فعلی
    # --------------------------------------------------------

    save_current_prices(
        current_prices
    )

    return "\n\n".join(
        blocks
    )


# ============================================================
# ارسال پیام به تلگرام
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

    print(
        "پیام با موفقیت ارسال شد."
    )


# ============================================================
# نمایش نمادهای API
# ============================================================

def list_all_symbols():

    data = get_all_prices()

    items = extract_items(data)

    print(
        f"\n=== نمادهای دریافت‌شده "
        f"({len(items)}) ==="
    )

    for item in items:

        if not isinstance(item, dict):
            continue

        symbol = (
            item.get("symbol")
            or item.get("code")
        )

        name = (
            item.get("name")
            or item.get("name_en")
        )

        price = extract_price(item)

        print(
            f"symbol={symbol!r} "
            f"name={name!r} "
            f"price={price!r}"
        )


# ============================================================
# اجرای برنامه
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # دستور list
    # --------------------------------------------------------

    if (
        len(sys.argv) > 1
        and sys.argv[1] == "list"
    ):

        try:

            list_all_symbols()

        except requests.RequestException as error:

            print(
                f"خطا در دریافت اطلاعات API: {error}"
            )

            sys.exit(1)

    # --------------------------------------------------------
    # اجرای عادی
    # --------------------------------------------------------

    else:

        try:

            message = build_message()

            print(
                "\n" + message
            )

            send_to_telegram(
                message
            )

        except requests.RequestException as error:

            print(
                f"خطا در دریافت اطلاعات از API: {error}"
            )

            sys.exit(1)

        except Exception as error:

            print(
                f"خطای غیرمنتظره: {error}"
            )

            sys.exit(1)
