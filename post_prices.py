"""
ربات ارسال قیمت دلار، یورو، طلا، سکه و کریپتو به کانال تلگرام

منبع قیمت‌ها:
    brsapi.ir

اجرا:
    python post_prices.py

برای مشاهده تمام نمادهای API:
    python post_prices.py list

Environment Variables:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    BRSAPI_KEY

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
BRSAPI_KEY = os.environ.get("BRSAPI_KEY")


if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not BRSAPI_KEY:
    print(
        "خطا: یکی از متغیرهای زیر تنظیم نشده است:\n"
        "TELEGRAM_BOT_TOKEN\n"
        "TELEGRAM_CHAT_ID\n"
        "BRSAPI_KEY"
    )
    sys.exit(1)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "last_prices.json"
)


# نام کانال
CHANNEL_USERNAME = "@LivePriceCurrency"


# ============================================================
# نمادهای مورد استفاده
# ============================================================

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


# سکه یک گرمی عمداً حذف شده است.
COIN_SYMBOLS = [
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
    """
    فرمت قیمت‌های معمولی.

    مثال:
        1025000 -> ۱,۰۲۵,۰۰۰
    """

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "نامشخص"

    return to_fa_digits(
        f"{value:,.0f}"
    )


def fa_change_number(value):
    """
    فرمت مقدار تغییر قیمت.

    مثال:
        2500 -> +۲,۵۰۰
        -700 -> -۷۰۰
    """

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "۰"

    if abs(value) >= 100:
        text = f"{value:+,.0f}"
    else:
        text = f"{value:+,.2f}"

    return to_fa_digits(text)


def fa_crypto_number(value):
    """
    فرمت قیمت ارز دیجیتال.

    اعداد بزرگ:
        117500 -> ۱۱۷,۵۰۰

    اعداد کوچک:
        3.10 -> ۳.۱۰
    """

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "نامشخص"

    if abs(value) >= 100:
        text = f"{value:,.0f}"
    else:
        text = f"{value:,.2f}"

    return to_fa_digits(text)


# ============================================================
# دریافت قیمت‌ها از API
# ============================================================

def get_all_prices():
    """دریافت تمام قیمت‌ها از BRS API."""

    url = (
        "https://Api.BrsApi.ir/Market/Gold_Currency.php"
        f"?key={BRSAPI_KEY}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15
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
    """
    ذخیره قیمت‌های فعلی به‌صورت امن.
    """

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
    """پیدا کردن یک نماد در لیست API."""

    for item in items or []:

        if item.get("symbol") == symbol:
            return item

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
    """
    نمایش تغییر قیمت.

    افزایش:
        🟢 (+۲,۵۰۰)

    کاهش:
        🔴 (-۷۰۰)

    بدون تغییر:
        چیزی نمایش داده نمی‌شود.
    """

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
    previous_prices,
    is_usd=False,
    is_crypto=False
):
    """
    ساخت یک ردیف قیمت.

    مثال:

    ▫️ دلار آمریکا: ۱۰۲,۵۰۰ تومان 🟢 (+۲,۵۰۰)
    """

    item = find_by_symbol(
        items,
        symbol
    )

    if not item:
        return None, None

    price = item.get("price")

    if price is None:
        return None, None

    # ذخیره قیمت فعلی
    current_prices[symbol] = price

    # تغییر قیمت
    change_html = trend_html(
        symbol,
        price,
        previous_prices
    )

    # --------------------------------------------------------
    # قیمت‌های دلاری
    # --------------------------------------------------------

    if is_usd or is_crypto:

        if is_crypto:
            price_text = fa_crypto_number(
                price
            )
        else:
            price_text = fa_number(
                price
            )

        row = (
            f"▫️ {label}: "
            f"<b>{price_text}</b> دلار"
            f"{change_html}"
        )

    # --------------------------------------------------------
    # قیمت‌های تومانی
    # --------------------------------------------------------

    else:

        price_text = fa_number(
            price
        )

        unit = item.get(
            "unit",
            "تومان"
        )

        row = (
            f"▫️ {label}: "
            f"<b>{price_text}</b> "
            f"{unit}"
            f"{change_html}"
        )

    direction, _ = get_price_change(
        symbol,
        price,
        previous_prices
    )

    return row, direction


# ============================================================
# ساخت یک بخش
# ============================================================

def render_section(
    title,
    icon,
    symbol_list,
    items,
    current_prices,
    previous_prices,
    is_usd=False,
    is_crypto=False
):
    """ساخت یک بخش مثل ارز، طلا، سکه یا کریپتو."""

    rows = []
    directions = []

    for symbol, label in symbol_list:

        row, direction = render_price_row(
            symbol=symbol,
            label=label,
            items=items,
            current_prices=current_prices,
            previous_prices=previous_prices,
            is_usd=is_usd,
            is_crypto=is_crypto
        )

        if row:
            rows.append(row)

        if direction in (
            "up",
            "down"
        ):
            directions.append(
                direction
            )

    if not rows:
        return "", directions

    block = (
        f"{icon} <b>{title}</b>\n"
        + "\n".join(rows)
    )

    return block, directions


# ============================================================
# خلاصه وضعیت بازار
# ============================================================

def market_summary(directions):
    """
    نمایش وضعیت کلی بازار.
    """

    up_count = directions.count(
        "up"
    )

    down_count = directions.count(
        "down"
    )

    if up_count == 0 and down_count == 0:
        return "⏺ <b>بازار بدون تغییر</b>"

    up_text = to_fa_digits(
        up_count
    )

    down_text = to_fa_digits(
        down_count
    )

    if up_count > down_count:

        return (
            "📈 <b>بازار صعودی</b>"
            f"  ·  🟢 {up_text}"
            f"  ·  🔴 {down_text}"
        )

    if down_count > up_count:

        return (
            "📉 <b>بازار نزولی</b>"
            f"  ·  🟢 {up_text}"
            f"  ·  🔴 {down_text}"
        )

    return (
        "↔️ <b>بازار متعادل</b>"
        f"  ·  🟢 {up_text}"
        f"  ·  🔴 {down_text}"
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

    currency_items = data.get(
        "currency",
        []
    )

    gold_items = data.get(
        "gold",
        []
    )

    crypto_items = data.get(
        "cryptocurrency",
        []
    )

    all_directions = []

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

    currency_block, currency_directions = render_section(
        title="ارز",
        icon="💵",
        symbol_list=CURRENCY_SYMBOLS,
        items=currency_items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if currency_block:

        blocks.append(
            currency_block
        )

    all_directions.extend(
        currency_directions
    )

    # --------------------------------------------------------
    # طلا
    # --------------------------------------------------------

    gold_block, gold_directions = render_section(
        title="طلا",
        icon="🥇",
        symbol_list=GOLD_SYMBOLS,
        items=gold_items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if gold_block:

        blocks.append(
            gold_block
        )

    all_directions.extend(
        gold_directions
    )

    # --------------------------------------------------------
    # سکه
    # --------------------------------------------------------

    coin_block, coin_directions = render_section(
        title="سکه",
        icon="🪙",
        symbol_list=COIN_SYMBOLS,
        items=gold_items,
        current_prices=current_prices,
        previous_prices=previous_prices
    )

    if coin_block:

        blocks.append(
            coin_block
        )

    all_directions.extend(
        coin_directions
    )

    # --------------------------------------------------------
    # کریپتو
    # --------------------------------------------------------

    crypto_block, crypto_directions = render_section(
        title="کریپتو",
        icon="₿",
        symbol_list=CRYPTO_SYMBOLS,
        items=crypto_items,
        current_prices=current_prices,
        previous_prices=previous_prices,
        is_crypto=True
    )

    if crypto_block:

        blocks.append(
            crypto_block
        )

    all_directions.extend(
        crypto_directions
    )

    # --------------------------------------------------------
    # خلاصه بازار
    # --------------------------------------------------------

    if all_directions:

        blocks.insert(
            1,
            market_summary(
                all_directions
            )
        )

    # --------------------------------------------------------
    # خط پایانی و نام کانال
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
# نمایش تمام نمادهای API
# ============================================================

def list_all_symbols():
    """
    نمایش تمام نمادهای موجود در API.

    اجرا:

        python post_prices.py list
    """

    data = get_all_prices()

    sections = [
        ("ارز", "currency"),
        ("طلا و سکه", "gold"),
        ("ارز دیجیتال", "cryptocurrency")
    ]

    for section_name, section_key in sections:

        items = data.get(
            section_key,
            []
        )

        print(
            f"\n=== {section_name} "
            f"({len(items)} نماد) ==="
        )

        for item in items:

            symbol = item.get(
                "symbol"
            )

            name = (
                item.get("name")
                or item.get("name_en")
            )

            print(
                f"  symbol={symbol!r} "
                f"name={name}"
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
