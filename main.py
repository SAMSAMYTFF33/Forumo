import os
TOKEN = "8872823199:AAGlOZmzYOb9C3esalQBsWW9I32HkV5BBkI"
BOT_USERNAME = "NOP3bot"

ADMIN_IDS = [123456789]
POINTS_ADMIN_ID = 7638322813

OWNER_IDS = [POINTS_ADMIN_ID, 8676850552]


def is_owner(user_id: int) -> bool:
    """يتحقق مما إذا كان المستخدم أحد مالكي البوت (OWNER_IDS)."""
    return user_id in OWNER_IDS


# --------------------------------------------------------------------------- 
# 👨‍💻 نظام إدارة المشرفين (Moderators) — مستقل عن OWNER_IDS الثابتة في الكود.
# يسمح لمالك البوت بإضافة/حذف مشرفين ديناميكيًا من داخل البوت نفسه، وتحديد
# صلاحيات دقيقة لكل مشرف على حدة (تُخزَّن في Firestore ضمن bot_moderators).
# ---------------------------------------------------------------------------

MODERATOR_PERMISSIONS = {
    "add_admins": "➕ إضافة مشرفين جدد",
    "delete_giveaways": "🎁 حذف السحوبات",
    "delete_contests": "🏁 حذف المسابقات",
    "delete_quick_roulette": "⚡ حذف السحب السريع",
    "manage_users": "👥 إدارة المستخدمين (حظر/فك حظر)",
    "manage_subscription": "📢 إدارة الاشتراك الإجباري",
    "manage_points": "💰 إدارة قسم الربح",
    "broadcast": "📣 الإذاعة",
}


def _moderator_doc_ref(user_id: int):
    """⚡ موحَّد الآن: يشير لنفس مستند المستخدم users/{id} بدل مجموعة
    bot_moderators منفصلة (انظر قسم «مستند المستخدم الموحّد» بالأسفل)."""
    return _user_doc_ref(user_id)


def _invalidate_moderator_cache(user_id: int = None) -> None:
    """يُفرغ كاش المستخدم الموحّد (_USER_CACHE) — لمستخدم واحد عند تمرير
    user_id، أو بالكامل إن لم يُمرَّر (أبسط وأضمن عند حذف مشرف)."""
    if user_id is None:
        _USER_CACHE.clear()
    else:
        _USER_CACHE.pop(user_id, None)


def get_moderator(user_id: int):
    """يعيد بيانات المشرف (FSRow) أو None إن لم يكن مشرفًا مسجّلًا.

    ⚡ موحَّد: بيانات الإشراف أصبحت حقولًا (is_moderator/mod_*) داخل نفس
    مستند المستخدم users/{id}، وتُقرأ عبر نفس الكاش الدائم بالذاكرة
    (_USER_CACHE) المستخدم أيضًا للحظر/النقاط/الإحالة — أي قراءة واحدة
    فعلية من Firestore لكل مستخدم طوال عمر التشغيلة، بدل قراءة منفصلة من
    مجموعة bot_moderators مع كل تحديث يصل للبوت كما كان سابقًا."""
    row = get_bot_user(user_id)
    if not row or not row.get("is_moderator"):
        return None
    data = dict(row)
    data["permissions"] = data.get("mod_permissions") or {}
    data["added_by"] = data.get("mod_added_by")
    data["added_at"] = data.get("mod_added_at")
    return FSRow(data)


def is_moderator(user_id: int) -> bool:
    """يتحقق مما إذا كان المستخدم مشرفًا مسجّلًا (بغض النظر عن صلاحياته)."""
    return get_moderator(user_id) is not None


def list_moderators() -> list:
    """يعيد كل المشرفين المسجَّلين، الأحدث إضافةً أولًا. (استعلام واحد على
    مستند users بشرط is_moderator == True، بدل مجموعة bot_moderators)."""
    docs = fs_db().collection("users").where("is_moderator", "==", True).stream()
    rows = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.setdefault("user_id", int(doc.id))
        data["permissions"] = data.get("mod_permissions") or {}
        data["added_at"] = data.get("mod_added_at")
        rows.append(FSRow(data))
    rows.sort(key=lambda r: r.get("added_at") or "", reverse=True)
    return rows


def add_moderator(user_id: int, added_by: int, username: str = None, first_name: str = None) -> None:
    """يضيف مشرفًا جديدًا بصلاحيات فارغة (كلها معطّلة افتراضيًا). يعمل حتى
    مع مستخدم لم يبدأ محادثة مع البوت من قبل — merge=True ينشئ مستند
    users/{id} إن لم يكن موجودًا، دون المساس بأي حقول أخرى إن كان موجودًا."""
    _user_doc_ref(user_id).set({
        "user_id": user_id,
        "is_moderator": True,
        "mod_username": username or "",
        "mod_first_name": first_name or "",
        "mod_added_by": added_by,
        "mod_added_at": datetime.now(timezone.utc).isoformat(),
        "mod_permissions": {key: False for key in MODERATOR_PERMISSIONS},
    }, merge=True)
    _invalidate_moderator_cache(user_id)


def remove_moderator(user_id: int) -> None:
    """يزيل صفة الإشراف عن مستخدم (بقية بياناته — الحظر/النقاط/الإحالة —
    تبقى محفوظة في نفس المستند الموحّد، فقط حقول الإشراف تُطفأ)."""
    _user_doc_ref(user_id).set({
        "is_moderator": False,
        "mod_permissions": {},
    }, merge=True)
    _invalidate_moderator_cache(user_id)


def set_moderator_permission(user_id: int, perm_key: str, value: bool) -> None:
    """يفعّل/يعطّل صلاحية واحدة لدى مشرف معيّن."""
    _user_doc_ref(user_id).set({"mod_permissions": {perm_key: value}}, merge=True)
    _invalidate_moderator_cache(user_id)


def moderator_can(user_id: int, perm_key: str) -> bool:
    """يتحقق مما إذا كان المستخدم يملك صلاحية معيّنة — مالك البوت يملك كل
    الصلاحيات دائمًا، وأي مستخدم آخر يُفحص عبر سجل المشرفين في Firestore."""
    if is_owner(user_id):
        return True
    row = get_moderator(user_id)
    if not row:
        return False
    return bool(row.get("permissions", {}).get(perm_key))


REQUIRED_CHANNEL_USERNAME = "w33lv"
REQUIRED_CHANNEL_URL = "https://t.me/w33lv"
REQUIRED_CHANNEL_BUTTON_TEXT = "VORTEX  𓏺"
REQUIRED_CHANNEL_DEFAULT_TARGET = "1000"

# أسماء افتراضية احترافية تُعرض على أزرار قنوات الاشتراك الإجباري عندما لا
# يكون قد تم تعيين اسم مخصّص (button_text) لها بعد من قسم إدارة الاشتراك
# الإجباري. تُستخدم كبديل عن عرض "الاشتراك في @username" الخام (غير احترافي).
# يمكن إضافة أي قناة أخرى هنا بنفس الطريقة: "username": "الاسم المطلوب".
REQUIRED_CHANNEL_DEFAULT_LABELS = {
    "w33lv": REQUIRED_CHANNEL_BUTTON_TEXT,
    "e_ggf": "𝐑𝐎𝐔𝐋𝐄𝐓𝐓𝐄 𝐕𝐎𝐑𝐓𝐄𝐗",
}

FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", "vortex-d8c4d")
FIREBASE_PRIVATE_KEY_ID = os.environ.get("FIREBASE_PRIVATE_KEY_ID", "fd74b425cfab1dfaaa8ec8523b203ee0966cd54b")
FIREBASE_CLIENT_EMAIL = os.environ.get("FIREBASE_CLIENT_EMAIL", "firebase-adminsdk-fbsvc@vortex-d8c4d.iam.gserviceaccount.com")
FIREBASE_CLIENT_ID = os.environ.get("FIREBASE_CLIENT_ID", "117685275264885485415")

FIREBASE_CLIENT_CERT_URL = os.environ.get(
    "FIREBASE_CLIENT_CERT_URL",
    f"https://www.googleapis.com/robot/v1/metadata/x509/{FIREBASE_CLIENT_EMAIL.replace('@', '%40')}"
)

# قراءة المفتاح الخاص حصراً من متغيرة البيئة
_raw_private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "")

if "\\n" in _raw_private_key and "\n" not in _raw_private_key:
    _raw_private_key = _raw_private_key.replace("\\n", "\n")

FIREBASE_SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": FIREBASE_PROJECT_ID,
    "private_key_id": FIREBASE_PRIVATE_KEY_ID,
    "private_key": _raw_private_key,
    "client_email": FIREBASE_CLIENT_EMAIL,
    "client_id": FIREBASE_CLIENT_ID,
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": FIREBASE_CLIENT_CERT_URL,
    "universe_domain": "googleapis.com",
}


import asyncio
import json
import logging
import random
import secrets
import sqlite3
import threading
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_boot_logger = logging.getLogger("contest_bot.bootstrap")

try:
    import apscheduler
except ImportError:
    _boot_logger.warning("مكتبة JobQueue غير مثبّتة — جارٍ تثبيتها تلقائيًا الآن (مرة واحدة فقط)...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--quiet",
            "python-telegram-bot[job-queue]",
        ])
        _boot_logger.warning(
            "تم تثبيت المكتبة بنجاح! سيتابع البوت الإقلاع الآن مباشرة بدون الحاجة لإعادة "
            "التشغيل يدويًا (وإن ظهر خطأ JobQueue رغم هذا، أعد تشغيل السكربت مرة واحدة)."
        )
    except Exception as _exc:
        _boot_logger.error(
            "فشل التثبيت التلقائي (%s). ثبّت يدويًا عبر: "
            "pip install \"python-telegram-bot[job-queue]\" ثم أعد التشغيل.",
            _exc,
        )

try:
    import firebase_admin
except ImportError:
    _boot_logger.warning("مكتبة firebase-admin غير مثبّتة — جارٍ تثبيتها تلقائيًا الآن (مرة واحدة فقط)...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--quiet", "firebase-admin",
        ])
        _boot_logger.warning("تم تثبيت firebase-admin بنجاح! يتابع البوت الإقلاع الآن مباشرة.")
    except Exception as _exc:
        _boot_logger.error(
            "فشل التثبيت التلقائي لـ firebase-admin (%s). ثبّت يدويًا عبر: "
            "pip install firebase-admin ثم أعد التشغيل.",
            _exc,
        )

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger("contest_bot")

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQueryResultArticle,
    InputTextMessageContent,
    SwitchInlineQueryChosenChat,
    MessageEntity,
    CopyTextButton,
    LabeledPrice,
    BotCommand,
    LinkPreviewOptions,
)
from telegram.error import RetryAfter, BadRequest, Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    TypeHandler,
    ApplicationHandlerStop,
    filters,
)
from telegram.request import HTTPXRequest

DEFAULT_POINTS_TITLE = "🎁 ربح من البوت"
DEFAULT_POINTS_CONDITIONS = (
    "الربح يكون فقط من قسم «إنشاء سحب».\n"
    "كل مستخدم جديد يجتاز منع الرشق ويشارك في السحب يمنح صاحب السحب نقاطًا مرة واحدة فقط."
)
TECH_SUPPORT_USERNAME = "y66vlBOT"
SUPPORT_BOT_STARS_AMOUNT = 5

# ---------------------------------------------------------------------------
# ⭐ نظام سحب النجوم (Stars Withdrawal Tiers) — قيم سحب ثابتة (15/30/50/100/
# 200/500/1000 نجمة)، كل قيمة لها تكلفة نقاط مستقلة يتحكم بها المالك بالكامل
# من داخل البوت (star_cost_<tier> في settings) دون الحاجة لتعديل الكود.
# القيم الافتراضية أدناه تُستخدم فقط أول مرة (init_db) أو إن حُذف الإعداد.
# ---------------------------------------------------------------------------
STAR_WITHDRAW_TIERS = [15, 30, 50, 100, 200, 500, 1000]
DEFAULT_STAR_COSTS = {
    15: 150,
    30: 300,
    50: 500,
    100: 1000,
    200: 2000,
    500: 5000,
    1000: 10000,
}

BRAND_NAME = "𝚁𝙾𝚄𝙻𝙴𝚃𝚃𝙴 𝚅𝙾𝚁𝚃𝙴𝚇"
BRAND_URL = "https://t.me/NOP3BOT"

GIVEAWAYS_LINK_TEXT = "السحوبات"
GIVEAWAYS_CHANNEL_URL = "https://t.me/n_bbo"

ANNOUNCE_CHANNEL_USERNAME = "n_bbo"
ANNOUNCE_CHANNEL_URL = "https://t.me/n_bbo"
ANNOUNCE_CHANNEL_CHAT_ID = f"@{ANNOUNCE_CHANNEL_USERNAME}"


ROULETTE_COUNTS = [5, 10, 15, 20, 25, 30, 50, 100]

DEFAULT_HIDE_PARTICIPANTS = "1"
DEFAULT_GAME_CLICHE = f"أهلا وسهلا بكم في {BRAND_NAME}"

ROULETTE_THUMBS = {
    n: f"https://wsrv.nl/?url=raw.githubusercontent.com/SAMSAMYTFF33/WEB/main/assets/Number{n}.png&w=100&h=100&output=jpg&q=60&v=2" for n in ROULETTE_COUNTS
}

EMOJI = {
    "trophy_create_draw": "5429387503129875330",
    "roulette": "5102856631562011824",
    "draws_check": "5843596438373667352",
    "chart": "5940378308003762340",
    "doc": "5334882760735598374",
    "remind_check": "5954244021508380732",
    "star": "5346309121794659890",
    "tech": "5814558770075803439",
    "trophy_contest": "5789577921727307070",
    "gear": "5341715473882955310",
    "hand": "5940774295398521609",
    "buoy": "6008036485436022431",
    "arrow_down": "5208903445729266755",
    "remind_on": "5206607081334906820",
    "remind_off": "5210952531676504517",
    "hide_participants_btn": "5332724926216428039",
    "cliche_btn": "5841360920781002031",
    "restore_defaults_btn": "6012661228910939253",
    "back_section_btn": "6039539366177541657",
    "register_plus": "5226945370684140473",
    "target_pin": "5310278924616356636",
    "num_one": "5260562728249996728",
    "num_two": "5260273822979863490",
    "pin_note": "5769520351440540688",
    "arrow_left": "5769534112515756980",
    "envelope_klesha": "5406631276042002796",
    "new_badge": "5895669571058142797",
    "end_question": "5208748474719293821",
    "alarm_clock": "5208413342716153772",
    "votes_chart_btn": "5429651785352501917",
    "alarm_clock_btn": "6217487596486922033",
    "people": "5769289664452104963",
    "bullet_point": "5769338979266597469",
    "target": "5965522064461799191",
    "party": "5370870691140737817",
    "medal": "5789703004059868939",
    "trophy_win": "5789577921727307070",
    "alarm_clock_title": "5215394081911351762",
    "time_option_btn": "5764762214871343251",
    "time_manual_btn": "6046294958892129907",
    "time_custom_btn": "5850317551090800862",
    "back_time_menu_btn": "5390885122775985914",
    "trophy_winners_title": "5429387503129875330",
    "back_winners_btn": "6039539366177541657",
    "confirm_check": "5429381339851796035",
    "notify_win_btn": "5458603043203327669",
    "no_btn": "5954244021508380732",
    "announce_results_btn": "5789428375261023681",
    "approve_participants_label_btn": "6026257381678124710",
    "yes_btn": "5852544431504234283",
    "premium_vote_btn": "5942584147372413048",
    "publish_btn": "5258332798409783582",
    "join_accept_btn": "5767193595857606245",
    "withdraw_btn": "5967594648175121607",
    "sub_laptop": "5769469013696451511",
    "sub_alert": "5769630100739854545",
    "sub_check": "5767193595857606245",
    "recent_contests_btn": "5213334816891631245",
    "seats_change_btn": "5429651785352501917",
    "pause_toggle_btn": "5852544431504234283",
    "edit_settings_refresh_btn": "6012661228910939253",
    "remove_contestant_btn": "5967594648175121607",
    "delete_all_btn": "5913597928487784523",
    "cross_flag_off": "5954244021508380732",
    "check_flag_on": "5429381339851796035",
    "num_three": "5260650672000348972",
    "num_four": "5260544569128269433",
    "num_five": "5260655426529146332",
    "num_six": "5260604105964926035",
    "gw_condition_channel": "6039381989985882045",
    "gw_vote_icon": "5895428924040548238",
    "gw_new_participant": "6032994772321309200",
    "gw_view_profile": "5904630315946611415",
    "gw_kick_btn": "5240241223632954241",
    "gw_atime_lightning": "5965286318001889755",
    "gw_atime_clock": "5852614259082530343",
}

CAPTCHA_EMOJIS = [
    "5402477260982731644",
    "5449449325434266744",
    "5438496463044752972",
    "5456140674028019486",
    "5447410659077661506",
    "5453976908159016299",
    "5454206993852029667",
    "5253984341591076047",
    "5253861243533406038",
    "5408850391154569842",
    "5019726470101075726",
    "5145427681680032825",
]

CAPTCHA_OPTIONS_COUNT = 3
CAPTCHA_SESSION_TTL_SECONDS = 10 * 60

CONTEST_TIME_OPTIONS = [
    [(5, "بعد 5 دقايق"), (1, "بعد 1 دقيقة")],
    [(30, "بعد 30 دقيقة"), (60, "بعد 1 ساعة")],
    [(120, "بعد 2 ساعات"), (180, "بعد 3 ساعات")],
    [(240, "بعد 4 ساعات"), (300, "بعد 5 ساعات")],
    [(360, "بعد 6 ساعات"), (720, "بعد 12 ساعات")],
    [(1440, "بعد 24 ساعة"), (2880, "بعد 48 ساعات")],
    [(4320, "بعد 3 ايام"), (10080, "بعد 1 اسبوع")],
]

def _build_single_back_keyboard(text: str, callback_data: str, style: str, emoji_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text, callback_data=callback_data,
            style=style, **emoji_kwargs(emoji_key),
        )],
    ])


def build_text_with_emojis(parts) -> tuple:
    """
    تقوم ببناء النص والكيانات (entities) لدعم التنسيقات المتداخلة:
    - كيان CUSTOM_EMOJI للإيموجيات المخصصة.
    - كيان TEXT_MENTION للإشارة إلى مستخدم (عبر user object).
    - كيان TEXT_LINK لإنشاء اسم أزرق قابل للضغط (باستخدام tg://user?id=).
    - كيان BOLD للخط العريض.
    - كيان BLOCKQUOTE للاقتباس الجانبي مع علامة ”.
    جميع الكيانات يمكن دمجها داخل بعضها (مثلاً اسم أزرق داخل اقتباس).
    """
    text = ""
    entities = []

    def add_bold(start_offset: int, end_offset: int):
        """إضافة كيان عريض للنص مع الحفاظ على الكيانات المتداخلة."""
        if end_offset > start_offset:
            entities.append(MessageEntity(
                type=MessageEntity.BOLD,
                offset=start_offset,
                length=end_offset - start_offset,
            ))

    def append_text(value: str, make_bold: bool = True):
        nonlocal text
        start_offset = len(text.encode("utf-16-le")) // 2
        text += str(value)
        end_offset = len(text.encode("utf-16-le")) // 2
        if make_bold:
            add_bold(start_offset, end_offset)

    def process_part(p, inside_bold: bool = False):
        nonlocal text, entities
        if isinstance(p, tuple):
            if len(p) == 3 and p[1] == "mention":
                display_name, _, user_obj = p
                offset = len(text.encode("utf-16-le")) // 2
                length = len(display_name.encode("utf-16-le")) // 2
                entities.append(MessageEntity(type=MessageEntity.TEXT_MENTION, offset=offset, length=length, user=user_obj))
                text += display_name
                if not inside_bold:
                    add_bold(offset, offset + length)
            elif len(p) == 3 and p[1] == "mention_id":
                display_name, _, user_id = p
                offset = len(text.encode("utf-16-le")) // 2
                length = len(display_name.encode("utf-16-le")) // 2
                entities.append(MessageEntity(type=MessageEntity.TEXT_LINK, offset=offset, length=length, url=f"tg://user?id={user_id}"))
                text += display_name
                if not inside_bold:
                    add_bold(offset, offset + length)
            elif len(p) == 2:
                placeholder, custom_emoji_id = p
                offset = len(text.encode("utf-16-le")) // 2
                length = len(placeholder.encode("utf-16-le")) // 2
                entities.append(MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=offset, length=length, custom_emoji_id=custom_emoji_id))
                text += placeholder
            elif len(p) == 3 and p[1] in ["bold", "blockquote", "italic", "spoiler", "code"]:
                content, ent_type, _ = p
                start_offset = len(text.encode("utf-16-le")) // 2
                if isinstance(content, list):
                    for sub in content:
                        process_part(sub, inside_bold or ent_type == "bold")
                else:
                    append_text(content, make_bold=inside_bold or ent_type != "bold")
                end_offset = len(text.encode("utf-16-le")) // 2
                length = end_offset - start_offset
                t_type = {
                    "bold": MessageEntity.BOLD,
                    "blockquote": MessageEntity.BLOCKQUOTE,
                    "italic": MessageEntity.ITALIC,
                    "spoiler": MessageEntity.SPOILER,
                    "code": MessageEntity.CODE,
                }[ent_type]
                entities.append(MessageEntity(type=t_type, offset=start_offset, length=length))
            elif len(p) == 3 and p[1] == "link":
                content, _, url = p
                start_offset = len(text.encode("utf-16-le")) // 2
                if isinstance(content, list):
                    for sub in content:
                        process_part(sub, inside_bold)
                else:
                    append_text(content, make_bold=not inside_bold)
                end_offset = len(text.encode("utf-16-le")) // 2
                length = end_offset - start_offset
                entities.append(MessageEntity(type=MessageEntity.TEXT_LINK, offset=start_offset, length=length, url=url))
            else:
                append_text(p, make_bold=not inside_bold)
        else:
            append_text(p, make_bold=not inside_bold)

    for part in parts:
        process_part(part)

    return text, entities


def build_brand_giveaways_parts(prefix: str = "• "):
    """يبني جزء الجملة الموحّد: «BRAND_NAME < السحوبات» — يُستخدم في القائمة
    الرئيسية وفي منشورات السحوبات والمسابقات. اسم العلامة رابط أزرق يفتح
    {BRAND_URL}، وكلمة «السحوبات» رابط أزرق عريض يفتح {GIVEAWAYS_CHANNEL_URL}.
    كلا الرابطين يُنشئان معاينة رابط صغيرة تلقائيًا من تيليجرام (صورة القناة)."""
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append((BRAND_NAME, "link", BRAND_URL))
    parts.append(" < ")
    parts.append((GIVEAWAYS_LINK_TEXT, "link", GIVEAWAYS_CHANNEL_URL))
    return parts


def bold_notice(message: str) -> tuple:
    """يبني رسالة تنبيه/تأكيد قصيرة بخط عريض — يُستخدم لتوحيد شكل رسائل النظام في البوت."""
    return build_text_with_emojis([([message], "bold", None)])


def emoji_kwargs(key: str) -> dict:
    value = EMOJI.get(key, "0")
    if value and value != "0":
        return {"icon_custom_emoji_id": value}
    return {}

def build_welcome_message(user) -> tuple:
    """
    رسالة الترحيب بالقائمة الرئيسية.

    كلمة VORTEX داخل الجملة الأولى رابط نصي أزرق قابل للضغط يفتح قناة
    العلامة (BRAND_URL)، وكلمة «السحوبات» رابط نصي أزرق قابل للضغط يفتح
    قناة السحوبات المحددة مسبقًا (GIVEAWAYS_CHANNEL_URL) — مدمجتان داخل
    نص الجملة نفسها بدل عرضهما كسطر منفصل («• ROULETTE VORTEX < السحوبات»)
    أعلى الجملتين. الجملتان قريبتان من بعضهما (سطر واحد بينهما) لتظهرا
    متلاصقتين كما في الصورة المرجعية.
    """
    user_name = user.first_name or user.username or "صديقنا"
    vortex_word = BRAND_NAME.split(" ", 1)[-1]  # "𝚅𝙾𝚁𝚃𝙴𝚇"
    parts = [
        ([
            ("👋", EMOJI["hand"]),
            " : أهلاً بك - ",
            (user_name, "mention", user),
            "\n\n",
            ([
                "روليت ", (vortex_word, "link", BRAND_URL),
                " لإنشاء ", (GIVEAWAYS_LINK_TEXT, "link", GIVEAWAYS_CHANNEL_URL),
                " والمسابقات والروليت السريع",
            ], "blockquote", None),
            "\n",
            ([
                "استمتع وابدأ الآن بالاختيار من القائمة أدناه ",
                ("⏬", EMOJI["arrow_down"]),
            ], "blockquote", None),
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_terms_message() -> tuple:
    """
    رسالة «سياسة الاستخدام والخصوصية»:
    - كامل النص بخط عريض (Bold).
    - السطرين الأخيرين («أي مخالفة = حظر دائم» / «ثقتكم هي أولويتنا») داخل
      اقتباس وردي (Blockquote) منتهي بعلامة ”، تمامًا كما في الصورة المرفقة.
    """
    parts = [
        ([
            ("📜", EMOJI["doc"]),
            " : سياسة الاستخدام والخصوصية",
            "\n\n",
            "ثقتكم هي أولويتنا",
            "\n\n",
            "✅ : المسموح به:\n",
            "├ تنظيم سحوبات حقيقية وواضحة\n",
            "├ تقديم جوائز حقيقية وموثوقة\n",
            "└ احترام جميع المشاركين",
            "\n\n",
            "❌ : الممنوع:\n",
            "├ سحوبات وهمية أو مضللة\n",
            "├ خداع المستخدمين\n",
            "└ التلاعب بالنتائج",
            "\n\n",
            ([
                "🚨 : أي مخالفة = حظر دائم\n",
                "ثقتكم هي أولويتنا",
            ], "blockquote", None),
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_terms_keyboard() -> InlineKeyboardMarkup:
    """كيبورد رسالة الشروط والأحكام: زر «رجوع» أحمر يعيد للقائمة الرئيسية."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "رجوع", callback_data="back_main_menu",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_support_bot_message() -> tuple:
    """رسالة قائمة «دعم البوت» — نفس نص وتنسيق الصورة المرفقة."""
    parts = [
        ([
            ("⭐", EMOJI["star"]),
            " دعم البوت",
        ], "bold", None),
        "\n\n",
        f"ادفع {SUPPORT_BOT_STARS_AMOUNT} نجوم تيليجرام لدعم تطوير البوت 💖",
        "\n\n",
        "كل نجمة تساعدنا في الاستمرار وتطوير ميزات جديدة!",
        "\n\n",
        "👇 اضغط على الزر أدناه للدفع:",
    ]
    return build_text_with_emojis(parts)


def build_support_bot_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"ادفع {SUPPORT_BOT_STARS_AMOUNT} نجوم", callback_data="support_pay_stars",
            style="success", **emoji_kwargs("star"),
        )],
        [InlineKeyboardButton(
            "رجوع", callback_data="back_main_menu",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def get_required_channel_username() -> str:
    """اسم يوزر قناة الاشتراك الإجباري الحالية (بدون @) — قابل للتغيير من قسم المالك."""
    return (get_setting("required_channel_username") or REQUIRED_CHANNEL_USERNAME).lstrip("@")


def get_required_channel_url() -> str:
    """رابط قناة الاشتراك الإجباري الحالية."""
    custom_url = get_setting("required_channel_url")
    if custom_url:
        return custom_url
    return f"https://t.me/{get_required_channel_username()}"


def get_required_channel_next_username() -> str:
    """اسم يوزر القناة التالية (بدون @) التي سيتم التحويل إليها تلقائيًا، أو فارغ إن لم تُحدَّد."""
    return (get_setting("required_channel_next_username") or "").lstrip("@")


def get_required_channel_auto_target() -> int:
    """عدد المشتركين المطلوب للتحويل التلقائي للقناة التالية."""
    raw = get_setting("required_channel_auto_target") or REQUIRED_CHANNEL_DEFAULT_TARGET
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(REQUIRED_CHANNEL_DEFAULT_TARGET)


def _normalize_channel_username(raw: str) -> str:
    """يستخرج اسم اليوزر من نص قد يكون @username أو t.me/username أو مجرد username."""
    value = (raw or "").strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
            break
    value = value.strip().strip("/")
    return value


def _next_required_channel_id() -> int:
    """عدّاد ذري لمعرّفات قنوات الاشتراك الإجباري، بنفس منطق _next_roulette_id."""
    client = fs_db()
    counter_ref = client.collection("counters").document("required_channels")
    transaction = client.transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = counter_ref.get(transaction=transaction)
        current = (snap.to_dict().get("next_id", 0) if snap.exists else 0) or 0
        next_id = current + 1
        transaction.set(counter_ref, {"next_id": next_id})
        return next_id

    return _txn(transaction)


_REQUIRED_CHANNELS_CACHE = {"data": None, "ts": 0.0}
REQUIRED_CHANNELS_CACHE_TTL = 30  # ثانية


def _invalidate_required_channels_cache() -> None:
    """يُفرغ كاش قنوات الاشتراك الإجباري فور أي تعديل (إضافة/تحديث/حذف/نقل)
    حتى لا يرى المالك أو المستخدمون بيانات قديمة بعد أي تغيير من لوحة الإدارة."""
    _REQUIRED_CHANNELS_CACHE["data"] = None
    _REQUIRED_CHANNELS_CACHE["ts"] = 0.0


def create_required_channel(
    username: str, url: str = "", button_text: str = "",
    target_count=None, auto_delete_on_target: bool = False,
    added_by=None,
) -> int:
    """يضيف قناة جديدة لقائمة قنوات الاشتراك الإجباري، ويعيد معرّفها."""
    username = username.lstrip("@")
    channels = get_required_channels()
    max_order = max([c.get("order", 0) for c in channels], default=-1)
    channel_id = _next_required_channel_id()
    fs_db().collection("required_channels").document(str(channel_id)).set({
        "channel_id": channel_id,
        "username": username,
        "url": url or f"https://t.me/{username}",
        "title": "",
        "button_text": button_text or "",
        "enabled": True,
        "order": max_order + 1,
        "target_count": target_count,
        "auto_delete_on_target": bool(auto_delete_on_target),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "added_by": added_by,
    })
    _invalidate_required_channels_cache()
    return channel_id


def get_required_channels(enabled_only: bool = False) -> list:
    """يعيد كل قنوات الاشتراك الإجباري مرتّبة بحسب الترتيب المحفوظ.

    ⚡ هذه الدالة تُستدعى مع كل تفاعل من أي مستخدم (كل زر/رسالة) عبر
    enforce_mandatory_subscription_gate، وكانت تقرأ Firestore مباشرة في كل
    مرة بدون أي كاش — هذا كان السبب الأساسي في استهلاك حصة القراءة اليومية
    بسرعة حتى مع عدد مستخدمين قليل جدًا. الآن تُقرأ من Firestore فعليًا مرة
    واحدة كل REQUIRED_CHANNELS_CACHE_TTL ثانية فقط، وبينهما تُعاد النتيجة
    من الذاكرة مباشرة (كاش) — القائمة نفسها ثابتة عمليًا (لا تتغير إلا من
    لوحة تحكم المالك)، فهذا آمن تمامًا ولا يؤثر على صحة البيانات، مع تفريغ
    فوري للكاش (_invalidate_required_channels_cache) عند أي إضافة/تعديل/حذف/
    نقل من لوحة الإدارة حتى تنعكس التغييرات مباشرة."""
    now = time.time()
    cached = _REQUIRED_CHANNELS_CACHE["data"]
    if cached is not None and now - _REQUIRED_CHANNELS_CACHE["ts"] < REQUIRED_CHANNELS_CACHE_TTL:
        rows = cached
    else:
        docs = fs_db().collection("required_channels").stream()
        rows = []
        for doc in docs:
            data = doc.to_dict() or {}
            data.setdefault("channel_id", int(doc.id))
            rows.append(FSRow(data))
        rows.sort(key=lambda r: (r.get("order", 0), r.get("channel_id", 0)))
        _REQUIRED_CHANNELS_CACHE["data"] = rows
        _REQUIRED_CHANNELS_CACHE["ts"] = now
    if enabled_only:
        return [r for r in rows if r.get("enabled", True)]
    return rows


def get_required_channel(channel_id: int):
    """يعيد بيانات قناة اشتراك إجباري واحدة أو None إن لم توجد."""
    doc = fs_db().collection("required_channels").document(str(channel_id)).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data.setdefault("channel_id", channel_id)
    return FSRow(data)


def update_required_channel(channel_id: int, **fields) -> None:
    """يحدّث حقولاً محددة في قناة اشتراك إجباري (دمج، لا يمس بقية الحقول)."""
    if not fields:
        return
    fs_db().collection("required_channels").document(str(channel_id)).set(fields, merge=True)
    _invalidate_required_channels_cache()


def delete_required_channel(channel_id: int) -> None:
    """يحذف قناة اشتراك إجباري نهائيًا من القائمة."""
    fs_db().collection("required_channels").document(str(channel_id)).delete()
    _invalidate_required_channels_cache()


def move_required_channel(channel_id: int, direction: int) -> bool:
    """يبدّل ترتيب قناة مع جارتها في القائمة (direction=-1 لأعلى، +1 لأسفل).
    يعيد True إن نجح التبديل، أو False إن كانت القناة في أول/آخر القائمة فعلاً."""
    channels = get_required_channels()
    idx = next((i for i, c in enumerate(channels) if c.get("channel_id") == channel_id), None)
    if idx is None:
        return False
    swap_idx = idx + direction
    if swap_idx < 0 or swap_idx >= len(channels):
        return False
    a, b = channels[idx], channels[swap_idx]
    order_a, order_b = a.get("order", 0), b.get("order", 0)
    update_required_channel(a["channel_id"], order=order_b)
    update_required_channel(b["channel_id"], order=order_a)
    return True


def _migrate_legacy_required_channel() -> None:
    """ترحيل تلقائي لمرة واحدة عند أول تشغيل بعد التحديث: تُنقَل قناة الاشتراك
    الإجباري القديمة (وقناة «التالية» إن كانت محددة) من نظام القناة الواحدة
    القديم لتصبح قنوات في قائمة required_channels الجديدة، حتى لا يفقد
    المالك إعداده الحالي أثناء الترقية لنظام القنوات المتعددة."""
    existing = list(fs_db().collection("required_channels").limit(1).stream())
    if existing:
        return
    legacy_username = (get_setting("required_channel_username") or "").lstrip("@")
    if legacy_username:
        create_required_channel(
            username=legacy_username,
            url=get_setting("required_channel_url") or f"https://t.me/{legacy_username}",
            button_text=REQUIRED_CHANNEL_BUTTON_TEXT,
            target_count=None,
            auto_delete_on_target=False,
        )
    legacy_next = (get_setting("required_channel_next_username") or "").lstrip("@")
    if legacy_next:
        create_required_channel(
            username=legacy_next,
            url=f"https://t.me/{legacy_next}",
            target_count=None,
            auto_delete_on_target=False,
        )


def _required_channel_label(ch) -> str:
    """اسم القناة المعروض للمستخدم: العنوان/النص المخصّص إن وُجد، وإلا اسم
    افتراضي احترافي معروف لهذه القناة (REQUIRED_CHANNEL_DEFAULT_LABELS) إن
    وُجد، وإلا يوزرها الخام كحل أخير."""
    username = ch.get("username", "")
    return (
        ch.get("button_text")
        or ch.get("title")
        or REQUIRED_CHANNEL_DEFAULT_LABELS.get(username)
        or ("@" + username)
    )


def build_required_channels_rows(channels: list) -> list:
    """يبني صفًا واحدًا (زر انضمام) لكل قناة من القنوات الممرَّرة — يُستخدم في
    كل بوابات الاشتراك الإجباري (البوابة العامة، بوابة تصويت المسابقة،
    وبوابة شروط السحب) بنفس المنطق بدل تكراره في كل واحدة."""
    rows = []
    for ch in channels:
        username = ch.get("username", "")
        custom_label = (
            ch.get("button_text")
            or ch.get("title")
            or REQUIRED_CHANNEL_DEFAULT_LABELS.get(username)
        )
        title = f"📢 {custom_label}" if custom_label else f"📢 الاشتراك في @{username}"
        url = ch.get("url") or f"https://t.me/{username}"
        rows.append([InlineKeyboardButton(title, url=url, style="primary")])
    return rows


def build_subscription_required_message(missing_channels: list = None, channels_status: list = None) -> tuple:
    """رسالة تطلب من المستخدم الاشتراك في القناة/القنوات قبل استخدام البوت.

    إن مُرِّرت channels_status (قائمة أزواج (channel, subscribed) لكل قنوات
    الاشتراك الإجباري المفعّلة)، تُعرض حالة كل قناة على حدة (✅ مشترك /
    ❌ غير مشترك) — مفيد عندما يكون المستخدم مشتركًا في بعض القنوات وخرج من
    غيرها. وإلا (channels_status غير ممرَّرة) تُعرض القنوات الناقصة فقط،
    كما في السابق."""
    missing_channels = missing_channels or []
    display_rows = channels_status if channels_status is not None else [
        (ch, False) for ch in missing_channels
    ]
    total = len(display_rows)
    label = "القنوات التالية" if total > 1 else "القناة التالية"

    parts = [
        "🔒 ", "خطوة أخيرة قبل استخدام البوت", "\n",
        "\n",
        f"يجب عليك الاشتراك في {label} أولاً:",
    ]
    if display_rows:
        lines = [
            f"{'✅' if ok else '❌'} {_required_channel_label(ch)}"
            for ch, ok in display_rows
        ]
        parts += ["\n", "\n".join(lines)]
    parts += [
        "\n",
        "\n",
        ([
            ("‼️", EMOJI["sub_alert"]),
            " | اشترك في القنوات أعلاه، ثم اضغط ",
            ("✅", EMOJI["sub_check"]),
            " «التحقق من الاشتراك»",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_subscription_required_keyboard(missing_channels: list = None) -> InlineKeyboardMarkup:
    missing_channels = missing_channels or []
    if missing_channels:
        rows = build_required_channels_rows(missing_channels)
    else:
        rows = [[InlineKeyboardButton(
            f"📢 {REQUIRED_CHANNEL_BUTTON_TEXT}", url=get_required_channel_url(), style="primary",
        )]]
    rows.append([InlineKeyboardButton(
        "✅ التحقق من الاشتراك", callback_data="check_sub_status", style="success",
    )])
    return InlineKeyboardMarkup(rows)


_SUBSCRIPTION_CACHE = {}
SUBSCRIPTION_CACHE_TTL = 60
SUBSCRIPTION_NEGATIVE_CACHE_TTL = 3


_CHANNEL_TARGET_CHECK_THROTTLE = {}
CHANNEL_TARGET_CHECK_THROTTLE_TTL = 30  # ثانية


async def _opportunistic_autodelete_reached_channels(
    context: ContextTypes.DEFAULT_TYPE, channels: list,
) -> list:
    """يحذف تلقائيًا أي قناة اشتراك إجباري وصلت إلى هدف عدد أعضائها، فور
    حدوث فحص اشتراك إجباري حي (وليس عبر انتظار المهمة الدورية المنفصلة
    check_required_channels_targets فقط) — بناءً على طلب أن يتم الحذف
    «عند تحقق من اشتراك إجباري» تحديدًا، لا فقط اعتمادًا على JobQueue التي
    قد لا تعمل أصلاً إن تعذّر تثبيت مكتبتها في بيئة الاستضافة.

    نظرًا لأن get_required_channels_status تُستدعى مع كل تفاعل لأي مستخدم
    (كل زر/رسالة الآن، بعد تفعيل الفحص الحي)، لا داعٍ لفحص عدد أعضاء كل
    قناة مع كل استدعاء — throttle قصير (30 ثانية) لكل قناة يمنع تكرار
    get_chat_member_count عشرات المرات في الدقيقة دون أي فائدة إضافية،
    فيبقى الحذف لحظيًا فعليًا من منظور المستخدمين (يحدث خلال أول دقائق من
    وصول الهدف، مع أول مستخدم يتفاعل مع البوت) بدون أي بطء ملموس."""
    now = time.time()
    eligible = [
        ch for ch in channels
        if ch.get("target_count") and ch.get("auto_delete_on_target")
        and now - _CHANNEL_TARGET_CHECK_THROTTLE.get(ch["channel_id"], 0) >= CHANNEL_TARGET_CHECK_THROTTLE_TTL
    ]
    if not eligible:
        return channels
    for ch in eligible:
        _CHANNEL_TARGET_CHECK_THROTTLE[ch["channel_id"]] = now
    results = await asyncio.gather(
        *[_check_and_maybe_delete_channel_target(context, ch) for ch in eligible],
        return_exceptions=True,
    )
    deleted_ids = set()
    for ch, result in zip(eligible, results):
        if isinstance(result, Exception) or result[0] != "deleted":
            continue
        deleted_ids.add(ch["channel_id"])
        count = result[1]
        for owner_id in OWNER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=(
                        f"🔄 تم حذف قناة الاشتراك الإجباري @{ch.get('username')} تلقائيًا من القائمة\n"
                        f"(وصلت إلى {count} مشترك، وكان الهدف {ch.get('target_count')})"
                    ),
                )
            except Exception:
                pass
    if not deleted_ids:
        return channels
    return [ch for ch in channels if ch["channel_id"] not in deleted_ids]


async def get_required_channels_status(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, force_refresh: bool = False
) -> list:
    """يتحقق من حالة اشتراك المستخدم الفعلية (اللحظية) في كل قنوات الاشتراك
    الإجباري المفعّلة حاليًا — وليس الناقصة منها فقط — ويعيد قائمة أزواج
    (channel, subscribed: bool) بنفس ترتيب القنوات. تُستخدم لعرض حالة كل
    قناة على حدة في واجهة الاشتراك الإجباري. يعتمد داخليًا على
    is_user_subscribed_to_chat لكل قناة (فحص حي عبر get_chat_member).

    قبل بناء حالة الاشتراك، تُستدعى _opportunistic_autodelete_reached_channels
    لحذف أي قناة وصلت لهدفها فورًا (بشكل مُنظَّم/throttled) بدل الاعتماد فقط
    على المهمة الدورية المنفصلة — فتُطبَّق قنوات «حذف تلقائي عند الهدف»
    فعليًا في نفس لحظة تحقق أي مستخدم من الاشتراك الإجباري.

    ⚡ الفحص لكل القنوات يتم بالتوازي (asyncio.gather) بدل حلقة for متتابعة —
    بحيث يبقى زمن الاستجابة قريبًا من طلب شبكة واحد فقط بصرف النظر عن عدد
    قنوات الاشتراك الإجباري (قناتين، ثلاث، ...)، بدل أن يتضاعف الزمن مع كل
    قناة إضافية كما كان الحال في الحلقة المتتابعة السابقة. هذا هو ما يجعل
    الفحص الحي (force_refresh=True) في enforce_mandatory_subscription_gate
    سريعًا رغم أنه يفحص أكثر من قناة في كل ضغطة زر."""
    channels = [ch for ch in get_required_channels(enabled_only=True) if ch.get("username")]
    if not channels:
        return []
    channels = await _opportunistic_autodelete_reached_channels(context, channels)
    if not channels:
        return []
    results = await asyncio.gather(*[
        is_user_subscribed_to_chat(context, user_id, f"@{ch['username']}", force_refresh=force_refresh)
        for ch in channels
    ])
    return list(zip(channels, results))


async def get_missing_required_channels(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, force_refresh: bool = False
) -> list:
    """يعيد قائمة قنوات الاشتراك الإجباري المفعّلة التي لم ينضم إليها المستخدم
    بعد (قائمة فارغة إن كان مشتركًا في الجميع، أو لا توجد أي قناة إجبارية
    حاليًا)."""
    status = await get_required_channels_status(context, user_id, force_refresh=force_refresh)
    return [channel for channel, subscribed in status if not subscribed]


async def is_user_subscribed(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, force_refresh: bool = False
) -> bool:
    """يتحقق مما إذا كان المستخدم مشتركًا في جميع قنوات الاشتراك الإجباري
    المفعّلة حاليًا. يعيد True إن لم توجد أي قناة إجبارية أصلاً، أو كان
    المستخدم مشتركًا في جميعها."""
    missing = await get_missing_required_channels(context, user_id, force_refresh=force_refresh)
    return not missing


async def enforce_mandatory_subscription_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بوابة عامة تُستدعى في بداية معالجات الرسائل النصية والأزرار العامة
    (text_router وmain_menu_callback) لضمان أن المستخدم ما زال مشتركًا
    فعليًا في كل قنوات الاشتراك الإجباري المفعّلة *في لحظة استخدامه للبوت*،
    وليس فقط عند أول مرة اجتاز فيها الشرط. لا تعتمد على أي نتيجة تحقق قديمة
    مخزّنة بشكل دائم — الفحص يتم دائمًا من حالة الاشتراك الفعلية عبر
    get_chat_member (مع كاش قصير جدًا بالثواني فقط لتفادي إبطاء استجابة
    الأزرار عند الضغطات المتكررة).

    تعيد True إن كان يمكن للمستخدم المتابعة بشكل طبيعي، أو False إن تم
    حجب الطلب وعرض بوابة الاشتراك الإجباري بدلاً منه (وعندها يجب على
    المستدعي التوقف فورًا وعدم متابعة تنفيذ الطلب الأصلي).

    force_refresh=True دائمًا هنا تحديدًا (بعكس بقية استخدامات
    get_required_channels_status في البوت): هذه هي البوابة التي تُنفَّذ قبل
    أي زر أو رسالة في المحادثة الخاصة، فأي كاش هنا يعني أن مستخدمًا خرج من
    القناة يبقى قادرًا على استخدام البوت لبضع ثوانٍ إضافية إلى أن تنتهي
    صلاحية الكاش. الفحص الحي مقبول أداءً هنا رغم تنفيذه في كل ضغطة زر لأن
    get_required_channels_status تفحص كل القنوات بالتوازي (asyncio.gather)
    لا بالتتابع، فزمن الفحص لا يتضاعف مع عدد القنوات.

    ملاحظة: مالكو البوت (OWNER_IDS) مستثنون دائمًا من هذا الشرط، حتى لا
    يُحجب وصولهم إلى قسم الإدارة (مثلاً لإضافة/تعديل قنوات الاشتراك نفسها)."""
    user = update.effective_user
    if not user or is_owner(user.id) or is_moderator(user.id):
        return True

    channels_status = await get_required_channels_status(context, user.id, force_refresh=True)
    if not channels_status:
        return True
    missing_channels = [ch for ch, ok in channels_status if not ok]
    if not missing_channels:
        return True

    text, entities = build_subscription_required_message(missing_channels, channels_status=channels_status)
    keyboard = build_subscription_required_keyboard(missing_channels)

    query = update.callback_query
    if query is not None:
        try:
            await query.answer(
                "⚠️ يجب الاشتراك في قنوات البوت الإجبارية أولاً لمتابعة استخدامه.",
                show_alert=True,
            )
        except Exception:
            pass
        try:
            await query.edit_message_text(text=text, entities=entities, reply_markup=keyboard)
        except Exception:
            try:
                await query.message.reply_text(text=text, entities=entities, reply_markup=keyboard)
            except Exception:
                pass
    elif update.message is not None:
        await update.message.reply_text(text=text, entities=entities, reply_markup=keyboard)

    return False


_GW_CONDITION_SUB_CACHE = {}


async def is_user_subscribed_to_chat(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_ref,
    force_refresh: bool = False,
) -> bool:
    """يتحقق من اشتراك المستخدم في أي قناة يتم تمريرها (chat_ref: يوزر بصيغة
    "@username" أو معرّف الشات الرقمي)، بنفس منطق/كاش is_user_subscribed لكن
    لقنوات «شرط السحب» الديناميكية بدل قناة الاشتراك الإجباري الثابتة. تُستخدم
    هذه الدالة للتحقق الداخلي دون تحويل المستخدم لأي بوت آخر."""
    cache_key = (user_id, str(chat_ref))
    cached = _GW_CONDITION_SUB_CACHE.get(cache_key)
    if not force_refresh and cached is not None:
        age = time.time() - cached["ts"]
        ttl = SUBSCRIPTION_CACHE_TTL if cached["value"] else SUBSCRIPTION_NEGATIVE_CACHE_TTL
        if age < ttl:
            return cached["value"]

    result = False
    for attempt in range(2):
        try:
            member = await context.bot.get_chat_member(chat_id=chat_ref, user_id=user_id)
            result = (
                member.status in ("member", "administrator", "creator")
                or (member.status == "restricted" and bool(getattr(member, "is_member", False)))
            )
            break
        except RetryAfter as exc:
            if attempt == 0 and exc.retry_after <= 5:
                await asyncio.sleep(exc.retry_after)
                continue
            result = False
            break
        except Exception:
            logger.exception(
                "تعذّر التحقق من اشتراك المستخدم %s في قناة الشرط %s", user_id, chat_ref,
            )
            result = False
            break
    _GW_CONDITION_SUB_CACHE[cache_key] = {"value": result, "ts": time.time()}
    return result


async def check_contest_channel_subscription(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, contest, force_refresh: bool = False,
) -> bool:
    """يتحقق تلقائيًا (في الخلفية) من عضوية المستخدم في القناة التي نُشرت فيها
    المسابقة تحديدًا (contest['chat_id']) — بصرف النظر عن كيفية وصوله لرسالة
    المسابقة (حتى لو من خارج القناة). هذا شرط ضمني دائم لكل مسابقة، ولا يُعرض
    للمستخدم أي شيء بخصوصه إلا إذا تبيّن أنه غير مشترك فعلاً."""
    chat_id = contest.get("chat_id") if hasattr(contest, "get") else contest["chat_id"]
    if not chat_id:
        return True
    return await is_user_subscribed_to_chat(context, user_id, chat_id, force_refresh=force_refresh)


async def _build_contest_channel_pseudo_entry(context: ContextTypes.DEFAULT_TYPE, contest) -> dict:
    """يبني عنصر قناة (بنفس شكل قنوات الاشتراك الإجباري القابلة للعرض عبر
    build_required_channels_rows) يمثّل قناة نشر هذه المسابقة تحديدًا،
    ليُعرض ضمن نفس بوابة شروط التصويت الموحّدة عند اكتشاف أن المصوّت غير
    مشترك فيها، تمامًا كما تُعرض قنوات الاشتراك الإجباري العامة."""
    chat_id = contest.get("chat_id") if hasattr(contest, "get") else contest["chat_id"]
    join_url = await build_contest_channel_join_link(context, chat_id)
    if not join_url:
        # تعذّر بناء أي رابط انضمام (حالة نادرة جدًا) — لا نعرض زرًا معطوبًا
        # برابط فارغ؛ نفس الحذر المتّبع في build_contest_channel_gate_keyboard.
        return None
    title = await get_chat_title_cached(context, chat_id) or "قناة المسابقة"
    return {
        "username": "",
        "url": join_url,
        "button_text": title,
        "title": title,
        "channel_id": f"contest_channel_{chat_id}",
    }


async def get_missing_contest_vote_channels(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, contest, force_refresh: bool = False,
) -> list:
    """يجمع كل القنوات التي يجب أن يكون المصوّت مشتركًا فيها فعليًا قبل
    احتساب تصويته: قنوات الاشتراك الإجباري العامة (VORTEX) + قناة نشر هذه
    المسابقة تحديدًا (contest['chat_id']).

    مهم جدًا: قبل هذه الدالة كان فحص التصويت يقتصر على قنوات الاشتراك
    الإجباري العامة فقط عبر get_missing_required_channels، بينما فحص شرط
    الانضمام للمسابقة (check_contest_channel_subscription) لم يكن يُستدعى
    إطلاقًا في مسار التصويت — فكان بإمكان أي مستخدم مشترك في القنوات العامة
    (أو حتى دون أي قناة إجبارية عامة مُفعّلة أصلاً) أن يصوّت لمتسابق دون أي
    اشتراك فعلي في قناة المسابقة نفسها. هذه الدالة توحّد الفحصين معًا حتى لا
    يُحتسب أي تصويت قبل اجتيازهما كليهما فعليًا."""
    missing = list(await get_missing_required_channels(context, user_id, force_refresh=force_refresh))
    if not await check_contest_channel_subscription(context, user_id, contest, force_refresh=force_refresh):
        entry = await _build_contest_channel_pseudo_entry(context, contest)
        if entry:
            missing.append(entry)
    return missing


async def build_channel_join_link(bot, chat_id: int) -> str:
    """يبني رابط انضمام لأي قناة عبر كائن bot مباشرة (دون الحاجة لـ context):
    يوزر عام إن وُجد، وإلا رابط دعوة لقناة خاصة. يُستخدم لإنشاء اسم قناة قابل
    للضغط في رسائل الفوز (سحب/مسابقة) حتى يدخل الفائز للقناة مباشرة."""
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
    except Exception:
        logger.exception("تعذّر جلب معلومات القناة %s لبناء رابط الانضمام", chat_id)
    try:
        invite_link = await bot.create_chat_invite_link(chat_id)
        return invite_link.invite_link
    except Exception:
        try:
            return await bot.export_chat_invite_link(chat_id)
        except Exception:
            logger.exception("تعذّر بناء رابط دعوة للقناة %s", chat_id)
            return ""


async def build_contest_channel_join_link(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> str:
    """يبني رابط انضمام لقناة المسابقة: يوزر عام إن وُجد، وإلا رابط دعوة لقناة
    خاصة. يُستخدم في زر «انضم إلى القناة» ببوابة شرط قناة المسابقة."""
    return await build_channel_join_link(context.bot, chat_id)


_CHAT_TITLE_CACHE = {}
CHAT_TITLE_CACHE_TTL = 3600


async def get_chat_title_cached(context: ContextTypes.DEFAULT_TYPE, chat_id) -> str:
    """يجلب عنوان أي محادثة (قناة/قروب) مع كاش لمدة ساعة، لتفادي نداء get_chat
    المتكرر عند بناء بوابات الشروط ورسائل التنبيه في كل ضغطة مشاركة."""
    cached = _CHAT_TITLE_CACHE.get(chat_id)
    if cached is not None and time.time() - cached["ts"] < CHAT_TITLE_CACHE_TTL:
        return cached["title"]
    title = ""
    try:
        chat = await context.bot.get_chat(chat_id)
        title = chat.title or ""
    except Exception:
        logger.exception("تعذّر جلب عنوان القناة %s", chat_id)
    _CHAT_TITLE_CACHE[chat_id] = {"title": title, "ts": time.time()}
    return title


async def check_giveaway_host_channel_subscription(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, giveaway, force_refresh: bool = False,
) -> bool:
    """يتحقق من اشتراك المستخدم في القناة التي استُضيف فيها السحب نفسه
    (giveaway['chat_id']) — شرط ضمني دائم لكل سحب، بنفس منطق
    check_contest_channel_subscription المستخدمة للمسابقات، وبمعزل تام عن
    قنوات الشرط الإضافية الاختيارية التي يضيفها المالك يدويًا
    (condition_channels). دون هذا الشرط يمكن للمستخدم المشاركة في السحب دون
    أن يكون منضمًا إطلاقًا إلى القناة التي نُشر فيها."""
    chat_id = giveaway.get("chat_id") if hasattr(giveaway, "get") else giveaway["chat_id"]
    if not chat_id:
        return True
    return await is_user_subscribed_to_chat(context, user_id, chat_id, force_refresh=force_refresh)


async def build_giveaway_gate_context(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, giveaway,
) -> dict:
    """يجهّز حالة «البوابة الموحّدة» لسحب معيّن: هل يلزم عرض شرط الاشتراك في
    قناة VORTEX، وهل يلزم عرض شرط الاشتراك في قناة استضافة السحب نفسها (مع
    رابط وعنوان تلك القناة عند الحاجة) — بحيث يُبنى الزرّان معًا في شاشة واحدة
    بدل بوابتين متتاليتين منفصلتين."""
    need_vortex = await get_missing_required_channels(context, user_id)
    host_channel_link = ""
    host_channel_title = ""
    if not await check_giveaway_host_channel_subscription(context, user_id, giveaway):
        host_channel_link = await build_contest_channel_join_link(context, giveaway["chat_id"])
        host_channel_title = await get_chat_title_cached(context, giveaway["chat_id"]) or "قناة السحب"
    return {
        "need_vortex": need_vortex,
        "host_channel_link": host_channel_link,
        "host_channel_title": host_channel_title,
    }


async def check_giveaway_condition_channels(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, giveaway,
) -> bool:
    """يتحقق من اشتراك المستخدم في جميع قنوات شرط السحب (واحدة أو قناتين).
    يُعيد True فقط إذا لم توجد قنوات شرط أصلاً، أو كان مشتركًا في جميعها."""
    channels = giveaway.get("condition_channels") or []
    for channel in channels:
        ref = channel.get("ref")
        if not ref:
            continue
        if not await is_user_subscribed_to_chat(context, user_id, ref):
            return False
    return True


async def check_giveaway_boost(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int,
) -> bool:
    """يتحقق مما إذا كان المستخدم قد عزّز (Boost) قناة السحب فعليًا، عبر
    استدعاء getUserChatBoosts الأصلي في تيليجرام (يُستخدم عند تفعيل خيار
    «تعزيز القناة» — Image A1/A2). يُعيد True فقط إذا كانت لدى المستخدم
    تعزيزة واحدة على الأقل مسجّلة على هذه القناة تحديدًا (Image A4/A5)."""
    try:
        result = await context.bot.get_user_chat_boosts(chat_id=chat_id, user_id=user_id)
        return bool(result.boosts)
    except Exception:
        logger.exception(
            "تعذّر التحقق من تعزيز المستخدم %s للقناة %s", user_id, chat_id,
        )
        return False


async def check_giveaway_requirements(context: ContextTypes.DEFAULT_TYPE, user, giveaway) -> tuple:
    """يتحقق من جميع شروط الدخول في السحب (بريميوم / قنوات الاشتراك / تعزيز /
    تصويت لمتسابق) بترتيب واحد موحّد، ويُستخدم في كل نقاط الدخول (زر المشاركة
    المباشر، بوابة الاشتراك قبل الكابتشا، والتحقق النهائي بعد الكابتشا) حتى لا
    تتكرر نفس الشروط بصيغ مختلفة في أكثر من مكان.
    يُعيد (True, "") عند اجتياز كل الشروط، أو (False, نص التنبيه المناسب لأول شرط لم يتحقق)."""
    if giveaway.get("premium_only") and not user.is_premium:
        return False, "💎 هذا السحب للأشخاص المفعلين مميز فقط!"

    if not await check_giveaway_host_channel_subscription(context, user.id, giveaway):
        host_title = await get_chat_title_cached(context, giveaway["chat_id"])
        return False, build_giveaway_host_channel_subscribe_alert(host_title)

    if not await check_giveaway_condition_channels(context, user.id, giveaway):
        return False, build_giveaway_condition_subscribe_alert()

    if giveaway.get("boost_required") and not await check_giveaway_boost(
        context, user.id, giveaway["chat_id"],
    ):
        return False, "❌ يجب عليك تعزيز القناة اولا"

    vote_contest_code = giveaway.get("vote_contest_code")
    vote_participant_id = giveaway.get("vote_participant_id")
    if vote_contest_code and vote_participant_id and not has_voted_for(
        vote_contest_code, user.id, vote_participant_id,
    ):
        return False, "❌ يجب عليك التصويت للمتسابق أولاً قبل المشاركة في السحب"

    return True, ""


async def build_giveaway_gate_links(context: ContextTypes.DEFAULT_TYPE, giveaway) -> tuple:
    """يبني رابط التعزيز (إن كان السحب يتطلب Boost) ورابط التصويت (إن كان
    مشروطًا بالتصويت لمتسابق)، لعرضهما كأزرار داخل بوابة شروط السحب."""
    boost_link = (
        await build_giveaway_boost_link(context, giveaway["chat_id"])
        if giveaway.get("boost_required") else ""
    )
    vote_contest_code = giveaway.get("vote_contest_code")
    vote_participant_id = giveaway.get("vote_participant_id")
    vote_link = (
        build_giveaway_vote_condition_link(vote_contest_code, vote_participant_id)
        if vote_contest_code and vote_participant_id else ""
    )
    return boost_link, vote_link


async def _check_bot_can_verify_channel(context: ContextTypes.DEFAULT_TYPE, username: str) -> str:
    """يتحقق من أن البوت نفسه مُضاف كمشرف (Admin) في قناة الاشتراك الإجباري
    الجديدة. هذا شرط ضروري لعمل get_chat_member بشكل صحيح — إن لم يكن البوت
    مشرفًا هناك، ستفشل عملية التحقق من الاشتراك لكل المستخدمين (حتى المشتركين
    الحقيقيين فعليًا)، وهو ما يظهر للمستخدم كخطأ "لم يتم العثور على اشتراكك"
    رغم أنه مشترك فعلاً. تُعيد نص تحذير جاهزًا للإرسال للمالكين، أو '' إن كان
    كل شيء سليمًا."""
    try:
        me = await context.bot.get_chat_member(chat_id=f"@{username}", user_id=context.bot.id)
    except Exception as exc:
        return (
            f"⚠️ تنبيه: تعذّر على البوت الوصول إلى @{username} ({exc}).\n"
            f"على الأغلب البوت غير مُضاف لهذه القناة إطلاقًا. أضِف البوت إليها كمشرف "
            f"(Admin) فورًا، وإلا فسيفشل التحقق من اشتراك جميع المستخدمين ويظهر لهم "
            f"خطأ «لم يتم العثور على اشتراكك» حتى لو كانوا مشتركين بالفعل."
        )
    if me.status not in ("administrator", "creator"):
        return (
            f"⚠️ تنبيه: البوت عضو في @{username} لكنه ليس مشرفًا (Admin) فيها.\n"
            f"يجب ترقية البوت إلى مشرف في هذه القناة الآن، وإلا فسيفشل التحقق من "
            f"اشتراك جميع المستخدمين ويظهر لهم خطأ «لم يتم العثور على اشتراكك» حتى "
            f"لو كانوا مشتركين بالفعل."
        )
    return ""


async def _check_and_maybe_delete_channel_target(context: ContextTypes.DEFAULT_TYPE, channel: dict):
    """يفحص قناة اشتراك إجباري واحدة مقابل هدفها، ويحذفها تلقائيًا إن كانت
    مؤهلة ووصلت للهدف. تعيد ("deleted", count) / ("not_reached", count) /
    ("error", exc) / ("skipped", None) حتى يمكن استخدامها من المهمة الدورية
    ومن زر «تحقق الآن» اليدوي معًا بنفس المنطق تمامًا دون تكرار الكود."""
    target = channel.get("target_count")
    username = channel.get("username")
    if not target or not channel.get("auto_delete_on_target") or not username:
        return "skipped", None
    try:
        count = await context.bot.get_chat_member_count(chat_id=f"@{username}")
    except Exception as exc:
        logger.exception(
            "تعذّر جلب عدد مشتركي قناة الاشتراك الإجباري @%s للتحقق من الهدف", username,
        )
        return "error", exc
    if count >= int(target):
        delete_required_channel(channel["channel_id"])
        logger.info(
            "تم حذف قناة الاشتراك الإجباري @%s تلقائيًا بعد وصولها إلى %s مشترك (الهدف: %s)",
            username, count, target,
        )
        return "deleted", count
    return "not_reached", count


async def check_required_channels_targets(context: ContextTypes.DEFAULT_TYPE):
    """
    مهمة دورية: تفحص كل قنوات الاشتراك الإجباري المفعّلة التي حدّد لها المالك
    عدد أعضاء مستهدف مع تفعيل «حذف تلقائي عند الوصول للهدف» (🔄). إن وصلت
    (أو تجاوزت) القناة عدد أعضائها المستهدف تُحذف تلقائيًا من قائمة قنوات
    الاشتراك الإجباري، ويُرسَل إشعار بذلك لكل مالك. القنوات المضبوطة على
    «إبقاء دائم» (♾️ auto_delete_on_target=False) أو بلا هدف محدد لا تُفحص
    أصلاً.

    ⚠️ السبب الشائع لعدم الحذف رغم الوصول للهدف: فشل صامت في جلب عدد
    الأعضاء (غالبًا لأن البوت ليس مشرفًا/عضوًا في القناة) كان يُسجَّل في
    اللوق فقط دون أي إشعار — فيبدو للمالك أن الميزة لا تعمل إطلاقًا دون أي
    تفسير. الآن يُرسَل تحذير فوري للمالك عند الفشل، بدل الاكتفاء باللوق
    الصامت. كما أُضيف زر «🎯 تحقق من الهدف الآن» يدوي (owner_sub_check_target_now)
    لكل قناة، بنفس منطق هذه الدالة تمامًا (عبر _check_and_maybe_delete_channel_target)،
    حتى لا ينتظر المالك دورة الفحص الدورية (كل دقيقتين) عند الاختبار."""
    channels = get_required_channels(enabled_only=True)
    for channel in channels:
        status, info = await _check_and_maybe_delete_channel_target(context, channel)
        username = channel.get("username")
        target = channel.get("target_count")
        if status == "error":
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=(
                            f"⚠️ تعذّر التحقق من هدف القناة @{username} تلقائيًا ({info}).\n"
                            f"غالبًا البوت غير مضاف كمشرف في هذه القناة — أضِفه كمشرف "
                            f"وإلا فلن يُحذف الهدف تلقائيًا أبدًا حتى لو تحقق فعلاً."
                        ),
                    )
                except Exception:
                    pass
        elif status == "deleted":
            count = info
            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=(
                            f"🔄 تم حذف قناة الاشتراك الإجباري @{username} تلقائيًا من القائمة\n"
                            f"(وصلت إلى {count} مشترك، وكان الهدف {target})"
                        ),
                    )
                except Exception:
                    pass


def build_contest_section_message() -> tuple:
    """
    رسالة قسم إنشاء المسابقات:
    - العنوان بخط عريض (Bold) + إيموجي الكأس.
    - سطر التوجيه داخل اقتباس وردي (Blockquote) منتهي بعلامة ” + إيموجي السهم.
    """
    parts = [
        ([
            ("🏆", EMOJI["trophy_create_draw"]),
            " قسم إنشاء المسابقات",
        ], "bold", None),
        "\n\n",
        ([
            "• اختر ما تريدمن القائمة أدناه ",
            ("⏬", EMOJI["arrow_down"]),
            "  ”",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_section_keyboard() -> InlineKeyboardMarkup:
    """
    كيبورد قسم إنشاء المسابقات بنفس ألوان الصورة:
    - أخضر (success) لزر «انشاء مسابقة».
    - أزرق/سماوي (primary) لزري «تسجيل قروب» و«تسجيل قناة».
    - أحمر (danger) لزر «رجوع».
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "انشاء مسابقة", callback_data="comp_start_create",
            style="success", **emoji_kwargs("trophy_contest"),
        )],
        [
            InlineKeyboardButton(
                "تسجيل قروب", callback_data="comp_reg_group",
                style="primary", **emoji_kwargs("register_plus"),
            ),
            InlineKeyboardButton(
                "تسجيل قناة", callback_data="comp_reg_channel",
                style="primary", **emoji_kwargs("register_plus"),
            ),
        ],
        [InlineKeyboardButton(
            "المسابقات الحديثة", callback_data="comp_recent",
            style="primary", **emoji_kwargs("recent_contests_btn"),
        )],
        [InlineKeyboardButton(
            "رجوع", callback_data="back_main_menu",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_contest_target_message() -> tuple:
    """
    شاشة «يرجى تحديد القناة أو القروب لـ المسابقة»:
    - العنوان بخط عريض (Bold) + إيموجي الهدف.
    - الجملتين التوجيهيتين داخل اقتباس وردي (Blockquote) — نفس نظام التلوين
      المستخدم سابقًا (تليجرام بيرسم كيان الـ blockquote بلون وردي/أحمر فاتح تلقائيًا
      مع علامة ” الجانبية، فهو نفس اللون المطلوب).
    """
    parts = [
        ([
            "يرجى تحديد القناة أو القروب لـ المسابقة ",
            ("🎯", EMOJI["target_pin"]),
        ], "bold", None),
        "\n\n",
        ([
            "تأكد أولا انك مشرف في القناة او القروب وان البوت أيضا مشرف",
        ], "blockquote", None),
        "\n\n",
        ([
            "إذا لم تظهر القناة أو الجروب وتأكدت ان البوت بها كمشرف وأنت كمشرف إذا يمكنك تسجيله يدويا من الأسفل",
            ("⏬", EMOJI["arrow_down"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_target_keyboard(owner_id: int = None) -> InlineKeyboardMarkup:
    """
    كيبورد شاشة تحديد القناة/القروب:
    - زر شفاف (بدون لون/بدون إيموجي) لكل قناة أو جروب تمت إضافة البوت كمشرف
      فيه لنفس صاحب الطلب — يظهر تلقائيًا فوق صف التسجيل، تمامًا مثل شكل
      الزر الشفاف في الصورة المرفقة.
    - أزرق/سماوي (primary) لزري «تسجيل قروب» و«تسجيل قناة» بجانب بعض.
    - أحمر (danger) لزر «رجوع» اللي بيرجّع لقسم إنشاء المسابقات.
    """
    rows = []

    if owner_id is not None:
        for chat in get_registered_chats(owner_id):
            title = chat["chat_title"] or str(chat["chat_id"])
            rows.append([InlineKeyboardButton(
                title, callback_data=f"comp_pick_chat_{chat['chat_id']}",
            )])

    rows.append([
        InlineKeyboardButton(
            "تسجيل قروب", callback_data="comp_reg_group",
            style="primary", **emoji_kwargs("register_plus"),
        ),
        InlineKeyboardButton(
            "تسجيل قناة", callback_data="comp_reg_channel",
            style="primary", **emoji_kwargs("register_plus"),
        ),
    ])
    rows.append([InlineKeyboardButton(
        "رجوع", callback_data="section_competition",
        style="danger", **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_back_to_competition_keyboard() -> InlineKeyboardMarkup:
    """كيبورد موحّد لزر «رجوع» اللي بيرجّع لقسم إنشاء المسابقات."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "رجوع", callback_data="section_competition",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_recent_contests_list_message() -> tuple:
    """شاشة اختيار القناة عند وجود أكثر من مسابقة جارية."""
    parts = [
        ([
            "📢 اختر القناة التي تريد التعديل على مسابقتها :",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_recent_contests_list_keyboard(contests) -> InlineKeyboardMarkup:
    """أزرار شفافة (بدون لون/إيموجي مخصص) بعدد المسابقات الجارية، باسم كل قناة."""
    rows = []
    for c in contests:
        title = get_chat_title_by_id(c["chat_id"])
        rows.append([InlineKeyboardButton(
            f"📢 {title}", callback_data=f"comp_detail:{c['contest_code']}",
        )])
    rows.append([InlineKeyboardButton(
        "رجوع", callback_data="section_competition",
        style="danger", **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_contest_detail_message(contest, channel_title: str, post_link, participants_count: int) -> tuple:
    """شاشة إعدادات مسابقة واحدة — تطابق تنسيق الصورة المرفقة."""
    name = contest_display_name(contest)
    status_line = "🟢 نشطة" if contest["status"] == "open" else "🔴 متوقفة"

    def flag(value):
        return ("✅", EMOJI["check_flag_on"]) if value else ("❌", EMOJI["cross_flag_off"])

    channel_line = ["📢 القناة : ", channel_title, " | "]
    if post_link:
        channel_line.append(("رابط منشور المسابقة", "link", post_link))
    else:
        channel_line.append("رابط منشور المسابقة")

    parts = [
        ([
            "📋 المسابقة :\n",
            name,
            "\n\n",
            *channel_line,
            "\n\n",
            f"📊 الحالة : {status_line}",
            "\n\n",
            f"👥 المتسابقون : {participants_count} / {contest['target_count']}",
            "\n\n",
            "⚙️ إعدادات المسابقة :",
            "\n\n",
            "🔔 تنبيه الفوز | ", flag(contest["notify_win"]), "\n",
            "📣 إعلان النتائج | ", flag(contest["announce_results"]), "\n",
            "🧩 موافقة المشاركات | ", flag(contest["approve_participants"]), "\n",
            "💎 تصويت بريميوم | ", flag(contest["premium_only"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_detail_keyboard(contest) -> InlineKeyboardMarkup:
    code = contest["contest_code"]
    toggle_label = "⏸ إيقاف المسابقة" if contest["status"] == "open" else "▶️ استئناف المسابقة"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "تغيير عدد المقاعد", callback_data=f"comp_change_seats:{code}",
            style="primary", **emoji_kwargs("seats_change_btn"),
        )],
        [InlineKeyboardButton(
            toggle_label, callback_data=f"comp_toggle_active:{code}",
            style="primary", **emoji_kwargs("pause_toggle_btn"),
        )],
        [InlineKeyboardButton(
            "تغيير إعدادات المسابقة", callback_data=f"comp_edit_settings:{code}",
            style="primary", **emoji_kwargs("edit_settings_refresh_btn"),
        )],
        [InlineKeyboardButton(
            "إزالة متسابق", callback_data=f"comp_remove_contestant:{code}",
            style="danger", **emoji_kwargs("remove_contestant_btn"),
        )],
        [InlineKeyboardButton(
            "حذف المسابقة بالكامل", callback_data=f"comp_delete_all:{code}",
            style="danger", **emoji_kwargs("delete_all_btn"),
        )],
        [InlineKeyboardButton(
            "رجوع", callback_data="section_competition",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_channel_registration_message() -> tuple:
    """

    شاشة «لـ اضافة قناة اتبع الخطوات التالية»:
    - العنوان الرئيسي وعنوان «ملاحظة» بخط عريض (Bold).
    - الخطوتين بأرقام مخصصة (1️⃣ / 2️⃣) كنص عادي.
    - جملة الملاحظة داخل اقتباس وردي (Blockquote) منتهية بعلامة ”.
    """
    parts = [
        ("لـ اضافة قناة اتبع الخطوات التالية:", "bold", None),
        "\n\n",
        ("1️⃣", EMOJI["num_one"]),
        f"أضف البوت @{BOT_USERNAME} كمشرف في قناتك.",
        "\n\n",
        ("2️⃣", EMOJI["num_two"]),
        "قم بإعادة توجيه أي رسالة من قناتك إلى البوت",
        "\n\n",
        ([("📌", EMOJI["pin_note"]), "ملاحظة:"], "bold", None),
        "\n",
        ([
            "جميع المشرفين الآخرين في القناة سيتمكنون أيضًا من استخدام البوت بعد إضافته  ”",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_group_registration_message() -> tuple:
    """
    شاشة «لـ اضافة جروب اتبع الخطوات التالية»:
    - العنوان الرئيسي بخط عريض (Bold).
    - الخطوتين بأرقام مخصصة (1️⃣ / 2️⃣) كنص عادي.
    """
    parts = [
        ("لـ اضافة جروب اتبع الخطوات التالية:", "bold", None),
        "\n\n",
        ("1️⃣", EMOJI["num_one"]),
        f"أضف البوت @{BOT_USERNAME} كمشرف في الجروب الخاص بك",
        "\n\n",
        ("2️⃣", EMOJI["num_two"]),
        "إذهب للجروب الخاص بك بعد إضافة البوت و اكتب ",
        ("◀️", EMOJI["arrow_left"]),
        "تفعيل روليت",
    ]
    return build_text_with_emojis(parts)


def build_contest_cliche_message() -> tuple:
    """
    شاشة «أرسل كليشة المسابقة»:
    - العنوان بخط عريض (Bold) + إيموجي الظرف.
    - أمثلة توضيحية فعلية لتنسيقات تيليجرام (عريض/مائل/مشوش/رابط).
    - سطر ختامي داخل اقتباس وردي (Blockquote) بعلامة ” كنموذج «نص مقتبس».
    """
    parts = [
        ([
            ("📨", EMOJI["envelope_klesha"]),
            " أرسل كليشة المسابقة",
        ], "bold", None),
        "\n\n",
        "اكتب نص المسابقة الذي تريد نشره في القناة.\n"
        "يمكنك استخدام تنسيقات تيليجرام، مثل:\n",
        "• ", ("نص عريض", "bold", None), "\n",
        "• ", ("نص مائل", "italic", None), "\n",
        "• ", ("نص مشوش", "spoiler", None), "\n",
        ([("🆕", EMOJI["new_badge"]), " يمكنك وضع رابط داخل النص"], "link", "https://t.me"),
        "\n",
        (["نص مقتبس  ”"], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_cliche_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "comp_start_create", "danger", "back_section_btn")


def build_contest_count_message() -> tuple:
    """شاشة «أرسل عدد المتسابقين المطلوب 🎯:» — عنوان واحد بخط عريض."""
    parts = [
        ([
            "أرسل عدد المتسابقين المطلوب ",
            ("🎯", EMOJI["target_pin"]),
            ":",
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_count_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "comp_back_to_klesha", "danger", "back_section_btn")


def build_contest_end_method_message() -> tuple:
    """
    شاشة «اختر طريقة انتهاء المسابقة»:
    - العنوان بخط عريض.
    - كل خيار داخل اقتباس وردي (Blockquote) منفصل.
    """
    parts = [
        ([" اختر طريقة انتهاء المسابقة:", ("❓", EMOJI["end_question"])], "bold", None),
        "\n\n",
        ([
            ("🎯", EMOJI["target_pin"]),
            "   عدد اصوات محدده: تنتهي المسابقة عند وصول المتسابقين عدد الاصوات الذي تحددها",
        ], "blockquote", None),
        "\n\n",
        ([
            ("⏰", EMOJI["alarm_clock"]),
            "   وقت محدد : تنتهي المسابقة تلقائياً عند انقضاء الوقت الذي تحدده ويفوز صاحب الاصوات الأعلى",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_end_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "عدد اصوات محدده", callback_data="comp_end_votes",
                style="primary", **emoji_kwargs("votes_chart_btn"),
            ),
            InlineKeyboardButton(
                "وقت محدد", callback_data="comp_end_time",
                style="primary", **emoji_kwargs("alarm_clock_btn"),
            ),
        ],
        [InlineKeyboardButton(
            "رجوع", callback_data="comp_back_to_count",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_contest_time_menu_message(selected_label: str = "غير محدد") -> tuple:
    """
    شاشة «⏰ وقت محدد للمسابقة»:
    - العنوان بخط عريض (Bold) + إيموجي الساعة.
    - القيمة الحالية في سطر مستقل.
    - جملة التوجيه.
    """
    parts = [
        ([
            ("⏰", EMOJI["alarm_clock_title"]),
            "وقت محدد للمسابقة",
        ], "bold", None),
        f"\nالوقت المختار: {selected_label}",
        "\n\n",
        "استخدم الأزرار أدناه لتحديد الوقت المطلوب لانتهاء المسابقة تلقائياً:",
    ]
    return build_text_with_emojis(parts)


def build_contest_time_menu_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for row in CONTEST_TIME_OPTIONS:
        rows.append([
            InlineKeyboardButton(
                label, callback_data=f"comp_atime_set_{minutes}",
                style="primary", **emoji_kwargs("time_option_btn"),
            )
            for minutes, label in row
        ])
    rows.append([
        InlineKeyboardButton(
            "وقت مخصص", callback_data="comp_atime_show_custom",
            style="primary", **emoji_kwargs("time_manual_btn"),
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            "رجوع", callback_data="comp_back_to_end_type",
            style="danger", **emoji_kwargs("back_time_menu_btn"),
        )
    ])
    return InlineKeyboardMarkup(rows)


CONTEST_TIME_CUSTOM_STEPS = [
    [(-1, "- 1 دقيقة"), (1, "+ 1 دقيقة")],
    [(-5, "- 5 دقيقة"), (5, "+ 5 دقيقة")],
    [(-10, "- 10 دقايق"), (10, "+ 10 دقايق")],
    [(-60, "- 1 ساعة"), (60, "+ 1 ساعة")],
    [(-1440, "- 1 يوم"), (1440, "+ 1 يوم")],
]


def build_contest_time_custom_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for row in CONTEST_TIME_CUSTOM_STEPS:
        rows.append([
            InlineKeyboardButton(
                label, callback_data=f"comp_atime_custom_delta:{delta}",
                style="primary", **emoji_kwargs("time_option_btn"),
            )
            for delta, label in row
        ])
    rows.append([InlineKeyboardButton(
        "تأكيد الوقت", callback_data="comp_atime_custom_confirm",
        style="success", **emoji_kwargs("yes_btn"),
    )])
    rows.append([
        InlineKeyboardButton(
            "إعادة تعيين", callback_data="comp_atime_custom_reset",
            style="success", **emoji_kwargs("restore_defaults_btn"),
        ),
        InlineKeyboardButton(
            "رجوع للخيارات", callback_data="comp_back_to_end_type",
            style="danger", **emoji_kwargs("back_section_btn"),
        ),
    ])
    return InlineKeyboardMarkup(rows)


def build_contest_votes_target_message() -> tuple:
    """شاشة «أرسل عدد الأصوات المطلوب» لتفعيل إنهاء المسابقة تلقائيًا عند وصول
    أحد المتسابقين لعدد الأصوات المحدد."""
    parts = [
        ([
            ("🎯", EMOJI["votes_chart_btn"]), " عدد أصوات محدد",
        ], "bold", None),
        "\n\n",
        "أرسل عدد الأصوات المطلوب لإنهاء المسابقة تلقائيًا عند وصول أحد المتسابقين إليه",
        "\n\n",
        ([
            "مثال: إذا أردت إنهاء المسابقة عند وصول أحد المتسابقين إلى 100 صوت "
            "أرسل الرقم 100",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_votes_target_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "comp_back_to_end_type", "danger", "back_section_btn")


def build_contest_winners_message() -> tuple:
    """شاشة «أرسل عدد الفائزين المطلوب 🏆:»."""
    parts = [
        ([
            "أرسل عدد الفائزين المطلوب ",
            ("🏆", EMOJI["trophy_winners_title"]),
            ":",
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_winners_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "comp_back_to_end_type", "danger", "back_winners_btn")


def build_contest_winners_confirm_message() -> tuple:
    """رسالة تأكيد «✅ تم تحديد عدد الفائزين» — تُرسل قبل شاشة إعدادات المسابقة."""
    parts = [
        ([
            ("✅", EMOJI["confirm_check"]),
            " تم تحديد عدد الفائزين",
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


CONTEST_SETTINGS_DEFAULTS = {
    "contest_notify_win": False,
    "contest_announce_results": False,
    "contest_approve_participants": False,
    "contest_premium_only": False,
}


def build_contest_settings_message() -> tuple:
    """
    شاشة «• اعدادات المسابقة الحالية:»:
    - عنوان بخط عريض.
    - كل إعداد: تسمية بخط عريض + شرح عادي.
    - سطر ختامي داخل اقتباس وردي (Blockquote).
    """
    parts = [
        (["• اعدادات المسابقة الحالية:"], "bold", None),
        "\n\n",
        (["- تنبيه الفوز"], "bold", None),
        " : ارسال اشعار تلقائي عند فوز احد المتسابقين",
        "\n\n",
        (["- اعلان النتائج"], "bold", None),
        " : اعلان نتائج المتسابقين وعدد اصواتهم",
        "\n\n",
        (["- موافقة المشاركات"], "bold", None),
        " : نشر أسماء المشاركين تلقائيا أو مراجعتها قبل الموافقة",
        "\n\n",
        (["- اصوات لـ المميزين"], "bold", None),
        " : التصويت متاحا فقط لمستخدمي تيليجرام المميز Premium.",
        "\n\n",
        ([
            ("✅", EMOJI["confirm_check"]),
            " الميزات المفعّلة تظهر بعلامة  ”",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_settings_keyboard(user_data: dict) -> InlineKeyboardMarkup:
    def yn_button(flag: bool, callback_data: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            "نعم" if flag else "لا",
            callback_data=callback_data,
            style="success" if flag else "danger",
            **emoji_kwargs("yes_btn" if flag else "no_btn"),
        )

    notify = user_data.get("contest_notify_win", CONTEST_SETTINGS_DEFAULTS["contest_notify_win"])
    announce = user_data.get("contest_announce_results", CONTEST_SETTINGS_DEFAULTS["contest_announce_results"])
    approve = user_data.get("contest_approve_participants", CONTEST_SETTINGS_DEFAULTS["contest_approve_participants"])
    premium = user_data.get("contest_premium_only", CONTEST_SETTINGS_DEFAULTS["contest_premium_only"])

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("تنبيه الفوز", callback_data="comp_toggle_notify_win",
                                  style="primary", **emoji_kwargs("notify_win_btn")),
            yn_button(notify, "comp_toggle_notify_win"),
        ],
        [
            InlineKeyboardButton("اعلان النتائج", callback_data="comp_toggle_announce_results",
                                  style="primary", **emoji_kwargs("announce_results_btn")),
            yn_button(announce, "comp_toggle_announce_results"),
        ],
        [
            InlineKeyboardButton("موافقة المشاركات", callback_data="comp_toggle_approve_participants",
                                  style="primary", **emoji_kwargs("approve_participants_label_btn")),
            yn_button(approve, "comp_toggle_approve_participants"),
        ],
        [
            InlineKeyboardButton("تصويت بريميوم", callback_data="comp_toggle_premium_only",
                                  style="primary", **emoji_kwargs("premium_vote_btn")),
            yn_button(premium, "comp_toggle_premium_only"),
        ],
        [InlineKeyboardButton(
            "نشر المسابقة", callback_data="comp_publish",
            style="primary", **emoji_kwargs("publish_btn"),
        )],
        [InlineKeyboardButton(
            "رجوع", callback_data="comp_back_to_winners",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_publish_success_message() -> tuple:
    """رسالة «✅ تم نشر المسابقة بنجاح!» — تحل محل قائمة الإعدادات فورًا عند الضغط على نشر."""
    parts = [
        (["✅ تم نشر المسابقة بنجاح !"], "bold", None),
    ]
    return build_text_with_emojis(parts)


def format_minutes_label(minutes: int) -> str:
    """يحوّل عدد الدقائق إلى تسمية عربية مقروءة (يوم/ساعة/دقيقة)."""
    if minutes >= 1440 and minutes % 1440 == 0:
        days = minutes // 1440
        if days == 1:
            return "يوم واحد"
        if days == 2:
            return "يومين"
        if days <= 10:
            return f"{days} أيام"
        return f"{days} يوم"
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        if hours == 1:
            return "ساعة واحدة"
        if hours == 2:
            return "ساعتين"
        if hours <= 10:
            return f"{hours} ساعات"
        return f"{hours} ساعة"
    if minutes == 1:
        return "دقيقة واحدة"
    if minutes == 2:
        return "دقيقتين"
    if minutes <= 10:
        return f"{minutes} دقائق"
    return f"{minutes} دقيقة"


def _duration_unit_label(n: int, one: str, two: str, few: str, many: str) -> str:
    """صيغة عربية مختصرة لوحدة زمنية ضمن تسمية مركّبة (يوم/ساعة/دقيقة معًا) —
    بدون «واحد/واحدة» كي لا تتكرر عبر كل وحدة (مثال: «يوم و ساعة و 11 دقيقة»)."""
    if n == 1:
        return one
    if n == 2:
        return two
    if n <= 10:
        return f"{n} {few}"
    return f"{n} {many}"


def format_duration_label(total_minutes) -> str:
    """يحوّل عدد الدقائق المتراكم (من قائمة «وقت مخصص» التراكمية) إلى تسمية عربية
    مقروءة. عند وجود وحدة واحدة فقط (مثلاً 60 دقيقة بالضبط) تُستخدم نفس صيغة
    format_minutes_label الكاملة («ساعة واحدة»)، وعند تركيب أكثر من وحدة تُستخدم
    صيغة مختصرة متسلسلة بـ«و» (مثال: «يوم و ساعة و 11 دقيقة»)، مطابقةً لتصميم
    قائمة «وقت مخصص» (Image 7/8)."""
    if not total_minutes or total_minutes <= 0:
        return "غير محدد"
    total_minutes = int(total_minutes)
    days, rem = divmod(total_minutes, 1440)
    hours, minutes = divmod(rem, 60)
    units_present = sum(1 for x in (days, hours, minutes) if x)
    if units_present <= 1:
        return format_minutes_label(total_minutes)
    parts = []
    if days:
        parts.append(_duration_unit_label(days, "يوم", "يومين", "أيام", "يوم"))
    if hours:
        parts.append(_duration_unit_label(hours, "ساعة", "ساعتين", "ساعات", "ساعة"))
    if minutes:
        parts.append(_duration_unit_label(minutes, "دقيقة", "دقيقتين", "دقائق", "دقيقة"))
    return " و ".join(parts)


def utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def shift_entities(entities, shift: int):
    shifted = []
    for e in entities or []:
        shifted.append(MessageEntity(
            type=e.type,
            offset=e.offset + shift,
            length=e.length,
            url=getattr(e, "url", None),
            user=getattr(e, "user", None),
            language=getattr(e, "language", None),
            custom_emoji_id=getattr(e, "custom_emoji_id", None),
        ))
    return shifted


def build_brand_footer() -> tuple:
    """يبني تذييل العلامة التجارية (اسم أزرق قابل للضغط + رابط «السحوبات» بجانبه)
    المستخدم في نهاية منشورات القناة (السحب والمسابقة)."""
    return build_text_with_emojis([
        "\n\n",
        *build_brand_giveaways_parts(),
    ])


def build_contest_channel_message(cliche_text: str, cliche_entities, target_count: int,
                                   end_type: str, time_minutes: int, votes_target: int = None,
                                   contest_code: str = None) -> tuple:
    """
    منشور المسابقة الذي يُنشر في القناة/القروب المحدد (صورة image 2):
    - كليشة المسابقة كما أرسلها صاحب المسابقة (بتنسيقاتها الأصلية).
    - عدد المشاركين المسموح بخط عريض.
    - تعليمات التسجيل داخل اقتباس ملوّن منفصل.
    - وقت انتهاء المسابقة تلقائيًا داخل اقتباس ملوّن منفصل (إذا كان معتمدًا على الوقت)،
      أو عدد الأصوات الذي تنتهي عنده المسابقة (إذا كان معتمدًا على عدد الأصوات).
    - كود المسابقة الفريد (contest_code) بصيغة monospace قابلة للنسخ بضغطة واحدة،
      حتى يتمكن أي مستخدم من استخدامه للبحث عن هذه المسابقة لاحقًا في قسم «المسابقات».
    - تذييل باسم العلامة التجارية بلون أزرق قابل للضغط.
    """
    extra_parts = [
        "\n\n",
        ([f"عدد المشاركين المسموح : {target_count}"], "bold", None),
        "\n\n",
        (["لتسجيل اسمك في المسابقة اضغط على زر المشاركة في المسابقة بأسفل المنشور  ”"], "blockquote", None),
    ]
    if end_type == "time" and time_minutes:
        extra_parts.append("\n\n")
        extra_parts.append(([f"سيتم انتهاء المسابقة بعد {format_minutes_label(time_minutes)}  ”"], "blockquote", None))
    elif end_type == "votes" and votes_target:
        extra_parts.append("\n\n")
        extra_parts.append(([
            f"ستنتهي المسابقة عند وصول أحد المتسابقين إلى {votes_target} صوت  ”",
        ], "blockquote", None))

    # 🚫 لم يعد كود المسابقة يُعرض داخل منشور القناة/القروب العام — أصبح مقصورًا
    # على قسم إدارة المسابقات الخاص بالمالك، حيث يظهر بصيغة monospace قابلة
    # للنسخ بضغطة واحدة. الوسيط contest_code ما زال يُمرَّر لهذه الدالة لأنه قد
    # يُستخدم في مواضع الاستدعاء الأخرى، لكنه لم يعد يُدرَج ضمن نص المنشور نفسه.

    extra_text, extra_entities = build_text_with_emojis(extra_parts)
    footer_text, footer_entities = build_brand_footer()

    base_text = cliche_text or ""
    base_entities = list(cliche_entities or [])
    shift = utf16_len(base_text)
    footer_shift = utf16_len(base_text + extra_text)

    combined_text = base_text + extra_text + footer_text
    combined_entities = (
        base_entities
        + shift_entities(extra_entities, shift)
        + shift_entities(footer_entities, footer_shift)
    )
    return combined_text, combined_entities


def build_contest_channel_keyboard(contest_code: str) -> InlineKeyboardMarkup:
    # 🔒 كان هذا الزر رابط (url) يفتح محادثة البوت مباشرة وبلا شرط، حتى لو لم يكن
    # المستخدم مشتركًا في قناة المسابقة أو في قنوات VORTEX الإجبارية — فيجد نفسه
    # داخل محادثة البوت دون أي تنبيه، أو حتى بلا أي رد إن تعثّرت معالجة /start.
    # أصبح الآن زر callback_data يمر أولاً عبر compjoin_button_callback الذي يتحقق
    # من الاشتراك ويعرض تنبيهًا فوريًا (show_alert) دون أي تحويل عند عدم الاشتراك،
    # ولا يفتح البوت (query.answer(url=...)) إلا بعد اجتياز هذا الشرط فعليًا.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ المشاركة في المسابقة",
            callback_data=f"compjoinbtn:{contest_code}",
            style="success",
        )],
    ])


ARABIC_ORDINALS = [
    "الأول", "الثاني", "الثالث", "الرابع", "الخامس",
    "السادس", "السابع", "الثامن", "التاسع", "العاشر",
]

MEDAL_EMOJI_BY_RANK = {1: EMOJI["medal"], 2: EMOJI["medal"], 3: EMOJI["medal"]}


def format_votes_label(votes: int) -> str:
    return f"{votes} صوت"


def build_contest_ended_message(cliche_text: str, cliche_entities, winners: list) -> tuple:
    """
    رسالة نهاية المسابقة — تُنشر كمنشور جديد منفصل (لا تُستبدل الرسالة القديمة):
    - عنوان «🏆 انتهت المسابقة!» داخل اقتباس (بخط عريض).
    - سطر لكل فائز: «الفائز 🥇 : [الاسم بلون أزرق قابل للضغط]  (X صوت)» — كل شيء بخط عريض،
      واسم الفائز رابط أزرق (TEXT_LINK) يشير إلى حساب الفائز الفعلي (وليس @يوزرنيم).
    winners: قائمة (user_id, display_name, participant_code, votes).
    """
    parts = [
        ([("🏆", EMOJI["trophy_win"]), " انتهت المسابقة!  ”"], "blockquote", None),
    ]

    if not winners:
        parts.append("\n\n")
        parts.append((["⚠️ لم يشارك أحد في هذه المسابقة، لم يتم اختيار فائز."], "bold", None))
    elif len(winners) == 1:
        user_id, name, _, votes = winners[0]
        parts.append("\n\n")
        parts.append(([
            "الفائز ",
            ("🥇", EMOJI["medal"]),
            " : ",
            (name, "mention_id", user_id),
            f"  ({format_votes_label(votes)})",
        ], "bold", None))
    else:
        for i, (user_id, name, _, votes) in enumerate(winners):
            ordinal = ARABIC_ORDINALS[i] if i < len(ARABIC_ORDINALS) else f"رقم {i + 1}"
            parts.append("\n\n")
            parts.append(([
                f"الفائز {ordinal} ",
                ("🥇", EMOJI["medal"]),
                " : ",
                (name, "mention_id", user_id),
                f"  ({format_votes_label(votes)})",
            ], "bold", None))

    combined_text, combined_entities = build_text_with_emojis(parts)
    return combined_text, combined_entities


def build_contest_ended_keyboard(contest_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "عرض النتائج", callback_data=f"comp_view_results:{contest_code}",
            style="success",
        )],
    ])


def build_contest_results_message(leaderboard: list, winners_count: int) -> tuple:
    """رسالة النتائج الكاملة (ترتيب جميع المتسابقين) — تُعرض عند الضغط على «عرض النتائج»."""
    parts = [
        ([("📊", EMOJI["chart"]), " النتائج الكاملة للمسابقة"], "bold", None),
    ]
    if not leaderboard:
        parts.append("\n\n")
        parts.append((["⚠️ لا يوجد أي متسابق مسجّل في هذه المسابقة."], "bold", None))
    else:
        bq_parts = []
        for i, (user_id, name, _, votes) in enumerate(leaderboard):
            rank = i + 1
            crown = "🏆 " if rank <= winners_count else ""
            bq_parts.append(f"{crown}({rank}) ")
            bq_parts.append((name, "mention_id", user_id))
            bq_parts.append(f" — {format_votes_label(votes)}")
            if i == 0:
                bq_parts.append("  ”\n")
            elif i != len(leaderboard) - 1:
                bq_parts.append("\n")
        parts.append("\n\n")
        parts.append(([(bq_parts, "bold", None)], "blockquote", None))
    return build_text_with_emojis(parts)


def build_contest_join_confirm_message(display_name: str) -> tuple:
    """رسالة «🎯 تأكيد المشاركة في المسابقة» (صورة image 3)."""
    parts = [
        ([("🎯", EMOJI["target_pin"]), " تأكيد المشاركة في المسابقة"], "bold", None),
        "\n\n",
        f"تريد المشاركة في المسابقة باسم: {display_name}",
        "\n\n",
        "هل أنت متأكد؟",
    ]
    return build_text_with_emojis(parts)


def build_contest_join_confirm_keyboard(contest_code: str, is_genuinely_new: bool = False) -> InlineKeyboardMarkup:
    # ⚡ is_genuinely_new تُمرَّر الآن ضمن callback_data (بدل إعادة حسابها لاحقًا
    # في comp_confirm_join) — لأن المستخدم يكون قد سُجِّل بالفعل عبر start()
    # قبل وصوله لهذه الشاشة، فإعادة استدعاء register_bot_user_and_check_new
    # هناك كانت تُعيد False دومًا حتى لمستخدم جديد فعليًا.
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "رفض", callback_data=f"comp_reject_join:{contest_code}",
                style="danger", **emoji_kwargs("remind_off"),
            ),
            InlineKeyboardButton(
                "قبول", callback_data=f"comp_confirm_join:{contest_code}:{1 if is_genuinely_new else 0}",
                style="success", **emoji_kwargs("join_accept_btn"),
            ),
        ],
    ])


def build_contest_join_pending_message() -> tuple:
    """رسالة «⏳ تم إرسال طلب المشاركة للمراجعة» — تظهر للمستخدم فور ضغطه
    «قبول» في شاشة تأكيد المشاركة، وذلك فقط عندما تكون خاصية «موافقة
    المشاركات» مفعّلة في المسابقة."""
    parts = [
        ([("⏳", EMOJI["alarm_clock"]), " تم إرسال طلب المشاركة للمراجعة!"], "bold", None),
        "\n\n",
        "سيتم إشعارك فور موافقة صاحب المسابقة على طلبك.",
    ]
    return build_text_with_emojis(parts)


def build_contest_join_request_owner_message(display_name: str, username: str, user_id: int) -> tuple:
    """رسالة «• طلب مشاركة جديد» تُرسل إلى صاحب المسابقة فقط، تحتوي بيانات
    مقدّم الطلب مع زرّي قبول/رفض — تُرسل فقط عند تفعيل «موافقة المشاركات»."""
    username_line = f"@{username}" if username else "—"
    parts = [
        ([("🎯", EMOJI["target_pin"]), " طلب مشاركة جديد :"], "bold", None),
        "\n\n",
        (["الاسم"], "bold", None), f" : {display_name}", "\n",
        (["الأيدي"], "bold", None), f" : {user_id}", "\n",
        (["اليوزر"], "bold", None), f" : {username_line}",
    ]
    return build_text_with_emojis(parts)


def build_contest_join_request_owner_keyboard(contest_code: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "رفض", callback_data=f"comp_appjoin_no:{contest_code}:{user_id}",
                style="danger", **emoji_kwargs("remind_off"),
            ),
            InlineKeyboardButton(
                "قبول", callback_data=f"comp_appjoin_ok:{contest_code}:{user_id}",
                style="success", **emoji_kwargs("join_accept_btn"),
            ),
        ],
    ])


def build_contest_join_request_decided_owner_message(display_name: str, accepted: bool) -> tuple:
    """تستبدل رسالة طلب المشاركة عند صاحب المسابقة بعد اتخاذ قراره، لمنع
    الضغط على الأزرار أكثر من مرة."""
    if accepted:
        return bold_notice(f"✅ تم قبول مشاركة: {display_name}")
    return bold_notice(f"❌ تم رفض مشاركة: {display_name}")


def build_contest_join_rejected_user_message() -> tuple:
    """رسالة تُرسل للمستخدم عند رفض صاحب المسابقة لطلب مشاركته."""
    return bold_notice("❌ تم رفض طلب مشاركتك في هذه المسابقة.")


def build_contest_channel_gate_message() -> tuple:
    """رسالة «يجب الانضمام إلى قناة المسابقة أولاً» — لا تُعرض إلا عند اكتشاف
    أن المستخدم غير مشترك فعليًا في القناة التي نُشرت فيها المسابقة (فحص
    خلفي تلقائي)، ولا تظهر أبدًا ضمن رسالة المسابقة أو أي شروط دائمة أخرى."""
    parts = [
        "يجب عليك الانضمام إلى قناة المسابقة أولاً",
        "\n",
        "- لتتمكن من المشاركة في المسابقة : ",
        ("🏁", EMOJI["target_pin"]),
        "\n",
        ([
            ("‼️", EMOJI["sub_alert"]),
            " | انضم ثم اضغط تحقق",
            ("✅", EMOJI["sub_check"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_channel_gate_keyboard(contest_code: str, join_url: str,
                                         is_genuinely_new: bool = False) -> InlineKeyboardMarkup:
    """كيبورد بوابة شرط قناة المسابقة: زر «انضم إلى القناة» (إن توفّر رابط) +
    زر «تحقق ✅» الذي يعيد فحص العضوية فعليًا (بدون كاش) قبل إكمال المشاركة."""
    rows = []
    if join_url:
        rows.append([InlineKeyboardButton("📢 انضم إلى القناة", url=join_url)])
    rows.append([
        InlineKeyboardButton(
            "تحقق ✅", callback_data=f"compjoinchk:{contest_code}:{1 if is_genuinely_new else 0}",
        ),
    ])
    return InlineKeyboardMarkup(rows)


def build_contest_registered_message(display_name: str, participant_code: str) -> tuple:
    """رسالة تأكيد التسجيل مع كود المتسابق (صورة image 4) — عناوين الأقسام داخل اقتباس ملوّن."""
    parts = [
        ([("✅", EMOJI["confirm_check"]), f" تم تسجيل مشاركتك في المسابقة بإسم : {display_name}"], "bold", None),
        "\n\n",
        (["🎟 كود المتسابق الخاص بك:"], "bold", None),
        f"\n{participant_code}",
        "\n\n",
        (["كيفية استخدام كود المتسابق:  ”"], "blockquote", None),
        "\n\n",
        ("❶", EMOJI["num_one"]),
         " افتح بوت ",
         (BRAND_NAME, "link", BRAND_URL),
         f" @{BOT_USERNAME} وأنشئ روليت جديد.",
        "\n\n",
        ("❷", EMOJI["num_two"]),
        " اختر شرط السحب: التصويت للمتسابق ثم أدخل الكود الخاص بك.",
        "\n\n",
        (["مميزات الكود :  ”"], "blockquote", None),
        "\n\n",
        ("✅", EMOJI["confirm_check"]),
        " يمنع أي شخص من المشاركة في السحب قبل أن يصوّت لك وهذا يزيد عدد المصوتين لصالحك.",
        "\n\n",
        ("✅", EMOJI["confirm_check"]),
        " يمكنك إعطاء الكود لصديق وسيتمكن من عمل سحب في قناته بشرط التصويت لك وسيُسجَّل التصويت باسمك.",
        "\n\n",
        ("✅", EMOJI["confirm_check"]),
        " كل استخدام للكود يرفع فرصك في الفوز بالمسابقة وجميع السحوبات المرتبطة بها.",
    ]
    return build_text_with_emojis(parts)


def build_contest_registered_keyboard(contest_code: str, user_id: int, participant_code: str) -> InlineKeyboardMarkup:
    try:
        copy_btn = InlineKeyboardButton(
            "انسخ كود المسابقة",
            copy_text=CopyTextButton(text=participant_code),
            style="success",
        )
    except Exception:
        copy_btn = InlineKeyboardButton("🎟 كودك: " + participant_code, callback_data="noop")
    return InlineKeyboardMarkup([
        [copy_btn],
        [InlineKeyboardButton(
            "سحب اسمي من المسابقه", callback_data=f"comp_withdraw:{contest_code}:{user_id}",
            style="danger", **emoji_kwargs("withdraw_btn"),
        )],
    ])


def build_contest_vote_post_message(display_name: str) -> tuple:
    """المنشور الذي يُنشر في القناة/القروب عند تسجيل متسابق جديد (صورة image 5)."""
    parts = [f"{display_name} : المتسابق"]
    return build_text_with_emojis(parts)


def build_contest_vote_keyboard(contest_code: str, participant_id: int, votes: int,
                                 participant_code: str) -> InlineKeyboardMarkup:
    try:
        copy_btn = InlineKeyboardButton(
            "نسخ كود المتسابق",
            copy_text=CopyTextButton(text=participant_code),
            style="success",
        )
    except Exception:
        copy_btn = InlineKeyboardButton("🎟 كود المتسابق: " + participant_code, callback_data="noop")
    # 🔒 نفس منطق build_contest_channel_keyboard أعلاه: كان زر التصويت رابط (url)
    # يفتح محادثة البوت مباشرة وبلا أي شرط اشتراك. أصبح الآن زر callback_data يمر
    # عبر compvote_button_callback الذي يتحقق من الاشتراك أولاً ويعرض تنبيهًا فوريًا
    # عند عدم الاشتراك دون أي تحويل، ولا يفتح البوت (لعرض كابتشا «منع الرشق») إلا
    # بعد اجتياز شرط الاشتراك فعليًا.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"🤍 {votes}",
            callback_data=f"compvotebtn:{contest_code}:{participant_id}",
            style="primary",
        )],
        [copy_btn],
    ])


def build_contest_vote_premium_blocked_message() -> tuple:
    """رسالة تُعرض لمستخدم غير مفعّل بريميوم عند محاولته التصويت في مسابقة
    مخصّصة حصريًا لمصوّتي تيليجرام بريميوم."""
    parts = [
        ([("💎", EMOJI.get("premium_vote_btn", "💎")),
          " هذه المسابقة تتيح التصويت فقط لمستخدمي تيليجرام المميز Premium."],
         "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_vote_gate_message() -> tuple:
    """رسالة بوابة الشرط الإلزامي قبل احتساب أي تصويت: يجب الاشتراك في
    القناة الإلزامية أولاً، ثم الضغط على زر «تحقق» لإكمال التصويت."""
    parts = [
        "للتصويت في هذه المسابقة عليك أولاً:",
        "\n\n",
        ([
            (" 1️⃣ ", None), "الاشتراك في القناة الإلزامية أدناه", "\n",
            (" 2️⃣ ", None), "ثم الضغط على زر «تحقق ✅» لإتمام تصويتك",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_contest_vote_gate_keyboard(
    contest_code: str, participant_id: int, missing_channels: list = None,
) -> InlineKeyboardMarkup:
    missing_channels = missing_channels or []
    if missing_channels:
        rows = build_required_channels_rows(missing_channels)
    else:
        rows = [[InlineKeyboardButton(REQUIRED_CHANNEL_BUTTON_TEXT, url=get_required_channel_url())]]
    rows.append([InlineKeyboardButton(
        "تحقق ✅", callback_data=f"compcond:{contest_code}:{participant_id}", style="success",
    )])
    return InlineKeyboardMarkup(rows)


def build_vote_captcha_message(target_emoji_id: str) -> tuple:
    """رسالة الكابتشا التي تُعرض للمستخدم عند محاولة التصويت لمتسابق (تحقق أنك لست روبوت)."""
    parts = [
        "🤖 للتحقق انك لست روبوت للتصويت اضغط على الرمز:",
        "\n\n",
        ("🔘", target_emoji_id),
    ]
    return build_text_with_emojis(parts)


def build_vote_captcha_keyboard(token: str, option_ids: list, correct_index: int,
                                 prefix: str = "compcap") -> InlineKeyboardMarkup:
    """
    يبني صف واحد من 3 أزرار إيموجي عشوائية (مطابق تمامًا لشكل كابتشا تيليجرام)،
    حيث يمثّل كل زر رمزًا مختلفًا وزر واحد فقط (عند correct_index) هو الرمز الصحيح.

    ملاحظة مهمة: هذه الدالة تُستخدم لبناء كابتشا التصويت في المسابقات (compcap)
    وأيضًا كابتشا منع الرشق في السحوبات (gwcap). كانت تُبنى دائمًا ببادئة "compcap"
    ثابتة بغض النظر عن السياق، فكانت أزرار كابتشا السحب تُرسل بيانات "compcap:..."
    فتُعالَج بواسطة hander كابتشا التصويت (الذي يبحث عن الجلسة في
    context.user_data["vote_captchas"]) بدل هاندلر كابتشا السحب (الذي يخزّن
    الجلسة في context.user_data["gw_captchas"]) — فتُعتبر الجلسة "غير موجودة"
    فورًا ويظهر خطأ "انتهت صلاحية هذا التحقق" حتى لو كانت الكابتشا جديدة تمامًا.
    الحل: تمرير بادئة مختلفة (prefix) حسب السياق حتى تُطابق كل كابتشا الهاندلر
    الصحيح الخاص بها.
    """
    row = [
        InlineKeyboardButton(
            "◻️",
            callback_data=f"{prefix}:{token}:{idx}",
            icon_custom_emoji_id=emoji_id,
        )
        for idx, emoji_id in enumerate(option_ids)
    ]
    return InlineKeyboardMarkup([row])


def build_vote_captcha_success_message() -> tuple:
    parts = [
        ([("✅", EMOJI["confirm_check"]), " تم التحقق وتسجيل تصويتك بنجاح!"], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_vote_captcha_wrong_alert() -> str:
    return "❌ رمز غير صحيح، حاول اختيار الرمز الصحيح مرة أخرى."


# معرّف الإيموجي المميز (custom emoji) المستخدم في إشعار خصم الصوت، كما هو
# مطلوب في المواصفة (يظهر بدل الرمز الافتراضي "➖").
VOTE_DEDUCTED_EMOJI_ID = "5215635927224820367"


def format_arabic_vote_time(dt: datetime = None) -> str:
    """يبني نص الوقت والتاريخ بصيغة "HH:MM DD/MM/YYYY ص/م" المستخدمة في
    إشعارات التصويت لصاحب المسابقة."""
    dt = dt or datetime.now(timezone.utc)
    hour_12 = dt.strftime("%I:%M")
    date_part = dt.strftime("%d/%m/%Y")
    period = "م" if dt.hour >= 12 else "ص"
    return f"{hour_12} {date_part} {period}"


def build_contest_new_vote_owner_notify_message(participant_display_name: str, voter_display_name: str,
                                                  voter_username: str, current_votes: int,
                                                  vote_time: datetime = None) -> tuple:
    """إشعار احترافي يُرسل لصاحب المسابقة فور احتساب تصويت جديد ومؤكد لأحد
    متسابقيه (بعد اجتياز المصوّت كل الشروط: كابتشا + اشتراك + بريميوم إن
    وُجد). يتضمن اسم المصوّت ويوزره، وقت التصويت، وإجمالي أصوات المتسابق
    بعد احتساب هذا الصوت."""
    username_display = f"@{voter_username}" if voter_username else "لا يوجد"
    parts = [
        ([("💗", EMOJI["gw_vote_icon"]), f" تصويت جديد لـ {participant_display_name}"], "bold", None),
        "\n\n",
        f"اسم المصوت : {voter_display_name}\n",
        f"يوزر المصوت : {username_display}\n",
        f"وقت التصويت : {format_arabic_vote_time(vote_time)}\n",
        f"عدد الأصوات الكلي : {current_votes}",
    ]
    return build_text_with_emojis(parts)


def build_contest_vote_deducted_owner_notify_message(participant_display_name: str,
                                                        voter_display_name: str,
                                                        voter_id: int,
                                                        current_votes: int) -> tuple:
    """إشعار احترافي يُرسل لصاحب المسابقة عند إلغاء تصويت كان مؤكدًا سابقًا،
    بسبب مغادرة المصوّت لإحدى القنوات الإلزامية، مع عدد أصوات المتسابق
    المحدّث فور الخصم مباشرة."""
    parts = [
        ([("➖", VOTE_DEDUCTED_EMOJI_ID), f" خصم صوت على {participant_display_name}"], "bold", None),
        "\n\n",
        "• السبب : غادر قناة المسابقة\n",
        f"• الاسم : {voter_display_name}\n",
        f"• الايدي : {voter_id}\n",
        f"• عدد الاصوات الكلي : {current_votes}",
    ]
    return build_text_with_emojis(parts)


def build_contest_participant_left_owner_notify_message(
    display_name: str, user_id: int, contest_name: str, remaining_count: int,
) -> tuple:
    """إشعار احترافي يُرسل لصاحب المسابقة فور اكتشاف خروج أحد المتسابقين
    فعليًا من قناة المسابقة نفسها — يوضّح أنه استُبعد تلقائيًا (حُذف منشوره
    من القناة وحُذفت كل الأصوات التي حصل عليها)، مع عدد المتسابقين
    المتبقين حاليًا في المسابقة."""
    parts = [
        ([("➖", VOTE_DEDUCTED_EMOJI_ID), " تم استبعاد متسابق تلقائيًا"], "bold", None),
        "\n\n",
        "• السبب : غادر قناة المسابقة\n",
        f"• الاسم : {display_name}\n",
        f"• الايدي : {user_id}\n",
        f"• المسابقة : {contest_name}\n",
        f"• عدد المتسابقين المتبقين : {remaining_count}",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_participant_left_owner_notify_message(
    display_name: str, username: str, user_id: int, gw_code: str, remaining_count: int,
) -> tuple:
    """نظير build_contest_participant_left_owner_notify_message لكن للسحوبات
    — لا يوجد منشور مستقل لكل مشارك في السحوبات (منشور واحد مشترك يُحدَّث
    فيه العدد فقط)، لذا لا يُذكر هنا حذف أي منشور، بل فقط خصم المشارك من
    العدد الإجمالي المعروض في منشور السحب."""
    username_display = f"@{username}" if username else "لا يوجد"
    parts = [
        ([("➖", VOTE_DEDUCTED_EMOJI_ID), " تم استبعاد مشارك تلقائيًا"], "bold", None),
        "\n\n",
        "• السبب : غادر قناة السحب\n",
        f"• الاسم : {display_name}\n",
        f"• اليوزر : {username_display}\n",
        f"• الايدي : {user_id}\n",
        f"• رقم السحب : #{gw_code}\n",
        f"• إجمالي المشاركين الآن : {remaining_count}",
    ]
    return build_text_with_emojis(parts)


QUICK_ROULETTE_TEXT = (
    "🎡 قسم روليت سريع\n\n"
    "• انشاء روليت: انشاء روليت سريع\n"
    "• الاعدادات: تحكم في اعدادة اللعبة\n\n"
    "• اختر ماتريد من الازرار ادناه ⬇️"
)

def _roulette_progress_bar(current: int, target: int, length: int = 10) -> str:
    """يبني شريط تقدّم مرئي بسيط (مربعات ملوّنة) لعدد المشاركين الحاليين
    مقابل العدد المطلوب، يُستخدم في منشور «روليت سريع» ليبدو أكثر احترافية."""
    if target <= 0:
        return ""
    ratio = min(1.0, current / target)
    filled = min(length, round(length * ratio))
    return "🟩" * filled + "⬜️" * (length - filled)


def build_quick_roulette_channel_message(target: int, current: int, roulette_id=None) -> tuple:
    """رسالة «روليت سريع» الاحترافية التي تُنشر عبر الوضع المضمّن (inline) في
    القناة/القروب، وتُحدَّث في نفس الرسالة عند كل مشاركة جديدة. تتضمّن كليشة
    اللعبة، عداد المشاركين مع شريط تقدّم داخل اقتباس مميّز، وتذييل العلامة
    التجارية الموحّد (نفس تذييل منشورات السحب/المسابقة).

    roulette_id: معرّف السحب السريع الفريد — يُعرض كسطر monospace قابل للنسخ
    حتى يمكن لاحقًا البحث عنه من قسم إدارة السحب السريع لدى المالك."""
    cliche = get_setting("game_cliche") or DEFAULT_GAME_CLICHE
    bar = _roulette_progress_bar(current, target)
    parts = [
        ([("🎡", EMOJI["roulette"]), " روليت سريع"], "bold", None),
        "\n\n",
        cliche,
        "\n\n",
        ([
            ("👥", EMOJI["people"]),
            f" المشاركين: {current}/{target}",
            "\n",
            bar,
        ], "blockquote", None),
    ]
    # 🚫 لم يعد كود السحب السريع يُعرض داخل منشور القناة/القروب العام — أصبح
    # مقصورًا على قسم إدارة السحب السريع الخاص بالمالك، حيث يظهر بصيغة
    # monospace قابلة للنسخ بضغطة واحدة. الوسيط roulette_id ما زال يُمرَّر
    # لهذه الدالة لاستخدامه المحتمل في مواضع الاستدعاء الأخرى، لكنه لم يعد
    # يُدرَج ضمن نص المنشور نفسه.
    base_text, base_entities = build_text_with_emojis(parts)
    footer_text, footer_entities = build_brand_footer()
    shift = utf16_len(base_text)
    combined_text = base_text + footer_text
    combined_entities = base_entities + shift_entities(footer_entities, shift)
    return combined_text, combined_entities


def build_quick_roulette_join_notify_message(display_name: str) -> tuple:
    """رسالة مختصرة تُرسل لمالك الروليت السريع فقط عند انضمام مشارك جديد —
    الاسم فقط دون أي تفاصيل إضافية (آيدي/يوزر/عدد المشاركين)."""
    parts = [
        ([("🎡", EMOJI["roulette"]), f" قام شخص بالاشتراك في روليتك: {display_name}"], "bold", None),
    ]
    return build_text_with_emojis(parts)



def build_waiting_spin_message(target: int, current: int, participants: list) -> tuple:
    """
    participants: قائمة من tuples (user_id, display_name)
    """
    hide = get_setting("hide_participants") == "1"
    parts = [
        ("⧉ اكتمل العدد\n\n", "bold", None),
        ([
            ("👥", EMOJI["people"]),
            f" المشاركين: {current}/{target}  ”"
        ], "blockquote", None),
        "\n\n"
    ]

    if not hide and participants:
        parts.append(("🫧 قائمة المشاركين:\n", "bold", None))
        bq_parts = []
        for i, (uid, name) in enumerate(participants):
            suffix = '  ”\n' if i == 0 else '\n'
            if i == len(participants) - 1:
                suffix = suffix.rstrip('\n')
            bq_parts.append(f"- المشارك ({i + 1}) : ")
            bq_parts.append((name, "mention_id", uid))
            bq_parts.append(suffix)
        parts.append((bq_parts, "blockquote", None))
        parts.append("\n\n")

    parts.append(([
        ("🎯", EMOJI["target"]),
        " في انتظار تدوير الروليت  ”"
    ], "blockquote", None))

    return build_text_with_emojis(parts)

def build_result_message(winner_id: int, winner_name: str, participants: list) -> tuple:
    hide = get_setting("hide_participants") == "1"
    parts = [
        ("• تم اختيار الفائز ", "bold", None), ("🥳", EMOJI["party"]), "\n\n",
        ([
            ("🏆", EMOJI["trophy_win"]),
            " الفائز : ",
            (winner_name, "mention_id", winner_id),
            " ",
            ("🥇", EMOJI["medal"]),
            "  ”"
        ], "blockquote", None),
        "\n\n"
    ]

    if not hide and participants:
        parts.append((f"🔹 جميع المشاركين ({len(participants)}):\n", "bold", None))
        bq_parts = []
        for i, (uid, name) in enumerate(participants):
            suffix = '  ”\n' if i == 0 else '\n'
            if i == len(participants) - 1:
                suffix = suffix.rstrip('\n')
            bq_parts.append(f"- المشارك ({i + 1}) : ")
            bq_parts.append((name, "mention_id", uid))
            bq_parts.append(suffix)
        parts.append((bq_parts, "blockquote", None))
        parts.append("\n\n")

    parts += build_brand_giveaways_parts()
    return build_text_with_emojis(parts)

def waiting_spin_keyboard(roulette_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔷 تدوير الروليت 🔷", callback_data=f"rr_spin_{roulette_id}", style="danger")],
    ])

def result_keyboard(roulette_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↻ اختيار فائز آخر", callback_data=f"rr_respin_{roulette_id}", style="danger")],
        [InlineKeyboardButton("↻ لعب مره اخرى", switch_inline_query="", style="success")],
    ])

def build_giveaway_target_message() -> tuple:
    """شاشة «يرجى تحديد القناة أو القروب للسحب» (Image 1)."""
    parts = [
        ([
            "يرجى تحديد القناة أو القروب للسحب ",
            ("🎯", EMOJI["target_pin"]),
        ], "bold", None),
        "\n\n",
        ([
            "تأكد أولاً أنك مشرف في القناة أو الجروب وأن البوت أيضاً مشرف.",
        ], "blockquote", None),
        "\n\n",
        ([
            "إذا لم تظهر القناة أو الجروب وتأكدت أن البوت موجود كـ «مشرف» وأنت كذلك، يمكنك تسجيله يدوياً من الأسفل ",
            ("⏬", EMOJI["arrow_down"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_target_keyboard(owner_id: int = None) -> InlineKeyboardMarkup:
    rows = []
    if owner_id is not None:
        for chat in get_registered_chats(owner_id):
            title = chat["chat_title"] or str(chat["chat_id"])
            rows.append([InlineKeyboardButton(
                title, callback_data=f"gw_sel:{chat['chat_id']}",
            )])
    rows.append([
        InlineKeyboardButton(
            "تسجيل قناة", callback_data="gw_reg_channel",
            style="primary", **emoji_kwargs("register_plus"),
        ),
        InlineKeyboardButton(
            "تسجيل جروب", callback_data="gw_reg_group",
            style="primary", **emoji_kwargs("register_plus"),
        ),
    ])
    rows.append([InlineKeyboardButton(
        "حذف قناة", callback_data="gw_del_channels",
        style="danger", **emoji_kwargs("delete_all_btn"),
    )])
    rows.append([InlineKeyboardButton(
        "رجوع", callback_data="back_main_menu",
        style="danger", **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_giveaway_delete_message() -> tuple:
    parts = [
        (["🗑️ حذف قناة أو مجموعة"], "bold", None),
        "\n\n",
        "اضغط على 🗑️ لحذف:",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_delete_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    rows = []
    for chat in get_registered_chats(owner_id):
        title = chat["chat_title"] or str(chat["chat_id"])
        rows.append([
            InlineKeyboardButton(title, callback_data="gw_noop"),
            InlineKeyboardButton("🗑️", callback_data=f"gw_delc:{chat['chat_id']}"),
        ])
    rows.append([InlineKeyboardButton(
        "رجوع", callback_data="gw_start_create",
        style="danger", **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_back_to_giveaway_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "gw_start_create", "danger", "back_section_btn")


GW_LIST_PAGE_SIZE = 8


def build_my_giveaways_list_message(page: int, total_pages: int) -> tuple:
    """شاشة «سحوباتي»: تعرض رقم الصفحة الحالية من إجمالي الصفحات."""
    parts = [
        ([("🎁", EMOJI["draws_check"]), " سحوباتي"], "bold", None),
        "\n\n",
        ([
            f"كل سحوباتك • صفحة {page}/{total_pages}", "\n",
            "اختر سحبًا لعرض تفاصيله:",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_my_giveaways_list_keyboard(giveaways, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    أزرار مرقّمة (زر لكل سحب) مع نقطة ملوّنة تدل على حالته (🟢 نشط / 🔴 متوقف).
    عند كثرة السحوبات تُقسَّم تلقائيًا إلى صفحات (GW_LIST_PAGE_SIZE في كل صفحة)
    مع صف تنقّل «السابق / التالي» حتى لا تتكدّس القائمة.
    """
    start = (page - 1) * GW_LIST_PAGE_SIZE
    page_items = giveaways[start:start + GW_LIST_PAGE_SIZE]

    rows = []
    for offset, gw in enumerate(page_items):
        index = start + offset + 1
        dot = "🟢" if gw["status"] == "open" else "🔴"
        rows.append([InlineKeyboardButton(
            f"{dot} #{index}", callback_data=f"gwmy_detail:{gw['gw_code']}:{page}",
        )])

    if total_pages > 1:
        rows.append(build_pager_nav_row(page, total_pages, "gwmy_page:{page}", "gw_noop"))

    rows.append([InlineKeyboardButton(
        "رجوع", callback_data="back_main_menu",
        style="danger", **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_my_giveaway_detail_message(giveaway, index: int, channel_title: str,
                                      participants_total: int, new_rewarded_count: int) -> tuple:
    """شاشة تفاصيل سحب واحد من «سحوباتي»."""
    status_line = "🟢 نشط" if giveaway["status"] == "open" else "🔴 متوقف"
    parts = [
        ([
            f"🎁 السحب #{index}",
            "\n\n",
            f"👥 عدد المشاركين الكلي : {participants_total}", "\n",
            f"🏆 عدد الفائزين : {giveaway['winners_count']}", "\n",
            f"📊 الحالة : {status_line}", "\n",
            f"✨ مشاركون جدد احتُسبت نقاطهم : {new_rewarded_count}", "\n",
            f"📢 القناة : {channel_title}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_my_giveaway_detail_keyboard(page: int) -> InlineKeyboardMarkup:
    """زر «رجوع» فقط، يعيد المستخدم لنفس صفحة القائمة التي جاء منها."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "رجوع", callback_data=f"gwmy_page:{page}",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_giveaway_cliche_message() -> tuple:
    parts = [
        ([
            ("📨", EMOJI["envelope_klesha"]),
            " أرسل كليشة السحب",
        ], "bold", None),
        "\n\n",
        "اكتب نص السحب الذي تريد نشره في القناة.\n"
        "يمكنك استخدام تنسيقات تيليجرام مثل:\n",
        "• ", ("نص عريض", "bold", None), "\n",
        "• ", ("نص مائل", "italic", None), "\n",
        "• ", ("نص مشوش", "spoiler", None), "\n",
        ([("🆕", EMOJI["new_badge"]), " يمكنك وضع رابط داخل النص"], "link", "https://t.me"),
        "\n",
        (["نص مقتبس  ”"], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_cliche_keyboard() -> InlineKeyboardMarkup:
    return build_back_to_giveaway_keyboard()


GIVEAWAY_SETTINGS_DEFAULTS = {
    "gw_boost": False,
    "gw_premium": False,
    "gw_antispam": False,
    "gw_vote_contest_code": None,
    "gw_vote_participant_id": None,
    "gw_vote_participant_code": None,
    "gw_vote_display_name": None,
    "gw_condition_channels": [],
    "gw_autospin_mode": None,
    "gw_autospin_target": None,
    "gw_autospin_minutes": None,
}

GW_CONDITION_CHANNELS_MAX = 2
GW_CONDITION_CIRCLE_NUMS = ["❶", "❷", "❸"]


def build_giveaway_settings_message() -> tuple:
    parts = [
        ([("⚙️", EMOJI["target"]), " إعدادات السحب"], "bold", None),
        "\n\n",
        (["اختر شرطًا لتحسين السحب:"], "blockquote", None),
        "\n\n",
        ("1️⃣", EMOJI["num_one"]), " قناة شرط: الاشتراك في قناة محددة", "\n",
        ("2️⃣", EMOJI["num_two"]), " تعزيز القناة: تعزيز قناتك", "\n",
        ("3️⃣", EMOJI["num_three"]), " التصويت: التصويت لمتسابق معين", "\n",
        ("4️⃣", EMOJI["num_four"]), " مشتركون مميزون: للمشتركين المميزين", "\n",
        ("5️⃣", EMOJI["num_five"]), " منع الرشق: حماية السحب من الرشق", "\n",
        ("6️⃣", EMOJI["num_six"]), " سحب تلقائي: عند اكتمال العدد أو انتهاء الوقت",
        "\n\n",
        ([
            "• اختر الشرط الذي تريده من الأزرار أدناه ",
            ("⏬", EMOJI["arrow_down"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_settings_keyboard(user_data: dict) -> InlineKeyboardMarkup:
    def toggle_btn(label: str, flag: bool, callback_data: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            f"{label} : {'نعم' if flag else 'لا'}",
            callback_data=callback_data,
            style="success" if flag else "danger",
            **emoji_kwargs("yes_btn" if flag else "no_btn"),
        )

    boost = user_data.get("gw_boost", GIVEAWAY_SETTINGS_DEFAULTS["gw_boost"])
    premium = user_data.get("gw_premium", GIVEAWAY_SETTINGS_DEFAULTS["gw_premium"])
    antispam = user_data.get("gw_antispam", GIVEAWAY_SETTINGS_DEFAULTS["gw_antispam"])

    vote_contest_code = user_data.get("gw_vote_contest_code")
    vote_participant_id = user_data.get("gw_vote_participant_id")
    if vote_contest_code and vote_participant_id:
        vote_display_name = user_data.get("gw_vote_display_name") or "متسابق"
        votes = get_participant_votes(vote_contest_code, vote_participant_id)
        vote_btn = InlineKeyboardButton(
            f"🤍 {votes}   {vote_display_name}", callback_data="gw_opt_vote",
            style="success", **emoji_kwargs("gw_vote_icon"),
        )
    else:
        vote_btn = InlineKeyboardButton("تصويت متسابق", callback_data="gw_opt_vote",
                                         style="primary", **emoji_kwargs("gw_vote_icon"))

    condition_channels = user_data.get("gw_condition_channels") or []
    if condition_channels:
        label = condition_channels[0]["title"]
        extra = len(condition_channels) - 1
        if extra > 0:
            label = f"{label} +{extra}"
        condition_btn = InlineKeyboardButton(
            label, callback_data="gw_opt_condition",
            style="success", **emoji_kwargs("gw_condition_channel"),
        )
    else:
        condition_btn = InlineKeyboardButton(
            "قناة شرط", callback_data="gw_opt_condition",
            style="primary", **emoji_kwargs("gw_condition_channel"),
        )

    autospin_mode = user_data.get("gw_autospin_mode", GIVEAWAY_SETTINGS_DEFAULTS["gw_autospin_mode"])
    if autospin_mode == "count" and user_data.get("gw_autospin_target"):
        autospin_label = f"سحب تلقائي: {user_data['gw_autospin_target']} مشترك"
        autospin_btn = InlineKeyboardButton(
            autospin_label, callback_data="gw_opt_autospin",
            style="success", **emoji_kwargs("target_pin"),
        )
    elif autospin_mode == "time" and user_data.get("gw_autospin_minutes"):
        autospin_label = f"سحب تلقائي: {format_duration_label(user_data['gw_autospin_minutes'])}"
        autospin_btn = InlineKeyboardButton(
            autospin_label, callback_data="gw_opt_autospin",
            style="success", **emoji_kwargs("gw_atime_clock"),
        )
    else:
        autospin_btn = InlineKeyboardButton(
            "سحب تلقائي", callback_data="gw_opt_autospin",
            style="primary", **emoji_kwargs("draws_check"),
        )

    return InlineKeyboardMarkup([
        [
            toggle_btn("تعزيز القناة", boost, "gw_toggle_boost"),
            condition_btn,
        ],
        [
            toggle_btn("مشتركين المميز", premium, "gw_toggle_premium"),
            vote_btn,
        ],
        [
            toggle_btn("منع الرشق", antispam, "gw_toggle_antispam"),
            autospin_btn,
        ],
        [InlineKeyboardButton(
            "نشر السحب", callback_data="gw_opt_create",
            style="success", **emoji_kwargs("yes_btn"),
        )],
        [InlineKeyboardButton(
            "رجوع", callback_data="gw_back_main",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_giveaway_autospin_end_method_message() -> tuple:
    """شاشة «اختر طريقة انتهاء السحب» الخاصة بالسحب التلقائي (Image 2)."""
    parts = [
        (["اختر طريقة انتهاء السحب", ("❓", EMOJI["end_question"])], "bold", None),
        "\n\n",
        ([
            ("🎯", EMOJI["target_pin"]), " عدد محدد ", ("⚡️", EMOJI["gw_atime_lightning"]),
            " : ينتهي السحب تلقائيًا عند وصول عدد المشاركين إلى الرقم الذي تحدده",
        ], "blockquote", None),
        "\n\n",
        ([
            ("🕖", EMOJI["gw_atime_clock"]), " وقت محدد : ينتهي السحب عند انتهاء الوقت الذي "
            "تحدده ويتم اختيار الفائزين ", ("🏆", EMOJI["trophy_win"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_autospin_end_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "عدد محدد", callback_data="gw_atime_end_count",
                style="primary", **emoji_kwargs("target_pin"),
            ),
            InlineKeyboardButton(
                "وقت محدد", callback_data="gw_atime_end_time",
                style="primary", **emoji_kwargs("gw_atime_clock"),
            ),
        ],
        [InlineKeyboardButton(
            "رجوع للخيارات", callback_data="gw_back_to_options",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_giveaway_autospin_count_message() -> tuple:
    """شاشة «أرسل عدد المشاركين المطلوب» لتفعيل السحب التلقائي لعدد محدد (Image 3)."""
    parts = [
        ([
            ("🎯", EMOJI["target_pin"]), " السحب التلقائي لـ عدد محدد",
        ], "bold", None),
        "\n\n",
        "أرسل عدد المشاركين المطلوب لبدء السحب تلقائياً",
        "\n\n",
        ([
            "مثال: إذا أردت تفعيل السحب التلقائي عند وصول عدد المشاركين إلى 100 "
            "أرسل الرقم 100",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_autospin_count_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع للخيارات", "gw_atime_back", "danger", "back_section_btn")


def build_giveaway_autospin_time_message(selected_label: str = "غير محدد") -> tuple:
    """شاشة «السحب التلقائي لـ وقت محدود» بعرض قائمة الأوقات الجاهزة (Image 4)."""
    parts = [
        ([
            ("🕖", EMOJI["gw_atime_clock"]), " السحب التلقائي لـ وقت محدود",
        ], "bold", None),
        f"\nالوقت المختار: {selected_label}",
        "\n\n",
        "استخدم الأزرار أدناه لتحديد الوقت المطلوب لبدء السحب تلقائياً:",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_autospin_time_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for row in CONTEST_TIME_OPTIONS:
        rows.append([
            InlineKeyboardButton(
                label, callback_data=f"gw_atime_set_{minutes}",
                style="primary", **emoji_kwargs("time_option_btn"),
            )
            for minutes, label in row
        ])
    rows.append([
        InlineKeyboardButton(
            "وقت مخصص", callback_data="gw_atime_show_custom",
            style="primary", **emoji_kwargs("time_manual_btn"),
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            "رجوع", callback_data="gw_atime_back",
            style="danger", **emoji_kwargs("back_time_menu_btn"),
        )
    ])
    return InlineKeyboardMarkup(rows)


GW_AUTOSPIN_CUSTOM_STEPS = [
    [(-1, "- 1 دقيقة"), (1, "+ 1 دقيقة")],
    [(-5, "- 5 دقيقة"), (5, "+ 5 دقيقة")],
    [(-10, "- 10 دقايق"), (10, "+ 10 دقايق")],
    [(-60, "- 1 ساعة"), (60, "+ 1 ساعة")],
    [(-1440, "- 1 يوم"), (1440, "+ 1 يوم")],
]


def build_giveaway_autospin_custom_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for row in GW_AUTOSPIN_CUSTOM_STEPS:
        rows.append([
            InlineKeyboardButton(
                label, callback_data=f"gw_atime_custom_delta:{delta}",
                style="primary", **emoji_kwargs("time_option_btn"),
            )
            for delta, label in row
        ])
    rows.append([InlineKeyboardButton(
        "تأكيد الوقت", callback_data="gw_atime_custom_confirm",
        style="success", **emoji_kwargs("yes_btn"),
    )])
    rows.append([
        InlineKeyboardButton(
            "إعادة تعيين", callback_data="gw_atime_custom_reset",
            style="success", **emoji_kwargs("restore_defaults_btn"),
        ),
        InlineKeyboardButton(
            "رجوع للخيارات", callback_data="gw_back_to_options",
            style="danger", **emoji_kwargs("back_section_btn"),
        ),
    ])
    return InlineKeyboardMarkup(rows)


def build_giveaway_vote_code_message() -> tuple:
    """شاشة طلب كود المتسابق لجعل التصويت له شرطًا للمشاركة في السحب (Image 2)."""
    parts = [
        ([("📌", EMOJI["pin_note"]), " يرجى ارسال كود المتسابق الذي تريد جعله شرطًا"], "bold", None),
        "\n\n",
        ("📌", EMOJI["pin_note"]), " مثال على الكود: C12345678",
        "\n\n",
        (["⚠️ ملاحظة: لن يتمكن أي شخص من المشاركة في السحب قبل إتمام التصويت للمتسابق المحدد"],
         "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_vote_code_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع", "gw_back_to_options", "danger", "back_section_btn")


def build_giveaway_vote_code_error_message() -> tuple:
    """رسالة الخطأ عند إرسال كود متسابق غير صحيح أو مسابقة منتهية (Image 5)."""
    parts = [
        (["❌ كود المتسابق غير صحيح أو المسابقة انتهت!"], "bold", None),
        "\n\n",
        "تأكد من الكود وحاول مجدداً.",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_vote_code_error_keyboard() -> InlineKeyboardMarkup:
    return build_giveaway_vote_code_keyboard()


def build_giveaway_vote_linked_message(participant_code: str) -> tuple:
    """رسالة تأكيد ربط كود المتسابق بشرط السحب بنجاح (Image 4)."""
    parts = [
        (["✅ تم ربط كود المتسابق:"], "bold", None),
        f"\n{participant_code}",
        "\n\n",
        "كل مشارك سيتحقق من تصويته قبل المشاركة في السحب.",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_type_message() -> tuple:
    """شاشة اختيار نوع «قناة الشرط»: عامة أو خاصة (Image 2)."""
    parts = [
        ([("📢", EMOJI["gw_condition_channel"]), " قناة الشرط"], "bold", None),
        "\n\n",
        "اختر نوع قناة الشرط:",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌐 قناة عامة", callback_data="gw_cond_public", style="primary"),
            InlineKeyboardButton("🔒 قناة خاصة", callback_data="gw_cond_private", style="primary"),
        ],
        [InlineKeyboardButton(
            "رجوع للخيارات", callback_data="gw_back_to_options",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_giveaway_condition_public_message() -> tuple:
    """شاشة طلب يوزر القناة العامة (أو قناتين) لجعلها شرط اشتراك للمشاركة (Image 3)."""
    parts = [
        ([("📢", EMOJI["gw_condition_channel"]), " قناة الشرط العامة"], "bold", None),
        "\n\n",
        "الان ارسل لي يوزر قناة الشرط", "\n",
        "مثال @e_ggf",
        "\n\n",
        "لا تضف أي نص إضافي مع اليوزر",
        "\n\n",
        (["تأكد من إضافة البوت كمشرف في قناة الشرط مع صلاحية إدارة الأعضاء"],
         "blockquote", None),
        "\n\n",
        ([
            "يمكنك إضافة قناتين كحد أقصى، ويتم إدخال الأسماء بهذا الشكل:", "\n",
            "@e_ggf", "\n",
            "@n_bbo",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_public_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع للخيارات", "gw_opt_condition", "danger", "back_section_btn")


def build_giveaway_condition_private_message(added_count: int = 0) -> tuple:
    """شاشة طلب توجيه رسالة من القناة الخاصة لجعلها شرط اشتراك للمشاركة.
    عند added_count == 1 (بعد إضافة أول قناة) تتحول الرسالة لعرض إمكانية إضافة
    قناة ثانية اختيارية أو إنهاء الآن بقناة واحدة فقط."""
    if added_count >= 1:
        parts = [
            ([("✅", EMOJI["sub_check"]), f" تم إضافة القناة الخاصة رقم {added_count} بنجاح"], "bold", None),
            "\n\n",
            "يمكنك إعادة توجيه رسالة من قناة خاصة ثانية (اختياري)، أو الضغط على «إنهاء» للاكتفاء بالقناة الحالية.",
        ]
    else:
        parts = [
            ([("📢", EMOJI["gw_condition_channel"]), " قناة الشرط الخاصة"], "bold", None),
            "\n\n",
            "الان قم بإعادة توجيه أي رسالة من قناتك الخاصة إلى هنا",
            "\n\n",
            (["تأكد من إضافة البوت كمشرف في القناة مع صلاحية إدارة الأعضاء، وأن تكون أنت مشرفًا فيها أيضًا"],
             "blockquote", None),
            "\n\n",
            (["يمكنك إضافة قناتين خاصتين كحد أقصى، بتوجيه رسالة من كل قناة على حدة"],
             "blockquote", None),
        ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_private_keyboard(added_count: int = 0) -> InlineKeyboardMarkup:
    if added_count >= 1:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "إنهاء ✅", callback_data="gw_cond_private_done",
                style="success", **emoji_kwargs("yes_btn"),
            )],
            [InlineKeyboardButton(
                "رجوع للخيارات", callback_data="gw_opt_condition",
                style="danger", **emoji_kwargs("back_section_btn"),
            )],
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "رجوع للخيارات", callback_data="gw_opt_condition",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ])


def build_giveaway_condition_error_message() -> tuple:
    """رسالة الخطأ عند تعذّر التحقق من قناة الشرط المُدخلة."""
    parts = [
        (["❌ تعذّر العثور على القناة أو أن البوت ليس مشرفًا فيها!"], "bold", None),
        "\n\n",
        "تأكد من اليوزر وأن البوت مضاف كمشرف بصلاحية إدارة الأعضاء، ثم حاول مجدداً.",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_max_error_message() -> tuple:
    """رسالة الخطأ عند إرسال أكثر من قناتين لشرط السحب."""
    parts = [
        (["❌ يمكنك إضافة قناتين كحد أقصى!"], "bold", None),
        "\n\n",
        "أرسل يوزر قناة واحدة أو قناتين فقط (كل يوزر في سطر منفصل).",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_linked_message(channel_titles) -> tuple:
    """رسالة تأكيد ربط قناة/قنوات الشرط بنجاح (Image 4)."""
    titles_line = "\n".join(channel_titles) if isinstance(channel_titles, (list, tuple)) else str(channel_titles)
    parts = [
        (["✅ تم اضافة قناة الشرط بنجاح"], "bold", None),
        f"\n{titles_line}",
        "\n\n",
        "كل مشارك سيتحقق من اشتراكه في القناة قبل المشاركة في السحب.",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_condition_subscribe_alert() -> str:
    """نص التنبيه الداخلي (show_alert) الذي يظهر عند محاولة المشاركة دون اشتراك في
    قناة/قنوات الشرط (Image 2 — نص عام دون ذكر اسم قناة محددة)."""
    return "❌ يجب عليك الاشتراك في قناة الشرط اولاً"


def build_giveaway_vortex_subscribe_alert(missing_channels: list) -> str:
    """نص التنبيه الداخلي (show_alert) الذي يظهر عند الضغط على زر «اضغط لـ
    المشاركة» أسفل منشور السحب حين يكون المستخدم غير مشترك في قناة/قنوات
    VORTEX الإجبارية العامة — تنبيه فوري بالنص فقط دون تحويله إلى البوت،
    بنفس أسلوب بقية تنبيهات شروط السحب (يسمّي القناة الناقصة إن كانت واحدة
    فقط، أو يشير لعددها إن كانت أكثر)."""
    if not missing_channels:
        return "❌ يجب عليك الاشتراك في قناة البوت الإجبارية أولاً للمشاركة"
    if len(missing_channels) == 1:
        label = _required_channel_label(missing_channels[0])
        return f"❌ يجب عليك الاشتراك في «{label}» أولاً للمشاركة في هذا السحب"
    labels = "، ".join(_required_channel_label(ch) for ch in missing_channels)
    return f"❌ يجب عليك الاشتراك في القنوات التالية أولاً للمشاركة: {labels}"


def build_contest_vortex_subscribe_alert(missing_channels: list) -> str:
    """نص تنبيه فوري (show_alert) يظهر عند الضغط على زر «المشاركة» أو زر
    التصويت 🤍 أسفل منشور المسابقة في القناة/القروب مباشرة، حين يكون المستخدم
    غير مشترك في قناة/قنوات VORTEX الإجبارية العامة — دون أي تحويل إلى البوت،
    بنفس أسلوب build_giveaway_vortex_subscribe_alert."""
    if not missing_channels:
        return "❌ يجب عليك الاشتراك في قناة البوت الإجبارية أولاً للمتابعة"
    if len(missing_channels) == 1:
        label = _required_channel_label(missing_channels[0])
        return f"❌ يجب عليك الاشتراك في «{label}» أولاً للمتابعة"
    labels = "، ".join(_required_channel_label(ch) for ch in missing_channels)
    return f"❌ يجب عليك الاشتراك في القنوات التالية أولاً: {labels}"


def build_contest_channel_subscribe_alert(channel_title: str = "") -> str:
    """نص تنبيه فوري (show_alert) يظهر عند عدم اشتراك المستخدم في قناة نشر
    هذه المسابقة نفسها تحديدًا (عند الضغط على زر المشاركة أو التصويت مباشرة من
    القناة/القروب) — دون أي تحويل إلى البوت، بنفس أسلوب
    build_giveaway_host_channel_subscribe_alert."""
    if channel_title:
        return f"🔔 يجب عليك الاشتراك في «{channel_title}» أولاً للمتابعة في هذه المسابقة"
    return "🔔 يجب عليك الاشتراك في قناة المسابقة أولاً للمتابعة"


def build_giveaway_host_channel_subscribe_alert(host_channel_title: str = "") -> str:
    """نص التنبيه الداخلي (show_alert) الذي يظهر عند الضغط المباشر على زر
    «اضغط لـ المشاركة» أسفل منشور السحب حين يكون المستخدم مشتركًا في VORTEX
    لكنه غير مشترك في القناة التي استضافت السحب نفسه — يظهر كتنبيه فوري دون
    تحويل المستخدم إلى البوت، تمييزًا عن حالة عدم الاشتراك في VORTEX."""
    if host_channel_title:
        return f"❌ يجب عليك الاشتراك في «{host_channel_title}» أولاً للمشاركة في هذا السحب"
    return "❌ يجب عليك الاشتراك في قناة السحب أولاً للمشاركة"


def build_giveaway_gate_message(giveaway, need_vortex: bool = False,
                                 host_channel_title: str = "") -> tuple:
    """رسالة «بوابة الشروط» التي تظهر للمستخدم داخل البوت بعد الضغط على زر
    المشاركة في سحب مفعّل عليه «منع الرشق» — تُعرض فقط عندما لا يكون قد
    اجتاز بعد شرط/شروط السحب (اشتراك في القنوات و/أو تعزيز)، وقبل ظهور زر
    التحقق (الكابتشا) الذي يظهر بعد إكمال هذه الشروط.

    عند need_vortex/host_channel_title تُدرَج أيضًا قناة VORTEX الإجبارية
    و/أو قناة استضافة السحب نفسها ضمن قائمة الشروط، لعرضهما معًا مع بقية
    الشروط في بوابة واحدة موحّدة بدل بوابتين متتاليتين."""
    channels = (giveaway.get("condition_channels") or [])[:GW_CONDITION_CHANNELS_MAX]
    lines = []
    for req_ch in (need_vortex or []):
        lines.append(f"• {req_ch.get('button_text') or req_ch.get('title') or ('@' + req_ch.get('username', ''))}")
    if host_channel_title:
        lines.append(f"• {host_channel_title}")
    lines += [f"• {ch.get('title') or ch.get('ref') or 'القناة'}" for ch in channels]
    if giveaway.get("boost_required"):
        lines.append("• تعزيز القناة (Boost)")
    vote_contest_code = giveaway.get("vote_contest_code")
    vote_participant_id = giveaway.get("vote_participant_id")
    if vote_contest_code and vote_participant_id:
        lines.append("• التصويت للمتسابق المطلوب")

    parts = [
        "عليك إكمال الشروط التالية أولاً", "\n",
        "- لتتمكن من المشاركة في السحب: ", ("🎁", EMOJI["target_pin"]),
    ]
    if lines:
        parts += ["\n", "\n".join(lines)]
    parts += [
        "\n\n",
        ([
            ("‼️", EMOJI["sub_alert"]),
            " | أكمل الشروط ثم اضغط تحقق",
            ("✅", EMOJI["sub_check"]),
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_gate_keyboard(gw_code: str, giveaway, is_genuinely_new: bool,
                                  boost_link: str = "", vote_link: str = "",
                                  need_vortex: bool = False, host_channel_link: str = "",
                                  host_channel_title: str = "") -> InlineKeyboardMarkup:
    """كيبورد بوابة الشروط: زر لكل قناة/تعزيز/تصويت مطلوب، وزر «تحقق ✅» أسفلها.
    عند الضغط على «تحقق» يُعاد فحص الشروط؛ فإن اجتازها المستخدم تتحوّل نفس
    الرسالة إلى كابتشا التحقق منع الرشق الموجودة مسبقًا.

    إن كان need_vortex/host_channel_link مفعّلين، يُضاف زر قناة VORTEX و/أو
    زر قناة استضافة السحب أعلى بقية الأزرار — فقط للشرط الناقص فعليًا، دون
    عرض زر لشرط مكتمل بالفعل."""
    rows = []
    if need_vortex:
        rows += build_required_channels_rows(need_vortex)
    if host_channel_link:
        rows.append([InlineKeyboardButton(host_channel_title or "قناة السحب", url=host_channel_link)])
    channels = (giveaway.get("condition_channels") or [])[:GW_CONDITION_CHANNELS_MAX]
    for ch in channels:
        title = ch.get("title") or "الإشتراك في القناة"
        link = ch.get("url") or f"https://t.me/{str(ch.get('ref', '')).lstrip('@')}"
        rows.append([InlineKeyboardButton(title, url=link)])
    if boost_link:
        rows.append([InlineKeyboardButton("تعزيز القناة (Boost)", url=boost_link)])
    if vote_link:
        rows.append([InlineKeyboardButton("التصويت للمتسابق", url=vote_link)])
    rows.append([
        InlineKeyboardButton(
            "تحقق ✅", callback_data=f"gwcond:{gw_code}:{1 if is_genuinely_new else 0}",
        )
    ])
    return InlineKeyboardMarkup(rows)


def build_giveaway_winners_message() -> tuple:
    parts = [
        ([
            "أرسل عدد الفائزين المطلوب ",
            ("🏆", EMOJI["trophy_winners_title"]),
        ], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_winners_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("رجوع للخيارات", "gw_back_to_options", "danger", "back_section_btn")


def build_giveaway_publish_success_message() -> tuple:
    parts = [
        (["✅ تم نشر السحب بنجاح !"], "bold", None),
    ]
    return build_text_with_emojis(parts)


def build_giveaway_vote_condition_link(vote_contest_code: str, vote_participant_id) -> str:
    """يبني رابط التصويت المخفي (نفس رابط زر 🤍 أسفل منشور المتسابق) الذي تحمله
    كلمة «هنا» داخل اقتباس شرط التصويت في منشور السحب."""
    return f"https://t.me/{BOT_USERNAME}?start=compvote_{vote_contest_code}_{vote_participant_id}"


def build_giveaway_autospin_notice_text(giveaway) -> str:
    """يبني نص عبارة «سحب تلقائي» المزخرفة المضافة أسفل منشور السحب (Image 9)،
    والتي تُحدَّث تلقائيًا كل 10 دقائق في حالة «وقت محدد» حتى وصول العداد للصفر."""
    mode = giveaway.get("autospin_mode")
    if mode == "count":
        target = giveaway.get("autospin_target")
        return f"يُسحب تلقائيًا عند اكتمال {target} مشارك"
    if mode == "time":
        end_at = giveaway_autospin_end_datetime(giveaway)
        remaining_minutes = max(0, (end_at - datetime.now(timezone.utc)).total_seconds() / 60)
        remaining_label = format_duration_label(round(remaining_minutes)) if remaining_minutes >= 1 else "لحظات"
        return f"يُسحب تلقائيًا بعد {remaining_label}"
    return ""


def build_giveaway_channel_message(cliche_text: str, cliche_entities, gw_code: str = None, vote_link: str = None,
                                    condition_channels=None, boost_link: str = None,
                                    autospin: dict = None) -> tuple:
    """منشور السحب الذي يُنشر في القناة/القروب (Image 5).

    gw_code: كود السحب الفريد. لا يُعرض داخل منشور القناة/القروب العام —
    يبقى مقصورًا على قسم «🎁 السحوبات» الخاص بالمالك (build_admgw_detail_message)
    حيث يظهر بصيغة monospace قابلة للنسخ بضغطة واحدة، حتى يتمكن المالك أو أي
    مشرف من استخدامه لاحقًا للبحث عن هذا السحب تحديدًا داخل قسم إدارة السحوبات.

    إذا كان السحب مشروطًا بالتصويت لمتسابق (vote_link)، يُضاف أعلى تذييل العلامة
    التجارية اقتباس مزخرف «شرط تصويت» تحمل فيه كلمة «هنا» رابطًا مخفيًا يفتح
    نفس مسار التصويت للمتسابق مباشرة عبر البوت (Image 6).

    وإذا كان السحب مشروطًا بالاشتراك في قناة شرط واحدة أو قناتين (condition_channels:
    قائمة عناصر {"title", "url"}) و/أو بتعزيز (Boost) القناة (boost_link)، يُضاف
    اقتباس واحد «الشرط» يحتوي سطرًا مرقّمًا (❶ / ❷ / ❸) لكل بند: قناة/قناتا
    الشرط أولاً ثم بند «تعزيز» إن وُجد، كل سطر تحمل فيه كلمة «هنا» الرابط
    الخاص بذلك البند تحديدًا (Image A3). بند «تعزيز» يفتح نافذة تعزيز القناة
    الأصلية في تيليجرام مباشرة عبر رابط https://t.me/boost/<username> (Image A4)."""
    extra_parts = []
    condition_channels = condition_channels or []
    condition_items = []
    for channel in condition_channels[:GW_CONDITION_CHANNELS_MAX]:
        link = channel.get("url") or f"https://t.me/{str(channel.get('ref', '')).lstrip('@')}"
        condition_items.append(("الإشتراك", link))
    if boost_link:
        condition_items.append(("تعزيز", boost_link))
    if condition_items:
        quote_content = ["• الشرط ", ("⏬", EMOJI["arrow_down"])]
        for idx, (label, link) in enumerate(condition_items):
            circle = GW_CONDITION_CIRCLE_NUMS[idx] if idx < len(GW_CONDITION_CIRCLE_NUMS) else f"{idx + 1}."
            quote_content += [
                "\n", f"{circle} ",
                ([label], "bold", None),
                " ›› ",
                (["هـــنـــا"], "link", link),
            ]
        extra_parts += ["\n\n", (quote_content, "blockquote", None)]
    if vote_link:
        quote_content = [
            "شرط تصويت", "\n\n",
            "• الشرط ", ("⏬", EMOJI["arrow_down"]), "\n",
            (["تصويت"], "bold", None),
            " ›› ",
            (["هـــنـــا"], "link", vote_link),
        ]
        extra_parts += ["\n\n", (quote_content, "blockquote", None)]

    if autospin and autospin.get("mode") in ("count", "time"):
        icon = ("🎯", EMOJI["target_pin"]) if autospin["mode"] == "count" else ("🕖", EMOJI["gw_atime_clock"])
        notice_text = autospin.get("notice_text") or ""
        quote_content = [icon, " ", notice_text]
        extra_parts += ["\n\n", (quote_content, "blockquote", None)]

    # 🚫 لم يعد كود السحب يُعرض داخل منشور القناة/القروب العام — أصبح مقصورًا
    # على قسم «🎁 السحوبات» الخاص بالمالك (build_admgw_detail_message) حيث
    # يظهر بصيغة code قابلة للنسخ بضغطة واحدة. الوسيط gw_code ما زال يُمرَّر
    # لهذه الدالة لأنه يُستخدم في بناء الكيبورد (build_giveaway_channel_keyboard)
    # في مواضع الاستدعاء، لكنه لم يعد يُدرَج ضمن نص المنشور نفسه.

    extra_text, extra_entities = build_text_with_emojis(extra_parts) if extra_parts else ("", [])
    footer_text, footer_entities = build_brand_footer()

    base_text = cliche_text or ""
    base_entities = list(cliche_entities or [])
    shift = utf16_len(base_text)
    footer_shift = utf16_len(base_text + extra_text)

    combined_text = base_text + extra_text + footer_text
    combined_entities = (
        base_entities
        + shift_entities(extra_entities, shift)
        + shift_entities(footer_entities, footer_shift)
    )
    return combined_text, combined_entities


def build_giveaway_channel_keyboard(gw_code: str, current_count: int,
                                     antispam: bool = False,
                                     status: str = "open") -> InlineKeyboardMarkup:
    """يبني كيبورد منشور السحب في القناة/القروب (Image 5)، بنفس تنسيق/ألوان بقية أزرار البوت.

    زر المشاركة دائمًا زر callback_data (gw_join:{gw_code}) بصرف النظر عن تفعيل
    «منع الرشق» من عدمه — ولو كان زر رابط (url) مباشر، لكان يفتح البوت فورًا
    حتى لو كان المستخدم غير مشترك إطلاقًا في قناة استضافة هذا السحب نفسها (أزرار
    الروابط تُفتح مباشرة من طرف تيليجرام دون أي فرصة لفحص أو تنبيه قبلها). بجعله
    callback_data دائمًا، يمر أولاً عبر gw_join_callback الذي يتحقق من شرط قناة
    السحب ويعرض تنبيهًا فوريًا (show_alert) دون تحويل عند عدم الاشتراك، ولا يفتح
    البوت (عبر gwcap_ عند «منع الرشق» أو gwjoin_ لبقية الشروط) إلا بعد اجتياز هذا
    الشرط فعليًا.

    الصف الثالث (أسفل الكيبورد) يتغيّر حسب حالة السحب (status):
    - "open"   : «ايقاف وسحب» (أحمر) لإيقاف استقبال المشاركات مؤقتًا، و
                 «ذكرني اذا فزت» (أخضر).
    - "paused" : بعد الضغط على «ايقاف وسحب» يتحوّل نفس الزر إلى «استئناف
                 المشاركة» (أخضر) لإعادة فتح المشاركة، والزر الآخر يتحوّل إلى
                 «ابدا السحب» (أحمر) الذي يقوم فعليًا باختيار الفائزين عشوائيًا.
    """
    join_text = f"• اضغط لـ المشاركة ({current_count})"
    join_button = InlineKeyboardButton(
        join_text, callback_data=f"gw_join:{gw_code}",
        style="primary",
    )

    if status == "paused":
        row3 = [
            InlineKeyboardButton(
                "استئناف المشاركة", callback_data=f"gw_resume:{gw_code}",
                style="success",
            ),
            InlineKeyboardButton(
                "ابدا السحب", callback_data=f"gw_draw:{gw_code}",
                style="danger",
            ),
        ]
    else:
        row3 = [
            InlineKeyboardButton(
                "ايقاف وسحب", callback_data=f"gw_pause:{gw_code}",
                style="danger",
            ),
            InlineKeyboardButton(
                "ذكرني اذا فزت",
                url=f"https://t.me/{BOT_USERNAME}?start=gw_remind",
                style="success",
            ),
        ]

    return InlineKeyboardMarkup([
        [join_button],
        [
            InlineKeyboardButton(
                "↻ إعادة نشر", callback_data=f"gw_repost:{gw_code}",
                style="primary",
            ),
            InlineKeyboardButton(
                "مشاركة السحب",
                url=f"https://t.me/{BOT_USERNAME}?start=gwshare_{gw_code}",
                style="success",
            ),
        ],
        row3,
    ])


def build_giveaway_join_notify_message(display_name: str, username: str, user_id: int,
                                        gw_number: str, total_participants: int) -> tuple:
    """رسالة إشعار «مشارك جديد في سحبك» تُرسل لمنشئ السحب فقط (Image 6)."""
    username_line = f"@{username}" if username else "—"
    parts = [
        ([("👤", EMOJI["gw_new_participant"]), " مشارك جديد في سحبك!"], "bold", None),
        "\n\n",
        f"• الاسم: {display_name}", "\n",
        f"• اليوزر: {username_line}", "\n",
        f"• الآيدي: {user_id}", "\n",
        f"• رقم السحب: #{gw_number}", "\n",
        f"• إجمالي المشاركين: {total_participants}",
    ]
    return build_text_with_emojis(parts)


def build_giveaway_join_notify_keyboard(gw_code: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "عرض الملف الشخصي", url=f"tg://user?id={user_id}",
            style="success", **emoji_kwargs("gw_view_profile"),
        )],
        [InlineKeyboardButton(
            "استبعاد", callback_data=f"gw_kick:{gw_code}:{user_id}",
            style="danger", **emoji_kwargs("gw_kick_btn"),
        )],
    ])


def build_giveaway_ended_message(cliche_text: str, cliche_entities, winners: list) -> tuple:
    """رسالة إعلان الفائز/الفائزين بعد «ايقاف وسحب»."""
    parts = [
        ([("🏆", EMOJI["trophy_win"]), " انتهى السحب!  ”"], "blockquote", None),
    ]
    if not winners:
        parts.append("\n\n")
        parts.append((["⚠️ لم يشارك أحد في هذا السحب، لم يتم اختيار فائز."], "bold", None))
    elif len(winners) == 1:
        user_id, name = winners[0]
        parts.append("\n\n")
        parts.append(([
            "الفائز ", ("🥇", EMOJI["medal"]), " : ", (name, "mention_id", user_id),
        ], "bold", None))
    else:
        for i, (user_id, name) in enumerate(winners):
            ordinal = ARABIC_ORDINALS[i] if i < len(ARABIC_ORDINALS) else f"رقم {i + 1}"
            parts.append("\n\n")
            parts.append(([
                f"الفائز {ordinal} ", ("🥇", EMOJI["medal"]), " : ", (name, "mention_id", user_id),
            ], "bold", None))
    return build_text_with_emojis(parts)


_FS_CLIENT = None
_FS_LOCK = threading.Lock()


class FSRow(dict):
    """
    يحاكي واجهة sqlite3.Row القديمة: وصول للحقول بالمفتاح row["field"] تمامًا كما
    كانت كل دوال الكود تستخدمها سابقًا مع SQLite، حتى لا يحتاج أي كود خارج طبقة
    قاعدة البيانات هذه إلى أي تعديل.
    """
    pass


def fs_db():
    """يعيد عميل Firestore واحد مشترك (Singleton) بدل تهيئته في كل استدعاء."""
    global _FS_CLIENT
    if _FS_CLIENT is None:
        with _FS_LOCK:
            if _FS_CLIENT is None:
                if not firebase_admin._apps:
                    if not FIREBASE_SERVICE_ACCOUNT.get("private_key"):
                        raise RuntimeError(
                            "متغير البيئة FIREBASE_PRIVATE_KEY غير موجود أو فارغ. "
                            "ضع فيه محتوى private_key من ملف Service Account قبل تشغيل البوت."
                        )
                    cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT)
                    firebase_admin.initialize_app(cred)
                _FS_CLIENT = firestore.client()
    return _FS_CLIENT


def _fs_row_or_none(doc) -> "FSRow | None":
    if doc is None or not doc.exists:
        return None
    return FSRow(doc.to_dict())


# ---------------------------------------------------------------------------
# 👤 مستند المستخدم الموحّد (users/{user_id})
# ---------------------------------------------------------------------------
# قبل هذا التعديل، كانت بيانات "هوية" كل مستخدم مبعثرة على 6 مجموعات
# منفصلة في Firestore: known_bot_users (الحظر/الاسم)، bot_moderators
# (الإشراف)، owner_points (رصيد النقاط)، bot_referrals + referral_signups
# (الإحالة)، remind_win (تذكير الفوز)، rewarded_users (مكافأة أول مشاركة).
# أي شاشة تحتاج صورة كاملة عن مستخدم واحد (مثل تصفّح المستخدمين مع نقاطهم
# وإحالاتهم) كانت تحتاج قراءات متفرقة من عدة مجموعات لكل مستخدم.
#
# الآن كل هذه البيانات حقول داخل مستند واحد فقط: users/{user_id}، وكلها
# تُقرأ وتُخزَّن مؤقتًا معًا عبر نفس الكاش الدائم بالذاكرة (_USER_CACHE) —
# قراءة Firestore واحدة فعلية لكل مستخدم طوال عمر تشغيلة البوت، بدل حتى 6
# قراءات متفرقة. مجموعات غير مرتبطة بهوية مستخدم واحد (channel_points
# مرتبطة بقناة لا بمستخدم، roulettes/contests/giveaways سجلات أحداث غير
# محدودة) بقيت كما هي عمدًا — دمجها داخل مستند مستخدم يخاطر بتجاوز حد حجم
# المستند (1MB) ولا يقلل الاستهلاك أصلًا لأنها لا تُقرأ مع كل رسالة.
#
# حقول مستند users/{id} (كلها اختيارية إلا user_id، تُقرأ بقيم افتراضية):
#   user_id, username, username_lower, first_name, last_name,
#   first_seen_at, last_seen_at, has_started (bool — أول /start فعلي),
#   banned, ban_reason, banned_at, banned_by,
#   is_moderator, mod_permissions, mod_added_by, mod_added_at,
#   points (int),
#   is_referrer, ref_active, ref_percentage, ref_added_by, ref_created_at,
#   ref_referred_count, ref_points_earned, referred_by (منع احتساب إحالة
#     نفس المستخدم مرتين — يغني عن مجموعة referral_signups المنفصلة),
#   remind_win (0/1), rewarded, rewarded_owner_id, rewarded_gw_code,
#   rewarded_at (يغني عن مجموعة rewarded_users المنفصلة).
#
# ⚠️ هذا تغيير في مخطط قاعدة البيانات: لن يقرأ الكود الجديد أي بيانات قديمة
# من known_bot_users/bot_moderators/owner_points/bot_referrals/
# referral_signups/remind_win/rewarded_users. يلزم تشغيل سكربت ترحيل مرة
# واحدة قبل النشر لنقل البيانات الحالية إلى users/{id} — راجع ملاحظات
# الترحيل المرفقة مع هذا الملف.
# ---------------------------------------------------------------------------

def _user_doc_ref(user_id: int):
    return fs_db().collection("users").document(str(user_id))


# ---------------------------------------------------------------------------
# 📜 سجل العمليات الإدارية (Admin Operations Log) — يسجّل تلقائيًا كل عملية
# إدارية حساسة تُنفَّذ من قسم المالك: حذف مسابقة/سحب/سحب سريع، إضافة/حذف
# قناة، حظر/فك حظر مستخدم، إضافة/حذف مشرف، تغيير إعدادات، إرسال إذاعة.
# ---------------------------------------------------------------------------

ADMIN_LOG_LABELS = {
    "delete_contest": "🗑️ حذف مسابقة",
    "delete_giveaway": "🗑️ حذف سحب",
    "delete_quick_roulette": "🗑️ حذف سحب سريع",
    "add_channel": "➕ إضافة قناة",
    "delete_channel": "🗑️ حذف قناة",
    "ban_user": "🚫 حظر مستخدم",
    "unban_user": "✅ فك حظر مستخدم",
    "add_admin": "👨‍💻 إضافة مشرف",
    "remove_admin": "🗑️ حذف مشرف",
    "add_referrer": "🔗 إضافة صاحب رابط دعوة",
    "remove_referrer": "🗑️ إزالة صاحب رابط دعوة",
    "toggle_referrer": "🔁 تغيير حالة رابط دعوة",
    "edit_referrer_percentage": "📊 تعديل نسبة إحالة",
    "add_points_manual": "➕ إضافة نقاط لمستخدم",
    "deduct_points_manual": "➖ خصم نقاط من مستخدم",
    "change_settings": "⚙️ تغيير إعدادات",
    "broadcast": "📣 إرسال إذاعة",
}

ADMIN_LOG_MAX_ENTRIES = 300
ADMIN_LOG_PAGE_SIZE = 8


def _admin_log_actor_label(actor_id: int, actor_name: str = None, actor_username: str = None) -> str:
    if actor_username:
        return f"@{actor_username}"
    if actor_name:
        return actor_name
    return str(actor_id)


def log_admin_action(action: str, actor_id: int, details: str = "",
                      actor_name: str = None, actor_username: str = None) -> None:
    """يسجّل عملية إدارية واحدة في Firestore (admin_logs)، ولا يوقف تنفيذ أي
    عملية إن فشل التسجيل لأي سبب (شبكة/صلاحيات) — مجرد سجل مساعد وليس جوهريًا."""
    try:
        fs_db().collection("admin_logs").add({
            "action": action,
            "actor_id": actor_id,
            "actor_label": _admin_log_actor_label(actor_id, actor_name, actor_username),
            "details": details or "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("تعذّر تسجيل العملية الإدارية: %s", action)


def get_admin_logs(limit: int = ADMIN_LOG_MAX_ENTRIES) -> list:
    """يعيد آخر العمليات الإدارية المسجَّلة، الأحدث أولًا."""
    try:
        docs = (
            fs_db().collection("admin_logs")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [FSRow(d.to_dict()) for d in docs]
    except Exception:
        logger.exception("تعذّر جلب سجل العمليات الإدارية")
        return []


# ---------------------------------------------------------------------------
# 🛠️ صيانة البوت (قسم المالك) — تفعيل/إيقاف وضع الصيانة، قياس سرعة استجابة
# البوت وتصنيفها، تسجيل/عرض الأخطاء غير المتوقعة، وعرض حالة البوت العامة.
# ---------------------------------------------------------------------------

BOT_START_TIME = datetime.now(timezone.utc)


SPEED_THRESHOLDS_MS = [
    (300, "🚀 سريع جدًا"),
    (700, "⚡ سريع"),
    (1500, "🙂 متوسط"),
    (3000, "🐢 بطيء نسبيًا"),
    (6000, "🐌 بطيء"),
]
SPEED_VERY_SLOW_LABEL = "🔴 بطيء جدًا"


def is_maintenance_mode() -> bool:
    """يتحقق مما إذا كان وضع الصيانة مفعّلًا حاليًا."""
    return get_setting("maintenance_mode") == "1"


def set_maintenance_mode(enabled: bool) -> None:
    """يفعّل/يوقف وضع الصيانة."""
    set_setting("maintenance_mode", "1" if enabled else "0")


def classify_response_speed(elapsed_ms: float) -> str:
    """يحوّل زمن استجابة بالمللي ثانية إلى وصف نصي مصنَّف (سريع جدًا ... بطيء جدًا)."""
    for threshold, label in SPEED_THRESHOLDS_MS:
        if elapsed_ms <= threshold:
            return label
    return SPEED_VERY_SLOW_LABEL


def measure_bot_response_time() -> tuple:
    """يقيس زمن استجابة قاعدة البيانات (Firestore) بعملية كتابة ثم قراءة فعليتين
    (أفضل مؤشر متاح لسرعة استجابة البوت ككل)، ويحفظ آخر نتيجة لعرضها لاحقًا
    ضمن «عرض حالة البوت» دون الحاجة لإعادة القياس في كل مرة."""
    start = time.perf_counter()
    ref = fs_db().collection("diagnostics").document("speed_probe")
    ref.set({"ts": datetime.now(timezone.utc).isoformat()})
    ref.get()
    elapsed_ms = (time.perf_counter() - start) * 1000
    label = classify_response_speed(elapsed_ms)
    set_setting("last_speed_ms", str(int(elapsed_ms)))
    set_setting("last_speed_label", label)
    set_setting("last_speed_checked_at", datetime.now(timezone.utc).isoformat())
    return elapsed_ms, label


def get_last_speed_check() -> dict:
    """يعيد آخر نتيجة قياس سرعة محفوظة (إن وُجدت) دون إجراء قياس جديد."""
    ms = get_setting("last_speed_ms")
    label = get_setting("last_speed_label")
    checked_at = get_setting("last_speed_checked_at")
    if not ms:
        return {}
    return {"elapsed_ms": int(ms), "label": label, "checked_at": checked_at}


def format_bot_uptime() -> str:
    """يُنسّق المدة منذ آخر إقلاع للبوت بصيغة بشرية مبسّطة (أيام/ساعات/دقائق)."""
    delta = datetime.now(timezone.utc) - BOT_START_TIME
    total_seconds = int(delta.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} يوم")
    if hours:
        parts.append(f"{hours} ساعة")
    parts.append(f"{minutes} دقيقة")
    return " و".join(parts)


def _fs_create_or_integrity_error(doc_ref, data: dict) -> None:
    """يحاكي سلوك INSERT الذي يفشل عند تكرار المفتاح الأساسي (sqlite3.IntegrityError)."""
    from google.api_core.exceptions import AlreadyExists
    try:
        doc_ref.create(data)
    except AlreadyExists:
        raise sqlite3.IntegrityError("duplicate key")


def _fs_bump_counter(doc_ref, field: str, amount: int, extra: dict = None) -> None:
    """يزيد قيمة حقل رقمي بشكل ذري داخل معاملة (transaction) لتفادي تعارض التحديثات المتزامنة.
    القيمة النهائية لا تنزل تحت الصفر أبدًا (مهم عند خصم نقاط ملغاة)."""
    client = fs_db()
    transaction = client.transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = doc_ref.get(transaction=transaction)
        current = (snap.to_dict().get(field, 0) if snap.exists else 0) or 0
        payload = dict(extra or {})
        payload[field] = max(0, current + amount)
        if snap.exists:
            transaction.update(doc_ref, payload)
        else:
            transaction.set(doc_ref, payload)

    _txn(transaction)


def _next_roulette_id() -> int:
    """عدّاد ذري بديل عن AUTOINCREMENT في SQLite، عبر معاملة على مستند عدّاد واحد."""
    client = fs_db()
    counter_ref = client.collection("counters").document("roulettes")
    transaction = client.transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = counter_ref.get(transaction=transaction)
        current = (snap.to_dict().get("next_id", 0) if snap.exists else 0) or 0
        next_id = current + 1
        transaction.set(counter_ref, {"next_id": next_id})
        return next_id

    return _txn(transaction)


def init_db():
    """
    Firestore بدون بنية جداول مسبقة — المجموعات (collections) تُنشأ تلقائيًا عند
    أول عملية كتابة فيها. الشيء الوحيد المطلوب هنا هو ضمان وجود قيم الإعدادات
    الافتراضية إن لم تكن موجودة بعد (بديل INSERT OR IGNORE في SQLite).
    """
    client = fs_db()
    defaults = {
        "points_enabled": "1",
        "points_per_user": "1",
        "points_required": "100",
        "reward_type": "رصيد",
        "reward_value": "10",
        "points_title": DEFAULT_POINTS_TITLE,
        "points_conditions": DEFAULT_POINTS_CONDITIONS,
        "hide_participants": DEFAULT_HIDE_PARTICIPANTS,
        "game_cliche": DEFAULT_GAME_CLICHE,
        "required_channel_username": REQUIRED_CHANNEL_USERNAME,
        "required_channel_url": REQUIRED_CHANNEL_URL,
        "required_channel_next_username": "",
        "required_channel_auto_target": REQUIRED_CHANNEL_DEFAULT_TARGET,
        "withdraw_channel_id": "",
        "withdraw_channel_username": "",
        "withdraw_channel_title": "",
    }
    for tier, cost in DEFAULT_STAR_COSTS.items():
        defaults[f"star_cost_{tier}"] = str(cost)
    for k, v in defaults.items():
        ref = client.collection("settings").document(k)
        if not ref.get().exists:
            ref.set({"value": v})
    _migrate_legacy_required_channel()

_SETTINGS_CACHE = {}

def get_setting(key: str) -> str:
    if key in _SETTINGS_CACHE:
        return _SETTINGS_CACHE[key]
    doc = fs_db().collection("settings").document(key).get()
    value = doc.to_dict().get("value") if doc.exists else None
    _SETTINGS_CACHE[key] = value
    return value

def set_setting(key: str, value: str):
    fs_db().collection("settings").document(key).set({"value": value})
    _SETTINGS_CACHE[key] = value

def create_roulette(owner_id: int, target_count: int) -> int:
    rid = _next_roulette_id()
    fs_db().collection("roulettes").document(str(rid)).set({
        "roulette_id": rid,
        "owner_id": owner_id,
        "target_count": target_count,
        "inline_message_id": None,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": 0,
    })
    return rid

def _next_roulette_ids(count: int) -> list:
    """يحجز عدة معرّفات دفعة واحدة عبر معاملة واحدة فقط (بدل معاملة Firestore منفصلة
    لكل رقم) — هذا هو أحد سببي بطء ظهور خيارات «روليت سريع»."""
    client = fs_db()
    counter_ref = client.collection("counters").document("roulettes")
    transaction = client.transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = counter_ref.get(transaction=transaction)
        current = (snap.to_dict().get("next_id", 0) if snap.exists else 0) or 0
        transaction.set(counter_ref, {"next_id": current + count})
        return list(range(current + 1, current + count + 1))

    return _txn(transaction)


def create_roulettes_batch(owner_id: int, target_counts: list) -> dict:
    """ينشئ كل خيارات «روليت سريع» (لكل الأعداد في ROULETTE_COUNTS) في طلبين فقط
    إلى Firestore (معاملة واحدة لحجز المعرّفات + كتابة دفعية واحدة)، بدل طلبين
    منفصلين لكل عدد (16 طلب سابقًا لـ 8 أعداد) — هذا يسرّع كثيرًا ظهور القائمة
    فور الضغط على «روليت سريع»."""
    ids = _next_roulette_ids(len(target_counts))
    client = fs_db()
    batch = client.batch()
    now_iso = datetime.now(timezone.utc).isoformat()
    result = {}
    for n, rid in zip(target_counts, ids):
        batch.set(client.collection("roulettes").document(str(rid)), {
            "roulette_id": rid,
            "owner_id": owner_id,
            "target_count": n,
            "inline_message_id": None,
            "status": "open",
            "created_at": now_iso,
            "channel_id": 0,
        })
        result[n] = rid
    batch.commit()
    return result

def set_inline_message_id(roulette_id: int, inline_message_id: str):
    ref = fs_db().collection("roulettes").document(str(roulette_id))
    doc = ref.get()
    if doc.exists and doc.to_dict().get("inline_message_id") is None:
        ref.update({"inline_message_id": inline_message_id})

def get_roulette(roulette_id: int):
    doc = fs_db().collection("roulettes").document(str(roulette_id)).get()
    return _fs_row_or_none(doc)

def set_roulette_status(roulette_id: int, status: str):
    fs_db().collection("roulettes").document(str(roulette_id)).update({"status": status})

def _counted_user_doc_id(user_id: int, roulette_id: int) -> str:
    return f"{roulette_id}_{user_id}"

def is_user_counted(user_id: int, roulette_id: int) -> bool:
    doc = fs_db().collection("counted_users").document(_counted_user_doc_id(user_id, roulette_id)).get()
    return doc.exists

def count_user(user_id: int, roulette_id: int, display_name: str = None):
    ref = fs_db().collection("counted_users").document(_counted_user_doc_id(user_id, roulette_id))
    if not ref.get().exists:
        ref.set({
            "user_id": user_id,
            "roulette_id": roulette_id,
            "display_name": display_name,
            "counted_at": datetime.now(timezone.utc).isoformat(),
        })

def count_participants(roulette_id: int) -> int:
    docs = fs_db().collection("counted_users").where("roulette_id", "==", roulette_id).stream()
    return sum(1 for _ in docs)

def get_participants_with_names(roulette_id: int):
    docs = list(fs_db().collection("counted_users").where("roulette_id", "==", roulette_id).stream())
    rows = [d.to_dict() for d in docs]
    rows.sort(key=lambda r: r.get("counted_at") or "")
    return [(r["user_id"], r.get("display_name") or str(r["user_id"])) for r in rows]

def get_points(owner_id: int, force_refresh: bool = False) -> int:
    """⚡ موحَّد: يُقرأ من نفس مستند users/{id} (حقل points) عبر نفس الكاش
    الدائم (_USER_CACHE)، بدل مجموعة owner_points منفصلة — فلا يستهلك أي
    قراءة Firestore إضافية بعد أول تحميل لهذا المستخدم في التشغيلة الحالية.
    force_refresh=True: يقرأ حيًّا من Firestore متجاوزًا الكاش تمامًا —
    يُستخدم فقط في نقاط العرض/القرار الحرجة القليلة التكرار (زر «🎁 ربح»،
    قائمة سحب النجوم، وتنفيذ طلب سحب فعلي) حتى يظهر الرصيد الصحيح 100%
    دائمًا مهما حصل، بمعزل تام عن أي علة أو تأخير محتمل بآلية إبطال الكاش —
    بلا أي كلفة إضافية على بقية البوت لأنها استدعاءات نادرة أصلًا (ضغطة
    مستخدم يدوية، لا تتكرر في كل رسالة)."""
    if force_refresh:
        _load_user_into_cache(owner_id)
    row = get_bot_user(owner_id)
    return int(row.get("points") or 0) if row else 0

def get_top_channel_points(limit: int = 5):
    """يعيد أعلى القنوات التي حصلت على نقاط فعلية من سحوبات منع الرشق.

    (محسّنة أكثر: تجلب مباشرة من Firestore أعلى القنوات نقاطًا فقط عبر
    order_by + limit، بدل قراءة كل قناة سجّلت نقاطًا على الإطلاق مهما كان
    عددها — الفكرة: معرفة إحصائيات أعلى 5 قنوات فقط، لا كل القنوات. تُستخدم
    دفعة (buffer) أكبر قليلاً من العدد المطلوب لتعويض أي قناة من ضمن الأعلى
    نقاطًا قد تكون غير نشطة أو ليست من نوع «قناة» فتُستبعد، مع التوقف فور
    الوصول للعدد المطلوب من القنوات الصالحة فعليًا — فيقل عدد قراءات
    registered_chats أيضًا إلى ما يُقارب 5 بدل قراءتها جميعًا.)"""
    return _top_channels_by_field("points", limit)


def get_top_channels_by_roulette_count(limit: int = 5):
    """يعيد أعلى القنوات عدد عمليات «روليت» (سحوبات + مسابقات) — اعتمادًا على
    عمود roulette_count المخصَّص على نفس مستند channel_points/{chat_id}، بدل
    مسح مجموعتي giveaways وcontests بالكامل في كل مرة (كانت هذه هي العملية
    المكلفة التي تستهلك مئات/آلاف قراءات Firestore عند كل ضغطة على شاشة
    الإحصائيات). يُحدَّث هذا العمود تلقائيًا (+1) لحظة إنشاء كل سحب أو مسابقة
    جديدة (bump_channel_roulette_count)، فتُصبح القراءة هنا استعلامًا واحدًا
    فقط (order_by + limit) — تمامًا بنفس كفاءة get_top_channel_points."""
    return _top_channels_by_field("roulette_count", limit)


def _top_channels_by_field(field: str, limit: int = 5):
    """⚡ قراءة واحدة فقط من مجموعة channel_points (بلا أي قراءة إضافية من
    registered_chats): كل مستند قناة هناك يحمل الآن أيضًا chat_title/
    chat_type/active مباشرة (مُزامَنة تلقائيًا من save_registered_chat/
    remove_registered_chat). التوافق مع بيانات قديمة: أي مستند قناة سابق لم
    يُسجَّل بعد بهذه الحقول (نادر، قبل هذا التحديث) يُستكمَل تلقائيًا بقراءة
    احتياطية واحدة من registered_chats — وتُكتب النتيجة فورًا على نفس مستند
    channel_points حتى لا تتكرر هذه القراءة الاحتياطية له مرة أخرى أبدًا."""
    client = fs_db()
    wanted = max(1, min(int(limit), 5))
    buffer_size = max(wanted * 6, 30)
    docs = (
        client.collection("channel_points")
        .order_by(field, direction=firestore.Query.DESCENDING)
        .limit(buffer_size)
        .stream()
    )
    candidates = []
    for d in docs:
        data = d.to_dict()
        if (data.get(field) or 0) <= 0:
            continue
        chat_id = data.get("chat_id")
        chat_type = data.get("chat_type")
        active = data.get("active")
        chat_title = data.get("chat_title")
        if chat_type is None or active is None:
            # مستند قديم بلا الحقول المُزامَنة — قراءة احتياطية نادرة لمرة
            # واحدة فقط، ثم استكمال المستند حتى لا تتكرر لاحقًا.
            rc_doc = client.collection("registered_chats").document(str(chat_id)).get()
            if not rc_doc.exists:
                continue
            rc = rc_doc.to_dict()
            chat_type = rc.get("chat_type")
            active = rc.get("active", True)
            chat_title = rc.get("chat_title") or chat_title
            d.reference.set({
                "chat_type": chat_type, "active": active, "chat_title": chat_title,
            }, merge=True)
        if chat_type != "channel" or not active:
            continue
        candidates.append(FSRow({
            "chat_id": chat_id,
            "owner_id": data.get("owner_id"),
            "points": data.get("points") or 0,
            "roulette_count": data.get("roulette_count") or 0,
            "updated_at": data.get("updated_at"),
            "chat_title": chat_title or f"قناة {chat_id}",
        }))
        if len(candidates) >= wanted:
            break
    candidates.sort(key=lambda r: (r.get(field) or 0, r.get("updated_at") or ""), reverse=True)
    return candidates[:wanted]


def bump_channel_roulette_count(chat_id: int) -> None:
    """يزيد عمود roulette_count المخصَّص لهذه القناة على مستند
    channel_points/{chat_id} بمقدار واحد فور إنشاء سحب أو مسابقة جديدة فيها —
    قراءة/كتابة واحدة فقط، بدل الاعتماد لاحقًا على مسح كامل لمجموعتي
    giveaways وcontests لحساب هذا الرقم عند فتح شاشة الإحصائيات."""
    if not chat_id:
        return
    ref = fs_db().collection("channel_points").document(str(chat_id))
    _fs_bump_counter(ref, "roulette_count", 1, extra={"chat_id": chat_id})



def bump_channel_new_users(chat_id: int) -> None:
    """يزيد عدّاد المستخدمين الجدد الذين انضمّوا للبوت عبر قناة معيّنة (من خلال
    سحب أو مسابقة نُشرت فيها) بمقدار واحد. يُستدعى مرة واحدة فقط لكل مستخدم
    جديد فعليًا (is_genuinely_new=True)، بمعزل تام عن نظام النقاط."""
    if not chat_id:
        return
    ref = fs_db().collection("channel_new_users").document(str(chat_id))
    _fs_bump_counter(ref, "new_users", 1, extra={"chat_id": chat_id})


_CHANNEL_NEW_USERS_CACHE = {"data": None, "ts": 0.0}
STATS_SCREEN_CACHE_TTL = 120  # ثانية — نفس فكرة الكاش المطبَّقة على إحصائيات
# المالك: تفادي إعادة قراءة مجموعات كاملة من Firestore عند كل ضغطة على شاشة
# «📊 الإحصائيات» العامة (يستخدمها كل المستخدمين وليس المالك فقط).


def get_channel_new_users_counts(force_refresh: bool = False) -> dict:
    """يعيد عدد المستخدمين الجدد المسجَّلين فعليًا لكل قناة (chat_id) من
    مجموعة channel_new_users. مُخزَّنة مؤقتًا (كاش) لأنها تُستدعى أكثر من
    مرة لكل ضغطة على شاشة الإحصائيات العامة."""
    now_ts = time.time()
    cached = _CHANNEL_NEW_USERS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _CHANNEL_NEW_USERS_CACHE["ts"] < STATS_SCREEN_CACHE_TTL:
        return cached
    counts = {}
    for doc in fs_db().collection("channel_new_users").stream():
        data = doc.to_dict()
        chat_id = data.get("chat_id")
        if chat_id:
            counts[chat_id] = data.get("new_users", 0) or 0
    _CHANNEL_NEW_USERS_CACHE["data"] = counts
    _CHANNEL_NEW_USERS_CACHE["ts"] = now_ts
    return counts


_TOP_CHANNELS_STATS_CACHE = {"data": None, "ts": 0.0}


def get_top_channels_full_stats(limit: int = 5, force_refresh: bool = False) -> list:
    """يجمع لكل قناة من أعلى القنوات عدد عمليات «روليت» (سحوبات + مسابقات):
    اسمها، عدد الروليت، عدد المستخدمين الجدد عبرها، ونقاطها — تُستخدم في
    شاشة «📊 الإحصائيات» العامة. الترتيب الآن اعتمادًا على عمود
    roulette_count المخصَّص مباشرة (استعلام واحد فقط عبر
    get_top_channels_by_roulette_count)، بدل مسح مجموعتي giveaways
    وcontests بالكامل في كل مرة — وهذا كان السبب الرئيسي في استهلاك مئات/آلاف
    قراءات Firestore عند فتح هذه الشاشة سابقًا. النتيجة الكاملة مُخزَّنة
    مؤقتًا (كاش) أيضًا فوق ذلك لتقليل القراءات أكثر."""
    now_ts = time.time()
    cached = _TOP_CHANNELS_STATS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _TOP_CHANNELS_STATS_CACHE["ts"] < STATS_SCREEN_CACHE_TTL:
        return cached
    top_roulette = get_top_channels_by_roulette_count(limit)
    new_user_counts = get_channel_new_users_counts(force_refresh=force_refresh)
    result = []
    for row in top_roulette:
        chat_id = row["chat_id"]
        result.append({
            "chat_id": chat_id,
            "chat_title": row["chat_title"],
            "points": row.get("points") or 0,
            "roulette_count": row.get("roulette_count") or 0,
            "new_users": new_user_counts.get(chat_id, 0),
        })
    _TOP_CHANNELS_STATS_CACHE["data"] = result
    _TOP_CHANNELS_STATS_CACHE["ts"] = now_ts
    return result


# ---------------------------------------------------------------------------
# 🗂️ كاش مستخدمي البوت (known_bot_users) — كل مستخدم يُقرأ من Firestore مرة
# واحدة فقط طول عمر تشغيل البوت (أول مرة يُحتاج فيها)، وتبقى نسخته بالذاكرة
# بعدها (_USER_CACHE). لا تحدث أي كتابة لـFirestore إلا عند تغيير فعلي حقيقي:
# مستخدم جديد كليًا لأول مرة، أو تغيّر يوزر/اسم المستخدم عن آخر نسخة معروفة.
# مجرد /start أو أي تفاعل عادي متكرر من مستخدم معروف مسبقًا وبلا تغيير في
# بياناته **لا يكتب شيئًا إطلاقًا** لـFirestore — يُحدَّث بالذاكرة فقط.
# ملاحظة: بما أن last_seen_at لم يعد يُكتب لـFirestore إلا مع تغيّر فعلي في
# اليوزر/الاسم، فإحصائيات «المستخدمين النشطين اليوم/الأسبوع» (المعتمدة على
# last_seen_at المخزّن) قد تصبح أقل دقة زمنيًا لمن لا يغيّر يوزره أبدًا. هذا
# تنازل مقصود لتقليل الكتابة إلى الحد الأدنى المطلق كما طُلب.
# ---------------------------------------------------------------------------

_USER_CACHE = {}  # user_id -> dict بيانات المستخدم كاملة، أو None إن لم يكن معروفًا


def _bot_user_doc_ref(user_id: int):
    """⚡ موحَّد الآن: يشير لنفس مستند المستخدم users/{id}."""
    return _user_doc_ref(user_id)


def _load_user_into_cache(user_id: int):
    """يقرأ مستخدمًا من Firestore ويخزّنه بالكاش (مرة واحدة فقط لكل مستخدم
    طول عمر التشغيلة، إلا إذا استُدعيت لاحقًا صراحة بعد تعديل)."""
    doc = _bot_user_doc_ref(user_id).get()
    data = doc.to_dict() if doc.exists else None
    if data is not None:
        data.setdefault("user_id", user_id)
    _USER_CACHE[user_id] = data
    return data


def register_bot_user_and_check_new(user_id: int, user=None) -> bool:
    """
    يسجّل أول تواصل لهذا المستخدم مع البوت مهما كان مصدر الدخول (رابط سحب/مسابقة،
    أو رابط عام، أو بحث عن اسم البوت... إلخ)، ويُستدعى مرة واحدة فقط في بداية
    /start قبل معالجة أي رابط دخول.
    يعيد True فقط إذا كانت هذه أول مرة يتواصل فيها المستخدم مع البوت إطلاقًا
    (مستخدم جديد كليًا) — وFalse إن كان قد استخدم البوت من قبل بأي طريقة،
    حتى لو لم يشارك في أي سحب سابقًا. تُستخدم هذه القيمة لمنع احتساب نقطة
    لصاحب السحب عندما يشارك مستخدم "قديم" وليس مستخدمًا جديدًا حقيقيًا.

    عند تمرير user (كائن telegram.User): يُحدَّث اليوزر/الاسم بالكاش دائمًا،
    لكن لا يُكتب لـFirestore إلا لو تغيّر فعليًا عن آخر نسخة معروفة — بدل
    كتابة last_seen_at في كل استدعاء بدون داعٍ.
    """
    ref = _bot_user_doc_ref(user_id)

    if user_id not in _USER_CACHE:
        _load_user_into_cache(user_id)

    cached = _USER_CACHE.get(user_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    # ⚡ has_started (وليس مجرد وجود المستند) هو ما يحدّد "مستخدم جديد فعليًا"
    # الآن — لأن المستند users/{id} قد يكون أُنشئ مسبقًا بجزء من بياناته فقط
    # (مثلاً مالك البوت أضافه كمشرف أو صاحب رابط إحالة أو منحه نقاطًا يدويًا
    # قبل أن يبدأ محادثة مع البوت إطلاقًا)، فوجود مستند لا يعني أنه استخدم
    # /start من قبل. بدون هذا التمييز كانت ستُحتسَب مكافآت "مستخدم جديد"
    # (نقاط سحب/إحالة) خطأً كـ"مستخدم قديم" في هذه الحالة النادرة.
    if cached is None or not cached.get("has_started"):
        new_data = dict(cached or {})
        new_data.update({
            "user_id": user_id,
            "has_started": True,
            "first_seen_at": new_data.get("first_seen_at") or now_iso,
            "last_seen_at": now_iso,
            "username": (user.username or "") if user is not None else "",
            "username_lower": ((user.username or "").lower()) if user is not None else "",
            "first_name": (user.first_name or "") if user is not None else "",
            "last_name": (user.last_name or "") if user is not None else "",
        })
        try:
            ref.set(new_data, merge=True)
        except Exception:
            logger.exception("تعذّر إنشاء سجل المستخدم %s", user_id)
        _USER_CACHE[user_id] = new_data
        return True

    # مستخدم معروف مسبقًا وسبق أن بدأ محادثة فعليًا — تحديث الكاش دائمًا،
    # وكتابة Firestore فقط لو تغيّر اليوزر/الاسم فعليًا عن آخر نسخة مخزَّنة.
    cached["last_seen_at"] = now_iso  # بالذاكرة فقط، بدون كتابة لـFirestore
    if user is not None:
        new_username = user.username or ""
        new_first = user.first_name or ""
        new_last = user.last_name or ""
        changed = (
            cached.get("username", "") != new_username
            or cached.get("first_name", "") != new_first
            or cached.get("last_name", "") != new_last
        )
        cached["username"] = new_username
        cached["username_lower"] = new_username.lower()
        cached["first_name"] = new_first
        cached["last_name"] = new_last
        if changed:
            try:
                ref.set({
                    "username": new_username,
                    "username_lower": new_username.lower(),
                    "first_name": new_first,
                    "last_name": new_last,
                    "last_seen_at": now_iso,
                }, merge=True)
            except Exception:
                logger.exception("تعذّر تحديث بيانات المستخدم %s", user_id)
    return False


_BAN_CACHE = {}
BAN_CACHE_TTL = 60


def get_bot_user(user_id: int):
    """يعيد بيانات مستخدم البوت (FSRow) أو None إن لم يكن معروفًا لدى البوت.
    تُقرأ من Firestore مرة واحدة فقط لكل مستخدم طول عمر تشغيل البوت (كاش
    دائم بالذاكرة _USER_CACHE)، وبعدها تُعاد من الذاكرة مباشرة بدون أي
    استدعاء إضافي لـFirestore."""
    if user_id in _USER_CACHE:
        data = _USER_CACHE[user_id]
    else:
        data = _load_user_into_cache(user_id)
    if data is None:
        return None
    return FSRow(dict(data))


def find_bot_user_by_username(username: str):
    """يبحث عن مستخدم بوت مسجَّل مسبقًا عبر اليوزر (بلا حساسية لحالة الأحرف
    ودون الحاجة لعلامة @). يعيد أول نتيجة مطابقة أو None."""
    normalized = username.strip().lstrip("@").lower()
    if not normalized:
        return None
    docs = list(
        fs_db().collection("users")
        .where("username_lower", "==", normalized)
        .limit(1)
        .stream()
    )
    if not docs:
        return None
    data = docs[0].to_dict() or {}
    data.setdefault("user_id", int(docs[0].id))
    return FSRow(data)


def is_bot_user_banned(user_id: int, force_refresh: bool = False) -> bool:
    """يتحقق مما إذا كان المستخدم محظورًا من استخدام البوت. يعتمد على نفس
    كاش المستخدم الدائم (_USER_CACHE) — بدون قراءة Firestore إطلاقًا بعد
    أول مرة، إلا لو force_refresh=True صراحة."""
    if force_refresh:
        _load_user_into_cache(user_id)
    row = get_bot_user(user_id)
    return bool(row and row.get("banned"))


def ban_bot_user(user_id: int, reason: str, banned_by: int) -> None:
    """يحظر مستخدمًا من استخدام البوت. يعمل حتى مع مستخدم لم يبدأ محادثة مع
    البوت من قبل إطلاقًا (حظر استباقي بالمعرف الرقمي فقط). كتابة فعلية لأن
    هذا تعديل حقيقي ومقصود من المشرف."""
    ban_fields = {
        "user_id": user_id,
        "banned": True,
        "ban_reason": reason or "",
        "banned_at": datetime.now(timezone.utc).isoformat(),
        "banned_by": banned_by,
    }
    _bot_user_doc_ref(user_id).set(ban_fields, merge=True)
    cached = _USER_CACHE.get(user_id) or {"user_id": user_id}
    cached.update(ban_fields)
    _USER_CACHE[user_id] = cached
    _BAN_CACHE[user_id] = {"banned": True, "ts": time.time()}


def unban_bot_user(user_id: int) -> None:
    """يفكّ حظر مستخدم. كتابة فعلية لأن هذا تعديل حقيقي ومقصود من المشرف."""
    _bot_user_doc_ref(user_id).set({
        "banned": False,
        "ban_reason": "",
    }, merge=True)
    cached = _USER_CACHE.get(user_id) or {"user_id": user_id}
    cached["banned"] = False
    cached["ban_reason"] = ""
    _USER_CACHE[user_id] = cached
    _BAN_CACHE[user_id] = {"banned": False, "ts": time.time()}


def get_banned_bot_users() -> list:
    """يعيد كل المستخدمين المحظورين، مرتّبين من الأحدث حظرًا للأقدم."""
    docs = fs_db().collection("users").where("banned", "==", True).stream()
    rows = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.setdefault("user_id", int(doc.id))
        rows.append(FSRow(data))
    rows.sort(key=lambda r: r.get("banned_at") or "", reverse=True)
    return rows


def get_bot_users_stats() -> dict:
    """إحصائيات عامة عن مستخدمي البوت: الإجمالي، عدد المحظورين، الجدد اليوم
    والجدد خلال آخر 7 أيام. كانت هذه الدالة تقرأ كل وثائق known_bot_users من
    Firestore مباشرة وبدون أي كاش عند كل ضغطة على زر «📊 إحصائيات المستخدمين»
    — بخلاف get_full_bot_statistics المجاورة لها التي كانت مُخزَّنة مؤقتًا
    (كاش) بالفعل. الآن تُعيد استخدام نفس نتيجة get_full_bot_statistics
    (ونفس كاشها لمدة FULL_BOT_STATS_CACHE_TTL ثانية) بدل مسح المجموعة مرة
    ثانية من الصفر — فتصبح قراءة واحدة فعلية بدل قراءتين لكل ضغطة زر."""
    users = get_full_bot_statistics().get("users", {})
    return {
        "total": users.get("total", 0),
        "banned": users.get("banned", 0),
        "new_today": users.get("new_today", 0),
        "new_week": users.get("new_week", 0),
    }


_FULL_BOT_STATS_CACHE = {"data": None, "ts": 0.0}
FULL_BOT_STATS_CACHE_TTL = 120  # ثانية — يمنع إعادة قراءة كل مستخدمي/قنوات
# البوت من Firestore عند كل ضغطة على «📊 إحصائيات البوت»، مع بقاء الأرقام
# قريبة جدًا من اللحظية (كحد أقصى دقيقتان قديمة). زر «🔄 تحديث» نفسه يستفيد
# من الكاش أيضًا خلال هذه المدة القصيرة، وهو فرق غير محسوس عمليًا.


def get_full_bot_statistics(force_refresh: bool = False) -> dict:
    """إحصائيات شاملة عن البوت: المستخدمون، القنوات، المجموعات — تُستخدم في
    قسم «📊 إحصائيات البوت» لدى المالك. تعتمد على last_seen_at لتحديد النشاط
    الفعلي (أي استخدام حقيقي للبوت: /start، مشاركة في سحب/مسابقة/روليت سريع)
    وليس مجرد الضغط على شرط التحقق من الاشتراك.

    تُخزَّن النتيجة مؤقتًا (كاش) لمدة FULL_BOT_STATS_CACHE_TTL ثانية، لأن هذه
    الدالة تقرأ كل وثائق known_bot_users وكل الشات المسجّلة من Firestore —
    عملية ثقيلة يجب ألا تتكرر عند كل ضغطة. يجب استدعاؤها دائمًا عبر
    asyncio.to_thread من أي async handler حتى لو كانت النتيجة ستأتي من
    الكاش، لتفادي أي حظر لحلقة الأحداث في حال انتهت صلاحية الكاش أثناء ذلك."""
    now_ts = time.time()
    cached = _FULL_BOT_STATS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _FULL_BOT_STATS_CACHE["ts"] < FULL_BOT_STATS_CACHE_TTL:
        return cached

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    total_users = 0
    banned_users = 0
    active_today = 0
    active_week = 0
    active_month = 0
    active_ever = 0
    new_today = 0
    new_week = 0
    new_month = 0

    for doc in fs_db().collection("users").stream():
        data = doc.to_dict() or {}
        if not data.get("has_started"):
            # مستند وُجد بسبب إشراف/إحالة/نقاط يدوية دون أن يبدأ صاحبه
            # محادثة فعلية مع البوت — لا يُحتسب ضمن إحصائيات "المستخدمين".
            continue
        total_users += 1
        if data.get("banned"):
            banned_users += 1

        last_seen_raw = data.get("last_seen_at")
        if last_seen_raw:
            active_ever += 1
            try:
                last_seen = datetime.fromisoformat(last_seen_raw)
                if last_seen >= today_start:
                    active_today += 1
                if last_seen >= week_start:
                    active_week += 1
                if last_seen >= month_start:
                    active_month += 1
            except (ValueError, TypeError):
                pass

        first_seen_raw = data.get("first_seen_at")
        if first_seen_raw:
            try:
                first_seen = datetime.fromisoformat(first_seen_raw)
                if first_seen >= today_start:
                    new_today += 1
                if first_seen >= week_start:
                    new_week += 1
                if first_seen >= month_start:
                    new_month += 1
            except (ValueError, TypeError):
                pass

    total_channels = 0
    active_channels = 0
    total_groups = 0
    active_groups = 0
    new_groups_today = 0
    new_groups_week = 0
    new_groups_month = 0

    for chat in get_all_registered_chats():
        chat_type = chat.get("chat_type")
        is_active = chat.get("active", True)
        if chat_type == "channel":
            total_channels += 1
            if is_active:
                active_channels += 1
        elif chat_type in ("group", "supergroup"):
            total_groups += 1
            if is_active:
                active_groups += 1
            registered_raw = chat.get("registered_at")
            if registered_raw:
                try:
                    registered_at = datetime.fromisoformat(registered_raw)
                    if registered_at >= today_start:
                        new_groups_today += 1
                    if registered_at >= week_start:
                        new_groups_week += 1
                    if registered_at >= month_start:
                        new_groups_month += 1
                except (ValueError, TypeError):
                    pass

    required_channels = get_required_channels()

    result = {
        "users": {
            "total": total_users,
            "active_today": active_today,
            "active_week": active_week,
            "active_month": active_month,
            "active_ever": active_ever,
            "new_today": new_today,
            "new_week": new_week,
            "new_month": new_month,
            "banned": banned_users,
        },
        "channels": {
            "total": total_channels,
            "active": active_channels,
            "inactive": total_channels - active_channels,
            "required_count": len(required_channels),
            "required_members": None,
        },
        "groups": {
            "total": total_groups,
            "active": active_groups,
            "inactive": total_groups - active_groups,
            "new_today": new_groups_today,
            "new_week": new_groups_week,
            "new_month": new_groups_month,
        },
    }
    _FULL_BOT_STATS_CACHE["data"] = result
    _FULL_BOT_STATS_CACHE["ts"] = now_ts
    return result


async def get_required_channels_total_members(context: ContextTypes.DEFAULT_TYPE) -> int:
    """يجمع عدد الأعضاء الفعلي لكل قنوات الاشتراك الإجباري عبر Telegram API
    (يُستدعى مباشرة عند فتح شاشة الإحصائيات، دون تخزينه لأنه قد يتغيّر باستمرار)."""
    total = 0
    for channel in get_required_channels():
        username = channel.get("username")
        if not username:
            continue
        try:
            count = await context.bot.get_chat_member_count(f"@{username}")
            total += count
        except Exception:
            continue
    return total


def _reward_new_user_once(user_id: int, owner_id: int, chat_id: int, source_fields: dict) -> bool:
    """يمنح النقاط مرة واحدة عالميًا لأي مستخدم جديد فعليًا اجتاز منع الرشق —
    سواء كان مصدره سحبًا أو مسابقة. منع الاحتساب المزدوج يعتمد على حقل
    rewarded الذري داخل مستند المستخدم users/{id} نفسه (معاملة واحدة، قراءة/
    كتابة واحدة)، فيُكافأ كل مستخدم مرة واحدة فقط عالميًا مهما تعدّدت
    مشاركاته اللاحقة (في سحوبات أو مسابقات أخرى)."""
    if get_setting("points_enabled") != "1":
        return False

    ref = _user_doc_ref(user_id)
    transaction = fs_db().transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = ref.get(transaction=transaction)
        data = snap.to_dict() if snap.exists else {}
        if data.get("rewarded"):
            return False
        payload = {
            "user_id": user_id,
            "rewarded": True,
            "rewarded_owner_id": owner_id,
            "rewarded_at": datetime.now(timezone.utc).isoformat(),
        }
        payload.update(source_fields)
        if snap.exists:
            transaction.update(ref, payload)
        else:
            transaction.set(ref, payload)
        return True

    if not _txn(transaction):
        return False
    _USER_CACHE.pop(user_id, None)

    raw_value = get_setting("points_per_user")
    amount = max(int(raw_value) if raw_value and str(raw_value).isdigit() else 1, 0)

    _fs_bump_counter(_user_doc_ref(owner_id), "points", amount, extra={"user_id": owner_id})
    _USER_CACHE.pop(owner_id, None)

    channel_ref = fs_db().collection("channel_points").document(str(chat_id))
    _fs_bump_counter(channel_ref, "points", amount, extra={
        "chat_id": chat_id,
        "owner_id": owner_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return True


def reward_giveaway_user(user_id: int, gw_code: str, owner_id: int, chat_id: int) -> bool:
    """يمنح النقاط مرة واحدة عالميًا بعد نجاح مشاركة السحب والكابتشا."""
    return _reward_new_user_once(user_id, owner_id, chat_id, {"rewarded_gw_code": gw_code})


def reward_contest_new_participant(user_id: int, contest_code: str, owner_id: int, chat_id: int) -> bool:
    """يمنح صاحب المسابقة نقاطًا مرة واحدة عالميًا عند مشاركة مستخدم جديد فعليًا
    كمتسابق (بمعزل تام عن نقاط التصويت award_contest_owner_points) — بنفس
    آلية وضمان reward_giveaway_user تمامًا."""
    return _reward_new_user_once(user_id, owner_id, chat_id, {"rewarded_contest_code": contest_code})

def award_contest_owner_points(owner_id: int) -> int:
    """يمنح صاحب المسابقة نقاطًا مقابل صوت واحد مكتمل الشروط (اشتراك + تحقق +
    عدم تلاعب). يعيد عدد النقاط الممنوحة فعليًا (0 إن كانت خاصية النقاط معطّلة).
    لا تُستدعى إلا مرة واحدة لكل تصويت مؤكد — الاستدعاء متروك لـ
    register_confirmed_contest_vote الذي يضمن ذلك."""
    if get_setting("points_enabled") != "1":
        return 0
    raw_value = get_setting("points_per_user")
    amount = max(int(raw_value) if raw_value and str(raw_value).isdigit() else 1, 0)
    if amount <= 0:
        return 0
    _fs_bump_counter(_user_doc_ref(owner_id), "points", amount, extra={"user_id": owner_id})
    _USER_CACHE.pop(owner_id, None)
    return amount


def reverse_contest_owner_points(owner_id: int, amount: int) -> None:
    """يخصم من صاحب المسابقة نقاطًا سبق منحها مقابل تصويت أُلغي لاحقًا (خروج
    المصوّت من القنوات الإلزامية) — لا تنزل النقاط تحت الصفر أبدًا."""
    if not amount or amount <= 0 or not owner_id:
        return
    _fs_bump_counter(_user_doc_ref(owner_id), "points", -amount, extra={"user_id": owner_id})
    _USER_CACHE.pop(owner_id, None)


# ---------------------------------------------------------------------------
# 💎 التحكم اليدوي بنقاط المستخدمين (قسم ربح — قسم المالك) — يمنح مالك البوت
# صلاحية كاملة لإضافة أو خصم نقاط من رصيد أي مستخدم مباشرة، بمعزل عن أي آلية
# احتساب تلقائية (سحوبات/مسابقات/إحالات)، مع تسجيل كل عملية في سجل العمليات
# الإدارية للتتبّع والمراجعة.
# ---------------------------------------------------------------------------

def add_points_to_user(user_id: int, amount: int) -> int:
    """يضيف نقاطًا يدويًا لرصيد مستخدم معيّن، ويعيد الرصيد الجديد."""
    if amount <= 0:
        return get_points(user_id)
    _fs_bump_counter(_user_doc_ref(user_id), "points", amount, extra={"user_id": user_id})
    _USER_CACHE.pop(user_id, None)
    invalidate_users_points_cache()
    return get_points(user_id)


def deduct_points_from_user(user_id: int, amount: int) -> int:
    """يخصم نقاطًا يدويًا من رصيد مستخدم معيّن (لا ينزل الرصيد تحت الصفر أبدًا
    بفضل _fs_bump_counter)، ويعيد الرصيد الجديد."""
    if amount <= 0:
        return get_points(user_id)
    _fs_bump_counter(_user_doc_ref(user_id), "points", -amount, extra={"user_id": user_id})
    _USER_CACHE.pop(user_id, None)
    invalidate_users_points_cache()
    return get_points(user_id)


_USERS_POINTS_CACHE = {"rows": None, "ts": 0.0}
USERS_POINTS_CACHE_TTL = 45  # ثانية — مدة صلاحية القائمة المخزّنة مؤقتًا


def invalidate_users_points_cache() -> None:
    """يُفرغ كاش قائمة تصفّح المستخدمين، لإجبار جلب البيانات من جديد في
    أقرب طلب — يمكن استدعاؤها بعد أي عملية تعرف مسبقًا أنها تغيّر نقاط أو
    إحالات مستخدم (مثلاً بعد إضافة/خصم نقاط يدويًا) لضمان ظهور القيمة
    المحدَّثة فورًا بدل انتظار انتهاء الـ TTL."""
    _USERS_POINTS_CACHE["rows"] = None
    _USERS_POINTS_CACHE["ts"] = 0.0


def get_all_known_users_with_points(sort_by_points: bool = True, force_refresh: bool = False) -> list:
    """يجمع كل مستخدمي البوت المعروفين (known_bot_users) مع رصيد نقاطهم
    الحالي (owner_points) وعدد إحالاتهم (referred_count إن كانوا من أصحاب
    روابط الدعوة، وإلا 0) في قائمة واحدة موحّدة.

    دالة عامة قابلة لإعادة الاستخدام في أي قسم يحتاج تصفّح المستخدمين مع
    نقاطهم وإحالاتهم (قسم ربح، إدارة المستخدمين، أو أي قسم مستقبلي) —
    تُستهلك دائمًا عبر build_users_points_browse_message/keyboard أدناه.

    ⚡ موحَّد: بعد دمج known_bot_users/owner_points/bot_referrals في مستند
    users/{id} واحد، أصبح جلب كل المستخدمين مع نقاطهم وإحالاتهم طلب Firestore
    واحد فقط (مسح مجموعة users) بدل 3 طلبات منفصلة سابقًا. النتيجة الكاملة
    تبقى مخزَّنة مؤقتًا (Cache) لمدة USERS_POINTS_CACHE_TTL ثانية حتى لا
    تتكرر حتى هذا الطلب الواحد مع كل تنقّل بين الصفحات (أقصى تأخر ممكن
    لظهور تحديث: مدة الـ TTL، أو فورًا عبر force_refresh)."""
    now = time.time()
    cached = _USERS_POINTS_CACHE["rows"]
    if not force_refresh and cached is not None and (now - _USERS_POINTS_CACHE["ts"]) < USERS_POINTS_CACHE_TTL:
        rows = cached
    else:
        rows = []
        for doc in fs_db().collection("users").stream():
            data = doc.to_dict() or {}
            if not data.get("has_started"):
                continue
            uid = data.get("user_id") or int(doc.id)
            rows.append(FSRow({
                "user_id": uid,
                "username": data.get("username") or "",
                "first_name": data.get("first_name") or "",
                "points": data.get("points") or 0,
                "referred_count": data.get("ref_referred_count") or 0,
            }))
        _USERS_POINTS_CACHE["rows"] = rows
        _USERS_POINTS_CACHE["ts"] = now

    rows = list(rows)
    if sort_by_points:
        rows.sort(key=lambda r: (r.get("points") or 0), reverse=True)
    else:
        rows.sort(key=lambda r: (r.get("first_name") or str(r.get("user_id"))))
    return rows


# ---------------------------------------------------------------------------
# 🔗 نظام روابط الإحالة (Referral Links) — يسمح لمالك البوت بمنح مستخدمين
# محددين (وليس الجميع تلقائيًا) رابط دعوة خاص بهم، مع نسبة ربح مخصّصة لكل
# مستخدم أو الاعتماد على نسبة افتراضية عامة. يُخزَّن كل ذلك في Firestore ضمن
# bot_referrals (بيانات صاحب الرابط ونسبته وإحصائياته)، وreferral_signups
# (سجل من دخل عبر كل رابط، لمنع احتساب نفس الشخص أكثر من مرة). نقاط الإحالة
# تُضاف مباشرة إلى رصيد صاحب الرابط ضمن نفس نظام owner_points/قسم السحب
# الحالي، فتخضع لنفس آلية طلب السحب الموجودة أصلًا.
# ---------------------------------------------------------------------------

REFERRAL_DEFAULT_PERCENTAGE = 50
REFERRAL_DEFAULT_SIGNUP_POINTS = 5


def _referral_doc_ref(user_id: int):
    """⚡ موحَّد الآن: يشير لنفس مستند المستخدم users/{id}."""
    return _user_doc_ref(user_id)


def get_referral_default_percentage() -> int:
    raw = get_setting("referral_default_percentage")
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return REFERRAL_DEFAULT_PERCENTAGE


def set_referral_default_percentage(value: int) -> None:
    set_setting("referral_default_percentage", str(max(0, min(100, int(value)))))


def get_referral_signup_points() -> int:
    raw = get_setting("referral_signup_points")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return REFERRAL_DEFAULT_SIGNUP_POINTS


def set_referral_signup_points(value: int) -> None:
    set_setting("referral_signup_points", str(max(0, int(value))))


def get_referral(user_id: int):
    """يعيد بيانات صاحب رابط دعوة (FSRow) أو None إن لم يكن مصرّحًا له بالإحالة.
    ⚡ موحَّد: يُقرأ من نفس مستند users/{id} عبر نفس الكاش الدائم _USER_CACHE."""
    row = get_bot_user(user_id)
    if not row or not row.get("is_referrer"):
        return None
    data = dict(row)
    data["percentage"] = data.get("ref_percentage")
    if data["percentage"] is None:
        data["percentage"] = get_referral_default_percentage()
    data["active"] = bool(data.get("ref_active", True))
    data["referred_count"] = data.get("ref_referred_count") or 0
    data["points_earned"] = data.get("ref_points_earned") or 0
    return FSRow(data)


def is_referrer_active(user_id: int) -> bool:
    row = get_referral(user_id)
    return bool(row and row.get("active"))


def list_referrers() -> list:
    """يعيد كل أصحاب روابط الدعوة المسجَّلين، الأحدث إضافةً أولًا."""
    docs = fs_db().collection("users").where("is_referrer", "==", True).stream()
    rows = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.setdefault("user_id", int(doc.id))
        data["percentage"] = data.get("ref_percentage") or get_referral_default_percentage()
        data["active"] = bool(data.get("ref_active", True))
        data["referred_count"] = data.get("ref_referred_count") or 0
        data["points_earned"] = data.get("ref_points_earned") or 0
        data["created_at"] = data.get("ref_created_at")
        rows.append(FSRow(data))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def add_referrer(user_id: int, added_by: int, percentage: int = None,
                  username: str = None, first_name: str = None) -> None:
    """يمنح مستخدمًا صلاحية نشر رابط دعوة خاص به، بنسبة ربح مخصّصة أو الافتراضية."""
    pct = get_referral_default_percentage() if percentage is None else max(0, min(100, int(percentage)))
    _referral_doc_ref(user_id).set({
        "user_id": user_id,
        "is_referrer": True,
        "ref_username": username or "",
        "ref_first_name": first_name or "",
        "ref_percentage": pct,
        "ref_active": True,
        "ref_added_by": added_by,
        "ref_created_at": datetime.now(timezone.utc).isoformat(),
        "ref_referred_count": 0,
        "ref_points_earned": 0,
    }, merge=True)
    _USER_CACHE.pop(user_id, None)


def remove_referrer(user_id: int) -> None:
    """يزيل صلاحية الإحالة عن مستخدم (إحصائياته السابقة — عدد المُحالين
    والنقاط المكتسبة — تبقى محفوظة في نفس مستنده، لكنه يفقد إمكانية نشر
    رابط جديد فورًا)."""
    _referral_doc_ref(user_id).set({"is_referrer": False, "ref_active": False}, merge=True)
    _USER_CACHE.pop(user_id, None)


def set_referrer_percentage(user_id: int, percentage: int) -> None:
    _referral_doc_ref(user_id).set({"ref_percentage": max(0, min(100, int(percentage)))}, merge=True)
    _USER_CACHE.pop(user_id, None)


def set_referrer_active(user_id: int, active: bool) -> None:
    _referral_doc_ref(user_id).set({"ref_active": bool(active)}, merge=True)
    _USER_CACHE.pop(user_id, None)


def process_referral_signup(referrer_id_raw: str, referred_user_id: int, referred_user=None) -> None:
    """يُستدعى مرة واحدة فقط عند دخول مستخدم جديد حقيقي عبر رابط دعوة
    (t.me/Bot?start=ref_<ID>) بعد اجتيازه فعليًا شرط الاشتراك الإجباري بالقنوات
    (بوابة الحماية ضد الرشق/الوهمي مطبَّقة بالفعل قبل استدعاء هذه الدالة في
    start() وcheck_sub_status_callback). يمنح صاحب الرابط نقاط الإحالة حسب
    نسبته الخاصة، ويحدّث عدّاد إحالاته. لا يُحتسب نفس المدعو مرتين أبدًا.

    ⚡ موحَّد: منع الاحتساب المزدوج لم يعد يعتمد على مجموعة referral_signups
    منفصلة، بل على حقل referred_by داخل مستند المُحال نفسه (users/{id})،
    ضمن معاملة (transaction) ذرية — نفس الضمان القديم (AlreadyExists) لكن
    بدون مجموعة إضافية."""
    if not referrer_id_raw or not referrer_id_raw.isdigit():
        return
    referrer_id = int(referrer_id_raw)
    if referrer_id == referred_user_id:
        return
    row = get_referral(referrer_id)
    if not row or not row.get("active"):
        return

    referred_ref = _user_doc_ref(referred_user_id)
    transaction = fs_db().transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = referred_ref.get(transaction=transaction)
        data = snap.to_dict() if snap.exists else {}
        if data.get("referred_by"):
            return False  # هذا المستخدم مُحتسَب مسبقًا كإحالة — لا يُحتسب مرتين
        payload = {"user_id": referred_user_id, "referred_by": referrer_id}
        if snap.exists:
            transaction.update(referred_ref, payload)
        else:
            transaction.set(referred_ref, payload)
        return True

    if not _txn(transaction):
        return
    _USER_CACHE.pop(referred_user_id, None)

    base_points = get_referral_signup_points()
    percentage = row.get("percentage", get_referral_default_percentage())
    earned = int(round(base_points * percentage / 100)) if base_points > 0 else 0

    referrer_ref = _referral_doc_ref(referrer_id)
    _fs_bump_counter(referrer_ref, "ref_referred_count", 1, extra={"user_id": referrer_id})
    if earned > 0:
        _fs_bump_counter(referrer_ref, "ref_points_earned", earned, extra={"user_id": referrer_id})
        _fs_bump_counter(referrer_ref, "points", earned, extra={"user_id": referrer_id})
    _USER_CACHE.pop(referrer_id, None)


def get_referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


def get_referrals_overview_stats() -> dict:
    """إحصائيات عامة لقسم المالك: عدد أصحاب الروابط، النشطين، إجمالي القادمين
    عبر الإحالات، إجمالي النقاط الموزَّعة، وأفضل 5 بعدد الإحالات."""
    rows = list_referrers()
    active_count = sum(1 for r in rows if r.get("active"))
    total_referred = sum(int(r.get("referred_count") or 0) for r in rows)
    total_points = sum(int(r.get("points_earned") or 0) for r in rows)
    top = sorted(rows, key=lambda r: int(r.get("referred_count") or 0), reverse=True)[:5]
    return {
        "total_referrers": len(rows),
        "active_referrers": active_count,
        "total_referred": total_referred,
        "total_points": total_points,
        "top": top,
    }


def create_withdraw_request(user_id: int, display_name: str, username: str,
                             points_amount: int) -> str:
    """
    نظام السحب الحقيقي: ينشئ طلب سحب جديد بحالة «pending» (قيد الانتظار)
    ويخصم كامل رصيد المستخدم من نقاطه فورًا عند تقديم الطلب — وليس عند
    تأكيد المالك — حتى لا يستطيع سحب نفس النقاط مرتين أثناء انتظار المراجعة.
    لا يُطلب من المستخدم أي نص إضافي؛ التواصل يتم عبر يوزر تليجرام الخاص به
    مباشرة (username إلزامي قبل إنشاء أي طلب). يعيد معرّف الطلب (request_id).
    """
    client = fs_db()
    ref = client.collection("withdraw_requests").document()
    ref.set({
        "request_id": ref.id,
        "user_id": user_id,
        "display_name": display_name,
        "username": username,
        "points_amount": points_amount,
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    })
    _fs_bump_counter(_user_doc_ref(user_id), "points", -points_amount, extra={"user_id": user_id})
    _USER_CACHE.pop(user_id, None)
    return ref.id


def get_withdraw_request(request_id: str):
    doc = fs_db().collection("withdraw_requests").document(request_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["request_id"] = doc.id
    return data


def get_user_withdraw_requests(user_id: int):
    """يعيد كل طلبات سحب مستخدم مرتّبة تنازليًا (الأحدث أولاً)."""
    docs = fs_db().collection("withdraw_requests").where("user_id", "==", user_id).stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        data["request_id"] = d.id
        rows.append(data)
    rows.sort(key=lambda r: r.get("requested_at") or "", reverse=True)
    return rows


def get_user_latest_withdraw_request(user_id: int):
    rows = get_user_withdraw_requests(user_id)
    return rows[0] if rows else None


def has_pending_withdraw_request(user_id: int) -> bool:
    latest = get_user_latest_withdraw_request(user_id)
    return bool(latest and latest.get("status") == "pending")


def get_pending_withdraw_requests(limit: int = 15):
    """يعيد كل طلبات السحب «قيد الانتظار» الحالية مرتّبة من الأقدم للأحدث
    (تُعرض في قسم المالك — سجلات مطالبة سحب)."""
    docs = fs_db().collection("withdraw_requests").where("status", "==", "pending").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        data["request_id"] = d.id
        rows.append(data)
    rows.sort(key=lambda r: r.get("requested_at") or "")
    return rows[:limit]


def mark_withdraw_completed(request_id: str) -> bool:
    """يعلّم طلب سحب كـ«مقبول» (استلمه المستخدم فعليًا) — يُستدعى فقط من
    قسم المالك بعد إرسال المكافأة الحقيقية للمستخدم يدويًا. يعيد True فقط
    إذا كان الطلب لا يزال «قيد الانتظار» فعليًا (يمنع التأكيد المزدوج)."""
    ref = fs_db().collection("withdraw_requests").document(request_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("status") != "pending":
        return False
    ref.update({
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    return True


def mark_withdraw_rejected(request_id: str) -> bool:
    """يعلّم طلب سحب كـ«مرفوض» ويعيد النقاط المخصومة عند تقديم الطلب إلى
    رصيد المستخدم فورًا (لأن create_withdraw_request يخصمها مسبقًا). يعيد
    True فقط إذا كان الطلب لا يزال «قيد الانتظار» فعليًا (يمنع الرفض المزدوج)."""
    ref = fs_db().collection("withdraw_requests").document(request_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("status") != "pending":
        return False
    data = doc.to_dict()
    ref.update({
        "status": "rejected",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    _fs_bump_counter(_user_doc_ref(data.get("user_id")), "points", int(data.get("points_amount") or 0),
                      extra={"user_id": data.get("user_id")})
    _USER_CACHE.pop(data.get("user_id"), None)
    invalidate_users_points_cache()
    return True


def get_all_withdraw_requests(limit: int = 30):
    """يعيد كل طلبات السحب (بكل حالاتها: قيد الانتظار/مقبول/مرفوض) مرتّبة
    تنازليًا (الأحدث أولاً) — تُستخدم لعرض سجل كامل في قسم المالك."""
    docs = fs_db().collection("withdraw_requests").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        data["request_id"] = d.id
        rows.append(data)
    rows.sort(key=lambda r: r.get("requested_at") or "", reverse=True)
    return rows[:limit]


def withdraw_status_label(status: str) -> str:
    """يحوّل قيمة حالة طلب السحب المخزّنة إلى نص عربي معروض للمستخدم/المالك."""
    return {
        "pending": "🕐 تحت المراجعة",
        "accepted": "🟢 مقبول",
        "completed": "✅ مكتمل",
        "rejected": "🔴 مرفوض",
    }.get(status, status or "-")


# ---------------------------------------------------------------------------
# 📢 قناة استقبال طلبات السحب — إعداد اختياري من المالك: عند تحديدها يُرسَل
# تفصيل كل طلب سحب جديد إليها تلقائيًا مع أزرار قبول/رفض، بجانب إشعار
# المالكين المباشر (OWNER_IDS) الذي يبقى يعمل دومًا كخط احتياط.
# ---------------------------------------------------------------------------

def get_withdraw_channel() -> dict:
    """يعيد بيانات قناة استقبال طلبات السحب الحالية، أو None إن لم تُحدَّد بعد."""
    chat_id = get_setting("withdraw_channel_id")
    if not chat_id:
        return None
    return {
        "chat_id": chat_id,
        "username": get_setting("withdraw_channel_username") or "",
        "title": get_setting("withdraw_channel_title") or "",
    }


def set_withdraw_channel(chat_id, username: str, title: str) -> None:
    set_setting("withdraw_channel_id", str(chat_id))
    set_setting("withdraw_channel_username", username or "")
    set_setting("withdraw_channel_title", title or "")


def clear_withdraw_channel() -> None:
    set_setting("withdraw_channel_id", "")
    set_setting("withdraw_channel_username", "")
    set_setting("withdraw_channel_title", "")


# ---------------------------------------------------------------------------
# ⭐ تكلفة كل قيمة سحب نجوم (نقاط) — يتحكم بها المالك بالكامل من قسمه الخاص،
# وتُقرأ من settings عبر get_setting/set_setting الموجودتين أصلًا (نفس آلية
# باقي إعدادات البوت)، فلا حاجة لأي بنية بيانات إضافية.
# ---------------------------------------------------------------------------

def get_star_cost(tier: int) -> int:
    """يعيد عدد النقاط المطلوبة لسحب قيمة نجوم معيّنة، أو القيمة الافتراضية
    إن لم يُعدّلها المالك بعد."""
    raw = get_setting(f"star_cost_{tier}")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_STAR_COSTS.get(tier, 0)


def set_star_cost(tier: int, value: int) -> None:
    set_setting(f"star_cost_{tier}", str(max(0, int(value))))


def get_all_star_costs() -> dict:
    return {tier: get_star_cost(tier) for tier in STAR_WITHDRAW_TIERS}


# ---------------------------------------------------------------------------
# ⭐ طلبات سحب النجوم — تُخزَّن في نفس مجموعة withdraw_requests الحالية مع
# type="stars" لتمييزها عن طلبات السحب القديمة (النظام الثابت السابق)، وتمر
# بثلاث مراحل واضحة: pending (تحت المراجعة) ← accepted (مقبولة، بانتظار
# تحويل النجوم فعليًا من المالك) ← completed (مكتملة). الخصم يتم فور إنشاء
# الطلب عبر معاملة Firestore ذرية (transaction) تتحقق من كفاية الرصيد وتخصمه
# وتُنشئ الطلب في نفس الخطوة — هذا يمنع أي استغلال بالضغط المتكرر على زر
# السحب (لا يوجد سباق بين «تحقق من الرصيد» و«خصمه» كما في الأنظمة اليدوية).
# ---------------------------------------------------------------------------

def has_pending_withdraw_request_any(user_id: int) -> bool:
    """يتحقق من وجود أي طلب سحب (نجوم) لم يُغلق بعد (قيد الانتظار أو مقبول
    بانتظار التحويل) — يُستخدم لمنع إنشاء طلب جديد قبل إغلاق الحالي تمامًا،
    بخلاف الاكتفاء بفحص آخر طلب فقط."""
    for r in get_user_withdraw_requests(user_id):
        if r.get("status") in ("pending", "accepted"):
            return True
    return False


def create_star_withdraw_request(user_id: int, display_name: str, username: str,
                                  stars_amount: int, points_cost: int):
    """ينشئ طلب سحب نجوم جديد ويخصم تكلفته من رصيد المستخدم بذرية كاملة عبر
    معاملة Firestore واحدة: تقرأ الرصيد الحالي، تتحقق من كفايته، ثم تخصمه
    وتُنشئ مستند الطلب في نفس المعاملة. يعيد request_id عند النجاح، أو None
    إن كان الرصيد غير كافٍ فعليًا لحظة التنفيذ (يمنع أي خصم مزدوج ناتج عن
    ضغط متكرر أو سباق بين طلبين متزامنين)."""
    client = fs_db()
    owner_ref = _user_doc_ref(user_id)
    req_ref = client.collection("withdraw_requests").document()
    transaction = client.transaction()

    @firestore.transactional
    def _txn(transaction):
        snap = owner_ref.get(transaction=transaction)
        current = (snap.to_dict().get("points", 0) if snap.exists else 0) or 0
        if current < points_cost:
            return None
        new_balance = current - points_cost
        if snap.exists:
            transaction.update(owner_ref, {"points": new_balance})
        else:
            transaction.set(owner_ref, {"points": new_balance, "user_id": user_id})
        transaction.set(req_ref, {
            "request_id": req_ref.id,
            "user_id": user_id,
            "display_name": display_name,
            "username": username,
            "type": "stars",
            "stars_amount": stars_amount,
            "points_amount": points_cost,
            "status": "pending",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "accepted_at": None,
            "completed_at": None,
        })
        return req_ref.id

    request_id = _txn(transaction)
    if request_id:
        _USER_CACHE.pop(user_id, None)
        invalidate_users_points_cache()
    return request_id


def get_user_star_withdraw_requests(user_id: int) -> list:
    """يعيد فقط طلبات سحب النجوم لمستخدم معيّن (الأحدث أولًا)."""
    return [r for r in get_user_withdraw_requests(user_id) if r.get("type") == "stars"]


def mark_star_withdraw_accepted(request_id: str) -> bool:
    """المرحلة الأولى من القبول: يعلّم الطلب كـ«مقبول» (🟢) بانتظار أن يرسل
    المالك النجوم فعليًا يدويًا ثم يعلّمه لاحقًا كمكتمل. يعيد True فقط إذا
    كان الطلب لا يزال «قيد الانتظار» فعليًا (يمنع القبول المزدوج)."""
    ref = fs_db().collection("withdraw_requests").document(request_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("status") != "pending":
        return False
    ref.update({"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat()})
    return True


def mark_star_withdraw_completed(request_id: str) -> bool:
    """المرحلة الثانية: يعلّم طلبًا «مقبولًا» بالفعل كـ«مكتمل» (✅) بعد إرسال
    النجوم يدويًا. يعيد True فقط إذا كان الطلب بحالة «مقبول» فعليًا."""
    ref = fs_db().collection("withdraw_requests").document(request_id)
    doc = ref.get()
    if not doc.exists or doc.to_dict().get("status") != "accepted":
        return False
    ref.update({"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()})
    return True


def mark_star_withdraw_rejected(request_id: str) -> bool:
    """يرفض طلب سحب نجوم «قيد الانتظار» فقط، ويعيد النقاط المخصومة عند
    الإنشاء فورًا إلى رصيد المستخدم. يعيد True فقط إذا كان الطلب لا يزال
    قيد الانتظار فعليًا (يمنع الرفض المزدوج)."""
    ref = fs_db().collection("withdraw_requests").document(request_id)
    doc = ref.get()
    data = doc.to_dict() if doc.exists else None
    if not data or data.get("status") != "pending":
        return False
    ref.update({"status": "rejected", "completed_at": datetime.now(timezone.utc).isoformat()})
    _fs_bump_counter(_user_doc_ref(data.get("user_id")), "points", int(data.get("points_amount") or 0),
                      extra={"user_id": data.get("user_id")})
    _USER_CACHE.pop(data.get("user_id"), None)
    invalidate_users_points_cache()
    return True


# ---------------------------------------------------------------------------
# 🔔 إشعارات دخول المستخدمين الجدد — إعداد اختياري من المالك: عند تفعيلها
# وتحديد قناة، يُرسَل إشعار تلقائي بكل مستخدم يدخل البوت لأول مرة (اسمه،
# يوزره، معرّفه، ووقت الدخول) إلى تلك القناة.
# ---------------------------------------------------------------------------

def is_new_user_notify_enabled() -> bool:
    """يتحقق مما إذا كانت ميزة إشعارات دخول المستخدمين الجدد مفعّلة حاليًا."""
    return get_setting("new_user_notify_enabled") == "1"


def set_new_user_notify_enabled(enabled: bool) -> None:
    """يفعّل/يوقف ميزة إشعارات دخول المستخدمين الجدد."""
    set_setting("new_user_notify_enabled", "1" if enabled else "0")


def get_new_user_notify_channel() -> dict:
    """يعيد بيانات قناة إشعارات دخول المستخدمين الحالية، أو None إن لم تُحدَّد بعد."""
    chat_id = get_setting("new_user_notify_channel_id")
    if not chat_id:
        return None
    return {
        "chat_id": chat_id,
        "username": get_setting("new_user_notify_channel_username") or "",
        "title": get_setting("new_user_notify_channel_title") or "",
    }


def set_new_user_notify_channel(chat_id, username: str, title: str) -> None:
    set_setting("new_user_notify_channel_id", str(chat_id))
    set_setting("new_user_notify_channel_username", username or "")
    set_setting("new_user_notify_channel_title", title or "")


def clear_new_user_notify_channel() -> None:
    set_setting("new_user_notify_channel_id", "")
    set_setting("new_user_notify_channel_username", "")
    set_setting("new_user_notify_channel_title", "")


async def _notify_new_user_join(context: ContextTypes.DEFAULT_TYPE, user) -> None:
    """يرسل إشعارًا بدخول مستخدم جديد إلى قناة الإشعارات المحددة، فقط إن كانت
    الميزة مفعّلة وتم تحديد قناة فعليًا. لا يرفع أي استثناء عند فشل الإرسال
    (تعطُّل الإشعار لا يجب أن يؤثر على تجربة المستخدم الجديد نفسه إطلاقًا)."""
    if not user or not is_new_user_notify_enabled():
        return
    channel = get_new_user_notify_channel()
    if not channel or not channel.get("chat_id"):
        return
    full_name = (getattr(user, "first_name", "") or "").strip()
    last_name = (getattr(user, "last_name", "") or "").strip()
    if last_name:
        full_name = f"{full_name} {last_name}".strip()
    full_name = full_name or "بدون اسم"
    username = getattr(user, "username", None)
    username_line = f"@{username}" if username else "لا يوجد"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text, entities = build_text_with_emojis([
        ([
            "🔔 مستخدم جديد دخل البوت",
            "\n\n",
            ([
                f"👤 الاسم: {full_name}\n",
                f"🔗 اليوزر: {username_line}\n",
                f"🆔 المعرف: {user.id}\n",
                f"🕒 وقت الدخول: {now_str}",
            ], "blockquote", None),
        ], "bold", None),
    ])
    try:
        await context.bot.send_message(
            chat_id=int(channel["chat_id"]), text=text, entities=entities,
        )
    except Exception:
        logger.exception("تعذّر إرسال إشعار مستخدم جديد إلى قناة الإشعارات")

def toggle_remind_win(user_id: int) -> bool:
    """⚡ موحَّد: يقرأ/يكتب حقل remind_win داخل مستند users/{id} عبر نفس
    الكاش الدائم، بدل مجموعة remind_win منفصلة."""
    row = get_bot_user(user_id)
    current = row.get("remind_win", 1) if row else 1
    new_value = 0 if current == 1 else 1
    _user_doc_ref(user_id).set({
        "user_id": user_id,
        "remind_win": new_value,
        "remind_win_updated_at": datetime.now(timezone.utc).isoformat(),
    }, merge=True)
    _USER_CACHE.pop(user_id, None)
    return bool(new_value)

def get_remind_win_state(user_id: int):
    row = get_bot_user(user_id)
    if not row or "remind_win" not in row:
        return None
    return bool(row.get("remind_win"))

def save_registered_chat(chat_id: int, owner_id: int, chat_title: str, chat_type: str):
    ref = fs_db().collection("registered_chats").document(str(chat_id))
    existing = ref.get()
    registered_at = None
    if existing.exists:
        registered_at = (existing.to_dict() or {}).get("registered_at")
    ref.set({
        "chat_id": chat_id,
        "owner_id": owner_id,
        "chat_title": chat_title,
        "chat_type": chat_type,
        "registered_at": registered_at or datetime.now(timezone.utc).isoformat(),
        "active": True,
        "removed_at": None,
    })
    # ⚡ نسخ الحقول الوصفية (العنوان/النوع/الفعالية) أيضًا على نفس مستند
    # channel_points/{chat_id} — حتى تُقرأ شاشة الإحصائيات كل بيانات القناة
    # (نقاط + عدد سحوبات + عنوان) من قراءة واحدة فقط لمجموعة channel_points،
    # دون الحاجة لقراءة إضافية من registered_chats لكل قناة مرشَّحة كما كان
    # سابقًا (كان هذا يُضاعف عدد القراءات تقريبًا).
    fs_db().collection("channel_points").document(str(chat_id)).set({
        "chat_id": chat_id,
        "chat_title": chat_title,
        "chat_type": chat_type,
        "active": True,
    }, merge=True)

def remove_registered_chat(chat_id: int):
    """حذف ناعم: يُبقي القناة/الجروب في السجل موسومًا كغير نشط (active=False)
    بدل حذفه نهائيًا، حتى تبقى إحصائيات «القنوات/المجموعات غير النشطة» دقيقة."""
    fs_db().collection("registered_chats").document(str(chat_id)).set({
        "active": False,
        "removed_at": datetime.now(timezone.utc).isoformat(),
    }, merge=True)
    # نفس المزامنة أعلاه، بالاتجاه المعاكس (تعطيل)، حتى لا تظهر قناة أُزيلت
    # ضمن أعلى 5 قنوات بشاشة الإحصائيات رغم عدم وجودها فعليًا.
    fs_db().collection("channel_points").document(str(chat_id)).set({
        "active": False,
    }, merge=True)

def get_registered_chats(owner_id: int):
    docs = fs_db().collection("registered_chats").where("owner_id", "==", owner_id).stream()
    rows = [FSRow(d.to_dict()) for d in docs]
    rows = [r for r in rows if r.get("active", True)]
    rows.sort(key=lambda r: r.get("registered_at") or "", reverse=True)
    return rows

def get_all_registered_chats() -> list:
    """يعيد كل القنوات والمجموعات المسجَّلة عبر كل الملاك (نشطة وغير نشطة)،
    تُستخدم لإحصائيات البوت العامة في قسم المالك."""
    docs = fs_db().collection("registered_chats").stream()
    return [FSRow(d.to_dict()) for d in docs]

def entities_to_json(entities) -> str:
    if not entities:
        return "[]"
    out = []
    for e in entities:
        d = {"type": e.type, "offset": e.offset, "length": e.length}
        if getattr(e, "url", None):
            d["url"] = e.url
        if getattr(e, "language", None):
            d["language"] = e.language
        if getattr(e, "custom_emoji_id", None):
            d["custom_emoji_id"] = e.custom_emoji_id
        out.append(d)
    return json.dumps(out, ensure_ascii=False)


def json_to_entities(raw: str):
    try:
        data = json.loads(raw or "[]")
    except Exception:
        return []
    result = []
    for d in data:
        result.append(MessageEntity(
            type=d.get("type"),
            offset=d.get("offset", 0),
            length=d.get("length", 0),
            url=d.get("url"),
            language=d.get("language"),
            custom_emoji_id=d.get("custom_emoji_id"),
        ))
    return result


def generate_contest_code() -> str:
    """كود فريد من 8 أرقام يُستخدم في رابط المشاركة وفي بيانات الأزرار."""
    while True:
        code = str(random.randint(10_000_000, 99_999_999))
        if not get_contest(code):
            return code


def generate_participant_code(contest_code: str) -> str:
    """كود المتسابق الفريد: C + كود المسابقة + 4 أرقام عشوائية."""
    while True:
        suffix = str(random.randint(1000, 9999))
        code = f"C{contest_code}{suffix}"
        if not get_participant_by_code(code):
            return code


# ---------------------------------------------------------------------------
# 🗳️ كاش المسابقات (مشاركين + أصوات + قائمة المفتوحة) — كل مسابقة تُقرأ من
# Firestore مرة واحدة فقط (أول مرة تُحتاج فيها خلال التشغيلة الحالية)، وتبقى
# بالذاكرة بعدها. أي حدث مشاركة حقيقي (تصويت جديد، انضمام متسابق، إلغاء
# تصويت، تغيير حالة) يُحدَّث بالذاكرة وبـFirestore معًا بنفس اللحظة — فتُقرأ
# لوحة المتصدرين وعدّ الأصوات وفحص «هل صوّت» والـaudit الدوري كلها من الذاكرة
# دون أي قراءة متكررة، وتقتصر القراءات/الكتابات الفعلية على لحظة الإنشاء أو
# المشاركة فقط، تمامًا كما طُلب.
# ---------------------------------------------------------------------------

_CONTEST_VOTES_CACHE = {}          # contest_code -> {voter_id: vote_dict}
_CONTEST_VOTES_LOADED = set()      # contest_codes التي حُمِّلت فعليًا من Firestore
_CONTEST_PARTICIPANTS_CACHE = {}   # contest_code -> {user_id: participant_dict}
_CONTEST_PARTICIPANTS_LOADED = set()
_PARTICIPANT_CODE_INDEX = {}       # participant_code -> (contest_code, user_id)
_OPEN_CONTEST_CODES = None         # None = لم تُحمَّل بعد؛ set بعد أول تحميل

# طلبات مشاركة بانتظار موافقة صاحب المسابقة (خاصية "موافقة المشاركات").
# تُحفظ في الذاكرة فقط بلا أي كتابة/قراءة من قاعدة البيانات لحظة الطلب —
# القراءة/الكتابة الفعلية في Firestore تحدث فقط عند قرار صاحب المسابقة
# (قبول/رفض)، تمامًا كطلب المستخدم بعدم استهلاك موارد القراءة.
# (contest_code, user_id) -> {"display_name": str, "username": str|None}
_CONTEST_PENDING_JOIN_REQUESTS = {}


def _get_open_contest_codes() -> set:
    """يعيد مجموعة أكواد المسابقات المفتوحة حاليًا. تُقرأ من Firestore مرة
    واحدة فقط طول عمر تشغيل البوت، وتُحدَّث بعدها بالذاكرة فقط عند إنشاء/
    إغلاق أي مسابقة فعليًا."""
    global _OPEN_CONTEST_CODES
    if _OPEN_CONTEST_CODES is None:
        _OPEN_CONTEST_CODES = {
            d.to_dict().get("contest_code")
            for d in fs_db().collection("contests").where("status", "==", "open").stream()
        }
        _OPEN_CONTEST_CODES.discard(None)
    return _OPEN_CONTEST_CODES


def _load_contest_votes(contest_code: str) -> dict:
    """يحمّل أصوات مسابقة معيّنة من Firestore مرة واحدة فقط، ويبقيها بالذاكرة
    (dict بمفتاح voter_id) لكل الاستدعاءات اللاحقة بنفس التشغيلة."""
    if contest_code not in _CONTEST_VOTES_LOADED:
        votes = {}
        for d in fs_db().collection("contest_votes").where("contest_code", "==", contest_code).stream():
            data = d.to_dict() or {}
            voter_id = data.get("voter_id")
            if voter_id is not None:
                votes[voter_id] = data
        _CONTEST_VOTES_CACHE[contest_code] = votes
        _CONTEST_VOTES_LOADED.add(contest_code)
    return _CONTEST_VOTES_CACHE.setdefault(contest_code, {})


def _load_contest_participants(contest_code: str) -> dict:
    """يحمّل متسابقي مسابقة معيّنة من Firestore مرة واحدة فقط، ويبقيهم بالذاكرة
    (dict بمفتاح user_id) لكل الاستدعاءات اللاحقة بنفس التشغيلة."""
    if contest_code not in _CONTEST_PARTICIPANTS_LOADED:
        parts = {}
        for d in fs_db().collection("contest_participants").where("contest_code", "==", contest_code).stream():
            data = d.to_dict() or {}
            uid = data.get("user_id")
            if uid is not None:
                parts[uid] = data
                pc = data.get("participant_code")
                if pc:
                    _PARTICIPANT_CODE_INDEX[pc] = (contest_code, uid)
        _CONTEST_PARTICIPANTS_CACHE[contest_code] = parts
        _CONTEST_PARTICIPANTS_LOADED.add(contest_code)
    return _CONTEST_PARTICIPANTS_CACHE.setdefault(contest_code, {})


def _evict_contest_cache(contest_code: str) -> None:
    """يفرّغ كاش مسابقة معيّنة من الذاكرة كليًا (بعد الحذف النهائي)."""
    _CONTEST_VOTES_CACHE.pop(contest_code, None)
    _CONTEST_VOTES_LOADED.discard(contest_code)
    parts = _CONTEST_PARTICIPANTS_CACHE.pop(contest_code, {})
    _CONTEST_PARTICIPANTS_LOADED.discard(contest_code)
    for data in parts.values():
        pc = data.get("participant_code")
        if pc:
            _PARTICIPANT_CODE_INDEX.pop(pc, None)
    if _OPEN_CONTEST_CODES is not None:
        _OPEN_CONTEST_CODES.discard(contest_code)


def create_contest(contest_code: str, owner_id: int, chat_id: int, cliche_text: str,
                    cliche_entities, target_count: int, end_type: str, time_minutes,
                    winners_count, settings: dict, votes_target=None) -> None:
    fs_db().collection("contests").document(contest_code).set({
        "contest_code": contest_code,
        "owner_id": owner_id,
        "chat_id": chat_id,
        "cliche_text": cliche_text,
        "cliche_entities": entities_to_json(cliche_entities),
        "target_count": target_count,
        "end_type": end_type,
        "time_minutes": time_minutes,
        "votes_target": votes_target,
        "winners_count": winners_count,
        "notify_win": int(bool(settings.get("contest_notify_win", False))),
        "announce_results": int(bool(settings.get("contest_announce_results", False))),
        "approve_participants": int(bool(settings.get("contest_approve_participants", False))),
        "premium_only": int(bool(settings.get("contest_premium_only", False))),
        "channel_message_id": None,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # حدث إنشاء فعلي — يُضاف مباشرة لكاش المسابقات المفتوحة بالذاكرة (يضمن
    # التحميل الأول من Firestore لو لم يحدث بعد بهذه التشغيلة).
    _get_open_contest_codes().add(contest_code)
    _CONTEST_VOTES_CACHE[contest_code] = {}
    _CONTEST_VOTES_LOADED.add(contest_code)
    _CONTEST_PARTICIPANTS_CACHE[contest_code] = {}
    _CONTEST_PARTICIPANTS_LOADED.add(contest_code)
    bump_channel_roulette_count(chat_id)


def get_contest(contest_code: str):
    doc = fs_db().collection("contests").document(contest_code).get()
    return _fs_row_or_none(doc)


def get_open_contests_by_chat(chat_id: int) -> list:
    """يعيد كل المسابقات المفتوحة حاليًا والمستضافة في قناة/قروب معيّن —
    تُستخدم فور اكتشاف خروج مستخدم من قناة لمعرفة أي مسابقات مستضافة هناك
    يلزم فحص مشاركته فيها تحديدًا (بدل المرور على كل المسابقات المفتوحة في
    البوت)."""
    docs = (
        fs_db().collection("contests")
        .where("chat_id", "==", chat_id)
        .where("status", "==", "open")
        .stream()
    )
    return [FSRow(d.to_dict()) for d in docs]


def get_contests_by_owner(owner_id: int):
    """يعيد المسابقات الجارية (غير المنتهية) الخاصة بالمالك، الأحدث أولًا."""
    docs = fs_db().collection("contests").where("owner_id", "==", owner_id).stream()
    rows = [FSRow(d.to_dict()) for d in docs if d.to_dict().get("status") in ("open", "paused")]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def get_chat_title_by_id(chat_id: int) -> str:
    doc = fs_db().collection("registered_chats").document(str(chat_id)).get()
    if doc.exists and doc.to_dict().get("chat_title"):
        return doc.to_dict()["chat_title"]
    return str(chat_id)


def contest_display_name(contest) -> str:
    """يستخرج اسمًا معروضًا للمسابقة من أول سطر بنص إعلانها، أو رمزها كبديل."""
    text = (contest["cliche_text"] or "").strip()
    if text:
        first_line = text.splitlines()[0].strip()
        if len(first_line) > 40:
            first_line = first_line[:40].rstrip() + "…"
        return first_line
    return f"مسابقة #{contest['contest_code']}"


async def build_contest_post_link(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id):
    """يبني رابط منشور المسابقة في القناة (عام أو خاص) إن توفّر معرف الرسالة."""
    if not message_id:
        return None
    try:
        chat = await context.bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}/{message_id}"
    except Exception:
        pass
    str_id = str(chat_id)
    if str_id.startswith("-100"):
        return f"https://t.me/c/{str_id[4:]}/{message_id}"
    return None


async def build_giveaway_boost_link(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> str:
    """يبني رابط تعزيز (Boost) القناة المرتبطة بسحب مفعّل عليه خيار «تعزيز
    القناة» (Image A1/A2)، بصيغة https://t.me/boost/<username> التي يتعرّف
    عليها تطبيق تيليجرام تلقائيًا ويفتح نافذة التعزيز الأصلية عند الضغط عليها
    (Image A4). يعيد نصًا فارغًا إن تعذّر جلب يوزر القناة (مثلاً قناة خاصة بلا
    يوزر عام)، لأن رابط التعزيز يتطلب يوزر عامًا للقناة."""
    try:
        chat = await context.bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/boost/{chat.username}"
    except Exception:
        logger.exception("تعذّر جلب يوزر القناة %s لبناء رابط التعزيز", chat_id)
    return ""


async def announce_new_post(context: ContextTypes.DEFAULT_TYPE, source_chat_id: int,
                             sent_message_id: int, kind: str, extra: dict = None) -> None:
    """بعد نشر مسابقة أو سحب بنجاح في قناة/جروب المستخدم، يُنشر إعلانًا إضافيًا في قناة
    الإعلانات العامة (ANNOUNCE_CHANNEL_CHAT_ID) يحتوي على زر أخضر يفتح المنشور الأصلي
    مباشرة، لتوسيع دائرة انتشار السحوبات والمسابقات. لا يرفع أي استثناء أبدًا حتى لا
    يؤثر فشل الإعلان على نجاح النشر الأساسي في قناة المستخدم.

    إعلان قناة السحوبات هذا (بخلاف المنشور العام في قناة/قروب المستخدم) هو المكان
    المخصَّص لعرض كود المسابقة/السحب (extra["code"])، مرفقًا بزر نسخ تلقائي بضغطة
    واحدة (CopyTextButton) — احترافي وبلا حاجة لتحديد النص يدويًا.
    """
    try:
        chat = await context.bot.get_chat(source_chat_id)
        label = f"@{chat.username}" if chat.username else (chat.title or "قناتك")
        if chat.username:
            post_link = f"https://t.me/{chat.username}/{sent_message_id}"
        else:
            str_id = str(source_chat_id)
            post_link = f"https://t.me/c/{str_id[4:]}/{sent_message_id}" if str_id.startswith("-100") else None
    except Exception:
        label = "قناتك"
        post_link = await build_contest_post_link(context, source_chat_id, sent_message_id)

    if not post_link:
        return

    code = (extra or {}).get("code")

    if kind == "contest":
        text = f"🏁 مسابقة جديدة في قناة - {label}"
        button_text = "المشاركة في المسابقة"
    else:
        winners_count = (extra or {}).get("winners_count") or 1
        text = f"🎉 سحب جديد في قناة: {label}\n🏆 عدد الفائزين: {winners_count}"
        button_text = "رؤية السحب"

    if code:
        text += f"\n🆔 الكود : {code}"

    rows = [[InlineKeyboardButton(button_text, url=post_link, style="success")]]
    if code:
        try:
            copy_btn = InlineKeyboardButton(
                "📋 نسخ الكود", copy_text=CopyTextButton(text=code), style="primary",
            )
        except Exception:
            copy_btn = InlineKeyboardButton(f"📋 الكود: {code}", callback_data="noop")
        rows.append([copy_btn])
    keyboard = InlineKeyboardMarkup(rows)
    try:
        await context.bot.send_message(
            chat_id=ANNOUNCE_CHANNEL_CHAT_ID,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.warning("تعذر نشر الإعلان في قناة الإعلانات (%s)", ANNOUNCE_CHANNEL_CHAT_ID)


def delete_contest_completely(contest_code: str) -> None:
    """يحذف المسابقة بكل مشاركيها وأصواتها نهائيًا من قاعدة البيانات. عملية
    إدارية نادرة (حذف كامل من المالك) — لازم تعداد المستندات الفعلية لحذفها،
    فتبقى قراءات هذه الدالة تحديدًا كما هي."""
    client = fs_db()
    for d in client.collection("contest_votes").where("contest_code", "==", contest_code).stream():
        d.reference.delete()
    for d in client.collection("contest_participants").where("contest_code", "==", contest_code).stream():
        d.reference.delete()
    client.collection("contests").document(contest_code).delete()
    _evict_contest_cache(contest_code)


def set_contest_channel_message(contest_code: str, message_id: int):
    fs_db().collection("contests").document(contest_code).update({"channel_message_id": message_id})


def set_contest_status(contest_code: str, status: str):
    fs_db().collection("contests").document(contest_code).update({"status": status})
    if status == "open":
        _get_open_contest_codes().add(contest_code)
    elif _OPEN_CONTEST_CODES is not None:
        _OPEN_CONTEST_CODES.discard(contest_code)


def count_contest_participants(contest_code: str) -> int:
    return len(_load_contest_participants(contest_code))


def _contest_participant_doc_id(contest_code: str, user_id: int) -> str:
    return f"{contest_code}_{user_id}"


def get_contest_participant(contest_code: str, user_id: int):
    data = _load_contest_participants(contest_code).get(user_id)
    return FSRow(dict(data)) if data is not None else None


def get_participant_by_code(participant_code: str):
    """يبحث عن متسابق عبر كوده. يعتمد أولًا على الفهرس بالذاكرة (مبني من كل
    مسابقة سبق تحميلها بهذه التشغيلة)؛ فقط لو لم يوجد الكود بالفهرس بعد،
    يقرأ من Firestore مباشرة (حالة نادرة: كود يخص مسابقة لم تُفتح بعد بهذه
    التشغيلة)."""
    hit = _PARTICIPANT_CODE_INDEX.get(participant_code)
    if hit is not None:
        contest_code, user_id = hit
        data = _CONTEST_PARTICIPANTS_CACHE.get(contest_code, {}).get(user_id)
        if data is not None:
            return FSRow(dict(data))
    docs = fs_db().collection("contest_participants").where("participant_code", "==", participant_code).limit(1).stream()
    for d in docs:
        data = d.to_dict() or {}
        cc = data.get("contest_code")
        uid = data.get("user_id")
        if cc and uid is not None:
            _load_contest_participants(cc)  # يضمن تحميل بقية مسابقته للكاش أيضًا
            _CONTEST_PARTICIPANTS_CACHE.setdefault(cc, {})[uid] = data
            _PARTICIPANT_CODE_INDEX[participant_code] = (cc, uid)
        return FSRow(data)
    return None


def add_contest_participant(contest_code: str, user_id: int, display_name: str, participant_code: str):
    ref = fs_db().collection("contest_participants").document(_contest_participant_doc_id(contest_code, user_id))
    new_data = {
        "contest_code": contest_code,
        "user_id": user_id,
        "display_name": display_name,
        "participant_code": participant_code,
        "channel_message_id": None,
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }
    _fs_create_or_integrity_error(ref, new_data)
    # حدث مشاركة فعلي — يُحدَّث الكاش مباشرة بالذاكرة.
    parts = _load_contest_participants(contest_code)
    parts[user_id] = new_data
    _PARTICIPANT_CODE_INDEX[participant_code] = (contest_code, user_id)


def remove_contest_participant(contest_code: str, user_id: int):
    client = fs_db()
    client.collection("contest_participants").document(_contest_participant_doc_id(contest_code, user_id)).delete()
    votes = _load_contest_votes(contest_code)
    for voter_id, vd in list(votes.items()):
        if vd.get("participant_user_id") == user_id:
            if vd.get("status", "confirmed") == "confirmed" and vd.get("points_awarded"):
                reverse_contest_owner_points(vd.get("owner_id"), vd.get("points_awarded"))
            client.collection("contest_votes").document(f"{contest_code}_{voter_id}").delete()
            votes.pop(voter_id, None)
    parts = _load_contest_participants(contest_code)
    removed = parts.pop(user_id, None)
    if removed:
        pc = removed.get("participant_code")
        if pc:
            _PARTICIPANT_CODE_INDEX.pop(pc, None)


def set_participant_channel_message(contest_code: str, user_id: int, message_id: int):
    fs_db().collection("contest_participants").document(_contest_participant_doc_id(contest_code, user_id)).update(
        {"channel_message_id": message_id}
    )
    parts = _load_contest_participants(contest_code)
    if user_id in parts:
        parts[user_id]["channel_message_id"] = message_id


def has_voted(contest_code: str, voter_id: int) -> bool:
    """يعيد True فقط إذا كان لدى المصوّت تصويت «مؤكد» حاليًا. التصويتات
    الملغاة (بسبب مغادرة القنوات الإلزامية) لا تُحتسب هنا، ما يسمح للمصوّت
    بالتصويت من جديد إذا عاد واشترك لاحقًا."""
    data = _load_contest_votes(contest_code).get(voter_id)
    return bool(data and data.get("status", "confirmed") == "confirmed")


def register_confirmed_contest_vote(contest_code: str, voter_id: int, participant_user_id: int,
                                     owner_id: int, voter_display_name: str = None) -> bool:
    """يسجّل تصويتًا «مؤكدًا» بعد اجتياز كل الشروط (اشتراك + تحقق + عدم تلاعب)،
    ويمنح صاحب المسابقة نقاطه فورًا لهذا الصوت. إن كان هناك تصويت سابق أُلغي
    لنفس المصوّت في نفس المسابقة، يُستبدل بتصويت جديد مؤكد بدل رفضه. يعيد
    True إذا سُجّل التصويت فعليًا، وFalse إذا كان هناك تصويت مؤكد سابقًا بالفعل.
    يُخزَّن أيضًا اسم المصوّت وقت التصويت (voter_display_name) لاستخدامه لاحقًا
    في إشعار خصم الصوت دون الحاجة لطلب بيانات المستخدم من تيليجرام من جديد."""
    votes = _load_contest_votes(contest_code)
    existing = votes.get(voter_id)
    if existing and existing.get("status", "confirmed") == "confirmed":
        return False
    ref = fs_db().collection("contest_votes").document(f"{contest_code}_{voter_id}")
    vote_data = {
        "contest_code": contest_code,
        "voter_id": voter_id,
        "participant_user_id": participant_user_id,
        "owner_id": owner_id,
        "voter_display_name": voter_display_name or str(voter_id),
        "voted_at": datetime.now(timezone.utc).isoformat(),
        "status": "confirmed",
        "points_awarded": 0,
    }
    ref.set(vote_data)
    amount = award_contest_owner_points(owner_id)
    if amount:
        vote_data["points_awarded"] = amount
        ref.update({"points_awarded": amount})
    # حدث مشاركة فعلي (تصويت) — يُحدَّث الكاش مباشرة بالذاكرة.
    votes[voter_id] = vote_data
    return True


def has_voted_for(contest_code: str, voter_id: int, participant_user_id: int) -> bool:
    """يتحقق من أن المستخدم صوّت تحديدًا لهذا المتسابق (وليس لأي متسابق آخر في نفس
    المسابقة) — يُستخدم للتحقق من شرط «تصويت متسابق» قبل السماح بالمشاركة في السحب.
    لا يُحتسب أي تصويت مُلغى بسبب مغادرة القنوات الإلزامية."""
    data = _load_contest_votes(contest_code).get(voter_id)
    if not data:
        return False
    return (
        data.get("status", "confirmed") == "confirmed"
        and data.get("participant_user_id") == participant_user_id
    )


def get_participant_votes(contest_code: str, participant_user_id: int) -> int:
    votes = _load_contest_votes(contest_code)
    return sum(
        1 for v in votes.values()
        if v.get("participant_user_id") == participant_user_id
        and v.get("status", "confirmed") == "confirmed"
    )


def get_contest_leaderboard(contest_code: str):
    """
    يُعيد قائمة كل المتسابقين مرتّبة تنازليًا حسب عدد الأصوات (الأعلى أولًا)،
    وعند التعادل يُقدَّم من انضمّ أولًا. كل عنصر: (user_id, display_name, participant_code, votes).
    التصويتات الملغاة (بسبب مغادرة القنوات الإلزامية) لا تُحتسب ضمن العدد.
    """
    participants = _load_contest_participants(contest_code)
    votes = _load_contest_votes(contest_code)
    vote_counts = {}
    for vd in votes.values():
        if vd.get("status", "confirmed") != "confirmed":
            continue
        pid = vd.get("participant_user_id")
        vote_counts[pid] = vote_counts.get(pid, 0) + 1
    rows = []
    for uid, data in participants.items():
        rows.append((
            uid, data.get("display_name") or str(uid), data.get("participant_code"),
            vote_counts.get(uid, 0), data.get("joined_at") or "",
        ))
    rows.sort(key=lambda r: (-r[3], r[4]))
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def get_open_time_contests():
    """يُعيد كل المسابقات المفتوحة المعتمدة على وقت محدد (لإعادة جدولة المؤقتات بعد إعادة تشغيل البوت)."""
    docs = fs_db().collection("contests").where("status", "==", "open").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        if data.get("end_type") == "time" and data.get("time_minutes") is not None:
            rows.append(FSRow(data))
    return rows


# ---------------------------------------------------------------------------
# 🏁 المسابقات (قسم المالك) — عرض/حذف كل المسابقات وإحصائياتها، بنفس نظام
# إدارة السحوبات لدى المالك (admgw_*) أعلاه. المسابقات المنتهية (status == "ended")
# لا تُحذف تلقائيًا أبدًا، وتبقى محفوظة بكل بياناتها حتى يحذفها المالك يدويًا.
# ---------------------------------------------------------------------------

def get_all_contests() -> list:
    """يعيد كل مسابقات البوت (لكل المستخدمين، بجميع الحالات)، الأحدث أولًا."""
    docs = fs_db().collection("contests").stream()
    rows = [FSRow(d.to_dict()) for d in docs]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def delete_contest_admin(contest_code: str) -> None:
    """يحذف مسابقة نهائيًا مع كل متسابقيها وأصواتها — يُستخدم من قسم إدارة المسابقات لدى المالك."""
    delete_contest_completely(contest_code)


_CONTESTS_STATS_CACHE = {"data": None, "ts": 0.0}


def get_contests_statistics(force_refresh: bool = False) -> dict:
    """إحصائيات شاملة عن كل مسابقات البوت — تُستخدم في «📊 إحصائيات المسابقات»
    ضمن قسم إدارة المسابقات لدى المالك، وفي شاشة «📊 الإحصائيات» العامة.

    (محسّنة: تحسب عدد المشاركين لكل المسابقات بقراءة واحدة شاملة لمجموعة
    contest_participants وتجميعها في الذاكرة حسب contest_code، بدل استعلام
    منفصل لكل مسابقة — نفس الأرقام تمامًا، بقراءة واحدة بدل مئات القراءات.
    ومُخزَّنة مؤقتًا (كاش) لتفادي إعادة هذه القراءة عند كل ضغطة.)"""
    now_ts = time.time()
    cached = _CONTESTS_STATS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _CONTESTS_STATS_CACHE["ts"] < STATS_SCREEN_CACHE_TTL:
        return cached
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    contests = get_all_contests()
    total = len(contests)
    active = sum(1 for c in contests if c.get("status") in ("open", "paused"))
    finished = sum(1 for c in contests if c.get("status") == "ended")

    today_count = week_count = month_count = 0
    for c in contests:
        created_raw = c.get("created_at")
        if not created_raw:
            continue
        try:
            created = datetime.fromisoformat(created_raw)
        except (ValueError, TypeError):
            continue
        if created >= today_start:
            today_count += 1
        if created >= week_start:
            week_count += 1
        if created >= month_start:
            month_count += 1

    participants_by_code = {}
    for doc in fs_db().collection("contest_participants").stream():
        code = doc.to_dict().get("contest_code")
        if code:
            participants_by_code[code] = participants_by_code.get(code, 0) + 1
    participant_counts = [participants_by_code.get(c["contest_code"], 0) for c in contests]
    total_participants = sum(participant_counts)
    avg_participants = (total_participants / total) if total else 0

    top_contest_code = None
    top_count = 0
    for c, cnt in zip(contests, participant_counts):
        if cnt > top_count:
            top_count = cnt
            top_contest_code = c["contest_code"]

    result = {
        "total": total,
        "active": active,
        "finished": finished,
        "total_participants": total_participants,
        "avg_participants": avg_participants,
        "today_count": today_count,
        "week_count": week_count,
        "month_count": month_count,
        "top_contest_code": top_contest_code,
        "top_count": top_count,
    }
    _CONTESTS_STATS_CACHE["data"] = result
    _CONTESTS_STATS_CACHE["ts"] = now_ts
    return result


def generate_gw_code() -> str:
    """كود فريد من 8 محارف hex يُستخدم في بيانات أزرار السحب المنشور."""
    while True:
        code = uuid.uuid4().hex[:8]
        if not get_giveaway(code):
            return code


def create_giveaway(gw_code: str, owner_id: int, chat_id: int, cliche_text: str,
                     cliche_entities, winners_count: int, settings: dict) -> None:
    autospin_mode = settings.get("gw_autospin_mode")
    autospin_target = settings.get("gw_autospin_target")
    autospin_minutes = settings.get("gw_autospin_minutes")
    autospin_ends_at = (
        (datetime.now(timezone.utc) + timedelta(minutes=autospin_minutes)).isoformat()
        if autospin_mode == "time" and autospin_minutes else None
    )
    fs_db().collection("giveaways").document(gw_code).set({
        "gw_code": gw_code,
        "owner_id": owner_id,
        "chat_id": chat_id,
        "cliche_text": cliche_text,
        "cliche_entities": entities_to_json(cliche_entities),
        "winners_count": winners_count,
        "boost_required": int(bool(settings.get("gw_boost", False))),
        "premium_only": int(bool(settings.get("gw_premium", False))),
        "antispam": int(bool(settings.get("gw_antispam", False))),
        "vote_contest_code": settings.get("gw_vote_contest_code"),
        "vote_participant_id": settings.get("gw_vote_participant_id"),
        "vote_participant_code": settings.get("gw_vote_participant_code"),
        "vote_display_name": settings.get("gw_vote_display_name"),
        "condition_channels": settings.get("gw_condition_channels") or [],
        "channel_message_id": None,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "autospin_mode": autospin_mode,
        "autospin_target": autospin_target,
        "autospin_minutes": autospin_minutes,
        "autospin_ends_at": autospin_ends_at,
    })
    bump_channel_roulette_count(chat_id)


def get_giveaway(gw_code: str):
    doc = fs_db().collection("giveaways").document(gw_code).get()
    return _fs_row_or_none(doc)


def set_giveaway_channel_message(gw_code: str, message_id: int):
    fs_db().collection("giveaways").document(gw_code).update({"channel_message_id": message_id})


def set_giveaway_status(gw_code: str, status: str):
    fs_db().collection("giveaways").document(gw_code).update({"status": status})


def count_giveaway_participants(gw_code: str) -> int:
    docs = fs_db().collection("giveaway_participants").where("gw_code", "==", gw_code).stream()
    return sum(1 for _ in docs)


def _giveaway_participant_doc_id(gw_code: str, user_id: int) -> str:
    return f"{gw_code}_{user_id}"


def is_giveaway_participant(gw_code: str, user_id: int) -> bool:
    doc = fs_db().collection("giveaway_participants").document(_giveaway_participant_doc_id(gw_code, user_id)).get()
    return doc.exists


def add_giveaway_participant(gw_code: str, user_id: int, display_name: str, username: str = None) -> bool:
    """يضيف مشاركًا جديدًا؛ يُعيد False إن كان مسجّلاً بالفعل."""
    from google.api_core.exceptions import AlreadyExists
    ref = fs_db().collection("giveaway_participants").document(_giveaway_participant_doc_id(gw_code, user_id))
    try:
        ref.create({
            "gw_code": gw_code,
            "user_id": user_id,
            "display_name": display_name,
            "username": username,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        })
        return True
    except AlreadyExists:
        return False


def remove_giveaway_participant(gw_code: str, user_id: int):
    fs_db().collection("giveaway_participants").document(_giveaway_participant_doc_id(gw_code, user_id)).delete()


def get_giveaway_participants(gw_code: str):
    docs = list(fs_db().collection("giveaway_participants").where("gw_code", "==", gw_code).stream())
    rows = [d.to_dict() for d in docs]
    rows.sort(key=lambda r: r.get("joined_at") or "")
    return [(r["user_id"], r.get("display_name") or str(r["user_id"])) for r in rows]


def get_open_giveaways_by_chat(chat_id: int) -> list:
    """نظير get_open_contests_by_chat لكن للسحوبات — يعيد كل السحوبات
    المفتوحة حاليًا والمستضافة في قناة/قروب معيّن."""
    docs = (
        fs_db().collection("giveaways")
        .where("chat_id", "==", chat_id)
        .where("status", "==", "open")
        .stream()
    )
    return [FSRow(d.to_dict()) for d in docs]


def get_giveaways_by_owner(owner_id: int):
    """يعيد كل سحوبات المستخدم (بجميع حالاتها)، الأقدم أولًا، لترقيمها بثبات عبر الصفحات."""
    docs = fs_db().collection("giveaways").where("owner_id", "==", owner_id).stream()
    rows = [FSRow(d.to_dict()) for d in docs]
    rows.sort(key=lambda r: r.get("created_at") or "")
    return rows


def get_open_time_giveaways():
    """يُعيد كل السحوبات المفتوحة المعتمدة على «سحب تلقائي - وقت محدد» (لإعادة
    جدولة المؤقتات بعد إعادة تشغيل البوت، ولتحديث العد التنازلي كل 10 دقائق)."""
    docs = fs_db().collection("giveaways").where("status", "==", "open").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        if data.get("autospin_mode") == "time" and data.get("autospin_ends_at"):
            rows.append(FSRow(data))
    return rows


def giveaway_autospin_end_datetime(giveaway) -> datetime:
    end_at = datetime.fromisoformat(giveaway["autospin_ends_at"])
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)
    return end_at


def count_giveaway_new_rewarded(gw_code: str) -> int:
    """يعيد عدد المشاركين الجدد الذين احتُسبت نقاط لصاحب السحب بسبب مشاركتهم في هذا السحب تحديدًا."""
    docs = fs_db().collection("users").where("rewarded_gw_code", "==", gw_code).stream()
    return sum(1 for _ in docs)


# ---------------------------------------------------------------------------
# 🎁 إدارة السحوبات (قسم المالك) — عرض/حذف كل سحوبات البوت وإحصائياتها.
# المالك هنا لا يختار الفائز ولا يعيد السحب، فقط يستعرض ويحذف.
# ---------------------------------------------------------------------------

def get_all_giveaways() -> list:
    """يعيد كل سحوبات البوت (لكل المستخدمين، بجميع الحالات)، الأحدث أولًا."""
    docs = fs_db().collection("giveaways").stream()
    rows = [FSRow(d.to_dict()) for d in docs]
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def delete_giveaway_admin(gw_code: str) -> None:
    """يحذف سحبًا نهائيًا مع كل مشاركيه — يُستخدم من قسم إدارة السحوبات لدى المالك."""
    for doc in fs_db().collection("giveaway_participants").where("gw_code", "==", gw_code).stream():
        doc.reference.delete()
    fs_db().collection("giveaways").document(gw_code).delete()


_GIVEAWAYS_STATS_CACHE = {"data": None, "ts": 0.0}


def get_giveaways_statistics(force_refresh: bool = False) -> dict:
    """إحصائيات شاملة عن كل سحوبات البوت — تُستخدم في «📊 إحصائيات السحوبات»
    ضمن قسم إدارة السحوبات لدى المالك، وفي شاشة «📊 الإحصائيات» العامة.

    (محسّنة: تحسب عدد المشاركين لكل السحوبات بقراءة واحدة شاملة لمجموعة
    giveaway_participants وتجميعها في الذاكرة حسب gw_code، بدل استعلام منفصل
    لكل سحب — نفس الأرقام تمامًا، بقراءة واحدة بدل مئات القراءات. ومُخزَّنة
    مؤقتًا (كاش) لتفادي إعادة هذه القراءة عند كل ضغطة.)"""
    now_ts = time.time()
    cached = _GIVEAWAYS_STATS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _GIVEAWAYS_STATS_CACHE["ts"] < STATS_SCREEN_CACHE_TTL:
        return cached
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    giveaways = get_all_giveaways()
    total = len(giveaways)
    active = sum(1 for g in giveaways if g.get("status") in ("open", "paused"))
    finished = sum(1 for g in giveaways if g.get("status") == "closed")

    today_count = week_count = month_count = 0
    for g in giveaways:
        created_raw = g.get("created_at")
        if not created_raw:
            continue
        try:
            created = datetime.fromisoformat(created_raw)
        except (ValueError, TypeError):
            continue
        if created >= today_start:
            today_count += 1
        if created >= week_start:
            week_count += 1
        if created >= month_start:
            month_count += 1

    participants_by_code = {}
    for doc in fs_db().collection("giveaway_participants").stream():
        code = doc.to_dict().get("gw_code")
        if code:
            participants_by_code[code] = participants_by_code.get(code, 0) + 1
    participant_counts = [participants_by_code.get(g["gw_code"], 0) for g in giveaways]
    total_participants = sum(participant_counts)
    avg_participants = (total_participants / total) if total else 0

    top_gw_code = None
    top_count = 0
    for g, cnt in zip(giveaways, participant_counts):
        if cnt > top_count:
            top_count = cnt
            top_gw_code = g["gw_code"]

    result = {
        "total": total,
        "active": active,
        "finished": finished,
        "total_participants": total_participants,
        "avg_participants": avg_participants,
        "today_count": today_count,
        "week_count": week_count,
        "month_count": month_count,
        "top_gw_code": top_gw_code,
        "top_count": top_count,
    }
    _GIVEAWAYS_STATS_CACHE["data"] = result
    _GIVEAWAYS_STATS_CACHE["ts"] = now_ts
    return result


# ---------------------------------------------------------------------------
# ⚡ السحب السريع (قسم المالك) — عرض/حذف كل عمليات الروليت السريع وإحصائياتها.
# الخيارات التي أنشأها البحث المضمّن (Inline) ولم يتم اختيارها أبدًا لها
# inline_message_id فارغ ولا تُعتبر سحوبات فعلية، فتُستبعد من كل ما يلي.
# ---------------------------------------------------------------------------

def get_all_quick_roulettes() -> list:
    """يعيد كل عمليات السحب السريع المنشورة فعليًا (لها inline_message_id)، الأحدث أولًا."""
    docs = fs_db().collection("roulettes").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        if data.get("inline_message_id"):
            rows.append(FSRow(data))
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return rows


def delete_quick_roulette_admin(roulette_id: int) -> None:
    """يحذف عملية سحب سريع نهائيًا مع كل مشاركيها."""
    for doc in fs_db().collection("counted_users").where("roulette_id", "==", roulette_id).stream():
        doc.reference.delete()
    fs_db().collection("roulettes").document(str(roulette_id)).delete()


_QUICK_ROULETTE_STATS_CACHE = {"data": None, "ts": 0.0}


def get_quick_roulette_statistics(force_refresh: bool = False) -> dict:
    """إحصائيات شاملة عن كل عمليات السحب السريع — تعتمد على count_participants
    الموجودة مسبقًا لحساب عدد المشاركين لكل عملية سحب. مُخزَّنة مؤقتًا (كاش)
    لتفادي إعادة قراءة كل السجلات عند كل ضغطة."""
    now_ts = time.time()
    cached = _QUICK_ROULETTE_STATS_CACHE["data"]
    if not force_refresh and cached is not None and now_ts - _QUICK_ROULETTE_STATS_CACHE["ts"] < STATS_SCREEN_CACHE_TTL:
        return cached
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    roulettes = get_all_quick_roulettes()
    total = len(roulettes)
    active = sum(1 for r in roulettes if r.get("status") in ("open", "waiting_spin"))
    finished = sum(1 for r in roulettes if r.get("status") == "closed")

    today_count = week_count = month_count = 0
    for r in roulettes:
        created_raw = r.get("created_at")
        if not created_raw:
            continue
        try:
            created = datetime.fromisoformat(created_raw)
        except (ValueError, TypeError):
            continue
        if created >= today_start:
            today_count += 1
        if created >= week_start:
            week_count += 1
        if created >= month_start:
            month_count += 1

    # محسّنة: قراءة واحدة شاملة لمجموعة counted_users وتجميعها حسب roulette_id
    # بدل استعلام منفصل لكل عملية سحب سريع — نفس الأرقام تمامًا.
    participants_by_id = {}
    for doc in fs_db().collection("counted_users").stream():
        rid = doc.to_dict().get("roulette_id")
        if rid:
            participants_by_id[rid] = participants_by_id.get(rid, 0) + 1
    participant_counts = [participants_by_id.get(r["roulette_id"], 0) for r in roulettes]
    total_participants = sum(participant_counts)
    avg_participants = (total_participants / total) if total else 0

    result = {
        "total": total,
        "active": active,
        "finished": finished,
        "total_participants": total_participants,
        "avg_participants": avg_participants,
        "today_count": today_count,
        "week_count": week_count,
        "month_count": month_count,
    }
    _QUICK_ROULETTE_STATS_CACHE["data"] = result
    _QUICK_ROULETTE_STATS_CACHE["ts"] = now_ts
    return result


async def bot_chat_status_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يلتقط لحظة إضافة/ترقية البوت كمشرف (أو إزالته) في قناة أو جروب،
    ويسجّل/يحذف القناة أو الجروب تلقائيًا لصاحب العملية.
    """
    result = update.my_chat_member
    if result is None:
        return

    chat = result.chat
    if chat.type not in ("channel", "group", "supergroup"):
        return

    if chat.username and chat.username.lower() == ANNOUNCE_CHANNEL_USERNAME.lower():
        return

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    actor = result.from_user

    became_admin = new_status == "administrator" and old_status != "administrator"
    left_or_removed = new_status in ("left", "kicked", "member", "restricted") and old_status == "administrator"

    if became_admin and actor is not None:
        save_registered_chat(
            chat_id=chat.id,
            owner_id=actor.id,
            chat_title=chat.title or (f"@{chat.username}" if chat.username else str(chat.id)),
            chat_type=chat.type,
        )
    elif left_or_removed:
        remove_registered_chat(chat.id)


def build_points_message(user_id: int) -> tuple:
    """واجهة ربح احترافية: رصيد النقاط بارز، ثم الشروط، ثم تنبيه واضح إن كان
    للمستخدم طلب سحب نجوم لم يُغلق بعد (تفاصيله الكاملة في «سجل السحب»)."""
    pts = get_points(user_id, force_refresh=True)
    content = [
        ("🎁", EMOJI["star"]),
        " ", get_setting("points_title") or "ربح من البوت",
        "\n\n",
        ([
            f"💎 رصيدك الحالي: {pts} نقطة",
        ], "blockquote", None),
        "\n\n",
        ([
            "📌 الشروط:\n",
            get_setting("points_conditions") or "الربح من قسم «إنشاء سحب» فقط.",
            "\n\n”",
        ], "blockquote", None),
    ]
    if has_pending_withdraw_request_any(user_id):
        content.append("\n\n")
        content.append(([
            "🕐 لديك طلب سحب نجوم قيد المعالجة حاليًا — تابع تفاصيله من «📋 سجل السحب» ”",
        ], "blockquote", None))
    content.extend(build_referral_info_block(user_id))
    return build_text_with_emojis([(content, "bold", None)])


def build_points_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """كيبورد قسم ربح مرتّب: سجل السحب أولًا (لمتابعة الطلبات)، ثم زر سحب
    النجوم الرئيسي، ثم الرجوع — بدون ازدحام."""
    rows = [
        [InlineKeyboardButton("📋 سجل السحب", callback_data="wd_history:1", style="primary")],
        [InlineKeyboardButton("⭐ سحب نجوم", callback_data="wd_stars_menu", style="success")],
        [InlineKeyboardButton(
            "🔙 رجوع", callback_data="back_main_menu",
            style="danger", **emoji_kwargs("back_section_btn"),
        )],
    ]
    return InlineKeyboardMarkup(rows)


WITHDRAW_HISTORY_PAGE_SIZE = 6


def build_stars_withdraw_menu_message(user_id: int) -> tuple:
    pts = get_points(user_id, force_refresh=True)
    return build_text_with_emojis([
        ([
            ("⭐", EMOJI["star"]), " سحب نجوم",
            "\n\n",
            ([
                f"💎 رصيدك الحالي: {pts} نقطة\n",
                "اختر قيمة النجوم التي تريد سحبها من الأزرار أدناه ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_stars_withdraw_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """زر كل قيمة سحب يعكس حالتها فورًا: ✅ متاحة، 🔒 رصيد غير كافٍ، أو 🕐 إن
    كان لدى المستخدم طلب سابق لم يُغلق بعد (يُمنع فتح طلب جديد حتى يُغلق)."""
    pts = get_points(user_id, force_refresh=True)
    blocked = has_pending_withdraw_request_any(user_id)
    rows = []
    for tier in STAR_WITHDRAW_TIERS:
        cost = get_star_cost(tier)
        if blocked:
            label, cb = f"🕐 ⭐ {tier} نجمة — طلب سابق قيد المعالجة", "withdraw_pending"
        elif cost <= 0:
            label, cb = f"⭐ {tier} نجمة (غير متاحة حاليًا)", "withdraw_locked"
        elif pts >= cost:
            label, cb = f"✅ ⭐ {tier} نجمة — {cost} نقطة", f"wd_stars_pick:{tier}"
        else:
            label, cb = f"🔒 ⭐ {tier} نجمة ({pts}/{cost} نقطة)", "withdraw_locked"
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="my_stats", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_wd_history_message(user_id: int, page: int) -> tuple:
    requests = get_user_star_withdraw_requests(user_id)
    total_pages = max(1, (len(requests) + WITHDRAW_HISTORY_PAGE_SIZE - 1) // WITHDRAW_HISTORY_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * WITHDRAW_HISTORY_PAGE_SIZE
    page_items = requests[start:start + WITHDRAW_HISTORY_PAGE_SIZE]

    content = ["📋 سجل السحب", "\n\n"]
    if not requests:
        content.append(([
            "📭 لا توجد أي طلبات سحب حتى الآن — استخدم «⭐ سحب نجوم» لإنشاء أول طلب لك ”",
        ], "blockquote", None))
    else:
        content.append(([f"📄 صفحة {page}/{total_pages} — إجمالي الطلبات: {len(requests)} ”"], "blockquote", None))
        content.append("\n\n")
        for req in page_items:
            block = [
                f"🆔 الطلب: {req.get('request_id', '')[:8]}\n",
                f"⭐ القيمة: {req.get('stars_amount', 0)} نجمة\n",
                f"💎 النقاط المخصومة: {req.get('points_amount', 0)}\n",
                f"🕒 تاريخ الطلب: {(req.get('requested_at') or '')[:16]}\n",
                f"📌 الحالة: {withdraw_status_label(req.get('status'))} ”",
            ]
            content.append((block, "blockquote", None))
            content.append("\n\n")
    return build_text_with_emojis([(content, "bold", None)])


def build_wd_history_keyboard(user_id: int, page: int) -> InlineKeyboardMarkup:
    requests = get_user_star_withdraw_requests(user_id)
    total_pages = max(1, (len(requests) + WITHDRAW_HISTORY_PAGE_SIZE - 1) // WITHDRAW_HISTORY_PAGE_SIZE)
    rows = []
    if total_pages > 1:
        rows.append(build_pager_nav_row(page, total_pages, "wd_history:{page}", "wd_history_noop"))
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="my_stats", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


async def build_points_statistics_message(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    """لوحة إحصائيات عامة احترافية: تعرض أعلى 5 قنوات عدد عمليات «روليت»
    (سحوبات + مسابقات) — الترتيب اعتمادًا على عمود roulette_count المخصَّص
    (استعلام واحد فقط بدل مسح كامل)، ولكل قناة اسمها كرابط قابل للضغط، وعدد
    السحوبات/المسابقات المستضافة فيها، وعدد المشتركين الفعلي بها (يُقرأ حيًّا
    من تيليجرام مباشرة لـ5 قنوات فقط — استدعاء API عادي لا يكلّف أي قراءة من
    حصة Firestore المجانية)، وعدد المستخدمين الجدد عبرها، ونقاطها. تُذيَّل
    بملخّص عام يشمل الروليت السريع أيضًا."""
    # كل هذه الاستدعاءات تقرأ من Firestore بشكل متزامن (blocking)؛ تُنفَّذ عبر
    # asyncio.to_thread في خيط منفصل حتى لا تُجمِّد حلقة أحداث البوت وتُعلِّق
    # باقي المستخدمين — خصوصًا أن هذه الشاشة يفتحها كل مستخدمي البوت وليس
    # المالك فقط. النتائج مخزَّنة مؤقتًا (كاش) داخل كل دالة، فحتى عند إخفاق
    # الكاش تبقى العملية معزولة في خيطها الخاص.
    rows = await asyncio.to_thread(get_top_channels_full_stats, 5)
    quick_stats = await asyncio.to_thread(get_quick_roulette_statistics)
    gw_stats = await asyncio.to_thread(get_giveaways_statistics)
    ct_stats = await asyncio.to_thread(get_contests_statistics)

    total_roulette_ops = gw_stats["total"] + ct_stats["total"] + quick_stats["total"]
    grand_new_users = await asyncio.to_thread(get_channel_new_users_counts)
    total_new_via_channels = sum(grand_new_users.values()) if grand_new_users else 0

    # عدد المشتركين الفعلي: استدعاء مباشر لتيليجرام (وليس Firestore) لكل
    # قناة من الـ5 الظاهرة فقط — لا يُخزَّن ولا يُكرَّر لبقية القنوات، فلا يزيد
    # أي استهلاك على قاعدة البيانات إطلاقًا، ويبقى الرقم حيًّا ودقيقًا دائمًا.
    member_counts = {}
    for row in rows:
        try:
            member_counts[row["chat_id"]] = await context.bot.get_chat_member_count(row["chat_id"])
        except Exception:
            member_counts[row["chat_id"]] = None

    content = [
        ("📊", EMOJI["chart"]), " لوحة الإحصائيات", "\n",
        "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈", "\n\n",
    ]

    content.append(([
        "◈ عمليات الروليت الكلي  ", ([f"{total_roulette_ops:,}"], "code", None), "\n",
        "◈ الإحالات عبر القنوات  ", ([f"{total_new_via_channels:,}"], "code", None),
    ], "blockquote", None))
    content.append("\n\n")

    if not rows:
        content.append((["لا توجد إحصائيات مسجّلة للقنوات حتى الآن ”"], "blockquote", None))
    else:
        content.append([("🏆", EMOJI["trophy_win"]), " الأعلى نشاطًا"])
        content.append("\n\n")
        for index, row in enumerate(rows):
            title = row["chat_title"] or str(row["chat_id"])
            link = ""
            try:
                link = await build_contest_channel_join_link(context, row["chat_id"])
            except Exception:
                link = ""
            name_part = (title, "link", link) if link else title
            mc = member_counts.get(row["chat_id"])
            mc_text = f"{mc:,}" if isinstance(mc, int) else "—"
            block = [
                f"#{index + 1:02d}  ", name_part, "\n",
                "◈ سحوبات ", ([f"{row['roulette_count']:,}"], "code", None), "   ",
                "◈ مشتركون ", ([mc_text], "code", None), "   ",
                "◈ نقاط ", ([f"{row['points']:,}"], "code", None),
            ]
            if index < len(rows) - 1:
                block.append("\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈")
            content.append((block, "blockquote", None))
            content.append("\n\n" if index < len(rows) - 1 else "\n")

    content.append(([
        "الترتيب اعتمادًا على عدد السحوبات/المسابقات المستضافة بكل قناة، "
        "والنقاط تُحتسب من المشاركات المؤكدة في سحوبات منع الرشق ”"
    ], "blockquote", None))
    if quick_stats["total"]:
        content.append("\n")
        content.append(([
            "◈ الروليت السريع (غير مرتبط بقناة محددة)  ",
            ([f"{quick_stats['total']:,}"], "code", None),
        ], "blockquote", None))
    return build_text_with_emojis([(content, "bold", None)])


def build_points_statistics_keyboard() -> InlineKeyboardMarkup:
    return _build_single_back_keyboard("🔙 رجوع", "back_main_menu", "danger", "back_section_btn")


def build_points_settings_message() -> tuple:
    enabled = get_setting("points_enabled") == "1"
    status = "مفعّل ✅" if enabled else "متوقف ❌"
    return build_text_with_emojis([
        ([
            ("⚙️", EMOJI["gear"]), " إعدادات النقاط",
            "\n\n",
            ([
                f"🔘 الحالة: {status}\n",
                f"💎 لكل مشارك جديد: {get_setting('points_per_user') or '1'} نقطة\n",
                f"🎯 الحد الأدنى للسحب: {get_setting('points_required') or '0'} نقطة",
            ], "blockquote", None),
            "\n\n",
            (["اختر الإعداد الذي تريد تعديله ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_points_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 لكل مستخدم", callback_data="points_edit:points_per_user", style="primary")],
        [InlineKeyboardButton("🎯 الحد الأدنى للسحب", callback_data="points_edit:points_required", style="primary")],
        [InlineKeyboardButton("📝 نصوص قسم ربح", callback_data="points_text_settings", style="primary")],
        [InlineKeyboardButton("↩️ العودة للوضع الافتراضي", callback_data="points_restore_defaults", style="success")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_points_section", style="danger")],
    ])


def build_points_text_settings_message() -> tuple:
    return build_text_with_emojis([
        ([
            ("📝", EMOJI["doc"]), " تعديل نصوص قسم ربح",
            "\n\n",
            ([
                f"🏷️ العنوان: {get_setting('points_title') or 'ربح من البوت'}\n",
                "📌 يمكنك تعديل العنوان أو جملة الشروط من الأزرار أدناه ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_points_text_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ تعديل العنوان", callback_data="points_edit:points_title", style="primary")],
        [InlineKeyboardButton("📌 تعديل الشروط", callback_data="points_edit:points_conditions", style="primary")],
        [InlineKeyboardButton("↩️ افتراضي", callback_data="points_restore_defaults", style="success")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="points_settings", style="danger")],
    ])


def build_owner_withdraw_section_message() -> tuple:
    """سجلات طلبات السحب — قسم المالك: يعرض سجل كامل بكل طلبات السحب (تحت
    المراجعة/مقبولة/مكتملة/مرفوضة، نجوم أو النظام القديم) مع اسم كل مستخدم
    ومعرّفه والقيمة وتاريخ ووقت الطلب وحالته."""
    all_requests = get_all_withdraw_requests()
    content = [
        "💳 سجلات طلبات السحب",
        "\n\n",
    ]
    if not all_requests:
        content.append((["📭 لا توجد أي طلبات سحب حتى الآن ”"], "blockquote", None))
    else:
        for req in all_requests:
            name = req.get("display_name") or str(req.get("user_id"))
            username = req.get("username")
            contact = f"@{username}" if username else "-"
            if req.get("type") == "stars":
                amount_line = f"⭐ القيمة: {req.get('stars_amount', 0)} نجمة — 💎 {req.get('points_amount', 0)} نقطة"
            else:
                amount_line = f"💎 المبلغ: {req.get('points_amount', 0)} نقطة"
            content.append(([
                f"👤 {name} (ID: {req.get('user_id')})\n",
                f"🔗 يوزر: {contact}\n",
                f"{amount_line}\n",
                f"🕒 وقت الطلب: {req.get('requested_at', '')[:16]}\n",
                f"📌 الحالة: {withdraw_status_label(req.get('status'))} ”",
            ], "blockquote", None))
            content.append("\n\n")
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_withdraw_section_keyboard() -> InlineKeyboardMarkup:
    """أزرار الإجراء تظهر فقط للطلبات المفتوحة: «قبول/رفض» لما هو تحت
    المراجعة، و«تم الإرسال» لما تم قبوله بانتظار تأكيد تحويل النجوم فعليًا."""
    open_requests = [r for r in get_all_withdraw_requests(limit=60) if r.get("status") in ("pending", "accepted")]
    open_requests.sort(key=lambda r: r.get("requested_at") or "")
    rows = []
    for req in open_requests:
        name = (req.get("display_name") or str(req.get("user_id")))[:14]
        is_stars = req.get("type") == "stars"
        if req.get("status") == "pending":
            accept_cb = f"wd_stars_accept:{req['request_id']}" if is_stars else f"wd_complete:{req['request_id']}"
            reject_cb = f"wd_stars_reject:{req['request_id']}" if is_stars else f"wd_reject:{req['request_id']}"
            rows.append([
                InlineKeyboardButton(f"✅ قبول: {name}", callback_data=accept_cb, style="success"),
                InlineKeyboardButton(f"❌ رفض: {name}", callback_data=reject_cb, style="danger"),
            ])
        elif req.get("status") == "accepted":
            rows.append([InlineKeyboardButton(
                f"📤 تم الإرسال: {name}", callback_data=f"wd_stars_complete:{req['request_id']}", style="success",
            )])
    rows.append([InlineKeyboardButton("📢 قناة استقبال السحب", callback_data="wd_channel_settings", style="primary")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_points_section", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_star_settings_message() -> tuple:
    lines = []
    for tier in STAR_WITHDRAW_TIERS:
        lines.append(f"⭐ {tier} نجمة  ←  💎 {get_star_cost(tier)} نقطة\n")
    return build_text_with_emojis([
        ([
            ("⭐", EMOJI["star"]), " سعر نجوم — إدارة المالك",
            "\n\n",
            (lines + ["اضغط على أي قيمة أدناه لتعديل عدد النقاط المطلوبة لها مباشرة ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_star_settings_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"⭐ {tier} — 💎{get_star_cost(tier)}", callback_data=f"star_edit:{tier}", style="primary")
        for tier in STAR_WITHDRAW_TIERS
    ]
    rows = pair_buttons(buttons)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_points_section", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_withdraw_channel_settings_message() -> tuple:
    channel = get_withdraw_channel()
    if channel:
        label = f"@{channel['username']}" if channel.get("username") else (channel.get("title") or channel["chat_id"])
        status_line = f"✅ القناة الحالية: {label}"
    else:
        status_line = "❌ لم يتم تحديد قناة استقبال بعد"
    return build_text_with_emojis([
        ([
            "📢 قناة استقبال طلبات السحب",
            "\n\n",
            ([
                f"{status_line}\n\n",
                "عند تحديد قناة، تُرسَل تفاصيل كل طلب سحب جديد إليها تلقائيًا "
                "مع أزرار «قبول» و«رفض» للتحكم بالطلب مباشرة منها ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_withdraw_channel_settings_keyboard() -> InlineKeyboardMarkup:
    channel = get_withdraw_channel()
    rows = []
    if channel:
        rows.append([InlineKeyboardButton("🔄 تغيير القناة", callback_data="wd_channel_set", style="primary")])
        rows.append([InlineKeyboardButton("🗑️ إلغاء القناة الحالية", callback_data="wd_channel_clear", style="danger")])
    else:
        rows.append([InlineKeyboardButton("➕ تعيين القناة", callback_data="wd_channel_set", style="success")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_withdraw_section", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_new_user_notify_section_message() -> tuple:
    enabled = is_new_user_notify_enabled()
    channel = get_new_user_notify_channel()
    status_line = "🟢 مفعّلة" if enabled else "🔴 غير مفعّلة"
    if channel:
        label = f"@{channel['username']}" if channel.get("username") else (channel.get("title") or channel["chat_id"])
        channel_line = f"✅ القناة الحالية: {label}"
    else:
        channel_line = "❌ لم يتم تحديد قناة بعد"
    return build_text_with_emojis([
        ([
            "🔔 إشعارات دخول المستخدمين",
            "\n\n",
            ([
                f"الحالة: {status_line}\n",
                f"{channel_line}\n\n",
                "عند التفعيل وتحديد قناة، يُرسَل إشعار تلقائي بكل مستخدم جديد "
                "يدخل البوت لأول مرة، يحتوي على اسمه ويوزره ومعرّفه ووقت "
                "دخوله ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_new_user_notify_section_keyboard() -> InlineKeyboardMarkup:
    enabled = is_new_user_notify_enabled()
    channel = get_new_user_notify_channel()
    toggle_text = "🔴 إيقاف الإشعارات" if enabled else "🟢 تفعيل الإشعارات"
    toggle_style = "danger" if enabled else "success"
    rows = [[InlineKeyboardButton(toggle_text, callback_data="owner_newuser_toggle", style=toggle_style)]]
    if channel:
        rows.append([InlineKeyboardButton("🔄 تغيير القناة", callback_data="owner_newuser_channel_set", style="primary")])
        rows.append([InlineKeyboardButton("🗑️ إلغاء القناة الحالية", callback_data="owner_newuser_channel_clear", style="danger")])
    else:
        rows.append([InlineKeyboardButton("➕ تحديد القناة", callback_data="owner_newuser_channel_set", style="success")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                       **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "👑 قسم المالك",
            "\n\n",
            (["اختر القسم الذي تريد إدارته من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_section_keyboard() -> InlineKeyboardMarkup:
    menu_buttons = [
        InlineKeyboardButton("💰 قسم ربح", callback_data="owner_points_section", style="primary"),
        InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="owner_sub_section", style="primary"),
        InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="owner_users_section", style="primary"),
        InlineKeyboardButton("🎁 السحوبات", callback_data="owner_draws_section", style="primary"),
        InlineKeyboardButton("🏁 المسابقات", callback_data="owner_contests_section", style="primary"),
        InlineKeyboardButton("⚡ السحب السريع", callback_data="owner_quick_roulette_section", style="primary"),
        InlineKeyboardButton("📣 الإذاعة", callback_data="owner_broadcast_section", style="primary"),
        InlineKeyboardButton("👨‍💻 إدارة المشرفين", callback_data="owner_admins_section", style="primary"),
        InlineKeyboardButton("🔗 إدارة روابط الدعوة", callback_data="owner_referrals_section", style="primary"),
        InlineKeyboardButton("📊 إحصائيات البوت", callback_data="owner_stats_section", style="primary"),
        InlineKeyboardButton("📜 سجل العمليات", callback_data="owner_logs:1", style="primary"),
        InlineKeyboardButton("🛠️ صيانة البوت", callback_data="owner_maintenance_section", style="primary"),
        InlineKeyboardButton("🔔 إشعارات دخول المستخدمين", callback_data="owner_new_user_notify_section", style="primary"),
    ]
    rows = pair_buttons(menu_buttons)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main_menu", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_logs_section_message(logs: list, page: int) -> tuple:
    if not logs:
        content = [
            "📜 سجل العمليات",
            "\n\n",
            (["لا توجد أي عمليات إدارية مسجَّلة حتى الآن ”"], "blockquote", None),
        ]
        return build_text_with_emojis([(content, "bold", None)])

    total_pages = max(1, (len(logs) + ADMIN_LOG_PAGE_SIZE - 1) // ADMIN_LOG_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * ADMIN_LOG_PAGE_SIZE
    page_items = logs[start:start + ADMIN_LOG_PAGE_SIZE]

    content = [f"📜 سجل العمليات ({len(logs)})", "\n\n"]
    for entry in page_items:
        label = ADMIN_LOG_LABELS.get(entry.get("action"), entry.get("action") or "—")
        actor = entry.get("actor_label") or entry.get("actor_id")
        when = _format_ts(entry.get("created_at"))
        lines = [f"{label}\n", f"👤 بواسطة: {actor}\n", f"🕒 {when}"]
        details = entry.get("details")
        if details:
            lines.append(f"\n📝 {details}")
        content.append((lines, "blockquote", None))
        content.append("\n\n")
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_logs_section_keyboard(logs: list, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(logs) + ADMIN_LOG_PAGE_SIZE - 1) // ADMIN_LOG_PAGE_SIZE)
    page = max(1, min(page, total_pages))

    rows = []
    if total_pages > 1:
        rows.append(build_pager_nav_row(page, total_pages, "owner_logs:{page}", "owner_logs_noop"))

    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_maintenance_section_message() -> tuple:
    maintenance_on = is_maintenance_mode()
    status_line = "🔴 مفعّل — البوت متوقف عن أي مستخدم عادي حاليًا" if maintenance_on else "🟢 غير مفعّل — البوت يعمل بشكل طبيعي"
    speed = get_last_speed_check()
    if speed:
        speed_line = f"{speed['label']} ({speed['elapsed_ms']} مللي ثانية) — آخر فحص: {_format_ts(speed.get('checked_at'))}"
    else:
        speed_line = "لم يتم فحص السرعة بعد"
    return build_text_with_emojis([
        ([
            "🛠️ صيانة البوت",
            "\n\n",
            ([
                f"⚙️ وضع الصيانة: {status_line}\n",
                f"📶 آخر قياس سرعة: {speed_line}",
            ], "blockquote", None),
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_maintenance_section_keyboard() -> InlineKeyboardMarkup:
    maintenance_on = is_maintenance_mode()
    toggle_text = "🟢 إيقاف وضع الصيانة" if maintenance_on else "🔴 تفعيل وضع الصيانة"
    toggle_style = "success" if maintenance_on else "danger"
    rows = [[InlineKeyboardButton(toggle_text, callback_data="owner_maintenance_toggle", style=toggle_style)]]
    rows += pair_buttons([
        InlineKeyboardButton("📶 فحص سرعة الاستجابة", callback_data="owner_maintenance_speedtest", style="primary"),
        InlineKeyboardButton("📊 عرض حالة البوت", callback_data="owner_maintenance_status", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🧪 حذف مستخدم اختباري", callback_data="owner_reset_test_user", style="danger")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_maintenance_speedtest_message(elapsed_ms: float, label: str) -> tuple:
    return build_text_with_emojis([
        ([
            "📶 نتيجة فحص سرعة الاستجابة",
            "\n\n",
            ([
                f"⏱️ الزمن: {int(elapsed_ms)} مللي ثانية\n",
                f"📊 التصنيف: {label}",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_maintenance_status_message() -> tuple:
    maintenance_on = is_maintenance_mode()
    status_line = "🔴 مفعّل" if maintenance_on else "🟢 غير مفعّل"
    speed = get_last_speed_check()
    speed_line = f"{speed['label']} ({speed['elapsed_ms']} مللي ثانية)" if speed else "لم يُفحص بعد"
    uptime = format_bot_uptime()
    return build_text_with_emojis([
        ([
            "📊 حالة البوت",
            "\n\n",
            ([
                f"🛠️ وضع الصيانة: {status_line}\n",
                f"📶 سرعة الاستجابة: {speed_line}\n",
                f"⏳ مدة التشغيل منذ آخر إقلاع: {uptime}",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_points_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "💰 قسم ربح — إدارة المالك",
            "\n\n",
            (["من هنا يمكنك التحكم بكل إعدادات قسم الربح (النقاط، المكافآت، النصوص) ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_points_section_keyboard() -> InlineKeyboardMarkup:
    points_on = get_setting("points_enabled") == "1"
    rows = pair_buttons([
        InlineKeyboardButton("⚙️ إعدادات", callback_data="points_settings",
                             style="primary", **emoji_kwargs("gear")),
        InlineKeyboardButton("💎 إدارة نقاط المستخدمين", callback_data="points_manage_section", style="primary"),
        InlineKeyboardButton("⭐ سعر نجوم", callback_data="star_settings", style="primary"),
        InlineKeyboardButton("💳 سجلات طلبات السحب", callback_data="owner_withdraw_section", style="primary"),
        InlineKeyboardButton("📢 قناة استقبال السحب", callback_data="wd_channel_settings", style="primary"),
    ])
    rows.append([InlineKeyboardButton(
        "⛔ إيقاف ربح" if points_on else "✅ تفعيل ربح",
        callback_data="points_toggle", style="danger" if points_on else "success",
    )])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# 💎 واجهات التحكم اليدوي بنقاط المستخدمين (قسم ربح — قسم المالك)
# ---------------------------------------------------------------------------

def build_points_manage_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "💎 إدارة نقاط المستخدمين",
            "\n\n",
            (["تحكّم كامل في رصيد أي مستخدم: إضافة نقاط، خصم نقاط، أو تصفّح "
              "جميع المستخدمين مع أرصدتهم الحالية ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_points_manage_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("➕ إضافة نقاط لمستخدم", callback_data="points_manage_add_lookup", style="success"),
        InlineKeyboardButton("➖ خصم نقاط من مستخدم", callback_data="points_manage_deduct_lookup", style="danger"),
        InlineKeyboardButton("📋 تصفح جميع المستخدمين", callback_data="points_browse:list:1", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_points_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


USERS_BROWSE_PAGE_SIZE = 20


def _display_name(row: dict) -> str:
    """اسم معروض موحّد لأي مستخدم عبر كل أقسام البوت (تصفّح النقاط،
    المشرفين، أصحاب روابط الإحالة، ...) — دالة واحدة مشتركة بدل تكرارها
    باسم مختلف في كل قسم."""
    first_name = row.get("first_name")
    username = row.get("username")
    if first_name:
        return first_name
    if username:
        return f"@{username}"
    return str(row.get("user_id"))


def build_pager_nav_row(page: int, total_pages: int, page_callback: str, noop_callback: str) -> list:
    """صف تنقّل موحّد «◀️ السابق / صفحة X من Y / التالي ▶️» يُستخدم في كل
    قوائم الصفحات بالبوت (تصفّح المستخدمين، سجل العمليات، القنوات، أخطاء
    الصيانة، المشرفين، أصحاب روابط الإحالة، السحوبات، السحب السريع، ...)
    بدل تكرار نفس منطق التنقّل في كل قسم على حدة.

    page_callback: نص callback_data يحتوي '{page}' ليُستبدل برقم الصفحة
    الجديد عند الضغط على السابق/التالي، مثل 'owner_logs:{page}' أو
    'owner_admins_list:view:{page}' (يمكن تضمين أي متغيّرات إضافية داخل
    النص طالما بقي '{page}' هو الجزء المتغيّر الوحيد).
    noop_callback: callback_data لزر رقم الصفحة نفسه (بلا أي إجراء)."""
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=page_callback.format(page=page - 1)))
    nav_row.append(InlineKeyboardButton(f"صفحة {page}/{total_pages}", callback_data=noop_callback))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=page_callback.format(page=page + 1)))
    return nav_row


def pair_buttons(buttons: list) -> list:
    """يحوّل قائمة أزرار بعرض السطر الكامل (زر واحد لكل سطر) إلى صفوف من
    زرّين متجاورين في مستطيل واحد صغير — يُستخدم لتصغير القوائم الطويلة
    (قوائم أقسام المالك، تصفّح المستخدمين، ...) بدل زر عريض واحد لكل سطر.
    إن كان عدد الأزرار فرديًا يبقى آخر زر بمفرده في سطره."""
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def build_users_points_browse_message(rows: list, page: int,
                                       title: str = "📋 تصفح المستخدمين") -> tuple:
    """رسالة عامة لقائمة تصفّح المستخدمين (20 لكل صفحة) — قابلة لإعادة
    الاستخدام من أي قسم يحتاج عرض المستخدمين مع نقاطهم."""
    total_pages = max(1, (len(rows) + USERS_BROWSE_PAGE_SIZE - 1) // USERS_BROWSE_PAGE_SIZE)
    content = [title, "\n\n"]
    if not rows:
        content.append((["📭 لا يوجد أي مستخدم مسجّل حتى الآن ”"], "blockquote", None))
    else:
        content.append(([
            f"👥 إجمالي المستخدمين: {len(rows)} — صفحة {page}/{total_pages}\n",
            "💎 = عدد النقاط  •  📥 = عدد الإحالات\n",
            "اضغط على أي مستخدم لعرض بياناته وتعديل نقاطه ”",
        ], "blockquote", None))
    return build_text_with_emojis([(content, "bold", None)])


def build_users_points_browse_keyboard(rows: list, page: int, callback_prefix: str,
                                        back_callback: str) -> InlineKeyboardMarkup:
    """كيبورد عام لتصفّح المستخدمين (20 لكل صفحة) مع تنقّل أمام/خلف — قابل
    لإعادة الاستخدام من أي قسم عبر تمرير callback_prefix مختلف لكل قسم
    (مثال: 'points_browse') وback_callback الخاص بزر الرجوع لذلك القسم.
    صيغة الأزرار الناتجة:
      - {prefix}:list:<page>       تنقّل بين الصفحات
      - {prefix}:pick:<uid>:<page> اختيار مستخدم من الصفحة الحالية
      - {prefix}:noop              زر رقم الصفحة (بلا أي إجراء)"""
    total_pages = max(1, (len(rows) + USERS_BROWSE_PAGE_SIZE - 1) // USERS_BROWSE_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * USERS_BROWSE_PAGE_SIZE
    page_items = rows[start:start + USERS_BROWSE_PAGE_SIZE]

    kb_rows = []
    user_buttons = []
    for row in page_items:
        uid = row.get("user_id")
        name = _display_name(row)
        if len(name) > 10:
            name = name[:10] + "…"
        pts = row.get("points", 0)
        refs = row.get("referred_count", 0)
        user_buttons.append(InlineKeyboardButton(
            f"{name} 💎{pts} 📥{refs}",
            callback_data=f"{callback_prefix}:pick:{uid}:{page}",
        ))
    kb_rows.extend(pair_buttons(user_buttons))

    if total_pages > 1:
        kb_rows.append(build_pager_nav_row(
            page, total_pages, f"{callback_prefix}:list:{{page}}", f"{callback_prefix}:noop",
        ))

    kb_rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_callback, style="danger",
                                         **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(kb_rows)


def build_user_points_profile_message(row: dict) -> tuple:
    name = _display_name(row)
    content = [
        "👤 رصيد نقاط المستخدم",
        "\n\n",
        ([
            f"🆔 المعرف: {row.get('user_id')}\n",
            f"👤 الاسم: {name}\n",
            f"🔗 اليوزر: @{row['username']}\n" if row.get("username") else "🔗 اليوزر: لا يوجد\n",
            f"💎 الرصيد الحالي: {row.get('points', 0)} نقطة\n",
            f"📥 عدد الإحالات: {row.get('referred_count', 0)}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_user_points_profile_keyboard(user_id: int, back_page: int = 1,
                                        browse_prefix: str = "points_browse") -> InlineKeyboardMarkup:
    """كيبورد بروفايل نقاط مستخدم واحد. browse_prefix يحدّد إلى أي قائمة
    تصفّح يعود زر «رجوع للقائمة» (نفس البادئة التي فُتح منها هذا البروفايل)،
    ليعمل البروفايل بشكل صحيح بغضّ النظر عن القسم الذي استُدعي منه."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ إضافة نقاط", callback_data=f"points_manual_add:{user_id}:{back_page}:{browse_prefix}",
                style="success"),
            InlineKeyboardButton(
                "➖ خصم نقاط", callback_data=f"points_manual_deduct:{user_id}:{back_page}:{browse_prefix}",
                style="danger"),
        ],
        [InlineKeyboardButton(
            "🔙 رجوع للقائمة", callback_data=f"{browse_prefix}:list:{back_page}", style="danger",
            **emoji_kwargs("back_section_btn"))],
    ])


REQUIRED_CHANNELS_PAGE_SIZE = 8
BANNED_USERS_PAGE_SIZE = 8


def _format_ts(iso_str: str) -> str:
    """ينسّق نص تاريخ/وقت ISO المخزَّن في Firestore لعرض بشري مبسّط."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, TypeError):
        return str(iso_str)


def build_owner_sub_section_message() -> tuple:
    channels = get_required_channels()
    enabled_count = len([c for c in channels if c.get("enabled", True)])
    return build_text_with_emojis([
        ([
            "📢 الاشتراك الإجباري — إدارة المالك",
            "\n\n",
            ([
                f"📡 عدد القنوات: {len(channels)}\n",
                f"🟢 المفعّلة حاليًا: {enabled_count}",
            ], "blockquote", None),
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_sub_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("➕ إضافة قناة", callback_data="owner_sub_add", style="success"),
        InlineKeyboardButton("📋 عرض جميع القنوات", callback_data="owner_sub_list:1", style="primary"),
        InlineKeyboardButton("🔢 ترتيب القنوات", callback_data="owner_sub_reorder", style="primary"),
        InlineKeyboardButton("📊 إحصائيات جميع قنوات الاشتراك", callback_data="owner_sub_stats_all", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_sub_list_message(channels: list) -> tuple:
    if not channels:
        content = [
            "📋 عرض جميع القنوات",
            "\n\n",
            (["لا توجد أي قناة اشتراك إجباري حاليًا، أضف قناة أولاً ”"], "blockquote", None),
        ]
    else:
        content = [
            f"📋 عرض جميع القنوات ({len(channels)})",
            "\n\n",
            (["اضغط على أي قناة لإدارتها ”"], "blockquote", None),
        ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_list_keyboard(channels: list, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(channels) + REQUIRED_CHANNELS_PAGE_SIZE - 1) // REQUIRED_CHANNELS_PAGE_SIZE)
    start = (page - 1) * REQUIRED_CHANNELS_PAGE_SIZE
    page_items = channels[start:start + REQUIRED_CHANNELS_PAGE_SIZE]

    item_buttons = []
    for ch in page_items:
        dot = "🟢" if ch.get("enabled", True) else "🔴"
        label = f"{dot} @{ch.get('username', '')}"
        if ch.get("target_count"):
            label += f" 🎯{ch.get('target_count')}"
        item_buttons.append(InlineKeyboardButton(
            label, callback_data=f"owner_sub_channel:{ch['channel_id']}", style="primary",
        ))
    rows = pair_buttons(item_buttons)

    if total_pages > 1:
        rows.append(build_pager_nav_row(page, total_pages, "owner_sub_list:{page}", "owner_sub_noop"))

    rows.append([InlineKeyboardButton("➕ إضافة قناة", callback_data="owner_sub_add", style="success")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_sub_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


async def build_owner_sub_channel_message(context: ContextTypes.DEFAULT_TYPE, channel: dict) -> tuple:
    username = channel.get("username", "")
    url = channel.get("url") or f"https://t.me/{username}"
    target = channel.get("target_count")
    target_line = f"{target} عضو" if target else "غير محدد"
    autodel_line = (
        "🔄 حذف تلقائي عند الوصول للهدف" if channel.get("auto_delete_on_target")
        else "♾️ إبقاء دائم بدون حذف"
    )
    status_line = "🟢 مفعّلة" if channel.get("enabled", True) else "🔴 معطّلة"
    try:
        count_line = str(await context.bot.get_chat_member_count(chat_id=f"@{username}"))
    except Exception:
        count_line = "تعذّر الجلب"

    display_name_line = channel.get("button_text") or "غير محدد (يظهر اليوزر الخام @{})".format(username)

    content = [
        f"📢 إدارة القناة @{username}",
        "\n\n",
        ([
            f"🪪 الاسم المعروض في الزر: {display_name_line}\n",
            f"🔗 الرابط: {url}\n",
            f"👥 عدد الأعضاء الحالي: {count_line}\n",
            f"🎯 الهدف: {target_line}\n",
            f"⚙️ عند الوصول للهدف: {autodel_line}\n",
            f"📌 الحالة: {status_line}\n",
            f"🔢 الترتيب: {channel.get('order', 0) + 1}",
        ], "blockquote", None),
        "\n\n",
        (["اختر ما تريد تعديله من الأزرار أدناه ”"], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_channel_keyboard(channel: dict) -> InlineKeyboardMarkup:
    cid = channel["channel_id"]
    enabled = channel.get("enabled", True)
    autodel = bool(channel.get("auto_delete_on_target"))
    has_target = bool(channel.get("target_count"))
    autodel_label = (
        "⚙️ عند الهدف: 🔄 حذف تلقائي" if autodel else "⚙️ عند الهدف: ♾️ إبقاء دائم"
    )
    rows = [
        [InlineKeyboardButton("🪪 تعديل الاسم المعروض في الزر", callback_data=f"owner_sub_edit_button_text:{cid}", style="primary")],
        [InlineKeyboardButton("✏️ تعديل يوزر القناة", callback_data=f"owner_sub_edit_username:{cid}", style="primary")],
        [InlineKeyboardButton("🔗 تعديل رابط القناة", callback_data=f"owner_sub_edit_link:{cid}", style="primary")],
        [InlineKeyboardButton("🎯 تحديد عدد الأعضاء المستهدف", callback_data=f"owner_sub_edit_target:{cid}", style="primary")],
        [InlineKeyboardButton(autodel_label, callback_data=f"owner_sub_toggle_autodel:{cid}", style="primary")],
    ]
    if has_target and autodel:
        # يظهر فقط عندما يكون هناك هدف فعلي مع حذف تلقائي مفعّل — يفحص هذه
        # القناة تحديدًا فورًا (بنفس منطق المهمة الدورية بالضبط عبر
        # _check_and_maybe_delete_channel_target) بدل انتظار دورة الفحص
        # القادمة (كل دقيقتين)، وأهم من ذلك: يُظهر سبب الفشل مباشرة كتنبيه
        # منبثق إن كان البوت غير مضاف كمشرف في القناة — وهو السبب الأشيع
        # لعدم الحذف رغم بلوغ الهدف.
        rows.append([InlineKeyboardButton(
            "🎯 تحقق من الهدف الآن", callback_data=f"owner_sub_check_target_now:{cid}", style="success",
        )])
    rows += [
        [InlineKeyboardButton(
            "🔘 الحالة: مفعّلة 🟢" if enabled else "🔘 الحالة: معطّلة 🔴",
            callback_data=f"owner_sub_toggle_enabled:{cid}", style="success" if enabled else "danger",
        )],
        [InlineKeyboardButton("📊 إحصائيات هذه القناة", callback_data=f"owner_sub_channel_stats:{cid}", style="primary")],
        [InlineKeyboardButton("🗑️ حذف القناة", callback_data=f"owner_sub_delete:{cid}", style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_sub_list:1", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ]
    return InlineKeyboardMarkup(rows)


def build_owner_sub_delete_confirm_message(channel: dict) -> tuple:
    content = [
        "🗑️ تأكيد حذف القناة",
        "\n\n",
        ([f"هل أنت متأكد من حذف القناة @{channel.get('username', '')} من قائمة الاشتراك الإجباري؟ ”"],
         "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_delete_confirm_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=f"owner_sub_channel:{channel_id}", style="primary"),
            InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"owner_sub_delete_confirm:{channel_id}", style="danger"),
        ],
    ])


def build_owner_sub_reorder_message(channels: list) -> tuple:
    if not channels:
        content = ["🔢 ترتيب القنوات", "\n\n", (["لا توجد أي قناة لترتيبها ”"], "blockquote", None)]
    else:
        lines = [f"{i + 1}. @{ch.get('username', '')}" for i, ch in enumerate(channels)]
        content = [
            "🔢 ترتيب القنوات",
            "\n\n",
            (["\n".join(lines)], "blockquote", None),
            "\n\n",
            (["استخدم ⬆️/⬇️ لتغيير ترتيب أي قناة ”"], "blockquote", None),
        ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_reorder_keyboard(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for i, ch in enumerate(channels):
        cid = ch["channel_id"]
        rows.append([InlineKeyboardButton(f"{i + 1}. @{ch.get('username', '')}", callback_data="owner_sub_noop")])
        nav = []
        if i > 0:
            nav.append(InlineKeyboardButton("⬆️", callback_data=f"owner_sub_move_up:{cid}"))
        if i < len(channels) - 1:
            nav.append(InlineKeyboardButton("⬇️", callback_data=f"owner_sub_move_down:{cid}"))
        if nav:
            rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_sub_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


async def build_owner_sub_stats_all_message(context: ContextTypes.DEFAULT_TYPE) -> tuple:
    channels = get_required_channels()
    lines = []
    total_members = 0
    for ch in channels:
        username = ch.get("username", "")
        try:
            count = await context.bot.get_chat_member_count(chat_id=f"@{username}")
            total_members += count
            count_str = str(count)
        except Exception:
            count_str = "—"
        dot = "🟢" if ch.get("enabled", True) else "🔴"
        target = ch.get("target_count")
        target_part = f" / هدف {target}" if target else ""
        lines.append(f"{dot} @{username}: {count_str} عضو{target_part}")

    content = [
        "📊 إحصائيات جميع قنوات الاشتراك",
        "\n\n",
        ([
            f"📡 إجمالي القنوات: {len(channels)}\n",
            f"👥 إجمالي الأعضاء (تقريبي، بدون احتساب التكرار بين القنوات): {total_members}",
        ], "blockquote", None),
    ]
    if lines:
        content += ["\n\n", (["\n".join(lines)], "blockquote", None)]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_stats_all_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_sub_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


async def build_owner_sub_channel_stats_message(context: ContextTypes.DEFAULT_TYPE, channel: dict) -> tuple:
    username = channel.get("username", "")
    count = None
    try:
        count = await context.bot.get_chat_member_count(chat_id=f"@{username}")
    except Exception:
        pass
    target = channel.get("target_count")
    lines = [f"👥 عدد الأعضاء الحالي: {count if count is not None else 'تعذّر الجلب'}"]
    if target:
        lines.append(f"🎯 الهدف: {target} عضو")
        if count is not None:
            pct = min(100, round((count / target) * 100))
            lines.append(f"📈 نسبة الإنجاز: {pct}٪")
    lines.append(f"📅 أُضيفت في: {_format_ts(channel.get('created_at'))}")

    content = [
        f"📊 إحصائيات القناة @{username}",
        "\n\n",
        (["\n".join(lines)], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_sub_channel_stats_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_sub_channel:{channel_id}", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 👥 إدارة المستخدمين
# ---------------------------------------------------------------------------

def build_owner_users_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "👥 إدارة المستخدمين",
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_users_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("🔎 البحث عن مستخدم", callback_data="owner_users_search", style="primary"),
        InlineKeyboardButton("👤 عرض بيانات مستخدم", callback_data="owner_users_view", style="primary"),
        InlineKeyboardButton("🚫 حظر مستخدم", callback_data="owner_users_ban", style="danger"),
        InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="owner_users_unban", style="success"),
        InlineKeyboardButton("📋 قائمة المحظورين", callback_data="owner_users_banned:1", style="primary"),
        InlineKeyboardButton("📊 إحصائيات المستخدمين", callback_data="owner_users_stats", style="primary"),
        InlineKeyboardButton(
            "📋 تصفح المستخدمين (النقاط والإحالات)", callback_data="users_browse:list:1", style="primary",
        ),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_user_profile_message(row: dict) -> tuple:
    user_id = row.get("user_id")
    username = row.get("username")
    full_name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip() or "—"
    username_line = f"@{username}" if username else "لا يوجد"
    banned = bool(row.get("banned"))
    status_line = "🚫 محظور" if banned else "✅ غير محظور"

    content = [
        "👤 بيانات المستخدم",
        "\n\n",
        ([
            f"🆔 المعرف: {user_id}\n",
            f"📛 الاسم: {full_name}\n",
            f"🔗 اليوزر: {username_line}\n",
            f"📌 الحالة: {status_line}\n",
            f"🕐 أول ظهور: {_format_ts(row.get('first_seen_at'))}\n",
            f"🕓 آخر ظهور: {_format_ts(row.get('last_seen_at'))}",
        ], "blockquote", None),
    ]
    if banned:
        content += ["\n\n", ([f"📝 سبب الحظر: {row.get('ban_reason') or 'بدون سبب محدد'}"], "blockquote", None)]
    return build_text_with_emojis([(content, "bold", None)])


def build_user_profile_keyboard(row: dict) -> InlineKeyboardMarkup:
    user_id = row.get("user_id")
    banned = bool(row.get("banned"))
    rows = []
    if banned:
        rows.append([InlineKeyboardButton(
            "✅ فك الحظر", callback_data=f"owner_users_profile_unban:{user_id}", style="success",
        )])
    else:
        rows.append([InlineKeyboardButton(
            "🚫 حظر هذا المستخدم", callback_data=f"owner_users_profile_ban:{user_id}", style="danger",
        )])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_users_banned_list_message(banned_users: list) -> tuple:
    if not banned_users:
        content = [
            "📋 قائمة المحظورين",
            "\n\n",
            (["لا يوجد أي مستخدم محظور حاليًا ”"], "blockquote", None),
        ]
    else:
        content = [
            f"📋 قائمة المحظورين ({len(banned_users)})",
            "\n\n",
            (["اضغط على أي مستخدم لعرض بياناته أو فك حظره ”"], "blockquote", None),
        ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_users_banned_list_keyboard(banned_users: list, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(banned_users) + BANNED_USERS_PAGE_SIZE - 1) // BANNED_USERS_PAGE_SIZE)
    start = (page - 1) * BANNED_USERS_PAGE_SIZE
    page_items = banned_users[start:start + BANNED_USERS_PAGE_SIZE]

    item_buttons = []
    for row in page_items:
        uid = row.get("user_id")
        name = row.get("first_name") or (f"@{row['username']}" if row.get("username") else str(uid))
        item_buttons.append(InlineKeyboardButton(
            f"🚫 {name}", callback_data=f"owner_users_profile:{uid}", style="primary",
        ))
    rows = pair_buttons(item_buttons)

    if total_pages > 1:
        rows.append(build_pager_nav_row(page, total_pages, "owner_users_banned:{page}", "owner_users_noop"))

    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_owner_users_stats_message(stats: dict) -> tuple:
    content = [
        "📊 إحصائيات المستخدمين",
        "\n\n",
        ([
            f"👥 إجمالي المستخدمين: {stats['total']}\n",
            f"🚫 عدد المحظورين: {stats['banned']}\n",
            f"🆕 جدد اليوم: {stats['new_today']}\n",
            f"📈 جدد آخر 7 أيام: {stats['new_week']}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_users_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 👨‍💻 إدارة المشرفين (قسم المالك) — إضافة/حذف مشرفين وتحديد صلاحيات كل واحد
# منهم بدقة (إضافة مشرفين، حذف سحوبات، حذف سحب سريع، إدارة مستخدمين، ...).
# ---------------------------------------------------------------------------

def build_owner_admins_section_message() -> tuple:
    count = len(list_moderators())
    return build_text_with_emojis([
        ([
            "👨‍💻 إدارة المشرفين — إدارة المالك",
            "\n\n",
            ([f"👥 عدد المشرفين الحاليين: {count}"], "blockquote", None),
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_admins_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("➕ إضافة مشرف", callback_data="owner_admins_add", style="success"),
        InlineKeyboardButton("📋 عرض المشرفين", callback_data="owner_admins_list:view:1", style="primary"),
        InlineKeyboardButton("🔐 صلاحيات مشرف", callback_data="owner_admins_list:perms:1", style="primary"),
        InlineKeyboardButton("🗑️ حذف مشرف", callback_data="owner_admins_list:remove:1", style="danger"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


ADMINS_PAGE_SIZE = 8


def build_owner_admins_list_message(mods: list, mode: str) -> tuple:
    title = {
        "view": "📋 عرض المشرفين",
        "perms": "🔐 اختر مشرفًا لتعديل صلاحياته",
        "remove": "🗑️ اختر مشرفًا لحذفه",
    }.get(mode, "📋 عرض المشرفين")
    if not mods:
        content = [title, "\n\n", (["لا يوجد أي مشرف مسجّل حاليًا ”"], "blockquote", None)]
    else:
        content = [f"{title} ({len(mods)})", "\n\n", (["اضغط على أي مشرف من القائمة ”"], "blockquote", None)]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_admins_list_keyboard(mods: list, mode: str, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(mods) + ADMINS_PAGE_SIZE - 1) // ADMINS_PAGE_SIZE)
    start = (page - 1) * ADMINS_PAGE_SIZE
    page_items = mods[start:start + ADMINS_PAGE_SIZE]

    item_buttons = []
    for row in page_items:
        uid = row.get("user_id")
        name = _display_name(row)
        item_buttons.append(InlineKeyboardButton(f"👤 {name}", callback_data=f"owner_admins_pick:{mode}:{uid}"))
    rows = pair_buttons(item_buttons)

    if total_pages > 1:
        rows.append(build_pager_nav_row(
            page, total_pages, f"owner_admins_list:{mode}:{{page}}", "owner_admins_noop",
        ))

    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_admins_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_moderator_profile_message(row: dict) -> tuple:
    perms = row.get("permissions", {})
    enabled = [label for key, label in MODERATOR_PERMISSIONS.items() if perms.get(key)]
    perms_line = "، ".join(enabled) if enabled else "لا يوجد أي صلاحية مفعّلة"
    content = [
        "👤 بيانات المشرف",
        "\n\n",
        ([
            f"🆔 المعرف: {row.get('user_id')}\n",
            f"🔗 اليوزر: @{row['username']}\n" if row.get("username") else "🔗 اليوزر: لا يوجد\n",
            f"🕐 تاريخ الإضافة: {_format_ts(row.get('added_at'))}\n",
            f"🔐 الصلاحيات المفعّلة: {perms_line}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_moderator_profile_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 تعديل الصلاحيات", callback_data=f"owner_admins_pick:perms:{user_id}",
                               style="primary")],
        [InlineKeyboardButton("🗑️ حذف هذا المشرف", callback_data=f"owner_admins_pick:remove:{user_id}",
                               style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_admins_list:view:1", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_moderator_perms_message(row: dict) -> tuple:
    name = _display_name(row)
    content = [
        "🔐 تعديل صلاحيات المشرف",
        "\n\n",
        ([f"👤 المشرف: {name}\n", "اضغط على أي صلاحية لتفعيلها أو تعطيلها ”"], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_moderator_perms_keyboard(row: dict) -> InlineKeyboardMarkup:
    perms = row.get("permissions", {})
    user_id = row.get("user_id")
    rows = []
    for key, label in MODERATOR_PERMISSIONS.items():
        state_icon = "✅" if perms.get(key) else "❌"
        rows.append([InlineKeyboardButton(
            f"{state_icon} {label}", callback_data=f"owner_admins_toggle:{user_id}:{key}",
        )])
    rows.append([InlineKeyboardButton(
        "🔙 رجوع", callback_data=f"owner_admins_pick:view:{user_id}", style="danger",
        **emoji_kwargs("back_section_btn"),
    )])
    return InlineKeyboardMarkup(rows)


def build_moderator_delete_confirm_message(row: dict) -> tuple:
    name = _display_name(row)
    content = [
        "🗑️ تأكيد حذف مشرف",
        "\n\n",
        ([f"هل أنت متأكد أنك تريد حذف {name} من قائمة المشرفين؟ ”"], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_moderator_delete_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"owner_admins_remove_do:{user_id}",
                               style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_admins_pick:view:{user_id}", style="primary",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 🔗 واجهات إدارة روابط الدعوة (قسم المالك)
# ---------------------------------------------------------------------------

def build_owner_referrals_section_message() -> tuple:
    stats = get_referrals_overview_stats()
    return build_text_with_emojis([
        ([
            "🔗 إدارة روابط الدعوة — إدارة المالك",
            "\n\n",
            ([
                f"👥 عدد أصحاب الروابط: {stats['total_referrers']}\n",
                f"🟢 الروابط النشطة: {stats['active_referrers']}\n",
                f"📥 إجمالي القادمين عبر الإحالة: {stats['total_referred']}\n",
                f"💎 إجمالي نقاط الإحالة الموزَّعة: {stats['total_points']}\n",
                f"⚙️ النسبة الافتراضية العامة: {get_referral_default_percentage()}%",
            ], "blockquote", None),
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_referrals_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("➕ إضافة مستخدم", callback_data="owner_referrals_add", style="success"),
        InlineKeyboardButton("🗑️ إزالة مستخدم", callback_data="owner_referrals_list:remove:1", style="danger"),
        InlineKeyboardButton("📋 أصحاب الروابط", callback_data="owner_referrals_list:view:1", style="primary"),
        InlineKeyboardButton("🔍 البحث عن مستخدم", callback_data="owner_referrals_search", style="primary"),
        InlineKeyboardButton("📊 إحصائيات الإحالة", callback_data="owner_referrals_stats", style="primary"),
        InlineKeyboardButton("⚙️ إعدادات النسبة", callback_data="owner_referrals_settings", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


REFERRALS_PAGE_SIZE = 8


def build_owner_referrals_list_message(rows: list, mode: str) -> tuple:
    title = {
        "view": "📋 أصحاب الروابط",
        "remove": "🗑️ اختر مستخدمًا لإزالة صلاحية الإحالة عنه",
    }.get(mode, "📋 أصحاب الروابط")
    if not rows:
        content = [title, "\n\n", (["لا يوجد أي صاحب رابط دعوة مسجّل حاليًا ”"], "blockquote", None)]
    else:
        content = [f"{title} ({len(rows)})", "\n\n", (["اضغط على أي مستخدم من القائمة ”"], "blockquote", None)]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_referrals_list_keyboard(rows: list, mode: str, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(rows) + REFERRALS_PAGE_SIZE - 1) // REFERRALS_PAGE_SIZE)
    start = (page - 1) * REFERRALS_PAGE_SIZE
    page_items = rows[start:start + REFERRALS_PAGE_SIZE]

    item_buttons = []
    for row in page_items:
        uid = row.get("user_id")
        name = _display_name(row)
        status_icon = "🟢" if row.get("active") else "🔴"
        item_buttons.append(InlineKeyboardButton(
            f"{status_icon} {name} {row.get('percentage')}%",
            callback_data=f"owner_referrals_pick:{mode}:{uid}",
        ))
    kb_rows = pair_buttons(item_buttons)

    if total_pages > 1:
        kb_rows.append(build_pager_nav_row(
            page, total_pages, f"owner_referrals_list:{mode}:{{page}}", "owner_referrals_noop",
        ))

    kb_rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_section", style="danger",
                                         **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(kb_rows)


def build_referrer_profile_message(row: dict) -> tuple:
    name = _display_name(row)
    status = "🟢 مفعّل" if row.get("active") else "🔴 معطّل"
    content = [
        "👤 بيانات صاحب رابط الدعوة",
        "\n\n",
        ([
            f"🆔 المعرف: {row.get('user_id')}\n",
            f"👤 الاسم: {name}\n",
            f"🔗 اليوزر: @{row['username']}\n" if row.get("username") else "🔗 اليوزر: لا يوجد\n",
            f"📊 نسبة الإحالة: {row.get('percentage')}%\n",
            f"📥 عدد الإحالات: {row.get('referred_count', 0)}\n",
            f"💎 أرباح الإحالة: {row.get('points_earned', 0)} نقطة\n",
            f"📌 حالة الرابط: {status}\n",
            f"🕐 تاريخ الإنشاء: {_format_ts(row.get('created_at'))}\n",
            f"🔗 الرابط: {get_referral_link(row.get('user_id'))}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_referrer_profile_keyboard(row: dict) -> InlineKeyboardMarkup:
    user_id = row.get("user_id")
    toggle_text = "🔴 تعطيل" if row.get("active") else "🟢 تفعيل"
    toggle_style = "danger" if row.get("active") else "success"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"owner_referrals_toggle:{user_id}", style=toggle_style)],
        [InlineKeyboardButton("📊 تعديل النسبة", callback_data=f"owner_referrals_edit_pct:{user_id}",
                              style="primary")],
        [InlineKeyboardButton("🗑️ إزالة هذا المستخدم", callback_data=f"owner_referrals_pick:remove:{user_id}",
                              style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_list:view:1", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_referrer_delete_confirm_message(row: dict) -> tuple:
    name = _display_name(row)
    content = [
        "🗑️ تأكيد إزالة صاحب رابط دعوة",
        "\n\n",
        ([f"هل أنت متأكد أنك تريد إزالة صلاحية الإحالة عن {name}؟\n",
          "📌 إحصائياته السابقة تبقى محفوظة، لكن رابطه سيتوقف عن العمل فورًا ”"], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_referrer_delete_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ تأكيد الإزالة", callback_data=f"owner_referrals_remove_do:{user_id}",
                              style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_referrals_pick:view:{user_id}", style="primary",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_owner_referrals_stats_message() -> tuple:
    stats = get_referrals_overview_stats()
    content = [
        "📊 إحصائيات نظام الإحالة",
        "\n\n",
        ([
            f"👥 عدد أصحاب الروابط: {stats['total_referrers']}\n",
            f"🟢 الروابط النشطة: {stats['active_referrers']}\n",
            f"📥 إجمالي القادمين عبر الإحالة: {stats['total_referred']}\n",
            f"💎 إجمالي نقاط الإحالة الموزَّعة: {stats['total_points']}",
        ], "blockquote", None),
        "\n\n",
    ]
    if not stats["top"]:
        content.append((["📭 لا توجد أي إحالات مسجّلة حتى الآن ”"], "blockquote", None))
    else:
        content.append((["🏆 أفضل 5 بعدد الإحالات ”"], "blockquote", None))
        content.append("\n\n")
        medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
        for index, row in enumerate(stats["top"]):
            name = _display_name(row)
            content.append(([
                f"{medals[index]} {index + 1}. {name}\n",
                f"📥 الإحالات: {row.get('referred_count', 0)} — 💎 النقاط: {row.get('points_earned', 0)}\n",
                "━━━━━━━━━━━━\n",
            ], "blockquote", None))
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_referrals_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث", callback_data="owner_referrals_stats", style="primary")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_owner_referrals_settings_message() -> tuple:
    return build_text_with_emojis([
        ([
            "⚙️ إعدادات نسبة الإحالة",
            "\n\n",
            ([
                f"📊 النسبة الافتراضية العامة: {get_referral_default_percentage()}%\n",
                f"💎 نقاط كل إحالة جديدة (عند نسبة 100%): {get_referral_signup_points()} نقطة",
            ], "blockquote", None),
            "\n\n",
            (["📌 هذه النسبة تُطبَّق تلقائيًا على أي مستخدم جديد يُضاف للنظام دون تحديد نسبة خاصة به ”"],
             "blockquote", None),
        ], "bold", None),
    ])


def build_owner_referrals_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تعديل النسبة الافتراضية", callback_data="owner_referrals_edit_default_pct",
                              style="primary")],
        [InlineKeyboardButton("💎 تعديل نقاط الإحالة", callback_data="owner_referrals_edit_signup_points",
                              style="primary")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_referral_info_block(user_id: int) -> list:
    """يبني قسمًا مستقلاً منسَّقًا باحترافية يعرض رابط الدعوة الخاص بالمستخدم
    وبياناته، إن كان مصرَّحًا له بالإحالة ورابطه مفعّل حاليًا. يُستخدم داخل
    قسم ربح (build_points_message) — يعود بقائمة فارغة إن لم يكن مؤهّلًا
    فلا يظهر شيء. الرابط يُعرض بصيغة code (monospace) لينسخه المستخدم بضغطة
    واحدة بدل رابط خام قد يلتف بشكل غير مرتّب."""
    row = get_referral(user_id)
    if not row or not row.get("active"):
        return []
    link = get_referral_link(user_id)
    return [
        "\n\n",
        "⟡▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬⟡",
        "\n\n",
        "🔗 قسم الإحالة الخاص بك",
        "\n\n",
        ([
            "📎 رابطك الخاص (اضغط عليه لنسخه) :\n",
            (link, "code", None),
        ], "blockquote", None),
        "\n\n",
        ([
            f"📊 نسبتك : {row.get('percentage')}%\n",
            f"📥 عدد الإحالات : {row.get('referred_count', 0)}\n",
            f"💎 أرباح الإحالة : {row.get('points_earned', 0)} نقطة ”",
        ], "blockquote", None),
    ]


# ---------------------------------------------------------------------------
# 📊 إحصائيات البوت (قسم المالك) — نظرة شاملة على المستخدمين والقنوات
# والمجموعات، بالاعتماد على الاستخدام الفعلي للبوت (last_seen_at) لا مجرد
# محاولة الاشتراك في شرط التحقق.
# ---------------------------------------------------------------------------

def build_owner_stats_message(stats: dict, required_members) -> tuple:
    u = stats["users"]
    c = stats["channels"]
    g = stats["groups"]
    members_line = f"{required_members}" if required_members is not None else "—"

    content = [
        "📊 إحصائيات البوت",
        "\n\n",
        (["👥 المستخدمون\n"], "bold", None),
        ([
            f"📌 إجمالي المستخدمين منذ إنشاء البوت: {u['total']}\n",
            f"🟢 النشطون اليوم: {u['active_today']}\n",
            f"🟢 النشطون آخر أسبوع: {u['active_week']}\n",
            f"🟢 النشطون آخر شهر: {u['active_month']}\n",
            f"🟢 النشطون منذ بداية البوت: {u['active_ever']}\n",
            f"🆕 المستخدمون الجدد اليوم: {u['new_today']}\n",
            f"🆕 المستخدمون الجدد هذا الأسبوع: {u['new_week']}\n",
            f"🆕 المستخدمون الجدد هذا الشهر: {u['new_month']}\n",
            f"🚫 المحظورون: {u['banned']}",
        ], "blockquote", None),
        "\n\n",
        (["📢 القنوات\n"], "bold", None),
        ([
            f"📌 إجمالي القنوات: {c['total']}\n",
            f"🟢 القنوات النشطة: {c['active']}\n",
            f"🔴 القنوات غير النشطة: {c['inactive']}\n",
            f"📡 قنوات الاشتراك الإجباري: {c['required_count']}\n",
            f"👥 إجمالي أعضاء قنوات الاشتراك: {members_line}",
        ], "blockquote", None),
        "\n\n",
        (["👥 المجموعات\n"], "bold", None),
        ([
            f"📌 إجمالي المجموعات: {g['total']}\n",
            f"🟢 المجموعات النشطة: {g['active']}\n",
            f"🔴 المجموعات غير النشطة: {g['inactive']}\n",
            f"🆕 مجموعات جديدة اليوم/الأسبوع/الشهر: {g['new_today']} / {g['new_week']} / {g['new_month']}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_owner_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث", callback_data="owner_stats_section", style="primary")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 🎁 السحوبات (قسم المالك) — عرض/حذف كل سحوبات البوت وإحصائياتها فقط
# (بدون اختيار فائز أو إعادة سحب، هذه صلاحية صاحب كل سحب وحده).
# ---------------------------------------------------------------------------

ADMGW_FILTER_LABELS = {
    "all": "📋 كل السحوبات",
    "active": "🟢 السحوبات النشطة",
    "closed": "⏰ السحوبات المنتهية",
    "delete": "🗑️ حذف أي سحب",
}


def _admgw_filter_giveaways(giveaways: list, filt: str) -> list:
    if filt == "active":
        return [g for g in giveaways if g["status"] in ("open", "paused")]
    if filt == "closed":
        return [g for g in giveaways if g["status"] == "closed"]
    return list(giveaways)


def build_owner_draws_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "🎁 السحوبات — إدارة المالك",
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_draws_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("📋 عرض السحوبات", callback_data="admgw_list:all:1", style="primary"),
        InlineKeyboardButton("🟢 السحوبات النشطة", callback_data="admgw_list:active:1", style="success"),
        InlineKeyboardButton("⏰ السحوبات المنتهية", callback_data="admgw_list:closed:1", style="primary"),
        InlineKeyboardButton("🗑️ حذف أي سحب", callback_data="admgw_list:delete:1", style="danger"),
        InlineKeyboardButton("📊 إحصائيات السحوبات", callback_data="admgw_stats", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admgw_list_message(filt: str, page: int, total_pages: int, count: int) -> tuple:
    label = ADMGW_FILTER_LABELS.get(filt, "📋 كل السحوبات")
    if not count:
        content = [label, "\n\n", (["لا توجد أي سحوبات هنا حاليًا ”"], "blockquote", None)]
        return build_text_with_emojis([(content, "bold", None)])
    hint = "اضغط على أي سحب لحذفه نهائيًا ”" if filt == "delete" else "اضغط على أي سحب لعرض تفاصيله ”"
    content = [
        f"{label} ({count})",
        "\n\n",
        ([f"صفحة {page}/{total_pages}", "\n", hint], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admgw_list_keyboard(giveaways: list, filt: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    start = (page - 1) * GW_LIST_PAGE_SIZE
    page_items = giveaways[start:start + GW_LIST_PAGE_SIZE]

    rows = []
    for offset, gw in enumerate(page_items):
        index = start + offset + 1
        dot = "🟢" if gw["status"] in ("open", "paused") else "🔴"
        if filt == "delete":
            rows.append([InlineKeyboardButton(
                f"🗑️ {dot} #{index}", callback_data=f"admgw_delc:{gw['gw_code']}:{filt}:{page}",
            )])
        else:
            rows.append([InlineKeyboardButton(
                f"{dot} #{index}", callback_data=f"admgw_detail:{gw['gw_code']}:{filt}:{page}",
            )])

    if total_pages > 1:
        rows.append(build_pager_nav_row(
            page, total_pages, f"admgw_list:{filt}:{{page}}", "admgw_noop",
        ))

    rows.append([InlineKeyboardButton("🔍 بحث عن سحب بالكود", callback_data=f"admgw_search:{filt}:{page}",
                                      style="primary")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_draws_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admgw_detail_message(giveaway, index, channel_title: str, participants_total: int) -> tuple:
    """تفاصيل السحب داخل قسم «🎁 السحوبات» الخاص بالمالك (Image 3).

    الكود يُعرض بصيغة code (monospace) عبر تركيبة (gw_code, "code", None)
    بدل تضمينه كنص عادي داخل سطر الاقتباس، حتى يستطيع المالك/المشرف نسخه
    بضغطة واحدة مباشرة من هذه الرسالة — هذا هو المكان الوحيد الذي يظهر
    فيه الكود الآن، بعد إزالته من منشور السحب العام في القناة/القروب."""
    status_line = "🟢 نشط" if giveaway["status"] in ("open", "paused") else "🔴 منتهي"
    header = f"🎁 السحب #{index}" if index else "🎁 تفاصيل السحب"
    parts = [
        ([
            header,
            "\n\n",
            "🆔 الكود : ", (str(giveaway['gw_code']), "code", None), "\n",
            f"👑 صاحب السحب : {giveaway['owner_id']}\n",
            f"👥 عدد المشاركين : {participants_total}\n",
            f"🏆 عدد الفائزين : {giveaway['winners_count']}\n",
            f"📊 الحالة : {status_line}\n",
            f"📢 القناة : {channel_title}\n",
            f"🕐 تاريخ الإنشاء : {_format_ts(giveaway.get('created_at'))}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_admgw_detail_keyboard(gw_code: str, filt: str, page: int, channel_url: str = None) -> InlineKeyboardMarkup:
    rows = []
    if channel_url:
        rows.append([InlineKeyboardButton("🔗 دخول إلى القناة", url=channel_url, style="primary")])
    rows.append([InlineKeyboardButton("🗑️ حذف هذا السحب", callback_data=f"admgw_delc:{gw_code}:{filt}:{page}",
                                      style="danger")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"admgw_list:{filt}:{page}", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admgw_delete_confirm_message(giveaway) -> tuple:
    content = [
        "🗑️ تأكيد حذف السحب",
        "\n\n",
        ([f"هل أنت متأكد من حذف السحب {giveaway['gw_code']} نهائيًا؟ سيتم حذف كل بيانات مشاركيه أيضًا ”"],
         "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admgw_delete_confirm_keyboard(gw_code: str, filt: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=f"admgw_detail:{gw_code}:{filt}:{page}", style="primary"),
            InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"admgw_delete_do:{gw_code}:{filt}:{page}",
                                 style="danger"),
        ],
    ])


def build_admgw_stats_message(stats: dict) -> tuple:
    top_line = (
        f"🔥 أكثر سحب مشاركةً : {stats['top_gw_code']} ({stats['top_count']} مشارك)"
        if stats["top_gw_code"] else "🔥 أكثر سحب مشاركةً : لا يوجد"
    )
    content = [
        "📊 إحصائيات السحوبات",
        "\n\n",
        ([
            f"🎁 إجمالي السحوبات : {stats['total']}\n",
            f"🟢 السحوبات النشطة : {stats['active']}\n",
            f"🔴 السحوبات المنتهية : {stats['finished']}\n",
            f"👥 إجمالي المشاركين : {stats['total_participants']}\n",
            f"📈 متوسط المشاركين لكل سحب : {stats['avg_participants']:.1f}\n",
            f"🆕 سحوبات اليوم : {stats['today_count']}\n",
            f"📆 سحوبات آخر 7 أيام : {stats['week_count']}\n",
            f"🗓️ سحوبات آخر 30 يوم : {stats['month_count']}\n",
            top_line,
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admgw_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_draws_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 🏁 المسابقات (قسم المالك) — نفس نظام وتنظيم قسم السحوبات أعلاه (admgw_*)
# بالضبط، لكن للمسابقات: عرض / نشطة / منتهية / حذف + بحث بالكود + إحصائيات.
# المسابقات المنتهية لا تُحذف تلقائيًا أبدًا وتبقى محفوظة حتى يحذفها المالك يدويًا.
# ---------------------------------------------------------------------------

ADMCT_FILTER_LABELS = {
    "all": "📋 كل المسابقات",
    "active": "🟢 المسابقات النشطة",
    "closed": "⏰ المسابقات المنتهية",
    "delete": "🗑️ حذف أي مسابقة",
}


def _admct_filter_contests(contests: list, filt: str) -> list:
    if filt == "active":
        return [c for c in contests if c["status"] in ("open", "paused")]
    if filt == "closed":
        return [c for c in contests if c["status"] == "ended"]
    return list(contests)


def build_owner_contests_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "🏁 المسابقات — إدارة المالك",
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_contests_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("📋 عرض المسابقات", callback_data="admct_list:all:1", style="primary"),
        InlineKeyboardButton("🟢 المسابقات النشطة", callback_data="admct_list:active:1", style="success"),
        InlineKeyboardButton("⏰ المسابقات المنتهية", callback_data="admct_list:closed:1", style="primary"),
        InlineKeyboardButton("🗑️ حذف أي مسابقة", callback_data="admct_list:delete:1", style="danger"),
        InlineKeyboardButton("📊 إحصائيات المسابقات", callback_data="admct_stats", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admct_list_message(filt: str, page: int, total_pages: int, count: int) -> tuple:
    label = ADMCT_FILTER_LABELS.get(filt, "📋 كل المسابقات")
    if not count:
        content = [label, "\n\n", (["لا توجد أي مسابقات هنا حاليًا ”"], "blockquote", None)]
        return build_text_with_emojis([(content, "bold", None)])
    hint = "اضغط على أي مسابقة لحذفها نهائيًا ”" if filt == "delete" else "اضغط على أي مسابقة لعرض تفاصيلها ”"
    content = [
        f"{label} ({count})",
        "\n\n",
        ([f"صفحة {page}/{total_pages}", "\n", hint], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admct_list_keyboard(contests: list, filt: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    start = (page - 1) * GW_LIST_PAGE_SIZE
    page_items = contests[start:start + GW_LIST_PAGE_SIZE]

    rows = []
    for offset, ct in enumerate(page_items):
        index = start + offset + 1
        dot = "🟢" if ct["status"] in ("open", "paused") else "🔴"
        if filt == "delete":
            rows.append([InlineKeyboardButton(
                f"🗑️ {dot} #{index}", callback_data=f"admct_delc:{ct['contest_code']}:{filt}:{page}",
            )])
        else:
            rows.append([InlineKeyboardButton(
                f"{dot} #{index}", callback_data=f"admct_detail:{ct['contest_code']}:{filt}:{page}",
            )])

    if total_pages > 1:
        rows.append(build_pager_nav_row(
            page, total_pages, f"admct_list:{filt}:{{page}}", "admct_noop",
        ))

    rows.append([InlineKeyboardButton("🔍 بحث عن مسابقة بالكود", callback_data=f"admct_search:{filt}:{page}",
                                      style="primary")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_contests_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def _contest_duration_label(contest) -> str:
    if contest.get("end_type") == "time" and contest.get("time_minutes"):
        return format_minutes_label(contest["time_minutes"])
    if contest.get("end_type") == "votes" and contest.get("votes_target"):
        return f"حتى {contest['votes_target']} صوت لأحد المتسابقين"
    return "غير محدد"


def _contest_prize_snippet(contest) -> str:
    text = (contest.get("cliche_text") or "").strip()
    if not text:
        return "لا يوجد نص مسابقة"
    if len(text) > 200:
        text = text[:200].rstrip() + "…"
    return text


def build_admct_detail_message(contest, index, channel_title: str, participants_total: int) -> tuple:
    status_labels = {"open": "🟢 نشطة", "paused": "🟡 متوقفة", "ended": "🔴 منتهية"}
    status_line = status_labels.get(contest["status"], contest["status"])
    header = f"🏁 المسابقة #{index}" if index else "🏁 تفاصيل المسابقة"
    lines = [
        header,
        "\n\n",
        f"📢 القناة : {channel_title}\n",
        f"🆔 كود المسابقة : {contest['contest_code']}\n",
        f"👑 صاحب المسابقة : {contest['owner_id']}\n",
        f"👥 عدد المتسابقين : {participants_total}\n",
        f"🏆 عدد الفائزين : {contest['winners_count']}\n",
        f"⏳ مدة المسابقة : {_contest_duration_label(contest)}\n",
        f"📊 حالة المسابقة : {status_line}\n",
        f"🕐 تاريخ الإنشاء : {_format_ts(contest.get('created_at'))}\n",
    ]
    if contest["status"] == "ended" and contest.get("ended_at"):
        lines.append(f"🏁 وقت الانتهاء : {_format_ts(contest.get('ended_at'))}\n")
    lines.append(f"🎁 تفاصيل المسابقة والجوائز :\n{_contest_prize_snippet(contest)}")
    parts = [(lines, "blockquote", None)]
    return build_text_with_emojis(parts)


def build_admct_detail_keyboard(contest_code: str, filt: str, page: int, channel_url: str = None) -> InlineKeyboardMarkup:
    rows = []
    if channel_url:
        rows.append([InlineKeyboardButton("🔗 دخول إلى القناة", url=channel_url, style="primary")])
    rows.append([InlineKeyboardButton("🗑️ حذف هذه المسابقة", callback_data=f"admct_delc:{contest_code}:{filt}:{page}",
                                      style="danger")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"admct_list:{filt}:{page}", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admct_delete_confirm_message(contest) -> tuple:
    content = [
        "🗑️ تأكيد حذف المسابقة",
        "\n\n",
        ([f"هل أنت متأكد من حذف المسابقة {contest['contest_code']} نهائيًا؟ سيتم حذف كل بيانات متسابقيها وأصواتهم أيضًا ”"],
         "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admct_delete_confirm_keyboard(contest_code: str, filt: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=f"admct_detail:{contest_code}:{filt}:{page}", style="primary"),
            InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"admct_delete_do:{contest_code}:{filt}:{page}",
                                 style="danger"),
        ],
    ])


def build_admct_stats_message(stats: dict) -> tuple:
    top_line = (
        f"🔥 أكثر مسابقة مشاركةً : {stats['top_contest_code']} ({stats['top_count']} متسابق)"
        if stats["top_contest_code"] else "🔥 أكثر مسابقة مشاركةً : لا يوجد"
    )
    content = [
        "📊 إحصائيات المسابقات",
        "\n\n",
        ([
            f"🏁 إجمالي المسابقات : {stats['total']}\n",
            f"🟢 المسابقات النشطة : {stats['active']}\n",
            f"🔴 المسابقات المنتهية : {stats['finished']}\n",
            f"👥 إجمالي المتسابقين : {stats['total_participants']}\n",
            f"📈 متوسط المتسابقين لكل مسابقة : {stats['avg_participants']:.1f}\n",
            f"🆕 مسابقات اليوم : {stats['today_count']}\n",
            f"📆 مسابقات آخر 7 أيام : {stats['week_count']}\n",
            f"🗓️ مسابقات آخر 30 يوم : {stats['month_count']}\n",
            top_line,
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admct_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_contests_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# ⚡ السحب السريع (قسم المالك) — عرض/حذف عمليات الروليت السريع وإحصائياتها فقط.
# ---------------------------------------------------------------------------

ADMRR_FILTER_LABELS = {
    "all": "📋 كل عمليات السحب السريع",
    "active": "🟢 السحوبات السريعة النشطة",
    "closed": "⏰ السحوبات السريعة المنتهية",
    "delete": "🗑️ حذف أي سحب سريع",
}


def _admrr_filter_roulettes(roulettes: list, filt: str) -> list:
    if filt == "active":
        return [r for r in roulettes if r["status"] in ("open", "waiting_spin")]
    if filt == "closed":
        return [r for r in roulettes if r["status"] == "closed"]
    return list(roulettes)


def build_owner_quick_roulette_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "⚡ السحب السريع — إدارة المالك",
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_quick_roulette_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("📋 عرض عمليات السحب السريع", callback_data="admrr_list:all:1", style="primary"),
        InlineKeyboardButton("🟢 النشطة", callback_data="admrr_list:active:1", style="success"),
        InlineKeyboardButton("⏰ المنتهية", callback_data="admrr_list:closed:1", style="primary"),
        InlineKeyboardButton("🗑️ حذف أي سحب سريع", callback_data="admrr_list:delete:1", style="danger"),
        InlineKeyboardButton("📊 إحصائيات السحب السريع", callback_data="admrr_stats", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admrr_list_message(filt: str, page: int, total_pages: int, count: int) -> tuple:
    label = ADMRR_FILTER_LABELS.get(filt, "📋 كل عمليات السحب السريع")
    if not count:
        content = [label, "\n\n", (["لا توجد أي عمليات سحب سريع هنا حاليًا ”"], "blockquote", None)]
        return build_text_with_emojis([(content, "bold", None)])
    hint = "اضغط على أي سحب سريع لحذفه نهائيًا ”" if filt == "delete" else "اضغط على أي سحب سريع لعرض تفاصيله ”"
    content = [
        f"{label} ({count})",
        "\n\n",
        ([f"صفحة {page}/{total_pages}", "\n", hint], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admrr_list_keyboard(roulettes: list, filt: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    start = (page - 1) * GW_LIST_PAGE_SIZE
    page_items = roulettes[start:start + GW_LIST_PAGE_SIZE]

    rows = []
    for offset, rr in enumerate(page_items):
        index = start + offset + 1
        dot = "🟢" if rr["status"] in ("open", "waiting_spin") else "🔴"
        if filt == "delete":
            rows.append([InlineKeyboardButton(
                f"🗑️ {dot} #{index}", callback_data=f"admrr_delc:{rr['roulette_id']}:{filt}:{page}",
            )])
        else:
            rows.append([InlineKeyboardButton(
                f"{dot} #{index}", callback_data=f"admrr_detail:{rr['roulette_id']}:{filt}:{page}",
            )])

    if total_pages > 1:
        rows.append(build_pager_nav_row(
            page, total_pages, f"admrr_list:{filt}:{{page}}", "admrr_noop",
        ))

    rows.append([InlineKeyboardButton("🔍 بحث عن سحب سريع بالكود", callback_data=f"admrr_search:{filt}:{page}",
                                      style="primary")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_quick_roulette_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_admrr_detail_message(roulette, index, participants_total: int) -> tuple:
    status_labels = {"open": "🟢 نشط", "waiting_spin": "🟡 بانتظار التدوير", "closed": "🔴 منتهي"}
    status_line = status_labels.get(roulette["status"], roulette["status"])
    header = f"⚡ السحب السريع #{index}" if index else "⚡ تفاصيل السحب السريع"
    parts = [
        ([
            header,
            "\n\n",
            f"🆔 المعرف : {roulette['roulette_id']}\n",
            f"👑 صاحب السحب : {roulette['owner_id']}\n",
            f"👥 عدد المشاركين : {participants_total}/{roulette['target_count']}\n",
            f"📊 الحالة : {status_line}\n",
            f"🕐 تاريخ الإنشاء : {_format_ts(roulette.get('created_at'))}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis(parts)


def build_admrr_detail_keyboard(roulette_id: int, filt: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف هذا السحب", callback_data=f"admrr_delc:{roulette_id}:{filt}:{page}",
                              style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"admrr_list:{filt}:{page}", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_admrr_delete_confirm_message(roulette) -> tuple:
    content = [
        "🗑️ تأكيد حذف السحب السريع",
        "\n\n",
        ([f"هل أنت متأكد من حذف السحب السريع رقم {roulette['roulette_id']} نهائيًا؟ سيتم حذف كل بيانات مشاركيه أيضًا ”"],
         "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admrr_delete_confirm_keyboard(roulette_id: int, filt: str, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ إلغاء", callback_data=f"admrr_detail:{roulette_id}:{filt}:{page}", style="primary"),
            InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"admrr_delete_do:{roulette_id}:{filt}:{page}",
                                 style="danger"),
        ],
    ])


def build_admrr_stats_message(stats: dict) -> tuple:
    content = [
        "📊 إحصائيات السحب السريع",
        "\n\n",
        ([
            f"⚡ إجمالي السحوبات السريعة : {stats['total']}\n",
            f"🟢 النشطة : {stats['active']}\n",
            f"🔴 المنتهية : {stats['finished']}\n",
            f"👥 إجمالي المشاركات : {stats['total_participants']}\n",
            f"📈 متوسط المشاركات لكل سحب : {stats['avg_participants']:.1f}\n",
            f"🆕 سحوبات اليوم : {stats['today_count']}\n",
            f"📆 سحوبات آخر 7 أيام : {stats['week_count']}\n",
            f"🗓️ سحوبات آخر 30 يوم : {stats['month_count']}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_admrr_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_quick_roulette_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


# ---------------------------------------------------------------------------
# 📣 الإذاعة (قسم المالك) — إرسال أي نوع محتوى يدعمه تيليجرام (نص/صورة/فيديو/
# ملف/صوت/رسالة صوتية/GIF/ملصق/فيديو دائري/استطلاع...) مع أو بدون نص مرفق،
# عبر copy_message (بلا فقدان تنسيق أو وسائط)، إيقافها، عرض إحصائياتها، ومراجعة
# سجل الإذاعات السابقة مع إمكانية حذفها فعليًا من عند الجميع أو تعديل أرشيفها.
# ---------------------------------------------------------------------------

BROADCAST_TYPE_LABELS = {
    "text": "📝 نص",
    "photo": "🖼️ صورة",
    "video": "🎥 فيديو",
    "document": "📎 ملف",
    "audio": "🎵 صوت",
    "voice": "🎙️ رسالة صوتية",
    "animation": "🎞️ صورة متحركة (GIF)",
    "video_note": "⭕ فيديو دائري",
    "sticker": "🧩 ملصق",
    "poll": "📊 استطلاع",
    "other": "📦 محتوى آخر",
}
BROADCAST_STATUS_LABELS = {
    "idle": "⚪ لا توجد إذاعة بعد",
    "running": "🟡 قيد التنفيذ",
    "stopped": "⏹️ تم إيقافها يدويًا",
    "completed": "✅ مكتملة",
}


def build_owner_broadcast_section_message() -> tuple:
    return build_text_with_emojis([
        ([
            "📣 الإذاعة — إدارة المالك",
            "\n\n",
            (["اختر ما تريد فعله من الأزرار أدناه ”"], "blockquote", None),
        ], "bold", None),
    ])


def build_owner_broadcast_section_keyboard() -> InlineKeyboardMarkup:
    rows = pair_buttons([
        InlineKeyboardButton("📢 إرسال لجميع المستخدمين", callback_data="broadcast_send_menu", style="primary"),
        InlineKeyboardButton("⏹️ إيقاف الإذاعة", callback_data="broadcast_stop", style="danger"),
        InlineKeyboardButton("📊 إحصائيات الإرسال", callback_data="broadcast_stats", style="primary"),
        InlineKeyboardButton("🗒️ سجل الإذاعات", callback_data="broadcast_logs:list:1", style="primary"),
    ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_section", style="danger",
                                      **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows)


def build_broadcast_universal_prompt_message() -> tuple:
    """رسالة الطلب الموحّدة لأي نوع محتوى إذاعة — تدعم أي شيء يدعمه تيليجرام
    (نص، صورة، فيديو، ملف، صوت، رسالة صوتية، GIF، ملصق، فيديو دائري...)، مع
    أو بدون نص مرفق، دون الحاجة لاختيار النوع يدويًا مسبقًا — يُكتشف تلقائيًا."""
    return build_text_with_emojis([
        ([
            "📢 إرسال لجميع المستخدمين",
            "\n\n",
            ([
                "أرسل الآن المحتوى الذي تريد إذاعته لكل المستخدمين ”\n\n",
                "يمكنك إرسال أي نوع من المحتوى: نص فقط، أو صورة/فيديو/ملف/صوت/رسالة صوتية مع نص "
                "توضيحي أو بدونه، أو ملصق أو GIF أو أي محتوى آخر يدعمه تيليجرام — سيصل للجميع "
                "تمامًا كما أرسلته دون أي تعديل في التنسيق أو الوسائط ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_broadcast_universal_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_broadcast_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_broadcast_confirm_message(content_type: str) -> tuple:
    label = BROADCAST_TYPE_LABELS.get(content_type, content_type)
    return build_text_with_emojis([
        ([
            "📣 تأكيد الإذاعة",
            "\n\n",
            ([
                f"👆 هذه معاينة رسالة الإذاعة ({label}) كما ستصل لكل المستخدمين.\n",
                "هل تريد المتابعة وإرسالها فعليًا لجميع المستخدمين، أم إلغاء الأمر؟ ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الإرسال للجميع", callback_data="broadcast_confirm_send", style="success"),
            InlineKeyboardButton("❌ إلغاء", callback_data="broadcast_cancel_send", style="danger"),
        ],
    ])


def build_broadcast_stats_message(stats: dict) -> tuple:
    status = stats.get("status", "idle")
    status_line = BROADCAST_STATUS_LABELS.get(status, status)
    type_line = BROADCAST_TYPE_LABELS.get(stats.get("content_type"), "—")
    content = [
        "📊 إحصائيات الإرسال",
        "\n\n",
        ([
            f"📌 الحالة : {status_line}\n",
            f"📦 نوع المحتوى : {type_line}\n",
            f"👥 إجمالي المستهدفين : {stats.get('total', 0)}\n",
            f"📤 تم الإرسال : {stats.get('sent', 0)}\n",
            f"⚠️ فشل الإرسال : {stats.get('failed', 0)}\n",
            f"🕐 بدأت في : {_format_ts(stats.get('started_at'))}\n",
            f"🕓 انتهت في : {_format_ts(stats.get('finished_at'))}",
        ], "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_broadcast_stats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="owner_broadcast_section", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


BROADCAST_LOGS_PAGE_SIZE = 10


def build_broadcast_logs_list_message(rows: list) -> tuple:
    if not rows:
        content = [
            "🗒️ سجل الإذاعات",
            "\n\n",
            (["لا توجد أي إذاعات مُرسَلة حتى الآن ”"], "blockquote", None),
        ]
    else:
        content = [
            f"🗒️ سجل الإذاعات ({len(rows)})",
            "\n\n",
            (["اضغط على أي إذاعة لعرض تفاصيلها أو حذفها أو تعديل نصّها المؤرشف ”"], "blockquote", None),
        ]
    return build_text_with_emojis([(content, "bold", None)])


def build_broadcast_logs_list_keyboard(rows: list, page: int) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(rows) + BROADCAST_LOGS_PAGE_SIZE - 1) // BROADCAST_LOGS_PAGE_SIZE)
    start = (page - 1) * BROADCAST_LOGS_PAGE_SIZE
    page_items = rows[start:start + BROADCAST_LOGS_PAGE_SIZE]

    item_buttons = []
    for row in page_items:
        type_label = BROADCAST_TYPE_LABELS.get(row.get("content_type"), row.get("content_type"))
        status_dot = {"running": "🟡", "completed": "🟢", "stopped": "⏹️"}.get(row.get("status"), "⚪")
        date_label = (row.get("started_at") or "")[:10]
        item_buttons.append(InlineKeyboardButton(
            f"{status_dot} {type_label} — {date_label}",
            callback_data=f"broadcast_logs:pick:{row['log_id']}:{page}", style="primary",
        ))
    rows_kb = pair_buttons(item_buttons)

    if total_pages > 1:
        rows_kb.append(build_pager_nav_row(page, total_pages, "broadcast_logs:list:{page}", "broadcast_logs:noop"))

    rows_kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="owner_broadcast_section", style="danger",
                                          **emoji_kwargs("back_section_btn"))])
    return InlineKeyboardMarkup(rows_kb)


def build_broadcast_log_detail_message(row: dict) -> tuple:
    type_label = BROADCAST_TYPE_LABELS.get(row.get("content_type"), row.get("content_type"))
    preview = row.get("text") if row.get("content_type") == "text" else row.get("caption")
    preview = (preview or "بدون نص/تعليق")[:300]
    lines = [
        f"📦 النوع: {type_label}\n",
        f"📌 الحالة: {broadcast_status_label(row.get('status'))}\n",
        f"👥 المستهدفون: {row.get('total', 0)}\n",
        f"📤 تم الإرسال: {row.get('sent', 0)}\n",
        f"⚠️ فشل: {row.get('failed', 0)}\n",
        f"🕐 بدأت: {_format_ts(row.get('started_at'))}\n",
        f"🕓 انتهت: {_format_ts(row.get('finished_at'))}\n",
    ]
    if row.get("actual_deleted"):
        lines.append(
            f"🚫 تم حذفها فعليًا من عند المستخدمين — نجح: {row.get('actual_deleted_count', 0)}، "
            f"تعذّر: {row.get('actual_delete_failed', 0)}\n"
        )
    lines.append(f"\n📝 المحتوى المؤرشف:\n{preview}")
    content = [
        "🗒️ تفاصيل الإذاعة",
        "\n\n",
        (lines, "blockquote", None),
    ]
    return build_text_with_emojis([(content, "bold", None)])


def build_broadcast_log_detail_keyboard(log_id: str, back_page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل النص المؤرشف", callback_data=f"broadcast_logs:edit:{log_id}:{back_page}", style="primary")],
        [InlineKeyboardButton("🗑️ حذف السجل فقط", callback_data=f"broadcast_logs:delete:{log_id}:{back_page}", style="danger")],
        [InlineKeyboardButton("🚫 حذف الإذاعة فعليًا من عند المستخدمين",
                              callback_data=f"broadcast_logs:delete_actual:{log_id}:{back_page}", style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"broadcast_logs:list:{back_page}", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_broadcast_log_delete_confirm_message() -> tuple:
    return build_text_with_emojis([
        ([
            "🗑️ تأكيد حذف السجل",
            "\n\n",
            (["هل أنت متأكد من حذف هذا السجل من سجل الإذاعات؟ لن يؤثر هذا على الرسائل التي وصلت المستخدمين بالفعل ”"],
             "blockquote", None),
        ], "bold", None),
    ])


def build_broadcast_log_delete_confirm_keyboard(log_id: str, back_page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ تأكيد الحذف", callback_data=f"broadcast_logs:delete_confirm:{log_id}:{back_page}",
                              style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"broadcast_logs:pick:{log_id}:{back_page}", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_broadcast_log_delete_actual_confirm_message(row: dict) -> tuple:
    total_refs = len(row.get("message_refs") or [])
    return build_text_with_emojis([
        ([
            "🚫 تأكيد الحذف الفعلي",
            "\n\n",
            ([
                f"هل أنت متأكد من حذف هذه الإذاعة فعليًا من محادثات المستخدمين؟\n"
                f"سيحاول البوت حذف {total_refs} رسالة مرسَلة فعليًا لدى المستخدمين.\n"
                "⚠️ قد يتعذّر حذف بعض الرسائل (مستخدم حظر البوت، أو حذف المحادثة، إلخ) — "
                "هذا الإجراء لا يمكن التراجع عنه ”",
            ], "blockquote", None),
        ], "bold", None),
    ])


def build_broadcast_log_delete_actual_confirm_keyboard(log_id: str, back_page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 تأكيد الحذف الفعلي", callback_data=f"broadcast_logs:delete_actual_confirm:{log_id}:{back_page}",
                              style="danger")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"broadcast_logs:pick:{log_id}:{back_page}", style="danger",
                              **emoji_kwargs("back_section_btn"))],
    ])


def build_main_keyboard(remind_state=None, user_id: int = None) -> InlineKeyboardMarkup:
    if remind_state is True:
        remind_emoji_key = "remind_on"
        remind_label = "ألغِ التذكير إن فزت"
    elif remind_state is False:
        remind_emoji_key = "remind_off"
        remind_label = "ذكرني إذا فزت"
    else:
        remind_emoji_key = "remind_check"
        remind_label = "ذكرني إذا فزت"

    keyboard = [
        [
            InlineKeyboardButton("انشاء سحب", callback_data="create_draw",
                                  style="primary", **emoji_kwargs("trophy_create_draw")),
            InlineKeyboardButton("روليت سريع", callback_data="quick_roulette_menu",
                                  style="primary", **emoji_kwargs("roulette")),
        ],
        [
            InlineKeyboardButton("سحوباتي", callback_data="my_draws",
                                  style="primary", **emoji_kwargs("draws_check")),
        ],
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="points_stats",
                                 style="primary", **emoji_kwargs("chart")),
            InlineKeyboardButton("🎁 ربح", callback_data="my_stats",
                                 style="primary", **emoji_kwargs("star")),
        ],
        [
            InlineKeyboardButton("الشروط والأحكام", callback_data="terms",
                                  style="danger", **emoji_kwargs("doc")),
            InlineKeyboardButton(remind_label, callback_data="remind_win",
                                  style="success", **emoji_kwargs(remind_emoji_key)),
        ],
        [
            InlineKeyboardButton("دعم البوت", callback_data="support_bot",
                                  style="success", **emoji_kwargs("star")),
            InlineKeyboardButton("الدعم الفني", url=f"https://t.me/{TECH_SUPPORT_USERNAME}",
                                  style="success", **emoji_kwargs("tech")),
        ],
        [
            InlineKeyboardButton("انشاء مسابقة", callback_data="create_contest",
                                  style="primary", **emoji_kwargs("trophy_contest")),
        ],
    ]
    if user_id is not None and is_owner(user_id):
        keyboard.append([InlineKeyboardButton(
            "👑 قسم المالك", callback_data="owner_section",
            style="danger", **emoji_kwargs("gear"),
        )])
    return InlineKeyboardMarkup(keyboard)

def build_quick_roulette_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "انشاء روليت",
                switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                    query="انشاء روليت",
                    allow_channel_chats=True,
                    allow_group_chats=True,
                    allow_bot_chats=True,
                    allow_user_chats=True,
                ),
                style="success",
                **emoji_kwargs("roulette"),
            ),
        ],
        [
            InlineKeyboardButton("الإعدادات", callback_data="qr_settings",
                                  style="primary", **emoji_kwargs("gear")),
        ],
        [
            InlineKeyboardButton("رجوع", callback_data="back_to_main",
                                  style="danger"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_roulette_privacy_settings_text() -> str:
    hide = get_setting("hide_participants") == "1"
    participants_status = "مخفي" if hide else "ظاهر"
    cliche = get_setting("game_cliche") or DEFAULT_GAME_CLICHE
    return (
        "⚙️ الإعدادات والخصوصية\n\n"
        f"اسماء المشاركين : {participants_status}\n"
        f"كليشة اللعبه : {cliche}\n\n"
        "يمكنك التحكم في ظهور و اخفاء اسماء المشاركين في كليشه اللعبه الرسميه\n\n"
        "🆕 يمكنك اضافه كليشه للعبه"
    )

def build_roulette_privacy_settings_keyboard() -> InlineKeyboardMarkup:
    hide = get_setting("hide_participants") == "1"
    participants_label = f"اسماء المشاركين : {'مخفي' if hide else 'ظاهر'}"
    keyboard = [
        [
            InlineKeyboardButton(participants_label, callback_data="toggle_hide_participants_internal",
                                  style="primary", **emoji_kwargs("hide_participants_btn")),
            InlineKeyboardButton("كليشة اللعبة", callback_data="edit_game_cliche",
                                  style="primary", **emoji_kwargs("cliche_btn")),
        ],
        [
            InlineKeyboardButton("الرجوع للافتراضي", callback_data="restore_defaults_roulette",
                                  style="success", **emoji_kwargs("restore_defaults_btn")),
        ],
        [
            InlineKeyboardButton("رجوع", callback_data="section_roulette",
                                  style="danger", **emoji_kwargs("back_section_btn")),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_cliche_prompt_text() -> str:
    cliche = get_setting("game_cliche") or DEFAULT_GAME_CLICHE
    return (
        "✍️ أرسل كليشة اللعبة\n\n"
        "اكتب نص السحب الذي تريد نشره في القناة.\n"
        "يمكنك استخدام تنسيقات تيليجرام، مثل:\n"
        "• نص عريض\n"
        "• نص مائل\n"
        "• نص مشوش\n"
        "- يمكنك وضع رابط داخل النص\n"
        "> نص مقتبس\n\n"
        "النص الحالي:\n"
        f"> • {cliche}"
    )

def build_cliche_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("رجوع", callback_data="qr_settings", style="danger", **emoji_kwargs("back_section_btn"))]
    ])

def roulette_share_keyboard(roulette_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔶 اضغط لـ المشاركة 🔶", callback_data=f"rr_join_{roulette_id}", style="primary")],
        [InlineKeyboardButton("🔷 تدوير الروليت 🔷", callback_data=f"rr_spin_{roulette_id}", style="danger")],
    ])

class _ReplyOnlyMessageShim:
    """كائن بديل خفيف يوفّر reply_text() فقط، يُستخدم لتمرير معالجات الروابط
    العميقة (compjoin_/gwjoin_/... إلخ) نفسها دون أي تعديل عندما يتم استدعاؤها
    من داخل رد على ضغطة زر (callback) بدل رسالة /start مباشرة — تحديدًا بعد
    نجاح زر «تحقق من الاشتراك» في بوابة قناة البوت الإلزامية."""
    def __init__(self, bot, chat_id: int):
        self._bot = bot
        self._chat_id = chat_id

    async def reply_text(self, *args, **kwargs):
        kwargs.pop("quote", None)
        return await self._bot.send_message(chat_id=self._chat_id, *args, **kwargs)


async def _dispatch_start_arg(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               arg: str, is_genuinely_new: bool) -> bool:
    """يوزّع معامل ?start=... على المعالج المناسب له (رابط مسابقة/سحب/روليت).
    يُعيد True إن تم التعرّف على المعامل ومعالجته، أو False إن كان غير معروف
    (فيُعرض حينها الترحيب الافتراضي). مُستخرجة كدالة مستقلة حتى تُستخدم في
    start() مباشرة، وأيضًا بعد اجتياز بوابة الاشتراك الإجباري عبر زر «تحقق»
    لإكمال نفس الطلب الأصلي الذي أوقفته البوابة، بدل عرض الترحيب العام."""
    if arg.startswith("rr_"):
        await handle_roulette_entry(update, context, arg[len("rr_"):])
        return True
    if arg.startswith("compjoin_"):
        await handle_contest_join_entry(
            update, context, arg[len("compjoin_"):], is_genuinely_new=is_genuinely_new,
        )
        return True
    if arg.startswith("compvote_"):
        await handle_contest_vote_entry(update, context, arg[len("compvote_"):])
        return True
    if arg.startswith("gwcap_"):
        await handle_giveaway_captcha_entry(
            update, context, arg[len("gwcap_"):], is_genuinely_new=is_genuinely_new,
        )
        return True
    if arg.startswith("gwjoin_"):
        await handle_giveaway_join_entry(
            update, context, arg[len("gwjoin_"):], is_genuinely_new=is_genuinely_new,
        )
        return True
    if arg.startswith("gwshare_"):
        await handle_giveaway_share_entry(update, context, arg[len("gwshare_"):])
        return True
    if arg == "gw_remind":
        await handle_giveaway_remind_entry(update, context)
        return True
    return False


async def _ban_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بوابة عامة تُسجَّل بمعزل عن بقية المعالِجات (بأولوية أعلى — group=-1)
    وتُنفَّذ قبل أي معالج آخر لأي تحديث. إن كان مُرسِل التحديث محظورًا من
    قسم «إدارة المستخدمين»، تُرسَل له رسالة توضيحية ويُوقَف تمرير التحديث
    لبقية المعالِجات (ApplicationHandlerStop) بدل تكرار هذا الفحص يدويًا
    داخل كل أمر/زر على حدة."""
    user = update.effective_user
    if not user or user.id in OWNER_IDS:
        return
    if not is_bot_user_banned(user.id):
        return
    row = get_bot_user(user.id)
    reason = (row.get("ban_reason") if row else "") or ""
    text = "🚫 أنت محظور من استخدام هذا البوت."
    if reason:
        text += f"\n📝 السبب: {reason}"
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(text)
    except Exception:
        logger.exception("تعذّر إرسال إشعار الحظر للمستخدم %s", user.id)
    raise ApplicationHandlerStop()


async def _maintenance_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بوابة عامة (group=-1) تُنفَّذ بعد بوابة الحظر مباشرة: إن كان وضع
    الصيانة مفعّلًا من قسم «🛠️ صيانة البوت»، يُوقَف تمرير التحديث لكل
    المستخدمين ما عدا مالك البوت والمشرفين، مع رسالة توضيحية بدل أي استجابة
    عادية للبوت."""
    user = update.effective_user
    if not user or is_owner(user.id) or is_moderator(user.id):
        return
    if not is_maintenance_mode():
        return
    text = "🛠️ البوت تحت الصيانة حاليًا، نعتذر عن الإزعاج ونعمل على تحسين الخدمة، حاول لاحقًا 🙏"
    try:
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(text)
    except Exception:
        logger.exception("تعذّر إرسال إشعار الصيانة للمستخدم %s", user.id)
    raise ApplicationHandlerStop()


async def _subscription_gate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بوابة عامة (نفس أولوية بوابتي الحظر والصيانة، group=-1) تُنفَّذ قبل أي
    معالج آخر لكل تحديث نصّي أو زر يصل من محادثة خاصة (بين المستخدم والبوت).
    تفحص اشتراك المستخدم الفعلي في كل قنوات الاشتراك الإجباري *في لحظة
    تفاعله* (وليس نتيجة تحقق قديمة مخزّنة)، فتغطي كل ميزات البوت في المحادثة
    الخاصة بمكان واحد (روليت، مسابقات، سحوبات، نقاط، لوحة الإدارة...) بدل
    تكرار الفحص داخل كل معالج على حدة.

    تُستثنى من هذه البوابة: تحديثات القنوات/المجموعات (لأن أزرار المشاركة
    في السحوبات والمسابقات المنشورة هناك لها بوابات شرط خاصة بها مستقلة
    تمامًا وتُفحص حيًّا بالفعل)، وأمر /start (له بوابته الخاصة الأكثر
    تفصيلاً وتحفظ رابط المشاركة المعلّق)، وزر «تحقق من الاشتراك» نفسه (له
    معالجه المستقل check_sub_status_callback)."""
    chat = update.effective_chat
    if not chat or chat.type != "private":
        return
    message = update.effective_message
    if message is not None and message.text and message.text.startswith("/start"):
        return
    query = update.callback_query
    if query is not None and query.data == "check_sub_status":
        return
    if not await enforce_mandatory_subscription_gate(update, context):
        raise ApplicationHandlerStop()


async def _global_gates_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المُجمِّع الفعلي لكل البوابات العامة (حظر ← صيانة ← اشتراك إجباري).

    ملاحظة تنفيذية مهمة: مكتبة python-telegram-bot تُنفّذ معالجًا واحدًا فقط
    لكل مجموعة (group) لكل تحديث — أول معالج تُطابق شروطه check_update يُنفَّذ
    ثم تتوقف المكتبة عن فحص بقية معالِجات *نفس* المجموعة وتنتقل مباشرة للمجموعة
    التالية. تسجيل _ban_gate_handler وَ_maintenance_gate_handler
    وَ_subscription_gate_handler كثلاثة TypeHandler منفصلة في نفس group=-1 كان
    يجعل _ban_gate_handler وحده (المسجَّل أولاً) هو من يعمل فعليًا؛ إذ TypeHandler
    يطابق كل تحديث دائمًا، فإن لم يرفع ApplicationHandlerStop (حالة المستخدم غير
    المحظور) تنتقل المكتبة مباشرة لمجموعة 0 متجاوزةً بوابتي الصيانة والاشتراك
    تمامًا — لذا يجب استدعاء الثلاث بوابات يدويًا بالتتابع من داخل معالج واحد."""
    await _ban_gate_handler(update, context)
    await _maintenance_gate_handler(update, context)
    await _subscription_gate_handler(update, context)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    # يُسجَّل المستخدم ويُرسَل إشعار "مستخدم جديد" (إن كانت الميزة مفعّلة)
    # فور أوّل تواصل فعلي مع البوت — قبل أي بوابة قد توقف التنفيذ لاحقًا
    # (كبوابة الاشتراك الإجباري أدناه). سابقًا كان هذا يحدث بعد بوابة
    # الاشتراك مباشرة، فكان أي مستخدم جديد لم يشترك بعد بالقنوات المطلوبة
    # (وهي الحالة الأكثر شيوعًا لأي مستخدم جديد حقيقي) يُفلت تمامًا من
    # التسجيل والإشعار؛ لأن استئناف التنفيذ لاحقًا عبر زر «تحقق من الاشتراك»
    # (check_sub_status_callback) كان مشروطًا بوجود رابط دخول عميق محفوظ
    # (pending_start_arg)، وهو غير موجود أصلاً لمن دخل البوت بلا رابط.
    is_genuinely_new = register_bot_user_and_check_new(update.effective_user.id, update.effective_user)
    if is_genuinely_new:
        await _notify_new_user_join(context, update.effective_user)

    if args and args[0].startswith("gwjoin_"):
        # حالة خاصة: رابط المشاركة في سحب يُحال إلى بوابته الموحّدة الخاصة به
        # مباشرة (VORTEX + قناة استضافة السحب معًا في شاشة واحدة) بدل بوابة
        # VORTEX العامة أدناه، حتى لا يمر المستخدم بخطوتين متتاليتين لإتمام
        # نفس الشرط عند فتح البوت عبر زر «اضغط لـ المشاركة».
        await handle_giveaway_join_entry(
            update, context, args[0][len("gwjoin_"):], is_genuinely_new=is_genuinely_new,
        )
        return

    # force_refresh=True لنفس سبب enforce_mandatory_subscription_gate: أول
    # تفاعل للمستخدم مع البوت (أمر /start) يجب أن يعكس حالة اشتراكه الفعلية
    # اللحظية دائمًا، لا نتيجة كاش قديمة.
    channels_status = await get_required_channels_status(context, update.effective_user.id, force_refresh=True)
    missing_channels = [ch for ch, ok in channels_status if not ok]
    if missing_channels:
        # يُحفظ معامل الرابط العميق (إن وُجد) مؤقتًا لهذا المستخدم، حتى إن
        # اجتاز اشتراكه لاحقًا عبر زر «تحقق من الاشتراك» تُستكمل نفس عملية
        # المشاركة الأصلية (مسابقة/سحب) تلقائيًا بدل فقدان السياق وعرض
        # الترحيب العام فقط.
        if context.args:
            context.user_data["pending_start_arg"] = context.args[0]
        # تُحفَظ أيضًا نتيجة is_genuinely_new (حُسبت أعلاه عند أول تواصل فعلي
        # مع البوت) لاستخدامها لاحقًا في check_sub_status_callback بدل إعادة
        # حسابها هناك — فالمستخدم صار مسجَّلاً بالفعل في known_bot_users الآن،
        # فإعادة استدعاء register_bot_user_and_check_new ستُعيد False خطأً.
        context.user_data["pending_is_genuinely_new"] = is_genuinely_new
        text, entities = build_subscription_required_message(missing_channels, channels_status=channels_status)
        await update.message.reply_text(
            text, entities=entities, reply_markup=build_subscription_required_keyboard(missing_channels)
        )
        return

    if args and args[0].startswith("ref_"):
        # لا نشترط هنا أن يكون هذا المستخدم "جديدًا كليًا على البوت" (is_genuinely_new)،
        # لأن هذا الشرط يقيس أول تواصل مع البوت إطلاقًا وليس أول إحالة له تحديدًا —
        # لو استخدم شخص البوت من قبل لأي سبب (رابط سحب سابق، فضول، ...) ثم فُتح له
        # رابط إحالة لأول مرة، كان الشرط القديم يُسقط احتسابه دومًا رغم أنه إحالة
        # حقيقية وأولى. الحماية الفعلية والدقيقة ضد الاحتساب المكرر موجودة أصلًا
        # داخل process_referral_signup نفسها (إنشاء ذري في referral_signups يفشل
        # تلقائيًا لو كان هذا الشخص بالتحديد مُحالًا من قبل)، فهي كافية ودقيقة —
        # عكس is_genuinely_new التي تقيس شيئًا مختلفًا تمامًا.
        process_referral_signup(args[0][len("ref_"):], update.effective_user.id, update.effective_user)
    if args and await _dispatch_start_arg(update, context, args[0], is_genuinely_new):
        return

    text, entities = build_welcome_message(update.effective_user)
    remind_state = get_remind_win_state(update.effective_user.id)
    await update.message.reply_text(
        text, entities=entities,
        reply_markup=build_main_keyboard(remind_state, update.effective_user.id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

async def check_sub_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستدعى عند الضغط على زر «تحقق من الاشتراك» — يعيد فحص الاشتراك في القناة.
    إن كان المستخدم قد وصل لهذه البوابة أثناء محاولة المشاركة في مسابقة/سحب
    (عبر زر «اضغط للمشاركة»)، يُكمل له نفس طلبه الأصلي تلقائيًا بعد نجاح
    التحقق، بدل عرض الترحيب العام فقط."""
    query = update.callback_query
    _SUBSCRIPTION_CACHE.pop(query.from_user.id, None)
    channels_status = await get_required_channels_status(context, query.from_user.id, force_refresh=True)
    missing_channels = [ch for ch, ok in channels_status if not ok]
    if missing_channels:
        await query.answer("⚠️ ما زلت غير مشترك في بعض القنوات، يرجى الاشتراك أولاً ثم إعادة المحاولة.", show_alert=True)
        # يُحدَّث نص الرسالة ليعكس حالة كل قناة الآن (أيها تم الاشتراك فيه
        # فعلاً وأيها ما زال ناقصًا)، بدل ترك المستخدم بلا أي مؤشر واضح.
        text, entities = build_subscription_required_message(missing_channels, channels_status=channels_status)
        try:
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_subscription_required_keyboard(missing_channels),
            )
        except Exception:
            pass
        return
    await query.answer()

    pending_arg = context.user_data.pop("pending_start_arg", None)
    # التسجيل وإشعار "مستخدم جديد" يحدثان الآن عند أوّل تواصل فعلي داخل
    # start() نفسها (قبل بوابة الاشتراك)، فقط تُستعاد القيمة المحفوظة هناك
    # بدل إعادة تسجيل المستخدم هنا (كان هذا يُعيد False دومًا لأنه سبق تسجيله،
    # فلا يصل أي إشعار أبدًا لمن دخل البوت بلا رابط دخول عميق — وهي الحالة
    # الأكثر شيوعًا لمستخدم جديد حقيقي).
    is_genuinely_new = context.user_data.pop("pending_is_genuinely_new", False)
    if pending_arg:
        if pending_arg.startswith("ref_"):
            # نفس المنطق المطبَّق في start(): لا نشترط is_genuinely_new هنا، لأن
            # الحماية الذرية الدقيقة ضد الاحتساب المكرر موجودة فعلًا داخل
            # process_referral_signup نفسها (referral_signups.create()).
            process_referral_signup(pending_arg[len("ref_"):], query.from_user.id, query.from_user)
        shim_update = SimpleNamespace(
            effective_user=query.from_user,
            message=_ReplyOnlyMessageShim(context.bot, query.from_user.id),
        )
        try:
            handled = await _dispatch_start_arg(shim_update, context, pending_arg, is_genuinely_new)
        except Exception:
            logger.exception("تعذّر إكمال الطلب المعلّق %s بعد التحقق من الاشتراك", pending_arg)
            handled = False
        if handled:
            try:
                await query.message.delete()
            except Exception:
                pass
            return

    text, entities = build_welcome_message(query.from_user)
    remind_state = get_remind_win_state(query.from_user.id)
    await query.edit_message_text(
        text=text, entities=entities,
        reply_markup=build_main_keyboard(remind_state, query.from_user.id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

async def handle_roulette_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_id: str):
    user = update.effective_user
    try:
        roulette_id = int(raw_id)
    except ValueError:
        text, entities = build_welcome_message(user)
        remind_state = get_remind_win_state(user.id)
        await update.message.reply_text(
            text, entities=entities, reply_markup=build_main_keyboard(remind_state, user.id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    roulette = get_roulette(roulette_id)
    if not roulette:
        _bt, _be = bold_notice("⚠️ هذا الروليت غير موجود.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    if roulette["status"] != "open":
        _bt, _be = bold_notice("⚠️ انتهى هذا الروليت بالفعل.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    owner_id = roulette["owner_id"]
    target = roulette["target_count"]

    if is_user_counted(user.id, roulette_id):
        current = count_participants(roulette_id)
        _bt, _be = bold_notice(f"✅ أنت مسجّل بالفعل في هذا الروليت.\n👥 المشاركين: {current}/{target}")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    count_user(user.id, roulette_id, user.first_name or user.username or str(user.id))

    current = count_participants(roulette_id)
    _bt, _be = bold_notice(f"✅ تم تسجيل مشاركتك بنجاح!\n👥 المشاركين: {current}/{target}")
    await update.message.reply_text(text=_bt, entities=_be)

    if roulette["inline_message_id"]:
        try:
            body_text, body_entities = build_quick_roulette_channel_message(target, current, roulette_id=roulette_id)
            await context.bot.edit_message_text(
                inline_message_id=roulette["inline_message_id"],
                text=body_text,
                entities=body_entities,
                reply_markup=roulette_share_keyboard(roulette_id),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception:
            pass

    if owner_id and owner_id != user.id:
        display_name = user.first_name or user.username or str(user.id)
        notify_text, notify_entities = build_quick_roulette_join_notify_message(display_name)
        try:
            await context.bot.send_message(
                chat_id=owner_id, text=notify_text, entities=notify_entities,
            )
        except Exception:
            pass

def join_roulette(user_id: int, roulette_id: int, display_name: str = None):
    from google.api_core.exceptions import AlreadyExists
    client = fs_db()

    roulette_doc = client.collection("roulettes").document(str(roulette_id)).get()
    if not roulette_doc.exists:
        return {"found": False}
    roulette = roulette_doc.to_dict()

    target = roulette["target_count"]
    owner_id = roulette["owner_id"]
    status = roulette["status"]

    def _current_count():
        docs = client.collection("counted_users").where("roulette_id", "==", roulette_id).stream()
        return sum(1 for _ in docs)

    counted_ref = client.collection("counted_users").document(_counted_user_doc_id(user_id, roulette_id))
    existing = counted_ref.get().exists

    if existing or status != "open":
        current = _current_count()
        return {
            "found": True, "already": existing, "current": current,
            "target": target, "owner_id": owner_id, "status": status,
        }

    try:
        counted_ref.create({
            "user_id": user_id,
            "roulette_id": roulette_id,
            "display_name": display_name,
            "counted_at": datetime.now(timezone.utc).isoformat(),
        })
    except AlreadyExists:
        current = _current_count()
        return {
            "found": True, "already": True, "current": current,
            "target": target, "owner_id": owner_id, "status": status,
        }

    current = _current_count()
    return {
        "found": True, "already": False, "current": current,
        "target": target, "owner_id": owner_id, "status": status,
    }

async def handle_contest_join_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, contest_code: str,
                                     is_genuinely_new: bool = False):
    """يُستدعى عند فتح البوت عبر رابط ?start=compjoin_{contest_code} (زر المشاركة في المسابقة).
    is_genuinely_new: مُحسَّبة مسبقًا مرة واحدة فقط في start() (أول تواصل فعلي
    مع البوت) وتُمرَّر هنا كي تُبنى بها أزرار «تحقق»/«قبول» اللاحقة، بدل إعادة
    حسابها لاحقًا (register_bot_user_and_check_new تُعيد False دومًا لو أُعيد
    استدعاؤها لمستخدم سبق تسجيله في start() لتوّها)."""
    user = update.effective_user

    contest = get_contest(contest_code)
    if not contest:
        _bt, _be = bold_notice("⚠️ هذه المسابقة غير موجودة أو انتهت.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    if contest["status"] != "open":
        _bt, _be = bold_notice("⚠️ انتهت هذه المسابقة بالفعل.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    existing = get_contest_participant(contest_code, user.id)
    if existing:
        _bt, _be = bold_notice(
            f"✅ أنت مسجّل بالفعل في هذه المسابقة بإسم: {existing['display_name']}\n"
            f"🎟 كودك: {existing['participant_code']}"
        )
        await update.message.reply_text(text=_bt, entities=_be)
        return

    current = count_contest_participants(contest_code)
    if current >= contest["target_count"]:
        _bt, _be = bold_notice("⚠️ اكتمل عدد المشاركين المسموح في هذه المسابقة.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    # فحص خلفي تلقائي: التأكد من أن المستخدم عضو فعلاً في القناة التي نُشرت
    # فيها هذه المسابقة تحديدًا، بصرف النظر عن مصدر وصوله لرسالة المسابقة.
    # لا يظهر له أي شيء بخصوص هذا الشرط إن كان مشتركًا بالفعل، وتُكمل
    # المشاركة مباشرة كالمعتاد.
    if not await check_contest_channel_subscription(context, user.id, contest):
        join_url = await build_contest_channel_join_link(context, contest["chat_id"])
        gate_text, gate_entities = build_contest_channel_gate_message()
        await update.message.reply_text(
            text=gate_text,
            entities=gate_entities,
            reply_markup=build_contest_channel_gate_keyboard(contest_code, join_url, is_genuinely_new),
        )
        return

    display_name = user.first_name or user.username or str(user.id)
    text, entities = build_contest_join_confirm_message(display_name)
    await update.message.reply_text(
        text=text,
        entities=entities,
        reply_markup=build_contest_join_confirm_keyboard(contest_code, is_genuinely_new),
    )


async def contest_channel_gate_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «تحقق ✅» في بوابة شرط قناة المسابقة (compjoinchk:{contest_code}:{is_genuinely_new}).
    يعيد الفحص الفعلي (بدون كاش) لعضوية المستخدم في قناة المسابقة؛ فإن اجتازه
    تتحوّل نفس الرسالة إلى رسالة «تأكيد المشاركة» المعتادة، وإلا يبقى ممنوعًا
    من إكمال المشاركة مع تذكيره بالانضمام أولًا."""
    query = update.callback_query
    try:
        _, contest_code, flag_raw = query.data.split(":", 2)
        is_genuinely_new = flag_raw == "1"
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    contest = get_contest(contest_code)
    if not contest:
        await query.answer("⚠️ هذه المسابقة غير موجودة أو انتهت.", show_alert=True)
        return
    if contest["status"] != "open":
        await query.answer("⚠️ انتهت هذه المسابقة بالفعل.", show_alert=True)
        return

    user = query.from_user
    existing = get_contest_participant(contest_code, user.id)
    if existing:
        await query.answer()
        text, entities = build_contest_registered_message(existing["display_name"], existing["participant_code"])
        await safe_edit_message_text(
            query, text, entities,
            reply_markup=build_contest_registered_keyboard(
                contest_code, user.id, existing["participant_code"]
            ),
        )
        return

    current = count_contest_participants(contest_code)
    if current >= contest["target_count"]:
        await query.answer("⚠️ اكتمل عدد المشاركين المسموح في هذه المسابقة.", show_alert=True)
        return

    if not await check_contest_channel_subscription(context, user.id, contest, force_refresh=True):
        await query.answer(
            "❌ لم يتم العثور على اشتراكك، انضم إلى قناة المسابقة ثم اضغط تحقق مجددًا.",
            show_alert=True,
        )
        return

    await query.answer("✅ تم التحقق من اشتراكك، أكمل المشاركة أدناه.")
    display_name = user.first_name or user.username or str(user.id)
    text, entities = build_contest_join_confirm_message(display_name)
    try:
        await query.edit_message_text(
            text=text, entities=entities,
            reply_markup=build_contest_join_confirm_keyboard(contest_code, is_genuinely_new),
        )
    except Exception:
        await query.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_contest_join_confirm_keyboard(contest_code, is_genuinely_new),
        )


async def compjoin_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «✅ المشاركة في المسابقة» أسفل منشور المسابقة في القناة/القروب
    مباشرة (compjoinbtn:{contest_code}) — بدل التحويل الفوري غير المشروط للبوت
    الذي كان يحدث سابقًا عبر زر رابط (url).

    الأولوية دائمًا لشرط قناة *هذه* المسابقة تحديدًا: تُفحص أولاً وتُعرض كتنبيه
    فوري (show_alert) باسم قناة واحدة محددة فقط عند عدم الاشتراك فيها — دون أي
    خلط مع قنوات VORTEX الإجبارية العامة في نفس التنبيه. شرط VORTEX العام لا
    يُفحص هنا إطلاقًا؛ فور اجتياز شرط قناة المسابقة يُفتح البوت (عبر
    query.answer(url=...)) عبر نفس رابط compjoin_ الحالي دون أي تعديل عليه،
    وهناك start() نفسها هي من تتحقق من VORTEX وتعرض بوابتها الموحّدة الجاهزة
    (بزر لكل قناة ناقصة) إن كان لا يزال غير مشترك فيها — بدل تكرار نفس الفحص
    بتنبيه نصي بسيط هنا."""
    query = update.callback_query
    try:
        contest_code = query.data.split(":", 1)[1]
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    contest = get_contest(contest_code)
    if not contest:
        await query.answer("⚠️ هذه المسابقة غير موجودة أو انتهت.", show_alert=True)
        return
    if contest["status"] != "open":
        await query.answer("⚠️ انتهت هذه المسابقة بالفعل.", show_alert=True)
        return

    user = query.from_user
    # ⚡ لا يُسجَّل تواصل المستخدم هنا: كل مسارات هذه الدالة تنتهي إما بتنبيه
    # (return) أو بفتح البوت عبر رابط compjoin_ (query.answer(url=...))، وهناك
    # start() هي من تسجّل أول تواصل فعلي وتحسب "هل هو مستخدم جديد فعليًا" —
    # تسجيله هنا مسبقًا كان يجعل استدعاء start() اللاحق يُعيد False دومًا
    # (لأنه صار مسجَّلاً بالفعل)، فتُفقَد نقاط المستخدم الجديد الحقيقي.
    existing = get_contest_participant(contest_code, user.id)
    if existing:
        await query.answer(
            f"✅ أنت مسجّل بالفعل في هذه المسابقة بإسم: {existing['display_name']}",
            show_alert=True,
        )
        return

    current = count_contest_participants(contest_code)
    if current >= contest["target_count"]:
        await query.answer("⚠️ اكتمل عدد المشاركين المسموح في هذه المسابقة.", show_alert=True)
        return

    if not await check_contest_channel_subscription(context, user.id, contest):
        title = await get_chat_title_cached(context, contest["chat_id"])
        await query.answer(build_contest_channel_subscribe_alert(title), show_alert=True)
        return

    await query.answer(url=f"https://t.me/{BOT_USERNAME}?start=compjoin_{contest_code}")


async def compvote_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر التصويت 🤍 أسفل منشور المتسابق في القناة/القروب مباشرة
    (compvotebtn:{contest_code}:{participant_id}) — بدل التحويل الفوري غير
    المشروط للبوت الذي كان يحدث سابقًا عبر زر رابط (url).

    بنفس منطق compjoin_button_callback أعلاه: يُفحص شرط قناة *هذه* المسابقة
    تحديدًا فقط هنا (تنبيه فوري باسم قناة واحدة عند عدم الاشتراك)، دون فحص
    قنوات VORTEX العامة في هذا التنبيه. فور اجتياز شرط قناة المسابقة يُفتح
    البوت (لعرض كابتشا «منع الرشق» ثم احتساب التصويت عبر مسار compvote_
    الحالي دون أي تعديل عليه)، وهناك start() تتحقق من VORTEX وتعرض بوابتها
    الموحّدة إن كان لا يزال غير مشترك فيها."""
    query = update.callback_query
    try:
        _, contest_code, participant_id_raw = query.data.split(":", 2)
        participant_id = int(participant_id_raw)
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    contest = get_contest(contest_code)
    if not contest:
        await query.answer("⚠️ هذه المسابقة غير موجودة أو انتهت.", show_alert=True)
        return
    if contest["status"] != "open":
        await query.answer("⚠️ انتهت هذه المسابقة بالفعل.", show_alert=True)
        return

    user = query.from_user
    if register_bot_user_and_check_new(user.id, user):
        await _notify_new_user_join(context, user)

    if user.id == participant_id:
        await query.answer("🚫 لا يمكنك التصويت لنفسك.", show_alert=True)
        return
    if has_voted(contest_code, user.id):
        await query.answer("✅ لقد قمت بالتصويت مسبقًا في هذه المسابقة.", show_alert=True)
        return
    if not get_contest_participant(contest_code, participant_id):
        await query.answer("⚠️ هذا المتسابق لم يعد مسجّلًا في المسابقة.", show_alert=True)
        return
    if contest.get("premium_only") and not user.is_premium:
        await query.answer("💎 هذه المسابقة للتصويت لمستخدمي بريميوم فقط.", show_alert=True)
        return

    if not await check_contest_channel_subscription(context, user.id, contest):
        title = await get_chat_title_cached(context, contest["chat_id"])
        await query.answer(build_contest_channel_subscribe_alert(title), show_alert=True)
        return

    await query.answer(
        url=f"https://t.me/{BOT_USERNAME}?start=compvote_{contest_code}_{participant_id}",
    )


async def handle_contest_vote_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_payload: str):
    """
    يُستدعى عند فتح البوت عبر رابط ?start=compvote_{contest_code}_{participant_id}
    (زر التصويت 🤍 الموجود أسفل منشور المتسابق). يعرض للمستخدم كابتشا إيموجي
    عشوائية للتحقق أنه ليس روبوتًا قبل تسجيل تصويته.
    """
    user = update.effective_user

    try:
        contest_code, participant_id_raw = raw_payload.rsplit("_", 1)
        participant_id = int(participant_id_raw)
    except (ValueError, AttributeError):
        _bt, _be = bold_notice("⚠️ رابط تصويت غير صالح.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    contest = get_contest(contest_code)
    if not contest:
        _bt, _be = bold_notice("⚠️ هذه المسابقة غير موجودة أو انتهت.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    if contest["status"] != "open":
        _bt, _be = bold_notice("⚠️ انتهت هذه المسابقة بالفعل.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    if user.id == participant_id:
        _bt, _be = bold_notice("🚫 لا يمكنك التصويت لنفسك.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    if has_voted(contest_code, user.id):
        _bt, _be = bold_notice("✅ لقد قمت بالتصويت مسبقًا في هذه المسابقة.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    participant = get_contest_participant(contest_code, participant_id)
    if not participant:
        _bt, _be = bold_notice("⚠️ هذا المتسابق لم يعد مسجّلًا في المسابقة.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    # شرط بريميوم: إن كانت المسابقة مخصّصة لمصوّتي بريميوم فقط، يُرفض أي
    # مستخدم غير مفعّل بريميوم هنا فورًا قبل أي خطوة أخرى، ويُعاد نفس الفحص
    # عند «تحقق» وعند تسجيل التصويت النهائي كطبقة حماية إضافية.
    if contest.get("premium_only") and not user.is_premium:
        text, entities = build_contest_vote_premium_blocked_message()
        await update.message.reply_text(text=text, entities=entities)
        return

    # بوابة الاشتراك الإجباري: لا تُعرض الكابتشا مباشرة إن لم يكن المستخدم
    # مشتركًا فعليًا في القناة الإلزامية العامة + قناة نشر هذه المسابقة
    # تحديدًا؛ بل تُعرض له بوابة اشتراك + زر «تحقق» صريح، ولا يُحتسب أي
    # تصويت قبل اجتياز هذا الفحص فعليًا.
    missing_channels = await get_missing_contest_vote_channels(context, user.id, contest)
    if missing_channels:
        gate_text, gate_entities = build_contest_vote_gate_message()
        await update.message.reply_text(
            text=gate_text,
            entities=gate_entities,
            reply_markup=build_contest_vote_gate_keyboard(contest_code, participant_id, missing_channels),
        )
        return

    text, entities, keyboard = _build_contest_vote_captcha_payload(context, contest_code, participant_id)
    await update.message.reply_text(text=text, entities=entities, reply_markup=keyboard)


def _build_contest_vote_captcha_payload(context: ContextTypes.DEFAULT_TYPE, contest_code: str,
                                         participant_id: int) -> tuple:
    """يبني رسالة/كيبورد كابتشا التصويت ويخزّن جلستها. تُستخدم عند اجتياز
    بوابة الشروط مباشرة (لا شرط اشتراك) وأيضًا بعد الضغط على زر «تحقق» في
    بوابة الاشتراك، حتى تظهر نفس الكابتشا في الحالتين."""
    correct_emoji = random.choice(CAPTCHA_EMOJIS)
    decoys_pool = [e for e in CAPTCHA_EMOJIS if e != correct_emoji]
    decoy_count = min(CAPTCHA_OPTIONS_COUNT - 1, len(decoys_pool))
    decoys = random.sample(decoys_pool, decoy_count)
    options = decoys + [correct_emoji]
    random.shuffle(options)
    correct_index = options.index(correct_emoji)

    token = secrets.token_hex(4)
    sessions = context.user_data.setdefault("vote_captchas", {})
    sessions[token] = {
        "contest_code": contest_code,
        "participant_id": participant_id,
        "correct_index": correct_index,
        "correct_emoji": correct_emoji,
        "created_at": time.time(),
    }

    text, entities = build_vote_captcha_message(correct_emoji)
    keyboard = build_vote_captcha_keyboard(token, options, correct_index)
    return text, entities, keyboard


async def contest_vote_gate_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «تحقق ✅» في بوابة اشتراك التصويت (compcond:{contest_code}:{participant_id}).
    يُعيد التحقق الفعلي (وليس من كاش قديم) من اشتراك المستخدم، ومن شرط
    بريميوم إن وُجد، قبل السماح له بالانتقال لخطوة الكابتشا النهائية."""
    query = update.callback_query
    try:
        _, contest_code, participant_id_raw = query.data.split(":", 2)
        participant_id = int(participant_id_raw)
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    user = query.from_user

    contest = get_contest(contest_code)
    if not contest or contest["status"] != "open":
        await query.answer("⚠️ انتهت هذه المسابقة.", show_alert=True)
        return
    if user.id == participant_id:
        await query.answer("🚫 لا يمكنك التصويت لنفسك.", show_alert=True)
        return
    if has_voted(contest_code, user.id):
        await query.answer("✅ لقد قمت بالتصويت مسبقًا في هذه المسابقة.", show_alert=True)
        return
    if not get_contest_participant(contest_code, participant_id):
        await query.answer("⚠️ هذا المتسابق لم يعد مسجّلًا.", show_alert=True)
        return
    if contest.get("premium_only") and not user.is_premium:
        await query.answer("💎 هذه المسابقة للتصويت لمستخدمي بريميوم فقط.", show_alert=True)
        return

    # فحص حي وشامل (بدون كاش): القنوات الإجبارية العامة + قناة نشر هذه
    # المسابقة تحديدًا معًا، بنفس منطق الدخول الأول لمسار التصويت.
    missing_channels = await get_missing_contest_vote_channels(context, user.id, contest, force_refresh=True)
    if missing_channels:
        await query.answer(
            "⚠️ ما زلت غير مشترك في بعض القنوات، يرجى الاشتراك أولاً ثم إعادة المحاولة.",
            show_alert=True,
        )
        # تُحدَّث نفس الرسالة لتعكس القنوات الناقصة فعليًا الآن (فقد تكون
        # إحدى القنوات السابقة أُنجزت بالفعل)، بدل ترك المستخدم بلا مؤشر واضح.
        gate_text, gate_entities = build_contest_vote_gate_message()
        try:
            await query.edit_message_text(
                text=gate_text, entities=gate_entities,
                reply_markup=build_contest_vote_gate_keyboard(contest_code, participant_id, missing_channels),
            )
        except Exception:
            pass
        return

    await query.answer("✅ تم التحقق من الاشتراك، أكمل التحقق أدناه.")
    text, entities, keyboard = _build_contest_vote_captcha_payload(context, contest_code, participant_id)
    try:
        await query.edit_message_text(text=text, entities=entities, reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text=text, entities=entities, reply_markup=keyboard)


def _build_giveaway_captcha_payload(context: ContextTypes.DEFAULT_TYPE, gw_code: str,
                                     is_genuinely_new: bool) -> tuple:
    """يبني رسالة/كيبورد كابتشا منع الرشق (نفس زر الإيموجي الموجود مسبقًا)
    ويخزّن جلستها. تُستخدم عند فتح البوت لأول مرة (إن كانت الشروط مكتملة
    مسبقًا) وأيضًا بعد اجتياز بوابة الشروط عبر زر «تحقق»، لتظهر نفس الكابتشا
    في الحالتين."""
    correct_emoji = random.choice(CAPTCHA_EMOJIS)
    decoys_pool = [e for e in CAPTCHA_EMOJIS if e != correct_emoji]
    decoy_count = min(CAPTCHA_OPTIONS_COUNT - 1, len(decoys_pool))
    decoys = random.sample(decoys_pool, decoy_count)
    options = decoys + [correct_emoji]
    random.shuffle(options)
    correct_index = options.index(correct_emoji)

    token = secrets.token_hex(4)
    sessions = context.user_data.setdefault("gw_captchas", {})
    sessions[token] = {
        "gw_code": gw_code,
        "correct_index": correct_index,
        "created_at": time.time(),
        "is_genuinely_new": is_genuinely_new,
    }

    text, entities = build_vote_captcha_message(correct_emoji)
    keyboard = build_vote_captcha_keyboard(token, options, correct_index, prefix="gwcap")
    return text, entities, keyboard


async def handle_giveaway_captcha_entry(
    update: Update, context: ContextTypes.DEFAULT_TYPE, gw_code: str, is_genuinely_new: bool = False,
):
    """يُستدعى عند فتح البوت عبر رابط ?start=gwcap_{gw_code} (زر «اضغط لـ
    المشاركة» على سحب مفعّل عليه «منع الرشق»).

    أولاً يتحقق من شروط السحب (الاشتراك في قناة/قنوات الشرط، التعزيز، التصويت
    للمتسابق إن وُجد). إن لم تكتمل بعد، يعرض للمستخدم بوابة الشروط (زر لكل
    قناة/شرط + زر «تحقق») بدل الكابتشا مباشرة. فقط بعد اجتياز هذه الشروط
    يظهر له زر التحقق (الكابتشا) الموجود مسبقًا."""
    user = update.effective_user

    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["status"] != "open":
        _bt, _be = bold_notice("⚠️ هذا السحب غير متاح حالياً.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    if is_giveaway_participant(gw_code, user.id):
        _bt, _be = bold_notice("✅ أنت مسجّل بالفعل في هذا السحب.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    ok, _alert = await check_giveaway_requirements(context, user, giveaway)
    if not ok:
        boost_link, vote_link = await build_giveaway_gate_links(context, giveaway)
        gate_text, gate_entities = build_giveaway_gate_message(giveaway)
        await update.message.reply_text(
            text=gate_text,
            entities=gate_entities,
            reply_markup=build_giveaway_gate_keyboard(
                gw_code, giveaway, is_genuinely_new, boost_link=boost_link, vote_link=vote_link,
            ),
        )
        return

    text, entities, keyboard = _build_giveaway_captcha_payload(context, gw_code, is_genuinely_new)
    await update.message.reply_text(text=text, entities=entities, reply_markup=keyboard)


async def gwcond_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «تحقق ✅» في بوابة شروط السحب (gwcond:{gw_code}:{is_genuinely_new}).
    عند اجتياز الشروط تتحوّل نفس الرسالة إلى كابتشا التحقق منع الرشق."""
    query = update.callback_query
    try:
        _, gw_code, flag_raw = query.data.split(":", 2)
        is_genuinely_new = flag_raw == "1"
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["status"] != "open":
        await query.answer("⚠️ هذا السحب لم يعد متاحاً.", show_alert=True)
        return

    user = query.from_user
    if is_giveaway_participant(gw_code, user.id):
        await query.answer("✅ أنت مسجّل بالفعل في هذا السحب.", show_alert=True)
        return

    # إعادة فحص قناة VORTEX وقناة استضافة السحب معًا (بكاش مُحدَّث)، فهذا الزر
    # هو نفسه زر التأكيد في البوابة الموحّدة القادمة من رابط gwjoin_ — إن ظل
    # أحدهما ناقصًا تُعاد نفس البوابة محدَّثة بدل رفض عام دون توضيح السبب.
    _SUBSCRIPTION_CACHE.pop(user.id, None)
    gate_ctx = await build_giveaway_gate_context(context, user.id, giveaway)
    if gate_ctx["need_vortex"] or gate_ctx["host_channel_link"]:
        await query.answer(
            "⚠️ لم يتم العثور على اشتراكك بعد، اشترك في القنوات المطلوبة ثم أعد المحاولة.",
            show_alert=True,
        )
        boost_link, vote_link = await build_giveaway_gate_links(context, giveaway)
        gate_text, gate_entities = build_giveaway_gate_message(
            giveaway,
            need_vortex=gate_ctx["need_vortex"],
            host_channel_title=gate_ctx["host_channel_title"],
        )
        try:
            await query.edit_message_text(
                text=gate_text,
                entities=gate_entities,
                reply_markup=build_giveaway_gate_keyboard(
                    gw_code, giveaway, is_genuinely_new, boost_link=boost_link, vote_link=vote_link,
                    need_vortex=gate_ctx["need_vortex"],
                    host_channel_link=gate_ctx["host_channel_link"],
                    host_channel_title=gate_ctx["host_channel_title"],
                ),
            )
        except Exception:
            pass
        return

    ok, alert_text = await check_giveaway_requirements(context, user, giveaway)
    if not ok:
        await query.answer(alert_text, show_alert=True)
        return

    await query.answer("✅ تم التحقق من الشروط، أكمل التحقق أدناه.")
    text, entities, keyboard = _build_giveaway_captcha_payload(context, gw_code, is_genuinely_new)
    try:
        await query.edit_message_text(text=text, entities=entities, reply_markup=keyboard)
    except Exception:
        await query.message.reply_text(text=text, entities=entities, reply_markup=keyboard)


async def handle_giveaway_share_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, gw_code: str):
    """يُستدعى عند فتح البوت عبر رابط ?start=gwshare_{gw_code} (زر «مشاركة السحب»)."""
    giveaway = get_giveaway(gw_code)
    if not giveaway:
        _bt, _be = bold_notice("⚠️ هذا السحب غير موجود أو انتهى.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    post_link = await build_contest_post_link(context, giveaway["chat_id"], giveaway["channel_message_id"])
    if post_link:
        _bt, _be = bold_notice(f"🎁 يمكنك المشاركة في هذا السحب من هنا:\n{post_link}")
    else:
        _bt, _be = bold_notice("🎁 توجّه إلى القناة/الجروب المنشور بها السحب للمشاركة.")
    await update.message.reply_text(text=_bt, entities=_be)


async def handle_giveaway_remind_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستدعى عند فتح البوت عبر رابط ?start=gw_remind (زر «ذكرني اذا فزت»)."""
    enabled = toggle_remind_win(update.effective_user.id)
    _bt, _be = bold_notice(
        "🔔 تم تفعيل تذكيرك إذا فزت." if enabled else "🔕 تم إلغاء تذكيرك إذا فزت."
    )
    await update.message.reply_text(text=_bt, entities=_be)


async def finalize_giveaway_join(context: ContextTypes.DEFAULT_TYPE, gw_code: str, giveaway,
                                  user, message=None, is_genuinely_new: bool = True):
    """يسجّل مشاركة مستخدم في سحب (بعد اجتياز الكابتشا إن لزم)، يحدّث زر المشاركة،
    ويُرسل إشعارًا خاصًا لمنشئ السحب مع زر استبعاد (Image 6)."""
    display_name = user.first_name or user.username or str(user.id)
    added = add_giveaway_participant(gw_code, user.id, display_name, user.username)
    if not added:
        return
    if is_genuinely_new:
        try:
            bump_channel_new_users(giveaway["chat_id"])
        except Exception:
            logger.exception("تعذّر تحديث عدّاد المستخدمين الجدد لقناة السحب %s", giveaway.get("chat_id"))
    if bool(giveaway["antispam"]) and is_genuinely_new:
        reward_giveaway_user(
            user.id, gw_code, giveaway["owner_id"], giveaway["chat_id"]
        )
    total = count_giveaway_participants(gw_code)

    new_keyboard = build_giveaway_channel_keyboard(
        gw_code, total, antispam=bool(giveaway["antispam"]), status=giveaway["status"],
    )
    try:
        if message is not None:
            await message.edit_reply_markup(reply_markup=new_keyboard)
        else:
            await context.bot.edit_message_reply_markup(
                chat_id=giveaway["chat_id"],
                message_id=giveaway["channel_message_id"],
                reply_markup=new_keyboard,
            )
    except Exception:
        pass

    notify_text, notify_entities = build_giveaway_join_notify_message(
        display_name, user.username, user.id, gw_code, total,
    )
    try:
        await context.bot.send_message(
            chat_id=giveaway["owner_id"],
            text=notify_text,
            entities=notify_entities,
            reply_markup=build_giveaway_join_notify_keyboard(gw_code, user.id),
        )
    except Exception:
        pass

    if giveaway.get("autospin_mode") == "count" and giveaway.get("autospin_target")\
            and total >= giveaway["autospin_target"]:
        await finish_giveaway_auto(context, gw_code)


async def handle_giveaway_join_entry(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                      gw_code: str, is_genuinely_new: bool = False):
    """يُستدعى عند فتح البوت عبر رابط ?start=gwjoin_{gw_code} — وهو التحويل
    التلقائي من زر «اضغط لـ المشاركة» أسفل منشور السحب في القناة عندما يكتشف
    البوت أن المستخدم غير مشترك في قناة البوت الإلزامية (VORTEX). بما أن
    start() يتحقق من هذا الاشتراك ويعرض بوابته الخاصة قبل الوصول لهذه الدالة،
    فالمستخدم هنا يكون قد اجتاز شرط الاشتراك بالفعل، فتكمل نفس منطق المشاركة
    المعتاد الموجود في gw_join_callback لكن عبر رسالة خاصة بدل استعلام كولباك."""
    user = update.effective_user

    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["status"] != "open":
        _bt, _be = bold_notice("⚠️ هذا السحب غير متاح حالياً.")
        await update.message.reply_text(text=_bt, entities=_be)
        return
    if is_giveaway_participant(gw_code, user.id):
        _bt, _be = bold_notice("✅ أنت مسجّل بالفعل في هذا السحب.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    # بوابة موحّدة: تُفحص قناة VORTEX الإجبارية وقناة استضافة السحب نفسها معًا
    # هنا دفعة واحدة (بدل بوابة VORTEX منفصلة في start() ثم بوابة أخرى لقناة
    # السحب لاحقًا)، وتُعرض للمستخدم شاشة واحدة فيها زر لكل شرط ناقص فعليًا
    # فقط + زر تأكيد واحد، سواء كان ناقصًا الاشتراك في القناتين معًا أو في
    # واحدة منهما فقط.
    context.user_data.pop("pending_start_arg", None)
    gate_ctx = await build_giveaway_gate_context(context, user.id, giveaway)
    if gate_ctx["need_vortex"] or gate_ctx["host_channel_link"]:
        boost_link, vote_link = await build_giveaway_gate_links(context, giveaway)
        gate_text, gate_entities = build_giveaway_gate_message(
            giveaway,
            need_vortex=gate_ctx["need_vortex"],
            host_channel_title=gate_ctx["host_channel_title"],
        )
        await update.message.reply_text(
            text=gate_text,
            entities=gate_entities,
            reply_markup=build_giveaway_gate_keyboard(
                gw_code, giveaway, is_genuinely_new, boost_link=boost_link, vote_link=vote_link,
                need_vortex=gate_ctx["need_vortex"],
                host_channel_link=gate_ctx["host_channel_link"],
                host_channel_title=gate_ctx["host_channel_title"],
            ),
        )
        return

    ok, _alert = await check_giveaway_requirements(context, user, giveaway)
    if not ok:
        # الشروط المتبقية هنا هي فقط شروط السحب الإضافية الاختيارية (قنوات شرط
        # يحددها المالك يدويًا / تعزيز / تصويت لمتسابق) — منفصلة عن VORTEX
        # وقناة الاستضافة اللتين فُحصتا بالفعل أعلاه.
        boost_link, vote_link = await build_giveaway_gate_links(context, giveaway)
        gate_text, gate_entities = build_giveaway_gate_message(giveaway)
        await update.message.reply_text(
            text=gate_text,
            entities=gate_entities,
            reply_markup=build_giveaway_gate_keyboard(
                gw_code, giveaway, is_genuinely_new, boost_link=boost_link, vote_link=vote_link,
            ),
        )
        return

    if giveaway["antispam"]:
        text, entities, keyboard = _build_giveaway_captcha_payload(context, gw_code, is_genuinely_new)
        await update.message.reply_text(text=text, entities=entities, reply_markup=keyboard)
        return

    await finalize_giveaway_join(context, gw_code, giveaway, user, is_genuinely_new=is_genuinely_new)
    _bt, _be = bold_notice("✅ تم تسجيل مشاركتك بنجاح!")
    await update.message.reply_text(text=_bt, entities=_be)


async def gw_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «اضغط لـ المشاركة» أسفل منشور السحب في القناة/القروب."""
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["status"] != "open":
        await query.answer("⚠️ هذا السحب غير متاح حالياً.", show_alert=True)
        return

    user = query.from_user
    # ⚡ لا يُسجَّل تواصل المستخدم هنا مبكرًا: هذه الدالة قد تنتهي بفتح البوت
    # (query.answer(url=...)) لإكمال شرط ناقص أو لعرض كابتشا منع الرشق —
    # وفي الحالتين تستدعي start() لاحقًا register_bot_user_and_check_new من
    # جديد، فتُعيد False دومًا لأنه صار مسجَّلاً هنا بالفعل، فتُفقَد نقطة كل
    # مستخدم جديد فعليًا في كل سحب مفعّل عليه «منع الرشق» (هذا كان سبب المشكلة
    # الأصلية). التسجيل الآن يحدث فقط أسفل الدالة، في الحالة الوحيدة التي لا
    # تفتح فيها البوت لاحقًا (لا منع رشق ولا شرط ناقص).
    if is_giveaway_participant(gw_code, user.id):
        await query.answer("✅ أنت مسجّل بالفعل في هذا السحب.", show_alert=True)
        return

    # 🎯 شرط بريميوم وشرط قناة *هذا* السحب تحديدًا (القناة التي نُشر فيها
    # المنشور) لهما الأولوية دائمًا، ويُعرضان كتنبيه فوري صغير (show_alert)
    # فقط — لا يجوز أبدًا فتح البوت أو تحويل المستخدم بسبب أيٍّ منهما مهما
    # كانت الحالة.
    if giveaway.get("premium_only") and not user.is_premium:
        await query.answer("💎 هذا السحب للأشخاص المفعلين مميز فقط!", show_alert=True)
        return

    if not await check_giveaway_host_channel_subscription(context, user.id, giveaway):
        host_title = await get_chat_title_cached(context, giveaway["chat_id"])
        await query.answer(build_giveaway_host_channel_subscribe_alert(host_title), show_alert=True)
        return

    # ✅ فقط بعد اجتياز شرط قناة السحب نفسها: أي شرط آخر ناقص من هنا فصاعدًا
    # (قناة/قنوات VORTEX الإجبارية العامة، أو قنوات شرط السحب الإضافية اليدوية
    # التي يضيفها المالك (حتى GW_CONDITION_CHANNELS_MAX قناة)، أو التعزيز، أو
    # التصويت لمتسابق) يُفتح له البوت الآن عبر رابط gwjoin_ الحالي (بدل تنبيه
    # نصي بسيط هنا)، حيث تُعرض له بوابة موحّدة بزر حقيقي لكل شرط ناقص فعليًا +
    # زر «تحقق ✅» أسفلها (نفس آلية build_giveaway_gate_message/keyboard
    # المستخدمة أصلاً داخل handle_giveaway_join_entry).
    need_vortex = await get_missing_required_channels(context, user.id)
    condition_ok = await check_giveaway_condition_channels(context, user.id, giveaway)
    boost_ok = (not giveaway.get("boost_required")) or await check_giveaway_boost(
        context, user.id, giveaway["chat_id"],
    )
    vote_contest_code = giveaway.get("vote_contest_code")
    vote_participant_id = giveaway.get("vote_participant_id")
    vote_required = bool(vote_contest_code and vote_participant_id)
    vote_ok = not vote_required or has_voted_for(vote_contest_code, user.id, vote_participant_id)

    if need_vortex or not condition_ok or not boost_ok or not vote_ok:
        await query.answer(url=f"https://t.me/{BOT_USERNAME}?start=gwjoin_{gw_code}")
        return

    if giveaway["antispam"]:
        await query.answer(
            url=f"https://t.me/{BOT_USERNAME}?start=gwcap_{gw_code}",
        )
        return

    # هنا فقط لا يوجد أي فتح لاحق للبوت — آمن الآن لتسجيل أول تواصل فعلي
    # وحساب "هل هو مستخدم جديد فعليًا" دون أن يُستهلك الاستدعاء قبل الأوان.
    is_genuinely_new = register_bot_user_and_check_new(user.id, user)
    if is_genuinely_new:
        await _notify_new_user_join(context, user)

    await finalize_giveaway_join(
        context, gw_code, giveaway, user, query.message, is_genuinely_new=is_genuinely_new,
    )
    if vote_required:
        await query.answer("✅ تم اشتراكك في السحب", show_alert=True)
    else:
        await query.answer("✅ تم تسجيل مشاركتك بنجاح!")


async def gw_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط أزرار كابتشا منع الرشق قبل المشاركة في السحب (gwcap:{token}:{idx})."""
    query = update.callback_query
    data = query.data
    try:
        _, token, idx_raw = data.split(":", 2)
        chosen_index = int(idx_raw)
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    sessions = context.user_data.get("gw_captchas", {})
    session = sessions.get(token)
    if not session:
        await query.answer("⚠️ انتهت صلاحية هذا التحقق، أعد المحاولة من زر المشاركة.", show_alert=True)
        return
    if time.time() - session.get("created_at", 0) > CAPTCHA_SESSION_TTL_SECONDS:
        sessions.pop(token, None)
        await query.answer("⚠️ انتهت صلاحية هذا التحقق، أعد المحاولة من زر المشاركة.", show_alert=True)
        return
    if chosen_index != session["correct_index"]:
        await query.answer(build_vote_captcha_wrong_alert(), show_alert=True)
        return

    gw_code = session["gw_code"]
    giveaway = get_giveaway(gw_code)
    is_genuinely_new = session.get("is_genuinely_new", False)
    sessions.pop(token, None)
    if not giveaway or giveaway["status"] != "open":
        await query.answer("⚠️ هذا السحب لم يعد متاحاً.", show_alert=True)
        return
    if is_giveaway_participant(gw_code, query.from_user.id):
        await query.answer("✅ أنت مسجّل بالفعل في هذا السحب.", show_alert=True)
        return

    # التحقق النهائي الموحّد (بريميوم/قنوات/تعزيز/تصويت) — بهذا يتم الدخول
    # تلقائيًا في السحب فقط بعد اجتياز الكابتشا وهذه الشروط معًا دفعة واحدة.
    ok, alert_text = await check_giveaway_requirements(context, query.from_user, giveaway)
    if not ok:
        # حالة نادرة: تحقق المستخدم من الشروط عند فتح البوت ثم ألغى اشتراكه
        # قبل الضغط على الكابتشا — نعيده لبوابة الشروط بدل تنبيه فقط حتى
        # يتمكن من إصلاح الأمر والمتابعة دون طلب رابط مشاركة جديد.
        await query.answer(alert_text, show_alert=True)
        boost_link, vote_link = await build_giveaway_gate_links(context, giveaway)
        gate_text, gate_entities = build_giveaway_gate_message(giveaway)
        try:
            await query.edit_message_text(
                text=gate_text,
                entities=gate_entities,
                reply_markup=build_giveaway_gate_keyboard(
                    gw_code, giveaway, is_genuinely_new, boost_link=boost_link, vote_link=vote_link,
                ),
            )
        except Exception:
            pass
        return

    await finalize_giveaway_join(
        context, gw_code, giveaway, query.from_user, None, is_genuinely_new=is_genuinely_new,
    )
    await query.answer("✅ تم التحقق وتسجيل مشاركتك بنجاح!", show_alert=True)

    text, entities = build_vote_captcha_success_message()
    try:
        await query.edit_message_text(text=text, entities=entities)
    except Exception:
        pass


async def gw_kick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «استبعاد» في إشعار مشارك جديد (Image 6) — يحذف المشارك من السحب."""
    query = update.callback_query
    try:
        _, gw_code, uid_raw = query.data.split(":", 2)
        target_user_id = int(uid_raw)
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["owner_id"] != query.from_user.id:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return

    remove_giveaway_participant(gw_code, target_user_id)
    total = count_giveaway_participants(gw_code)
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=giveaway["chat_id"],
            message_id=giveaway["channel_message_id"],
            reply_markup=build_giveaway_channel_keyboard(
                gw_code, total, antispam=bool(giveaway["antispam"]), status=giveaway["status"],
            ),
        )
    except Exception:
        pass

    await query.answer("🚫 تم استبعاد المشارك من السحب.", show_alert=True)
    try:
        await query.message.delete()
    except Exception:
        pass


async def gw_repost_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «↻ إعادة نشر» — ينشر نسخة جديدة من منشور السحب في نفس القناة/القروب."""
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["owner_id"] != query.from_user.id:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return

    await query.answer()
    total = count_giveaway_participants(gw_code)
    cliche_entities = json_to_entities(giveaway["cliche_entities"])
    vote_contest_code = giveaway.get("vote_contest_code")
    vote_participant_id = giveaway.get("vote_participant_id")
    vote_link = (
        build_giveaway_vote_condition_link(vote_contest_code, vote_participant_id)
        if vote_contest_code and vote_participant_id else None
    )
    condition_channels = giveaway.get("condition_channels") or []
    boost_link = (
        await build_giveaway_boost_link(context, giveaway["chat_id"])
        if giveaway.get("boost_required") else ""
    )
    post_text, post_entities = build_giveaway_channel_message(
        giveaway["cliche_text"], cliche_entities, gw_code=gw_code, vote_link=vote_link,
        condition_channels=condition_channels, boost_link=boost_link,
    )
    post_keyboard = build_giveaway_channel_keyboard(
        gw_code, total, antispam=bool(giveaway["antispam"]), status=giveaway["status"],
    )
    old_message_id = giveaway.get("channel_message_id")
    try:
        sent = await context.bot.send_message(
            chat_id=giveaway["chat_id"],
            text=post_text,
            entities=post_entities,
            reply_markup=post_keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        set_giveaway_channel_message(gw_code, sent.message_id)
    except Exception:
        await query.message.reply_text("⚠️ تعذر إعادة نشر السحب، تأكد من أن البوت مايزال مشرفًا هناك.")
        return

    # حذف النسخة السابقة من منشور السحب حتى لا يبقى أكثر من نسخة منشورة في
    # نفس الوقت — تبقى فقط أحدث نسخة (التي أُرسلت للتو) ظاهرة في القناة/القروب.
    if old_message_id and old_message_id != sent.message_id:
        try:
            await context.bot.delete_message(chat_id=giveaway["chat_id"], message_id=old_message_id)
        except Exception:
            pass


async def gw_pause_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج ضغط زر «ايقاف وسحب» — يوقف استقبال مشاركات جديدة في السحب فقط (حالة
    "paused")، ولا يسحب الفائزين بعد. يتحوّل نفس الزر إلى «استئناف المشاركة»
    (أخضر) والزر الآخر إلى «ابدا السحب» (أحمر)، وهو الزر الذي يقوم فعليًا
    باختيار الفائزين (انظر gw_draw_callback).
    """
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["owner_id"] != query.from_user.id:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return
    if giveaway["status"] != "open":
        await query.answer("⚠️ هذا السحب متوقف بالفعل.", show_alert=True)
        return

    await query.answer("⏸ تم إيقاف استقبال المشاركات.")
    set_giveaway_status(gw_code, "paused")
    total = count_giveaway_participants(gw_code)
    new_keyboard = build_giveaway_channel_keyboard(
        gw_code, total, antispam=bool(giveaway["antispam"]), status="paused",
    )
    try:
        await query.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass


async def gw_resume_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج ضغط زر «استئناف المشاركة» — يعيد فتح باب المشاركة في السحب بعد إيقافه
    مؤقتًا، ويعيد الكيبورد لحالته الأصلية («ايقاف وسحب» / «ذكرني اذا فزت»).
    لا يمكن لأحد الضغط على هذا الزر سوى صاحب السحب (owner_id).
    """
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["owner_id"] != query.from_user.id:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return
    if giveaway["status"] != "paused":
        await query.answer("⚠️ لا يمكن استئناف هذا السحب في حالته الحالية.", show_alert=True)
        return

    await query.answer("▶️ تم استئناف المشاركة.")
    set_giveaway_status(gw_code, "open")
    total = count_giveaway_participants(gw_code)
    new_keyboard = build_giveaway_channel_keyboard(
        gw_code, total, antispam=bool(giveaway["antispam"]), status="open",
    )
    try:
        await query.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception:
        pass


_GW_DRAW_STATE = {}


# ---------------------------------------------------------------------------
# 📣 الإذاعة (قسم المالك) — إرسال رسالة (نص/صورة/فيديو/ملف) لكل مستخدمي البوت،
# مع إمكانية إيقافها أثناء التنفيذ وعرض إحصائيات آخر عملية إرسال.
# ---------------------------------------------------------------------------

_BROADCAST_STATE = {
    "running": False,
    "stop_requested": False,
    "content_type": None,
    "total": 0,
    "sent": 0,
    "failed": 0,
    "started_at": None,
    "finished_at": None,
    "status": "idle",
}


def get_broadcast_target_user_ids() -> list:
    """يعيد معرفات كل مستخدمي البوت غير المحظورين — هدف الإذاعة."""
    ids = []
    for doc in fs_db().collection("users").stream():
        data = doc.to_dict() or {}
        if not data.get("has_started") or data.get("banned"):
            continue
        try:
            ids.append(int(doc.id))
        except (TypeError, ValueError):
            continue
    return ids


def save_broadcast_stats() -> None:
    """يحفظ حالة الإذاعة الحالية في Firestore لتبقى متاحة حتى بعد انتهائها أو إعادة تشغيل البوت."""
    fs_db().collection("broadcasts").document("current").set({
        "status": _BROADCAST_STATE["status"],
        "content_type": _BROADCAST_STATE["content_type"],
        "started_at": _BROADCAST_STATE["started_at"],
        "finished_at": _BROADCAST_STATE["finished_at"],
        "total": _BROADCAST_STATE["total"],
        "sent": _BROADCAST_STATE["sent"],
        "failed": _BROADCAST_STATE["failed"],
    })


def get_broadcast_stats() -> dict:
    """يعيد حالة الإذاعة الحالية (إن كانت قيد التنفيذ الآن من الذاكرة)، وإلا آخر
    حالة محفوظة في Firestore."""
    if _BROADCAST_STATE["running"]:
        return dict(_BROADCAST_STATE)
    doc = fs_db().collection("broadcasts").document("current").get()
    if doc.exists:
        data = doc.to_dict() or {}
        data["running"] = False
        data.setdefault("status", "idle")
        return data
    return dict(_BROADCAST_STATE)


# ---------------------------------------------------------------------------
# 🗒️ سجل الإذاعات — يحفظ كل عملية إذاعة كسجل مستقل (بخلاف broadcasts/current
# الذي يعكس آخر حالة فقط)، ليتمكن المالك من مراجعة كل الإذاعات السابقة،
# حذف أي سجل منها، أو تعديل النص/التعليق المؤرشف لتصحيح خطأ فيه.
# ---------------------------------------------------------------------------

def broadcast_status_label(status: str) -> str:
    """يستخدم نفس تسميات BROADCAST_STATUS_LABELS المعرَّفة مع واجهات قسم
    الإذاعة، مع إضافة قيمة افتراضية لأي حالة غير متوقعة."""
    return BROADCAST_STATUS_LABELS.get(status, status or "-")


def create_broadcast_log(content_type: str, owner_id: int, total: int,
                          text: str = None, caption: str = None) -> str:
    ref = fs_db().collection("broadcast_logs").document()
    ref.set({
        "log_id": ref.id,
        "content_type": content_type,
        "owner_id": owner_id,
        "text": text,
        "caption": caption,
        "total": total,
        "sent": 0,
        "failed": 0,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "message_refs": [],
        "actual_deleted": False,
        "actual_deleted_count": 0,
        "actual_delete_failed": 0,
    })
    return ref.id


def update_broadcast_log(log_id: str, **fields) -> None:
    if not log_id:
        return
    try:
        fs_db().collection("broadcast_logs").document(log_id).update(fields)
    except Exception:
        pass


def get_broadcast_log(log_id: str):
    doc = fs_db().collection("broadcast_logs").document(log_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    data["log_id"] = doc.id
    return data


def get_broadcast_logs(limit: int = 50) -> list:
    """يعيد كل سجلات الإذاعات مرتّبة تنازليًا (الأحدث أولاً)."""
    docs = fs_db().collection("broadcast_logs").stream()
    rows = []
    for d in docs:
        data = d.to_dict()
        data["log_id"] = d.id
        rows.append(data)
    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows[:limit]


def delete_broadcast_log(log_id: str) -> None:
    fs_db().collection("broadcast_logs").document(log_id).delete()


async def delete_broadcast_actual_messages(context: ContextTypes.DEFAULT_TYPE, log_id: str) -> tuple:
    """يحذف فعليًا كل الرسائل التي أُرسلت للمستخدمين ضمن إذاعة معيّنة (وليس
    فقط سجلها المؤرشف)، عبر بيانات message_refs المخزَّنة أثناء run_broadcast.
    يعيد (عدد المحذوف بنجاح، عدد الذي تعذّر حذفه)."""
    log = get_broadcast_log(log_id)
    if not log:
        return 0, 0
    refs = log.get("message_refs") or []
    deleted, failed = 0, 0
    for ref in refs:
        chat_id = ref.get("chat_id")
        message_id = ref.get("message_id")
        if not chat_id or not message_id:
            failed += 1
            continue
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            deleted += 1
        except RetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                deleted += 1
            except Exception:
                failed += 1
        except (BadRequest, Forbidden):
            # الرسالة محذوفة مسبقًا، أو المستخدم حظر البوت، أو انقضى وقت
            # طويل جدًا على الرسالة — تُحتسب كفشل غير حرج.
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    update_broadcast_log(
        log_id, actual_deleted=True, actual_deleted_count=deleted, actual_delete_failed=failed,
    )
    return deleted, failed


def edit_broadcast_log_content(log_id: str, new_text: str) -> bool:
    """يعدّل النص/التعليق المؤرشف لسجل إذاعة سابقة فقط (تصحيح الأرشيف) —
    لا يعيد إرسال أي شيء للمستخدمين، فالإذاعة الفعلية تمت بالفعل."""
    log = get_broadcast_log(log_id)
    if not log:
        return False
    field = "text" if log.get("content_type") == "text" else "caption"
    fs_db().collection("broadcast_logs").document(log_id).update({field: new_text})
    return True


async def run_broadcast(context: ContextTypes.DEFAULT_TYPE, content_type: str, owner_id: int,
                         source_chat_id: int, source_message_id: int,
                         text: str = None, caption: str = None) -> None:
    """يرسل محتوى الإذاعة لكل المستخدمين المستهدفين واحدًا تلو الآخر، مع احترام
    حدود تيليجرام (RetryAfter) وإمكانية الإيقاف من زر «⏹️ إيقاف الإذاعة».

    يعتمد على copy_message بدل send_message/send_photo/... المتخصصة: هذا يجعل
    الإذاعة تدعم أي نوع محتوى يقبله تيليجرام تلقائيًا (نص، صورة، فيديو، ملف،
    صوت، رسالة صوتية، GIF، ملصق، فيديو دائري، استطلاع...) دون فقدان أي تنسيق
    أو وسائط، ودون الحاجة لكتابة فرع send_* منفصل لكل نوع جديد — فالرسالة
    تُنسخ كما هي حرفيًا من محادثة المالك مع البوت (source_chat_id/source_message_id)
    إلى كل مستخدم مستهدف."""
    user_ids = get_broadcast_target_user_ids()
    log_admin_action(
        "broadcast", owner_id, details=f"نوع المحتوى: {content_type} — عدد المستهدفين: {len(user_ids)}",
    )
    log_id = create_broadcast_log(content_type, owner_id, len(user_ids), text=text, caption=caption)
    _BROADCAST_STATE.update({
        "running": True,
        "stop_requested": False,
        "content_type": content_type,
        "total": len(user_ids),
        "sent": 0,
        "failed": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "log_id": log_id,
    })
    save_broadcast_stats()

    # نخزّن (chat_id, message_id) لكل رسالة أُرسلت فعليًا حتى يمكن لاحقًا حذفها
    # فعليًا من عند المستخدمين (وليس فقط حذف سجلها من الأرشيف) عبر
    # delete_broadcast_actual_messages.
    message_refs = []

    for uid in user_ids:
        if _BROADCAST_STATE["stop_requested"]:
            break
        for attempt in range(2):
            try:
                sent_msg = await context.bot.copy_message(
                    chat_id=uid, from_chat_id=source_chat_id, message_id=source_message_id,
                )
                _BROADCAST_STATE["sent"] += 1
                if sent_msg is not None:
                    message_refs.append({"chat_id": uid, "message_id": sent_msg.message_id})
                break
            except RetryAfter as exc:
                if attempt == 0 and exc.retry_after <= 10:
                    await asyncio.sleep(exc.retry_after)
                    continue
                _BROADCAST_STATE["failed"] += 1
                break
            except Exception:
                _BROADCAST_STATE["failed"] += 1
                break
        await asyncio.sleep(0.05)
        if (_BROADCAST_STATE["sent"] + _BROADCAST_STATE["failed"]) % 50 == 0:
            save_broadcast_stats()
            update_broadcast_log(
                log_id, sent=_BROADCAST_STATE["sent"], failed=_BROADCAST_STATE["failed"],
                message_refs=message_refs,
            )

    _BROADCAST_STATE["running"] = False
    _BROADCAST_STATE["finished_at"] = datetime.now(timezone.utc).isoformat()
    _BROADCAST_STATE["status"] = "stopped" if _BROADCAST_STATE["stop_requested"] else "completed"
    save_broadcast_stats()
    update_broadcast_log(
        log_id, status=_BROADCAST_STATE["status"], sent=_BROADCAST_STATE["sent"],
        failed=_BROADCAST_STATE["failed"], finished_at=_BROADCAST_STATE["finished_at"],
        message_refs=message_refs,
    )
    try:
        summary = (
            "⏹️ تم إيقاف الإذاعة يدويًا." if _BROADCAST_STATE["status"] == "stopped"
            else "✅ اكتملت الإذاعة."
        )
        # زر سريع لحذف الإذاعة فعليًا من عند الجميع مباشرة من رسالة التلخيص،
        # دون الحاجة للذهاب إلى «🗒️ سجل الإذاعات» يدويًا.
        delete_keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗑️ حذف هذه الإذاعة من الجميع",
                                  callback_data=f"broadcast_logs:delete_actual:{log_id}:1", style="danger"),
        ]]) if message_refs else None
        await context.bot.send_message(
            chat_id=owner_id,
            text=f"{summary}\n📤 تم الإرسال: {_BROADCAST_STATE['sent']}\n⚠️ فشل: {_BROADCAST_STATE['failed']}",
            reply_markup=delete_keyboard,
        )
    except Exception:
        pass


def build_gw_draw_result_keyboard(gw_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ اختيار فائز آخر", callback_data=f"gw_reroll:{gw_code}", style="success")],
    ])


async def notify_giveaway_winner(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    """يرسل رسالة خاصة تصل للفائز فقط، بنفس تصميم/زخرفة وخط البوت العريض.
    اسم القناة يظهر كرابط أزرق قابل للضغط يفتح القناة مباشرة، لمساعدة الفائز
    على الدخول إليها فورًا."""
    channel_label = "القناة"
    channel_url = ""
    try:
        chat = await context.bot.get_chat(chat_id)
        channel_label = chat.title or "القناة"
        if chat.username:
            channel_url = f"https://t.me/{chat.username}"
    except Exception:
        pass
    if not channel_url:
        channel_url = await build_channel_join_link(context.bot, chat_id)
    channel_part = (channel_label, "link", channel_url) if channel_url else channel_label
    try:
        text, entities = build_text_with_emojis([
            ([
                ("🎉", EMOJI["party"]),
                " مبروك! أنت أحد الفائزين في السحب في قناة ",
                channel_part,
                " ",
                ("🏆", EMOJI["trophy_win"]),
            ], "bold", None),
        ])
        await context.bot.send_message(chat_id=user_id, text=text, entities=entities)
    except Exception:
        pass


async def _execute_giveaway_draw(context: ContextTypes.DEFAULT_TYPE, gw_code: str, giveaway,
                                  disable_original_keyboard: bool = True) -> list:
    """المنطق المشترك لتنفيذ سحب الفائزين فعليًا (يقفل السحب، يختار الفائزين
    عشوائيًا، وينشر منشور النتيجة). يُستخدم من:
    - gw_draw_callback (بعد ضغط «ابدا السحب» يدويًا).
    - finish_giveaway_auto (عند اكتمال السحب التلقائي — عدد أو وقت — دون أي
      ضغط يدوي لزر «ايقاف وسحب» أولًا).
    """
    set_giveaway_status(gw_code, "closed")
    participants = get_giveaway_participants(gw_code)
    winners_count = giveaway["winners_count"] or 1
    winners = random.sample(participants, min(winners_count, len(participants))) if participants else []
    remaining_pool = [p for p in participants if p not in winners]

    cliche_entities = json_to_entities(giveaway["cliche_entities"])
    end_text, end_entities = build_giveaway_ended_message(giveaway["cliche_text"], cliche_entities, winners)
    sent_message = None
    try:
        sent_message = await context.bot.send_message(
            chat_id=giveaway["chat_id"], text=end_text, entities=end_entities,
            reply_markup=build_gw_draw_result_keyboard(gw_code),
        )
    except Exception:
        pass

    if disable_original_keyboard and giveaway.get("channel_message_id"):
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=giveaway["chat_id"], message_id=giveaway["channel_message_id"], reply_markup=None,
            )
        except Exception:
            pass

    _GW_DRAW_STATE[gw_code] = {
        "winners": winners,
        "pool": remaining_pool,
        "chat_id": giveaway["chat_id"],
        "message_id": sent_message.message_id if sent_message else None,
        "cliche_text": giveaway["cliche_text"],
        "cliche_entities": giveaway["cliche_entities"],
        "owner_id": giveaway["owner_id"],
    }
    return winners


async def finish_giveaway_auto(context: ContextTypes.DEFAULT_TYPE, gw_code: str):
    """يُستدعى تلقائيًا فور اكتمال شرط «سحب تلقائي» (عدد المشاركين المطلوب أو
    انقضاء الوقت المحدد) — دون انتظار ضغط «ايقاف وسحب» يدويًا أولًا."""
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["status"] != "open":
        return
    winners = await _execute_giveaway_draw(context, gw_code, giveaway, disable_original_keyboard=True)
    for user_id, _name in winners:
        await notify_giveaway_winner(context, user_id, giveaway["chat_id"])


async def giveaway_autospin_time_job(context: ContextTypes.DEFAULT_TYPE):
    gw_code = context.job.data
    try:
        await finish_giveaway_auto(context, gw_code)
    except Exception:
        logger.exception("giveaway_autospin_time_job: فشل تنفيذ السحب التلقائي %s", gw_code)


def schedule_giveaway_autospin_time(job_queue, gw_code: str, delay_seconds: float):
    """يجدول تنفيذ السحب التلقائي فعليًا عند انقضاء الوقت المحدد (Image 9) —
    بنفس آلية schedule_contest_time_end تمامًا."""
    if delay_seconds is None:
        return
    if job_queue is None:
        logger.error(
            "schedule_giveaway_autospin_time: job_queue غير متاحة — لن يُنفَّذ السحب التلقائي %s! "
            "تأكد من تثبيت المكتبة عبر: pip install \"python-telegram-bot[job-queue]\"",
            gw_code,
        )
        return
    job_queue.run_once(
        giveaway_autospin_time_job,
        when=max(delay_seconds, 1),
        data=gw_code,
        name=f"gw_autospin_end_{gw_code}",
    )
    logger.info("schedule_giveaway_autospin_time: تمت جدولة السحب التلقائي %s بعد %.0f ثانية",
                gw_code, delay_seconds)


async def reschedule_pending_giveaway_timers(app):
    """يُستدعى عند إقلاع البوت لإعادة جدولة مؤقتات «سحب تلقائي - وقت محدد» المفتوحة
    (بعد أي إعادة تشغيل)، بنفس آلية reschedule_pending_contest_timers."""
    now = datetime.now(timezone.utc)
    for giveaway in get_open_time_giveaways():
        end_at = giveaway_autospin_end_datetime(giveaway)
        remaining = (end_at - now).total_seconds()
        if remaining <= 0:
            class _Ctx:
                bot = app.bot
            await finish_giveaway_auto(_Ctx(), giveaway["gw_code"])
        else:
            schedule_giveaway_autospin_time(app.job_queue, giveaway["gw_code"], remaining)


async def giveaway_autospin_countdown_tick(context: ContextTypes.DEFAULT_TYPE):
    """يعمل كل 10 دقائق (Image 9): يحدّث جملة العد التنازلي المعروضة داخل كل
    منشور سحب مفعّل عليه «سحب تلقائي - وقت محدد» ولا يزال مفتوحًا، ويُنهي فورًا
    أي سحب انقضى وقته فعليًا كخط أمان إضافي (احتياطًا لأي تعارض توقيت مع
    المؤقت الفردي run_once)."""
    for giveaway in get_open_time_giveaways():
        gw_code = giveaway["gw_code"]
        end_at = giveaway_autospin_end_datetime(giveaway)
        remaining = (end_at - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            try:
                await finish_giveaway_auto(context, gw_code)
            except Exception:
                logger.exception("giveaway_autospin_countdown_tick: فشل إنهاء السحب %s", gw_code)
            continue
        if not giveaway.get("channel_message_id"):
            continue
        try:
            cliche_entities = json_to_entities(giveaway["cliche_entities"])
            vote_contest_code = giveaway.get("vote_contest_code")
            vote_participant_id = giveaway.get("vote_participant_id")
            vote_link = (
                build_giveaway_vote_condition_link(vote_contest_code, vote_participant_id)
                if vote_contest_code and vote_participant_id else None
            )
            boost_link = (
                await build_giveaway_boost_link(context, giveaway["chat_id"])
                if giveaway.get("boost_required") else ""
            )
            post_text, post_entities = build_giveaway_channel_message(
                giveaway["cliche_text"], cliche_entities, gw_code=gw_code, vote_link=vote_link,
                condition_channels=giveaway.get("condition_channels") or [],
                boost_link=boost_link,
                autospin={"mode": "time", "notice_text": build_giveaway_autospin_notice_text(giveaway)},
            )
            await context.bot.edit_message_text(
                chat_id=giveaway["chat_id"], message_id=giveaway["channel_message_id"],
                text=post_text, entities=post_entities,
                reply_markup=build_giveaway_channel_keyboard(
                    gw_code, count_giveaway_participants(gw_code),
                    antispam=bool(giveaway.get("antispam", False)), status=giveaway["status"],
                ),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
        except Exception:
            pass


async def gw_draw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج ضغط زر «ابدا السحب» — يقفل السحب نهائيًا ويختار عدد الفائزين المحدد
    مسبقًا (winners_count) عشوائيًا من بين المشاركين. لا يظهر هذا الزر إلا بعد
    إيقاف استقبال المشاركات (gw_pause)، ولا يمكن لأحد الضغط عليه سوى صاحب السحب.
    """
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    giveaway = get_giveaway(gw_code)
    if not giveaway or giveaway["owner_id"] != query.from_user.id:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return
    if giveaway["status"] != "paused":
        await query.answer("⚠️ يجب إيقاف استقبال المشاركات أولًا من زر «ايقاف وسحب».", show_alert=True)
        return

    await query.answer("🎲 جارٍ سحب الفائزين...")
    winners = await _execute_giveaway_draw(context, gw_code, giveaway, disable_original_keyboard=False)
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    for user_id, _name in winners:
        await notify_giveaway_winner(context, user_id, giveaway["chat_id"])


async def gw_reroll_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج ضغط زر «➕ اختيار فائز آخر» — يضيف فائزًا إضافيًا عشوائيًا للقائمة الحالية."""
    query = update.callback_query
    gw_code = query.data.split(":", 1)[1]
    state = _GW_DRAW_STATE.get(gw_code)
    if not state:
        await query.answer("⚠️ انتهت صلاحية هذه القائمة.", show_alert=True)
        return
    if query.from_user.id != state["owner_id"] and query.from_user.id not in ADMIN_IDS:
        await query.answer("⚠️ لا تملك صلاحية القيام بهذا.", show_alert=True)
        return
    if not state["pool"]:
        await query.answer("⚠️ لا يوجد مشاركون إضافيون لاختيارهم.", show_alert=True)
        return

    await query.answer("🎲 جارٍ اختيار فائز جديد...")
    new_winner = random.choice(state["pool"])
    state["pool"].remove(new_winner)
    state["winners"].append(new_winner)

    cliche_entities = json_to_entities(state["cliche_entities"])
    end_text, end_entities = build_giveaway_ended_message(state["cliche_text"], cliche_entities, state["winners"])
    try:
        await context.bot.edit_message_text(
            chat_id=state["chat_id"], message_id=state["message_id"],
            text=end_text, entities=end_entities,
            reply_markup=build_gw_draw_result_keyboard(gw_code),
        )
    except Exception:
        pass

    await notify_giveaway_winner(context, new_winner[0], state["chat_id"])


def contest_end_datetime(contest) -> datetime:
    """يحسب موعد انتهاء مسابقة معتمدة على وقت محدد (created_at + time_minutes)."""
    created = datetime.fromisoformat(contest["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    minutes = contest["time_minutes"] or 0
    return created + timedelta(minutes=minutes)


async def finish_contest_by_time(bot, contest_code: str):
    """
    يُستدعى تلقائيًا عند انقضاء الوقت المحدد للمسابقة:
    - يقفل المسابقة، يحدد الفائز/الفائزين (الأعلى أصواتًا)، وينشر منشورًا جديدًا منفصلًا
      يعرض نتيجة المسابقة (فائز واحد أو أكثر) — دون تعديل منشور المشاركة الأصلي في القناة/القروب.
    """
    contest = get_contest(contest_code)
    if not contest or contest["status"] != "open":
        return

    fs_db().collection("contests").document(contest_code).update({
        "status": "ended",
        "ended_at": datetime.now(timezone.utc).isoformat(),
    })
    contest["status"] = "ended"
    if _OPEN_CONTEST_CODES is not None:
        _OPEN_CONTEST_CODES.discard(contest_code)

    leaderboard = get_contest_leaderboard(contest_code)
    winners_count = contest["winners_count"] or 1
    winners = leaderboard[:winners_count]

    ended_text, ended_entities = build_contest_ended_message(contest["cliche_text"], None, winners)
    ended_keyboard = build_contest_ended_keyboard(contest_code)

    try:
        await bot.send_message(
            chat_id=contest["chat_id"],
            text=ended_text,
            entities=ended_entities,
            reply_markup=ended_keyboard,
        )
    except Exception as exc:
        logger.warning("finish_contest_by_time: فشل نشر منشور النتيجة الجديد للمسابقة %s: %s",
                        contest_code, exc)
        stripped = [e for e in (ended_entities or []) if getattr(e, "type", None) != MessageEntity.CUSTOM_EMOJI]
        if len(stripped) != len(ended_entities or []):
            try:
                await bot.send_message(
                    chat_id=contest["chat_id"],
                    text=ended_text,
                    entities=stripped,
                    reply_markup=ended_keyboard,
                )
            except Exception as exc2:
                logger.error("finish_contest_by_time: فشلت المحاولة الاحتياطية أيضًا: %s", exc2)

    if contest["announce_results"]:
        results_text, results_entities = build_contest_results_message(leaderboard, winners_count)
        try:
            await bot.send_message(
                chat_id=contest["chat_id"],
                text=results_text,
                entities=results_entities,
            )
        except Exception:
            pass

    if contest["notify_win"] and winners:
        contest_channel_label = "القناة"
        contest_channel_url = ""
        try:
            contest_chat = await bot.get_chat(contest["chat_id"])
            contest_channel_label = contest_chat.title or "القناة"
            if contest_chat.username:
                contest_channel_url = f"https://t.me/{contest_chat.username}"
        except Exception:
            pass
        if not contest_channel_url:
            contest_channel_url = await build_channel_join_link(bot, contest["chat_id"])
        contest_channel_part = (
            (contest_channel_label, "link", contest_channel_url) if contest_channel_url else contest_channel_label
        )
        for user_id, name, _, votes in winners:
            try:
                text, entities = build_text_with_emojis([
                    ([
                        ("🎉", EMOJI["party"]),
                        " مبروك! لقد فزت في المسابقة في قناة ",
                        contest_channel_part,
                        f" بإسم: {name}",
                    ], "bold", None),
                    "\n\n",
                    f"عدد أصواتك: {format_votes_label(votes)}",
                ])
                await bot.send_message(chat_id=user_id, text=text, entities=entities)
            except Exception:
                pass


async def contest_time_end_job(context: ContextTypes.DEFAULT_TYPE):
    contest_code = context.job.data
    try:
        await finish_contest_by_time(context.bot, contest_code)
    except Exception:
        logger.exception("contest_time_end_job: فشل إنهاء المسابقة %s تلقائيًا", contest_code)


def schedule_contest_time_end(job_queue, contest_code: str, delay_seconds: float):
    if delay_seconds is None:
        return
    if job_queue is None:
        logger.error(
            "schedule_contest_time_end: job_queue غير متاحة — لن تُنهى المسابقة %s تلقائيًا! "
            "تأكد من تثبيت المكتبة عبر: pip install \"python-telegram-bot[job-queue]\"",
            contest_code,
        )
        return
    job_queue.run_once(
        contest_time_end_job,
        when=max(delay_seconds, 1),
        data=contest_code,
        name=f"contest_end_{contest_code}",
    )
    logger.info("schedule_contest_time_end: تمت جدولة إنهاء المسابقة %s بعد %.0f ثانية",
                contest_code, delay_seconds)


async def reschedule_pending_contest_timers(app):
    """يُستدعى عند إقلاع البوت لإعادة جدولة مؤقتات المسابقات المفتوحة (بعد أي إعادة تشغيل)."""
    now = datetime.now(timezone.utc)
    for contest in get_open_time_contests():
        end_at = contest_end_datetime(contest)
        remaining = (end_at - now).total_seconds()
        if remaining <= 0:
            await finish_contest_by_time(app.bot, contest["contest_code"])
        else:
            schedule_contest_time_end(app.job_queue, contest["contest_code"], remaining)


async def contest_results_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج زر «عرض النتائج» أسفل منشور نهاية المسابقة — متاح لمشرفي القناة/القروب فقط."""
    query = update.callback_query
    contest_code = query.data.split(":", 1)[1]

    contest = get_contest(contest_code)
    if not contest:
        await query.answer("⚠️ هذه المسابقة لم تعد متاحة.", show_alert=True)
        return

    is_admin = False
    try:
        member = await context.bot.get_chat_member(contest["chat_id"], query.from_user.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as exc:
        logger.warning("contest_results_callback: get_chat_member failed for chat=%s user=%s: %s",
                        contest["chat_id"], query.from_user.id, exc)

    if not is_admin:
        await query.answer("❌ عرض النتائج في القناة متاح لمشرفي القناة فقط.", show_alert=True)
        return

    await query.answer()

    leaderboard = get_contest_leaderboard(contest_code)
    winners_count = contest["winners_count"] or 1

    text, entities = build_contest_results_message(leaderboard, winners_count)
    try:
        await query.message.reply_text(text=text, entities=entities)
    except Exception as exc:
        logger.warning("contest_results_callback: reply_text failed: %s", exc)


async def contest_participation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج أزرار: رفض/قبول المشاركة، وسحب الاسم من المسابقة."""
    query = update.callback_query
    try:
        await _contest_participation_callback_inner(update, context)
    except Exception:
        try:
            await query.answer("⚠️ حدث خطأ غير متوقع، حاول مرة أخرى.", show_alert=True)
        except Exception:
            pass
        raise


async def safe_edit_message_text(query, text, entities=None, reply_markup=None):
    """
    إرسال/تعديل نص مع كيانات (entities) مع شبكة أمان: إن رفض تيليجرام الرسالة (400 Bad
    Request) — غالبًا بسبب إيموجي مخصص (custom_emoji_id) غير صالح أو غير متاح لهذا البوت —
    نسجّل الخطأ الحقيقي كاملًا، ثم نعيد المحاولة بعد حذف كيانات CUSTOM_EMOJI فقط (نُبقي على
    باقي التنسيق) حتى تصل الرسالة للمستخدم دائمًا بدل أن تبقى الشاشة القديمة ظاهرة.
    """
    try:
        await query.edit_message_text(text=text, entities=entities, reply_markup=reply_markup)
        return True
    except Exception as exc:
        logger.warning("safe_edit_message_text: المحاولة الأولى فشلت: %s", exc)

    stripped = [e for e in (entities or []) if getattr(e, "type", None) != MessageEntity.CUSTOM_EMOJI]
    if len(stripped) != len(entities or []):
        try:
            await query.edit_message_text(text=text, entities=stripped, reply_markup=reply_markup)
            logger.info("safe_edit_message_text: نجحت المحاولة الثانية بعد حذف الإيموجي المخصص.")
            return True
        except Exception as exc:
            logger.warning("safe_edit_message_text: فشلت المحاولة الثانية أيضًا: %s", exc)

    try:
        await query.edit_message_text(text=text)
        logger.info("safe_edit_message_text: نجحت المحاولة الثالثة (نص عادي بلا تنسيق).")
        return True
    except Exception as exc:
        logger.error("safe_edit_message_text: فشلت كل المحاولات: %s", exc)
        return False


async def _contest_participation_callback_inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("comp_reject_join:"):
        await query.answer()
        _bt, _be = bold_notice("❌ تم إلغاء المشاركة في المسابقة.")
        await query.edit_message_text(text=_bt, entities=_be)
        return

    if data.startswith("comp_confirm_join:"):
        # ⚡ is_genuinely_new تُقرأ من callback_data (مُمرَّرة من start() عبر
        # handle_contest_join_entry) بدل إعادة استدعاء register_bot_user_and_check_new
        # هنا — فالمستخدم مسجَّل بالفعل منذ فتح البوت عبر رابط compjoin_، وإعادة
        # الاستدعاء كانت تُعيد False دومًا فتُفقَد مكافأة كل مستخدم جديد فعليًا.
        parts = data.split(":", 2)
        contest_code = parts[1]
        is_genuinely_new = len(parts) > 2 and parts[2] == "1"
        user = query.from_user
        if is_genuinely_new:
            await _notify_new_user_join(context, user)

        contest = get_contest(contest_code)
        if not contest:
            await query.answer("⚠️ هذه المسابقة لم تعد متاحة.", show_alert=True)
            return

        existing = get_contest_participant(contest_code, user.id)
        if existing:
            await query.answer()
            text, entities = build_contest_registered_message(existing["display_name"], existing["participant_code"])
            await safe_edit_message_text(
                query, text, entities,
                reply_markup=build_contest_registered_keyboard(
                    contest_code, user.id, existing["participant_code"]
                ),
            )
            return

        if contest["status"] != "open":
            await query.answer("⚠️ هذه المسابقة لم تعد متاحة.", show_alert=True)
            return
        current = count_contest_participants(contest_code)
        if current >= contest["target_count"]:
            await query.answer("⚠️ اكتمل عدد المشاركين المسموح في هذه المسابقة.", show_alert=True)
            return

        # طبقة حماية إضافية: قد يكون المستخدم قد غادر قناة المسابقة بين خطوة
        # «تأكيد المشاركة» وضغط «قبول»، لذا يُعاد التحقق الفعلي من عضويته هنا
        # أيضًا قبل تسجيله نهائيًا، بدل الاعتماد فقط على الفحص السابق.
        if not await check_contest_channel_subscription(context, user.id, contest, force_refresh=True):
            join_url = await build_contest_channel_join_link(context, contest["chat_id"])
            gate_text, gate_entities = build_contest_channel_gate_message()
            await query.answer(
                "❌ يجب عليك الانضمام إلى قناة المسابقة أولاً", show_alert=True,
            )
            await safe_edit_message_text(
                query, gate_text, gate_entities,
                reply_markup=build_contest_channel_gate_keyboard(contest_code, join_url),
            )
            return

        display_name = user.first_name or user.username or str(user.id)

        # خاصية «موافقة المشاركات»: إن كانت مفعّلة لهذه المسابقة، لا يُسجَّل
        # المستخدم مباشرة، بل يُحفظ طلبه في الذاكرة فقط (بلا أي قراءة/كتابة
        # لقاعدة البيانات هنا) ويُرسَل لصاحب المسابقة لمراجعته. التسجيل
        # الفعلي في قاعدة البيانات يحدث فقط بعد ضغط صاحب المسابقة «قبول».
        if contest.get("approve_participants"):
            await query.answer()
            _CONTEST_PENDING_JOIN_REQUESTS[(contest_code, user.id)] = {
                "display_name": display_name,
                "username": user.username,
            }
            pending_text, pending_entities = build_contest_join_pending_message()
            await safe_edit_message_text(query, pending_text, pending_entities)

            owner_text, owner_entities = build_contest_join_request_owner_message(
                display_name, user.username, user.id
            )
            try:
                await context.bot.send_message(
                    chat_id=contest["owner_id"],
                    text=owner_text,
                    entities=owner_entities,
                    reply_markup=build_contest_join_request_owner_keyboard(contest_code, user.id),
                )
            except Exception:
                logger.exception("تعذّر إرسال طلب المشاركة إلى صاحب المسابقة %s", contest.get("owner_id"))
            return

        await query.answer()

        participant_code = generate_participant_code(contest_code)
        try:
            add_contest_participant(contest_code, user.id, display_name, participant_code)
            if is_genuinely_new:
                try:
                    bump_channel_new_users(contest["chat_id"])
                except Exception:
                    logger.exception("تعذّر تحديث عدّاد المستخدمين الجدد لقناة المسابقة %s", contest.get("chat_id"))
                # 💎 نفس آلية مكافأة "مستخدم جديد" المستخدمة في السحوبات (مرة واحدة
                # عالميًا لكل مستخدم عبر حقل rewarded الذري)، مطبَّقة الآن أيضًا على
                # مشاركة مستخدم جديد فعليًا في مسابقة — منح واحد فقط لصاحب المسابقة.
                try:
                    reward_contest_new_participant(
                        user.id, contest_code, contest["owner_id"], contest["chat_id"],
                    )
                except Exception:
                    logger.exception("تعذّر منح نقاط المستخدم الجديد لصاحب المسابقة %s", contest.get("owner_id"))
        except sqlite3.IntegrityError:
            existing = get_contest_participant(contest_code, user.id)
            if existing:
                display_name = existing["display_name"]
                participant_code = existing["participant_code"]
            else:
                _bt, _be = bold_notice("⚠️ حدث خطأ أثناء تسجيل مشاركتك، حاول مرة أخرى.")
                await query.message.reply_text(text=_bt, entities=_be)
                return

        text, entities = build_contest_registered_message(display_name, participant_code)
        await safe_edit_message_text(
            query, text, entities,
            reply_markup=build_contest_registered_keyboard(contest_code, user.id, participant_code),
        )

        vote_text, vote_entities = build_contest_vote_post_message(display_name)
        try:
            sent = await context.bot.send_message(
                chat_id=contest["chat_id"],
                text=vote_text,
                entities=vote_entities,
                reply_markup=build_contest_vote_keyboard(contest_code, user.id, 0, participant_code),
            )
            set_participant_channel_message(contest_code, user.id, sent.message_id)
        except Exception:
            pass
        return

    if data.startswith("comp_appjoin_ok:") or data.startswith("comp_appjoin_no:"):
        accepted = data.startswith("comp_appjoin_ok:")
        try:
            _, contest_code, user_id_raw = data.split(":", 2)
            target_user_id = int(user_id_raw)
        except (ValueError, IndexError):
            await query.answer("⚠️ طلب غير صالح.", show_alert=True)
            return

        contest = get_contest(contest_code)
        if not contest:
            await query.answer("⚠️ هذه المسابقة لم تعد متاحة.", show_alert=True)
            return
        if query.from_user.id != contest["owner_id"]:
            await query.answer("🚫 هذا القرار متاح فقط لصاحب المسابقة.", show_alert=True)
            return

        pending = _CONTEST_PENDING_JOIN_REQUESTS.pop((contest_code, target_user_id), None)
        if pending is None:
            await query.answer("⚠️ لم يعد هذا الطلب متاحًا (ربما تمت معالجته مسبقًا).", show_alert=True)
            return

        display_name = pending["display_name"]

        if not accepted:
            await query.answer()
            decided_text, decided_entities = build_contest_join_request_decided_owner_message(
                display_name, accepted=False
            )
            await safe_edit_message_text(query, decided_text, decided_entities)
            try:
                reject_text, reject_entities = build_contest_join_rejected_user_message()
                await context.bot.send_message(
                    chat_id=target_user_id, text=reject_text, entities=reject_entities,
                )
            except Exception:
                pass
            return

        existing = get_contest_participant(contest_code, target_user_id)
        if existing:
            await query.answer("✅ هذا المستخدم مسجّل بالفعل في المسابقة.")
            decided_text, decided_entities = build_contest_join_request_decided_owner_message(
                display_name, accepted=True
            )
            await safe_edit_message_text(query, decided_text, decided_entities)
            return

        if contest["status"] != "open":
            await query.answer("⚠️ هذه المسابقة لم تعد متاحة.", show_alert=True)
            return
        current = count_contest_participants(contest_code)
        if current >= contest["target_count"]:
            await query.answer("⚠️ اكتمل عدد المشاركين المسموح في هذه المسابقة بالفعل.", show_alert=True)
            return

        await query.answer()
        participant_code = generate_participant_code(contest_code)
        try:
            add_contest_participant(contest_code, target_user_id, display_name, participant_code)
        except sqlite3.IntegrityError:
            existing = get_contest_participant(contest_code, target_user_id)
            if existing:
                display_name = existing["display_name"]
                participant_code = existing["participant_code"]
            else:
                await query.message.reply_text("⚠️ حدث خطأ أثناء تسجيل المشاركة، حاول مرة أخرى.")
                return

        decided_text, decided_entities = build_contest_join_request_decided_owner_message(
            display_name, accepted=True
        )
        await safe_edit_message_text(query, decided_text, decided_entities)

        try:
            registered_text, registered_entities = build_contest_registered_message(display_name, participant_code)
            await context.bot.send_message(
                chat_id=target_user_id,
                text=registered_text,
                entities=registered_entities,
                reply_markup=build_contest_registered_keyboard(contest_code, target_user_id, participant_code),
            )
        except Exception:
            pass

        vote_text, vote_entities = build_contest_vote_post_message(display_name)
        try:
            sent = await context.bot.send_message(
                chat_id=contest["chat_id"],
                text=vote_text,
                entities=vote_entities,
                reply_markup=build_contest_vote_keyboard(contest_code, target_user_id, 0, participant_code),
            )
            set_participant_channel_message(contest_code, target_user_id, sent.message_id)
        except Exception:
            pass
        return

    if data.startswith("comp_withdraw:"):
        _, contest_code, user_id_raw = data.split(":", 2)
        target_user_id = int(user_id_raw)
        requester = query.from_user

        if requester.id != target_user_id:
            await query.answer("🚫 لا يمكنك سحب مشاركة شخص آخر.", show_alert=True)
            return

        participant = get_contest_participant(contest_code, target_user_id)
        if not participant:
            await query.answer("⚠️ أنت غير مسجّل في هذه المسابقة.", show_alert=True)
            return

        remove_contest_participant(contest_code, target_user_id)
        await query.answer("✅ تم سحب اسمك من المسابقة.")
        _bt, _be = bold_notice("🗑 تم سحب اسمك من المسابقة بنجاح.")
        await query.edit_message_text(text=_bt, entities=_be)

        contest = get_contest(contest_code)
        if contest and participant["channel_message_id"]:
            try:
                await context.bot.delete_message(
                    chat_id=contest["chat_id"],
                    message_id=participant["channel_message_id"],
                )
            except Exception:
                pass
        return


async def remove_contest_participant_for_channel_leave(
    context: ContextTypes.DEFAULT_TYPE, contest, participant, user,
) -> None:
    """يُنفَّذ فور اكتشاف خروج متسابق فعليًا (حدث تيليجرام مباشر) من قناة
    مسابقته: يحذف منشوره الخاص في القناة (بطاقة زر 🤍 وكود المتسابق —
    بنفس ما يفعله «سحب اسمي من المسابقة» يدويًا)، يحذف تسجيله وكل الأصوات
    التي حصل عليها مع عكس نقاط صاحب المسابقة المرتبطة بها (عبر
    remove_contest_participant الموجودة أصلًا)، ثم يُشعر صاحب المسابقة
    بخصم هذا المتسابق تلقائيًا."""
    contest_code = contest["contest_code"]
    message_id = participant.get("channel_message_id")
    if message_id:
        try:
            await context.bot.delete_message(chat_id=contest["chat_id"], message_id=message_id)
        except Exception:
            pass

    remove_contest_participant(contest_code, user.id)
    remaining = count_contest_participants(contest_code)

    display_name = participant.get("display_name") or user.first_name or user.username or str(user.id)
    text, entities = build_contest_participant_left_owner_notify_message(
        display_name, user.id, contest_display_name(contest), remaining,
    )
    try:
        await context.bot.send_message(chat_id=int(contest["owner_id"]), text=text, entities=entities)
    except Exception:
        logger.warning("تعذّر إرسال إشعار خصم متسابق لصاحب المسابقة %s", contest["owner_id"])


async def remove_giveaway_participant_for_channel_leave(
    context: ContextTypes.DEFAULT_TYPE, giveaway, user,
) -> None:
    """نظير remove_contest_participant_for_channel_leave لكن للسحوبات: لا
    يوجد منشور مستقل لكل مشارك هنا (منشور واحد مشترك للسحب يُحدَّث فيه
    العدد فقط، كما في gw_kick_callback عند الاستبعاد اليدوي)، لذا يُكتفى
    بحذف تسجيله وتحديث عدد المشاركين في نفس منشور السحب، ثم إشعار المالك."""
    gw_code = giveaway["gw_code"]
    remove_giveaway_participant(gw_code, user.id)
    total = count_giveaway_participants(gw_code)

    if giveaway.get("channel_message_id"):
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=giveaway["chat_id"],
                message_id=giveaway["channel_message_id"],
                reply_markup=build_giveaway_channel_keyboard(
                    gw_code, total, antispam=bool(giveaway.get("antispam")), status=giveaway["status"],
                ),
            )
        except Exception:
            pass

    display_name = user.first_name or user.username or str(user.id)
    text, entities = build_giveaway_participant_left_owner_notify_message(
        display_name, user.username, user.id, gw_code, total,
    )
    try:
        await context.bot.send_message(chat_id=int(giveaway["owner_id"]), text=text, entities=entities)
    except Exception:
        logger.warning("تعذّر إرسال إشعار خصم مشارك لصاحب السحب %s", giveaway["owner_id"])


async def handle_user_left_hosting_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user) -> None:
    """يُستدعى فور اكتشاف خروج فعلي لمستخدم من أي قناة/قروب البوت مشرف
    فيه (عبر _chat_member_leave_handler أدناه) — يفحص إن كانت هذه القناة
    تستضيف حاليًا مسابقة أو سحبًا مفتوحًا وكان هذا المستخدم مسجَّلًا فيه
    (كمتسابق أو كمشارك)، وعندها يُطبَّق الخصم فورًا في نفس اللحظة، بدل أي
    فحص دوري لاحق. لا يمس هذا نظام الاشتراك الإجباري العام أو تصويتات
    المسابقات (لهما آلياتهما الخاصة المستقلة)."""
    for contest in get_open_contests_by_chat(chat_id):
        participant = get_contest_participant(contest["contest_code"], user.id)
        if participant:
            await remove_contest_participant_for_channel_leave(context, contest, participant, user)

    for giveaway in get_open_giveaways_by_chat(chat_id):
        if is_giveaway_participant(giveaway["gw_code"], user.id):
            await remove_giveaway_participant_for_channel_leave(context, giveaway, user)


def _chat_member_actually_in(member) -> bool:
    """يحدّد إن كانت حالة عضوية معيّنة (ChatMember) تعني أن صاحبها لا يزال
    فعليًا داخل القناة/القروب — بنفس المعيار المستخدم في is_user_subscribed_to_chat
    (member/administrator/creator، أو restricted مع is_member=True)."""
    return member.status in ("member", "administrator", "creator") or (
        member.status == "restricted" and bool(getattr(member, "is_member", False))
    )


async def _chat_member_leave_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج حدث chat_member المباشر من تيليجرام (يصل فقط للقنوات/القروبات
    التي البوت مشرف فيها) — يُستخدم هنا حصرًا لاكتشاف لحظة خروج فعلي لعضو
    (وليس أي تغيير حالة آخر كالترقية لمشرف أو الحظر المؤقت)، للتحقق الفوري
    مما إذا كان هذا الخروج يمس مشاركته في مسابقة أو سحب مستضاف في نفس هذه
    القناة تحديدًا."""
    cmu = update.chat_member
    if not cmu:
        return
    was_in = _chat_member_actually_in(cmu.old_chat_member)
    still_in = _chat_member_actually_in(cmu.new_chat_member)
    if not (was_in and not still_in):
        return

    user = cmu.new_chat_member.user
    if user.is_bot:
        return

    try:
        await handle_user_left_hosting_chat(context, cmu.chat.id, user)
    except Exception:
        logger.exception(
            "تعذّر معالجة خروج المستخدم %s من القناة %s (فحص المسابقات/السحوبات المستضافة)",
            user.id, cmu.chat.id,
        )


async def _notify_contest_owner_new_vote(context: ContextTypes.DEFAULT_TYPE, contest, voter_display_name: str,
                                          voter_username: str, participant, vote_number: int) -> None:
    """يرسل لصاحب المسابقة إشعارًا احترافيًا فور احتساب تصويت جديد ومؤكد لأحد
    متسابقيه، بعد اجتياز المصوّت لكل الشروط (كابتشا + اشتراك + بريميوم إن
    وُجد). لا يرفع أي استثناء عند فشل الإرسال (مثلاً حظر صاحب المسابقة للبوت
    أو عدم فتحه له من قبل) حتى لا يتأثر تسجيل التصويت نفسه بفشل الإشعار."""
    owner_id = contest.get("owner_id") if contest else None
    if not owner_id:
        return
    participant_name = (participant.get("display_name") if participant else None) or "غير معروف"
    text, entities = build_contest_new_vote_owner_notify_message(
        participant_name, voter_display_name, voter_username, vote_number,
    )
    try:
        await context.bot.send_message(chat_id=int(owner_id), text=text, entities=entities)
    except Exception:
        logger.warning("تعذّر إرسال إشعار تصويت جديد لصاحب المسابقة %s", owner_id)


async def _notify_contest_owner_vote_deducted(context: ContextTypes.DEFAULT_TYPE, contest,
                                               voter_display_name: str, voter_id: int,
                                               participant_display_name: str,
                                               current_votes: int) -> None:
    """يرسل لصاحب المسابقة إشعارًا عند إلغاء تصويت كان مؤكدًا سابقًا بسبب مغادرة
    المصوّت لإحدى القنوات الإلزامية، مع عدد أصوات المتسابق المحدَّث فورًا بعد
    الخصم. يُستدعى مرة واحدة فقط لكل تصويت (بواسطة cancel_contest_vote_if_unsubscribed
    الذي يضمن عدم معالجة نفس التصويت مرتين)، ولا يرفع أي استثناء عند فشل الإرسال."""
    owner_id = contest.get("owner_id") if contest else None
    if not owner_id:
        return
    text, entities = build_contest_vote_deducted_owner_notify_message(
        participant_display_name, voter_display_name, voter_id, current_votes,
    )
    try:
        await context.bot.send_message(chat_id=int(owner_id), text=text, entities=entities)
    except Exception:
        logger.warning("تعذّر إرسال إشعار خصم تصويت لصاحب المسابقة %s", owner_id)


async def cancel_contest_vote_if_unsubscribed(context: ContextTypes.DEFAULT_TYPE,
                                               contest_code: str, voter_id: int, data: dict) -> bool:
    """نظام الأمان وإلغاء التصويت: يتحقق من استمرار اشتراك مصوّت واحد في القناة
    الإلزامية. إن غادرها بعد احتساب صوته يُلغي هذا النظام تلقائيًا:
    - يُسجَّل التصويت كـ«ملغى بسبب مغادرة القنوات الإلزامية» (لا يُحذف، للتوثيق) —
      وهذا يُسقطه فورًا من عدد أصوات المتسابق (get_participant_votes/leaderboard
      لا يحتسبان إلا التصويتات المؤكدة).
    - يُخصم من صاحب المسابقة أي نقاط كانت قد مُنحت مقابل هذا التصويت تحديدًا.
    - يُرسَل لصاحب المسابقة إشعار بخصم الصوت وبعدد أصوات المتسابق المحدَّث.
      تحديث الحالة إلى "cancelled_unsubscribed" أعلاه يحدث مرة واحدة فقط لكل
      تصويت (لأن الدالة تتحقق أولًا أن الحالة الحالية "confirmed")، لذا لا
      يتكرر الخصم ولا الإشعار أبدًا لنفس التصويت حتى لو استُدعيت الدالة عليه
      من جديد لاحقًا.
    - يسمح هذا للمصوّت بالتصويت من جديد إذا عاد واشترك لاحقًا (has_voted تعيد
      False لأي تصويت غير مؤكد)، مع خضوعه لنفس كابتشا منع الرشق من جديد.
    يعيد True إذا أُلغي التصويت فعليًا في هذه المرة.
    تأخذ الآن (contest_code, voter_id, data) من كاش الأصوات بالذاكرة بدل
    مستند Firestore حي — فلا قراءة إطلاقًا هنا، وتبقى الكتابة الوحيدة هي
    فعليًا لحظة إلغاء تصويت حقيقي فقط."""
    if data.get("status", "confirmed") != "confirmed":
        return False

    subscribed = await is_user_subscribed(context, voter_id, force_refresh=True)
    if subscribed:
        return False

    cancelled_at = datetime.now(timezone.utc).isoformat()
    ref = fs_db().collection("contest_votes").document(f"{contest_code}_{voter_id}")
    # كتابة فعلية لأن هذا تعديل حقيقي (إلغاء تصويت بسبب مغادرة قناة). تُنفَّذ
    # عبر asyncio.to_thread حتى لا تُجمِّد حلقة أحداث البوت.
    await asyncio.to_thread(
        ref.update,
        {"status": "cancelled_unsubscribed", "cancelled_at": cancelled_at},
    )
    data["status"] = "cancelled_unsubscribed"
    data["cancelled_at"] = cancelled_at

    amount = data.get("points_awarded") or 0
    owner_id = data.get("owner_id")
    if amount and owner_id:
        await asyncio.to_thread(reverse_contest_owner_points, owner_id, amount)

    participant_id = data.get("participant_user_id")
    if participant_id:
        contest = get_contest(contest_code)
        participant = get_contest_participant(contest_code, participant_id)
        new_votes = get_participant_votes(contest_code, participant_id)

        if contest and participant and contest.get("status") == "open" and participant.get("channel_message_id"):
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=contest["chat_id"],
                    message_id=participant["channel_message_id"],
                    reply_markup=build_contest_vote_keyboard(
                        contest_code, participant_id, new_votes, participant["participant_code"]
                    ),
                )
            except Exception:
                pass

        if contest and participant:
            voter_display_name = data.get("voter_display_name") or str(voter_id)
            await _notify_contest_owner_vote_deducted(
                context, contest, voter_display_name, voter_id,
                participant.get("display_name") or str(participant_id),
                new_votes,
            )
    return True


async def contest_votes_subscription_audit(context: ContextTypes.DEFAULT_TYPE):
    """فحص دوري (نظام الأمان): يمرّ على كل التصويتات المؤكدة في المسابقات
    المفتوحة حاليًا، ويتحقق من استمرار اشتراك كل مصوّت في القناة الإلزامية.
    من غادر القناة تُلغى نقطته تلقائيًا.

    ⚡ لم تعد هذه الدالة تقرأ من Firestore إطلاقًا في التشغيل العادي — تعتمد
    كليًا على كاش المسابقات بالذاكرة (_get_open_contest_codes + كاش الأصوات
    المحمَّل مسبقًا من أحداث الإنشاء/المشاركة الفعلية). القراءة الوحيدة
    المحتملة هي أول مرة تُفتح فيها مسابقة معيّنة بعد إعادة تشغيل البوت (تحميل
    كسول لمرة واحدة)، وبعدها صفر قراءات مهما تكرر الفحص. لا كتابة إطلاقًا
    إلا عند إلغاء تصويت حقيقي (مستخدم غادر القناة فعلًا)."""
    open_codes = _get_open_contest_codes()
    if not open_codes:
        return

    checked = 0
    cancelled = 0
    for contest_code in list(open_codes):
        if not contest_code:
            continue
        votes = await asyncio.to_thread(_load_contest_votes, contest_code)
        for voter_id, data in list(votes.items()):
            if data.get("status", "confirmed") != "confirmed":
                continue
            checked += 1
            try:
                if await cancel_contest_vote_if_unsubscribed(context, contest_code, voter_id, data):
                    cancelled += 1
            except Exception:
                logger.exception(
                    "contest_votes_subscription_audit: فشل فحص التصويت %s_%s", contest_code, voter_id
                )
            await asyncio.sleep(0.05)

    if checked:
        logger.info(
            "contest_votes_subscription_audit: تم فحص %d صوتًا، أُلغي منها %d بسبب مغادرة القناة الإلزامية",
            checked, cancelled,
        )


async def vote_captcha_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يعالج ضغط المستخدم على أحد أزرار كابتشا التصويت (compcap:{token}:{idx}).
    إذا اختار الرمز الصحيح المطابق للهدف المعروض في الرسالة يتم تسجيل تصويته فورًا،
    وإذا اختار رمزًا خاطئًا لا يتم تسجيل أي تصويت (ويمكنه إعادة المحاولة على نفس الرسالة).
    """
    query = update.callback_query
    data = query.data

    try:
        _, token, idx_raw = data.split(":", 2)
        chosen_index = int(idx_raw)
    except (ValueError, IndexError):
        await query.answer("⚠️ طلب غير صالح.", show_alert=True)
        return

    sessions = context.user_data.get("vote_captchas", {})
    session = sessions.get(token)

    if not session:
        await query.answer("⚠️ انتهت صلاحية هذا التحقق، أعد المحاولة من زر التصويت 🤍.", show_alert=True)
        return

    if time.time() - session.get("created_at", 0) > CAPTCHA_SESSION_TTL_SECONDS:
        sessions.pop(token, None)
        await query.answer("⚠️ انتهت صلاحية هذا التحقق، أعد المحاولة من زر التصويت 🤍.", show_alert=True)
        return

    if chosen_index != session["correct_index"]:
        await query.answer(build_vote_captcha_wrong_alert(), show_alert=True)
        return

    contest_code = session["contest_code"]
    participant_id = session["participant_id"]
    voter = query.from_user

    contest = get_contest(contest_code)
    if not contest or contest["status"] != "open":
        sessions.pop(token, None)
        await query.answer("⚠️ انتهت هذه المسابقة.", show_alert=True)
        try:
            _bt, _be = bold_notice("⚠️ انتهت هذه المسابقة.")
            await query.edit_message_text(text=_bt, entities=_be)
        except Exception:
            pass
        return

    if voter.id == participant_id:
        sessions.pop(token, None)
        await query.answer("🚫 لا يمكنك التصويت لنفسك.", show_alert=True)
        return

    if has_voted(contest_code, voter.id):
        sessions.pop(token, None)
        await query.answer("✅ لقد قمت بالتصويت مسبقًا في هذه المسابقة.", show_alert=True)
        return

    participant = get_contest_participant(contest_code, participant_id)
    if not participant:
        sessions.pop(token, None)
        await query.answer("⚠️ هذا المتسابق لم يعد مسجّلًا.", show_alert=True)
        return

    # طبقة حماية أخيرة: إعادة فحص شرط بريميوم مباشرة قبل احتساب التصويت،
    # حتى لو تغيّرت حالة اشتراك المستخدم في بريميوم بين فتح الكابتشا والضغط
    # على الرمز الصحيح — فلا يُحتسب أي صوت من مستخدم غير مؤهل مهما حدث.
    if contest.get("premium_only") and not voter.is_premium:
        sessions.pop(token, None)
        await query.answer("💎 هذه المسابقة للتصويت لمستخدمي بريميوم فقط.", show_alert=True)
        return

    # نظام الأمان: لا يُحتسب أي تصويت إلا بعد التأكد من أن المصوّت لا يزال
    # مشتركًا فعليًا في القناة الإلزامية العامة + قناة نشر هذه المسابقة
    # تحديدًا لحظة التحقق (وليس فقط لحظة فتح البوت).
    if await get_missing_contest_vote_channels(context, voter.id, contest, force_refresh=True):
        await query.answer(
            "⚠️ يجب الاشتراك في القناة أولاً، اشترك ثم اضغط نفس الزر مجددًا للتحقق.",
            show_alert=True,
        )
        return

    voter_display_name = voter.first_name or voter.username or str(voter.id)
    registered = register_confirmed_contest_vote(
        contest_code, voter.id, participant_id, contest["owner_id"],
        voter_display_name=voter_display_name,
    )
    if not registered:
        sessions.pop(token, None)
        await query.answer("✅ لقد قمت بالتصويت مسبقًا في هذه المسابقة.", show_alert=True)
        return
    new_votes = get_participant_votes(contest_code, participant_id)
    sessions.pop(token, None)

    await query.answer("✅ تم التحقق وتسجيل تصويتك بنجاح!", show_alert=True)

    text, entities = build_vote_captcha_success_message()
    try:
        await query.edit_message_text(text=text, entities=entities)
    except Exception:
        pass

    if participant["channel_message_id"]:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=contest["chat_id"],
                message_id=participant["channel_message_id"],
                reply_markup=build_contest_vote_keyboard(
                    contest_code, participant_id, new_votes, participant["participant_code"]
                ),
            )
        except Exception:
            pass

    # إشعار صاحب المسابقة بتصويت جديد مؤكد (بعد اجتياز الكابتشا والاشتراك
    # وشرط بريميوم إن وُجد)، فور احتساب الصوت مباشرة.
    await _notify_contest_owner_new_vote(
        context, contest, voter_display_name, voter.username, participant, new_votes,
    )

    # إنهاء تلقائي للمسابقات المعتمدة على «عدد أصوات محدد» عند وصول أي متسابق
    # لعدد الأصوات المستهدف — بنفس آلية إنهاء المسابقات المعتمدة على الوقت.
    if (
        contest.get("end_type") == "votes"
        and contest.get("votes_target")
        and new_votes >= contest["votes_target"]
    ):
        try:
            await finish_contest_by_time(context.bot, contest_code)
        except Exception:
            logger.exception("vote_captcha_callback: فشل إنهاء المسابقة %s تلقائيًا عند اكتمال الأصوات", contest_code)


async def rr_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    if register_bot_user_and_check_new(user.id, user):
        await _notify_new_user_join(context, user)
    roulette_id = int(query.data.replace("rr_join_", ""))

    # لا يوجد "قناة استضافة" خاصة بالروليت السريع (يُنشر عبر الوضع الخطّي inline
    # في أي محادثة)، لذا الشرط الوحيد المطلوب هنا هو قنوات VORTEX الإجبارية
    # العامة. إن كان المستخدم غير مشترك فيها، يُفتح له البوت مباشرة عبر رابط
    # ?start=rr_{roulette_id} الحالي (handle_roulette_entry) بدل إكمال مشاركته
    # فورًا؛ start() نفسها تتحقق من VORTEX وتعرض بوابتها الموحّدة الجاهزة (بزر
    # لكل قناة ناقصة)، وتُكمل نفس طلب الانضمام تلقائيًا بعد نجاح الاشتراك.
    need_vortex = await get_missing_required_channels(context, user.id)
    if need_vortex:
        await query.answer(url=f"https://t.me/{BOT_USERNAME}?start=rr_{roulette_id}")
        return

    result = join_roulette(user.id, roulette_id, user.first_name or user.username or str(user.id))

    if not result["found"]:
        await query.answer("⚠️ هذا الروليت غير موجود.", show_alert=True)
        return

    target = result["target"]
    current = result["current"]

    if result["status"] != "open":
        await query.answer("⚠️ انتهى هذا الروليت بالفعل.", show_alert=True)
        return

    if result["already"]:
        await query.answer(
            f"✅ أنت مسجّل بالفعل.\n👥 المشاركين: {current}/{target}",
            show_alert=True,
        )
        return

    try:
        body_text, body_entities = build_quick_roulette_channel_message(target, current, roulette_id=roulette_id)
        await query.edit_message_text(
            text=body_text,
            entities=body_entities,
            reply_markup=roulette_share_keyboard(roulette_id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        print(f"rr_join edit_message_text error: {e}")

    await query.answer(
        f"✅ تم تسجيل مشاركتك!\n👥 المشاركين: {current}/{target}",
        show_alert=True,
    )

    owner_id = result.get("owner_id")
    if owner_id and owner_id != user.id:
        display_name = user.first_name or user.username or str(user.id)
        notify_text, notify_entities = build_quick_roulette_join_notify_message(display_name)
        try:
            await context.bot.send_message(
                chat_id=owner_id, text=notify_text, entities=notify_entities,
            )
        except Exception:
            pass

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_id = update.inline_query.from_user.id
    results = []

    try:
        ids_map = create_roulettes_batch(owner_id, ROULETTE_COUNTS)
        for n in ROULETTE_COUNTS:
            roulette_id = ids_map[n]
            body_text, body_entities = build_quick_roulette_channel_message(n, 0, roulette_id=roulette_id)
            results.append(
                InlineQueryResultArticle(
                    id=str(roulette_id),
                    title=f"انشاء روليت لـ ({n}) مشاركين",
                    description="اضغط هنا لبدء روليت سريع بهذا العدد",
                    thumbnail_url=ROULETTE_THUMBS[n],
                    input_message_content=InputTextMessageContent(
                        body_text, entities=body_entities,
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                    ),
                    reply_markup=roulette_share_keyboard(roulette_id),
                )
            )

        await update.inline_query.answer(results, cache_time=0, is_personal=True)
    except Exception as e:
        print(f"Inline Query Error: {e}")

async def announce_new_roulette(context: ContextTypes.DEFAULT_TYPE, roulette_id: int, target_count: int) -> None:
    """ينشر إعلانًا في قناة السحوبات (ANNOUNCE_CHANNEL_CHAT_ID) عند مشاركة «روليت
    سريع» فعليًا في أي محادثة — أي لحظة اختيار المستخدم لنتيجة الاستعلام
    المضمّن (chosen_inline_result)، وهي اللحظة الوحيدة التي يصبح فيها الروليت
    منشورًا حقيقيًا. يتضمن كود الروليت مع زر نسخ تلقائي بضغطة واحدة.

    ملاحظة مهمة: لا يوجد هنا زر «عرض» يفتح المنشور مباشرة (خلافًا لإعلانات
    المسابقات والسحوبات) لأن تيليجرام لا يزوّد البوت بأي رابط عام أو حتى
    بمعرّف المحادثة التي شارك فيها المستخدم نتيجة الوضع المضمّن (inline mode)
    — فقط بـ inline_message_id، وهو معرّف يصلح فقط لتعديل الرسالة عبر
    البوت، ولا يمكن بناء رابط t.me منه. لا يرفع أي استثناء أبدًا حتى لا يؤثر
    فشل الإعلان على نجاح المشاركة الأساسية."""
    text = (
        "🎡 روليت سريع جديد\n"
        f"👥 عدد المشاركين المطلوب: {target_count}\n"
        f"🆔 الكود : {roulette_id}"
    )
    try:
        copy_btn = InlineKeyboardButton(
            "📋 نسخ الكود", copy_text=CopyTextButton(text=str(roulette_id)), style="primary",
        )
    except Exception:
        copy_btn = InlineKeyboardButton(f"📋 الكود: {roulette_id}", callback_data="noop")
    keyboard = InlineKeyboardMarkup([[copy_btn]])
    try:
        await context.bot.send_message(
            chat_id=ANNOUNCE_CHANNEL_CHAT_ID,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        logger.warning("تعذر نشر إعلان روليت سريع في قناة الإعلانات (%s)", ANNOUNCE_CHANNEL_CHAT_ID)


async def chosen_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    if not chosen.inline_message_id:
        return
    try:
        roulette_id = int(chosen.result_id)
    except ValueError:
        return
    set_inline_message_id(roulette_id, chosen.inline_message_id)
    roulette = get_roulette(roulette_id)
    if roulette:
        asyncio.create_task(
            announce_new_roulette(context, roulette_id, roulette.get("target_count"))
        )

async def rr_spin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    roulette_id = int(query.data.replace("rr_spin_", ""))
    roulette = get_roulette(roulette_id)
    if not roulette:
        await query.answer("هذا الروليت غير موجود.", show_alert=True)
        return

    if query.from_user.id != roulette["owner_id"] and query.from_user.id not in ADMIN_IDS:
        await query.answer("فقط منشئ الروليت يمكنه التدوير.", show_alert=True)
        return

    status = roulette["status"]

    if status == "closed":
        await query.answer("تم تدوير هذا الروليت من قبل.", show_alert=True)
        return

    participants = get_participants_with_names(roulette_id)
    if len(participants) < 2:
        await query.answer("يجب وجود مشاركين اثنين على الأقل!", show_alert=True)
        return

    if status == "open":
        await query.answer()
        set_roulette_status(roulette_id, "waiting_spin")
        text, entities = build_waiting_spin_message(
            roulette["target_count"], len(participants), participants
        )
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=waiting_spin_keyboard(roulette_id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    if status == "waiting_spin":
        await query.answer()
        winner_id, winner_name = random.choice(participants)
        set_roulette_status(roulette_id, "closed")

        text, entities = build_result_message(winner_id, winner_name, participants)
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=result_keyboard(roulette_id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

async def rr_respin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    roulette_id = int(query.data.replace("rr_respin_", ""))
    roulette = get_roulette(roulette_id)
    if not roulette:
        await query.answer("هذا الروليت غير موجود.", show_alert=True)
        return

    if query.from_user.id != roulette["owner_id"] and query.from_user.id not in ADMIN_IDS:
        await query.answer("فقط منشئ الروليت يمكنه إعادة الاختيار.", show_alert=True)
        return

    participants = get_participants_with_names(roulette_id)
    if len(participants) < 2:
        await query.answer("يجب وجود مشاركين اثنين على الأقل!", show_alert=True)
        return

    await query.answer()
    winner_id, winner_name = random.choice(participants)

    text, entities = build_result_message(winner_id, winner_name, participants)
    await query.edit_message_text(
        text=text,
        entities=entities,
        reply_markup=result_keyboard(roulette_id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

async def qr_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        build_roulette_privacy_settings_text(),
        reply_markup=build_roulette_privacy_settings_keyboard(),
    )

async def roulette_privacy_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "toggle_hide_participants_internal":
        await query.answer()
        current = get_setting("hide_participants")
        set_setting("hide_participants", "0" if current == "1" else "1")
        await query.edit_message_text(
            build_roulette_privacy_settings_text(),
            reply_markup=build_roulette_privacy_settings_keyboard(),
        )
        return

    if data == "edit_game_cliche":
        await query.answer()
        context.user_data["awaiting_setting"] = "game_cliche"
        await query.edit_message_text(
            build_cliche_prompt_text(),
            parse_mode="Markdown",
            reply_markup=build_cliche_prompt_keyboard(),
        )
        return

    if data == "restore_defaults_roulette":
        await query.answer("تمت إعادة الإعدادات للوضع الافتراضي ✅")
        set_setting("hide_participants", DEFAULT_HIDE_PARTICIPANTS)
        set_setting("game_cliche", DEFAULT_GAME_CLICHE)
        await query.edit_message_text(
            build_roulette_privacy_settings_text(),
            reply_markup=build_roulette_privacy_settings_keyboard(),
        )
        return

    if data == "section_roulette":
        await query.answer()
        await query.edit_message_text(
            text=QUICK_ROULETTE_TEXT,
            reply_markup=build_quick_roulette_keyboard(),
        )
        return

async def handle_setting_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("awaiting_setting")
    if not field:
        return
    value = update.message.text.strip()
    if not is_owner(update.effective_user.id) and (
        field.startswith("points_") or field.startswith("required_channel_")
    ):
        context.user_data.pop("awaiting_setting", None)
        return

    if field in ("points_per_user", "points_required", "reward_value"):
        if not value.isdigit() or int(value) < 0:
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا أكبر من أو يساوي صفر ”")
            return

    set_setting(field, value)
    context.user_data.pop("awaiting_setting", None)
    if field.startswith("points_") or field.startswith("required_channel_"):
        log_admin_action(
            "change_settings", update.effective_user.id, details=f"{field} = {value}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )

    if field == "game_cliche":
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("رجوع للإعدادات", callback_data="qr_settings", style="danger", **emoji_kwargs("back_section_btn"))]
        ])
        await update.message.reply_text(
            "✅ تم تحديث نص الترحيب في كليشة اللعبة بنجاح.",
            reply_markup=reply_markup
        )
        return
    if field.startswith("points_") or field in ("reward_type", "reward_value"):
        text, entities = build_points_settings_message()
        await update.message.reply_text(
            text="✅ تم حفظ الإعداد بنجاح ”",
            reply_markup=build_points_settings_keyboard(),
        )
        return

def build_under_development_message(emoji_key: str = None, emoji_char: str = "🚧") -> tuple:
    """رسالة موحّدة «قيد التطوير» لأي زر لم تُفعَّل وظيفته بعد — بخط عريض داخل اقتباس."""
    lead = (emoji_char, EMOJI[emoji_key]) if emoji_key else emoji_char
    return build_text_with_emojis([
        ([
            ([lead, " هذه الميزة قيد التطوير حاليًا، تابعنا قريبًا!  ”"], "bold", None),
        ], "blockquote", None),
    ])

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ملاحظة: فحص الاشتراك الإجباري يتم مركزيًا عبر _subscription_gate_handler
    # (group=-1) قبل الوصول إلى هذا المعالج أصلاً — لا حاجة لتكراره هنا.
    query = update.callback_query
    # ⚠️ إصلاح: كنا نستدعي query.answer() هنا مباشرة وبدون أي نص، وهذا كان
    # "يستهلك" الرد الوحيد المسموح به على الـ callback من تيليجرام. فأي محاولة
    # لاحقة لعرض تنبيه (show_alert=True) — مثل رسالة "القسم غير متاح حاليًا"
    # عند إيقاف قسم الربح — كانت تُرسَل لكنها لا تظهر أبدًا، لأن تيليجرام
    # يسمح برد واحد فقط لكل ضغطة زر. الحل: نؤجل الرد الفارغ إلى أن نتأكد أن
    # أي فرع من الفروع أدناه لم يرسل رده الخاص (ومنها التنبيهات) بنفسه.
    _cb_answered = False
    async def _cb_answer(*args, **kwargs):
        nonlocal _cb_answered
        _cb_answered = True
        await query.answer(*args, **kwargs)

    try:
        if query.data == "my_stats":
            if get_setting("points_enabled") != "1":
                await _cb_answer("🚫 القسم غير متاح حاليًا.", show_alert=True)
                return
            text, entities = build_points_message(query.from_user.id)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_keyboard(query.from_user.id),
            )
            return

        if query.data == "points_stats":
            text, entities = await build_points_statistics_message(context)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_statistics_keyboard(),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            return

        if query.data == "owner_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_section_keyboard(),
            )
            return

        if query.data == "owner_points_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_points_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_points_section_keyboard(),
            )
            return

        if query.data == "points_manage_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_points_manage_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_manage_section_keyboard(),
            )
            return

        if query.data in ("points_manage_add_lookup", "points_manage_deduct_lookup"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            action = "add" if query.data == "points_manage_add_lookup" else "deduct"
            context.user_data["awaiting"] = f"points_manual_{action}_lookup"
            verb = "إضافة" if action == "add" else "خصم"
            await query.edit_message_text(
                f"✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) لـ{verb} النقاط منه ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="points_manage_section", style="danger")
                ]]),
            )
            return

        # قائمة تصفّح المستخدمين (نقاط + إحالات) قابلة للربط من عدة أقسام —
        # كل قسم يمرّر بادئة (prefix) خاصة به وزر رجوع خاص به، مع نفس المنطق
        # والعرض الموحّد. لإضافة القائمة إلى قسم جديد يكفي إضافة بادئة هنا.
        BROWSE_LIST_PREFIXES = {
            "points_browse": "points_manage_section",
            "users_browse": "owner_users_section",
        }

        if query.data in (f"{p}:noop" for p in BROWSE_LIST_PREFIXES):
            await _cb_answer()
            return

        _browse_list_prefix = next(
            (p for p in BROWSE_LIST_PREFIXES if query.data.startswith(f"{p}:list:")), None,
        )
        if _browse_list_prefix:
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            page_str = query.data.split(":", 2)[2]
            page = int(page_str) if page_str.isdigit() else 1
            rows = get_all_known_users_with_points()
            text, entities = build_users_points_browse_message(rows, page)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_users_points_browse_keyboard(
                    rows, page, callback_prefix=_browse_list_prefix,
                    back_callback=BROWSE_LIST_PREFIXES[_browse_list_prefix],
                ),
            )
            return

        _browse_pick_prefix = next(
            (p for p in BROWSE_LIST_PREFIXES if query.data.startswith(f"{p}:pick:")), None,
        )
        if _browse_pick_prefix:
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, uid_str, page_str = query.data.split(":", 3)
            target_id = int(uid_str)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_bot_user(target_id)
            if not row:
                await _cb_answer("⚠️ تعذّر العثور على بيانات هذا المستخدم.", show_alert=True)
                return
            referral = get_referral(target_id)
            row = FSRow({
                "user_id": target_id,
                "username": row.get("username"),
                "first_name": row.get("first_name"),
                "points": get_points(target_id),
                "referred_count": int(referral.get("referred_count") or 0) if referral else 0,
            })
            text, entities = build_user_points_profile_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_user_points_profile_keyboard(
                    target_id, back_page, browse_prefix=_browse_pick_prefix,
                ),
            )
            return

        if query.data.startswith("points_manual_add:") or query.data.startswith("points_manual_deduct:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            action = "add" if query.data.startswith("points_manual_add:") else "deduct"
            parts = query.data.split(":")
            uid_str, page_str = parts[1], parts[2]
            browse_prefix = parts[3] if len(parts) > 3 else "points_browse"
            target_id = int(uid_str)
            back_page = int(page_str) if page_str.isdigit() else 1
            context.user_data["awaiting"] = f"points_manual_{action}_amount"
            context.user_data["points_manual_target_id"] = target_id
            context.user_data["points_manual_back_page"] = back_page
            context.user_data["points_manual_browse_prefix"] = browse_prefix
            verb = "إضافتها" if action == "add" else "خصمها"
            await query.edit_message_text(
                f"✍️ أرسل الآن عدد النقاط المراد {verb} (رقم صحيح موجب) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "🔙 رجوع", callback_data=f"{browse_prefix}:pick:{target_id}:{back_page}", style="danger",
                    )
                ]]),
            )
            return

        if query.data == "owner_withdraw_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_withdraw_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_withdraw_section_keyboard(),
            )
            return

        if query.data.startswith("wd_complete:") or query.data.startswith("wd_reject:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            is_reject = query.data.startswith("wd_reject:")
            request_id = query.data.split(":", 1)[1]
            req = get_withdraw_request(request_id)
            notify_text = None
            if not req:
                admin_result_text = "⚠️ هذا الطلب غير موجود."
                await _cb_answer(admin_result_text, show_alert=True)
            elif req.get("status") != "pending":
                admin_result_text = "✅ تم إغلاق هذا الطلب مسبقًا."
                await _cb_answer(admin_result_text, show_alert=True)
            else:
                if is_reject:
                    mark_withdraw_rejected(request_id)
                    admin_result_text = "❌ تم رفض الطلب وإعادة النقاط لرصيد المستخدم."
                    await _cb_answer(admin_result_text)
                    notify_text = (
                        "❌ تم رفض طلب سحبك.\n\n"
                        f"💎 عدد النقاط: {req.get('points_amount', 0)}\n"
                        "📌 الحالة: 🔴 مرفوض\n"
                        "↩️ تمت إعادة النقاط إلى رصيدك."
                    )
                else:
                    mark_withdraw_completed(request_id)
                    admin_result_text = "✅ تم قبول الطلب وتعليمه كمكتمل."
                    await _cb_answer(admin_result_text)
                    notify_text = (
                        "🎉 تم قبول طلب سحبك وتحويل مكافأتك!\n\n"
                        f"💎 عدد النقاط المسحوبة: {req.get('points_amount', 0)}\n"
                        "📌 الحالة: 🟢 مقبول"
                    )
                try:
                    await context.bot.send_message(chat_id=req["user_id"], text=notify_text)
                except Exception:
                    pass
            # ⚠️ إصلاح: إن كانت هذه الضغطة داخل «قناة استقبال طلبات السحب» نفسها،
            # فلا يجوز استبدال رسالة الإشعار البسيطة بلوحة تحكم المالك الكاملة
            # (بأزرار تنقّل/رجوع) — لأن ذلك يحوّل رسالة القناة إلى واجهة بوت
            # كاملة يمكن التنقل من خلالها. بدلًا من ذلك، تُستبدل الرسالة بنص
            # تأكيد صغير فقط بلا أي أزرار. أما داخل محادثة المالك الخاصة فتبقى
            # لوحة التحكم الكاملة كما كانت (سلوك مقصود هناك).
            is_channel_msg = getattr(getattr(query.message, "chat", None), "type", None) == "channel"
            if is_channel_msg:
                try:
                    await query.edit_message_text(text=admin_result_text, reply_markup=None)
                except Exception:
                    pass
            else:
                text, entities = build_owner_withdraw_section_message()
                try:
                    await query.edit_message_text(
                        text=text, entities=entities,
                        reply_markup=build_owner_withdraw_section_keyboard(),
                    )
                except Exception:
                    pass
            return

        if query.data == "wd_channel_settings":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_withdraw_channel_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_withdraw_channel_settings_keyboard(),
            )
            return

        if query.data == "wd_channel_set":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "withdraw_channel_set"
            await query.edit_message_text(
                "✍️ أرسل الآن يوزر القناة (مثال: @channel أو رابط t.me/channel).\n"
                "⚠️ تأكد من إضافة البوت كمشرف (Admin) في القناة أولًا حتى يتمكن من الإرسال إليها ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="wd_channel_settings", style="danger"),
                ]]),
            )
            return

        if query.data == "wd_channel_clear":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            clear_withdraw_channel()
            log_admin_action(
                "change_settings", query.from_user.id, details="إلغاء قناة استقبال طلبات السحب",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("✅ تم إلغاء قناة استقبال السحب.")
            text, entities = build_withdraw_channel_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_withdraw_channel_settings_keyboard(),
            )
            return

        if query.data == "withdraw_locked":
            await _cb_answer(
                "🔒 رصيدك غير كافٍ لسحب هذه القيمة حاليًا، أو أن الخيار غير مفعّل من المالك بعد.",
                show_alert=True,
            )
            return

        if query.data == "withdraw_pending":
            await _cb_answer(
                "🕐 لديك طلب سحب قيد المعالجة بالفعل، انتظر إغلاقه أولاً — تابعه من «📋 سجل السحب».",
                show_alert=True,
            )
            return

        if query.data == "wd_stars_menu":
            if get_setting("points_enabled") != "1":
                await _cb_answer("🚫 القسم غير متاح حاليًا.", show_alert=True)
                return
            text, entities = build_stars_withdraw_menu_message(query.from_user.id)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_stars_withdraw_menu_keyboard(query.from_user.id),
            )
            return

        if query.data == "wd_history_noop":
            await _cb_answer()
            return

        if query.data.startswith("wd_history:"):
            page_str = query.data.split(":", 1)[1]
            page = int(page_str) if page_str.isdigit() else 1
            text, entities = build_wd_history_message(query.from_user.id, page)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_wd_history_keyboard(query.from_user.id, page),
            )
            return

        if query.data.startswith("wd_stars_pick:"):
            user = query.from_user
            if get_setting("points_enabled") != "1":
                await _cb_answer("🚫 القسم غير متاح حاليًا.", show_alert=True)
                return
            tier_str = query.data.split(":", 1)[1]
            tier = int(tier_str) if tier_str.isdigit() else 0
            if tier not in STAR_WITHDRAW_TIERS:
                await _cb_answer("⚠️ خيار غير صالح.", show_alert=True)
                return
            # مانع ضغط متكرر: قفل مؤقت في user_data يمنع تنفيذ طلبين من نفس
            # المستخدم في نفس اللحظة قبل أن تُغلق المعاملة الذرية الأولى.
            if context.user_data.get("wd_processing"):
                await _cb_answer("⏳ جارٍ معالجة طلبك، فضلاً انتظر لحظة.", show_alert=True)
                return
            if has_pending_withdraw_request_any(user.id):
                await _cb_answer(
                    "🕐 لديك طلب سحب قيد المعالجة بالفعل، انتظر إغلاقه أولاً.", show_alert=True,
                )
                return
            cost = get_star_cost(tier)
            if cost <= 0:
                await _cb_answer("⚠️ هذا الخيار غير مفعّل حاليًا من المالك.", show_alert=True)
                return
            pts = get_points(user.id, force_refresh=True)
            if pts < cost:
                await _cb_answer(
                    f"🔒 تحتاج {cost} نقطة على الأقل لسحب ⭐{tier}، رصيدك الحالي: {pts} نقطة.",
                    show_alert=True,
                )
                return
            # التواصل مع صاحب طلب السحب يتم عبر يوزر تليجرام مباشرة، لذا لا يمكن
            # إنشاء أي طلب لمستخدم بلا اسم مستخدم (username) — نطلب منه إضافته
            # أولاً من إعدادات تليجرام قبل السماح له بالمتابعة.
            if not user.username:
                await _cb_answer(
                    "⚠️ يجب إضافة اسم مستخدم (Username) في إعدادات تليجرام أولاً "
                    "حتى نتمكن من التواصل معك، ثم اضغط على زر السحب مجددًا.",
                    show_alert=True,
                )
                return

            context.user_data["wd_processing"] = True
            try:
                display_name = user.first_name or user.username or str(user.id)
                request_id = await asyncio.to_thread(
                    create_star_withdraw_request, user.id, display_name, user.username, tier, cost,
                )
            finally:
                context.user_data.pop("wd_processing", None)

            if not request_id:
                await _cb_answer(
                    "⚠️ رصيدك لم يعد كافيًا لهذا الطلب (ربما تغيّر للتو)، حدّث الصفحة وحاول مجددًا.",
                    show_alert=True,
                )
                return

            await _cb_answer(
                f"✅ تم إرسال طلب سحب ⭐{tier} بنجاح!\n💎 تم خصم {cost} نقطة.\n📌 الحالة: تحت المراجعة",
                show_alert=True,
            )

            text, entities = build_points_message(user.id)
            try:
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_points_keyboard(user.id),
                )
            except Exception:
                pass

            wd_request_notify_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ قبول", callback_data=f"wd_stars_accept:{request_id}", style="success"),
                InlineKeyboardButton("❌ رفض", callback_data=f"wd_stars_reject:{request_id}", style="danger"),
            ]])
            wd_request_notify_text = (
                "⭐ طلب سحب نجوم جديد\n\n"
                f"👤 المستخدم: {display_name} (ID: {user.id})\n"
                f"🔗 يوزر: @{user.username}\n"
                f"⭐ القيمة: {tier} نجمة\n"
                f"💎 النقاط المخصومة: {cost}"
            )

            for owner_id in OWNER_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=owner_id,
                        text=wd_request_notify_text,
                        reply_markup=wd_request_notify_markup,
                    )
                except Exception:
                    pass

            withdraw_channel = get_withdraw_channel()
            if withdraw_channel:
                try:
                    await context.bot.send_message(
                        chat_id=withdraw_channel["chat_id"],
                        text=wd_request_notify_text,
                        reply_markup=wd_request_notify_markup,
                    )
                except Exception:
                    pass
            return

        if (query.data.startswith("wd_stars_accept:") or query.data.startswith("wd_stars_reject:")
                or query.data.startswith("wd_stars_complete:")):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            action, request_id = query.data.split(":", 1)
            req = get_withdraw_request(request_id)
            notify_text = None
            if not req:
                admin_result_text = "⚠️ هذا الطلب غير موجود."
                await _cb_answer(admin_result_text, show_alert=True)
            elif action == "wd_stars_reject":
                if mark_star_withdraw_rejected(request_id):
                    admin_result_text = "❌ تم رفض الطلب وإعادة النقاط لرصيد المستخدم."
                    await _cb_answer(admin_result_text)
                    notify_text = (
                        "❌ تم رفض طلب سحب النجوم الخاص بك.\n\n"
                        f"⭐ القيمة: {req.get('stars_amount', 0)} نجمة\n"
                        f"💎 النقاط: {req.get('points_amount', 0)}\n"
                        "📌 الحالة: 🔴 مرفوض\n"
                        "↩️ تمت إعادة النقاط إلى رصيدك."
                    )
                else:
                    admin_result_text = "✅ تم إغلاق هذا الطلب مسبقًا."
                    await _cb_answer(admin_result_text, show_alert=True)
            elif action == "wd_stars_accept":
                if mark_star_withdraw_accepted(request_id):
                    admin_result_text = "🟢 تم قبول الطلب. أرسل النجوم يدويًا ثم اضغط «📤 تم الإرسال»."
                    await _cb_answer(admin_result_text)
                    notify_text = (
                        "🟢 تم قبول طلب سحب النجوم الخاص بك، وسيتم تحويلها قريبًا.\n\n"
                        f"⭐ القيمة: {req.get('stars_amount', 0)} نجمة"
                    )
                else:
                    admin_result_text = "✅ تم إغلاق هذا الطلب مسبقًا."
                    await _cb_answer(admin_result_text, show_alert=True)
            else:  # wd_stars_complete
                if mark_star_withdraw_completed(request_id):
                    admin_result_text = "✅ تم تعليم الطلب كمكتمل."
                    await _cb_answer(admin_result_text)
                    notify_text = (
                        "🎉 تم إرسال نجومك بنجاح!\n\n"
                        f"⭐ القيمة: {req.get('stars_amount', 0)} نجمة\n"
                        "📌 الحالة: ✅ مكتمل"
                    )
                else:
                    admin_result_text = "⚠️ تعذّر إتمام الطلب (يجب أن يكون بحالة «مقبول» أولًا)."
                    await _cb_answer(admin_result_text, show_alert=True)
            if notify_text and req:
                try:
                    await context.bot.send_message(chat_id=req["user_id"], text=notify_text)
                except Exception:
                    pass
            # ⚠️ إصلاح: نفس مشكلة الدالة أعلاه — لا نستبدل رسالة الإشعار داخل
            # «قناة استقبال طلبات السحب» بلوحة تحكم المالك الكاملة، بل بنص
            # تأكيد صغير فقط بلا أزرار، حتى لا تتحول القناة إلى واجهة بوت كاملة.
            is_channel_msg = getattr(getattr(query.message, "chat", None), "type", None) == "channel"
            if is_channel_msg:
                try:
                    await query.edit_message_text(text=admin_result_text, reply_markup=None)
                except Exception:
                    pass
            else:
                text, entities = build_owner_withdraw_section_message()
                try:
                    await query.edit_message_text(
                        text=text, entities=entities,
                        reply_markup=build_owner_withdraw_section_keyboard(),
                    )
                except Exception:
                    pass
            return

        if query.data == "star_settings":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_star_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_star_settings_keyboard(),
            )
            return

        if query.data.startswith("star_edit:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            tier_str = query.data.split(":", 1)[1]
            tier = int(tier_str) if tier_str.isdigit() else 0
            if tier not in STAR_WITHDRAW_TIERS:
                await _cb_answer("⚠️ قيمة غير صالحة.", show_alert=True)
                return
            context.user_data["awaiting"] = "star_cost_edit"
            context.user_data["star_cost_edit_tier"] = tier
            await query.edit_message_text(
                f"✍️ أرسل الآن عدد النقاط المطلوبة لسحب ⭐{tier} نجمة (رقم صحيح ≥ صفر) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="star_settings", style="danger")
                ]]),
            )
            return

        if query.data == "owner_sub_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_sub_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_section_keyboard(),
            )
            return

        if query.data == "owner_sub_add":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "admin_channel_add_username"
            await query.edit_message_text(
                "✍️ أرسل الآن يوزر القناة الجديدة (مثال: @channel أو رابط t.me/channel) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_sub_section", style="danger")
                ]]),
            )
            return

        if query.data in ("owner_sub_add_autodel_yes", "owner_sub_add_autodel_no"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            username = context.user_data.pop("admin_new_channel_username", None)
            target = context.user_data.pop("admin_new_channel_target", None)
            if not username:
                await _cb_answer("⚠️ انتهت صلاحية هذه العملية، ابدأ من جديد.", show_alert=True)
                return
            auto_delete = query.data == "owner_sub_add_autodel_yes"
            channel_id = create_required_channel(
                username=username, target_count=target, auto_delete_on_target=auto_delete,
                added_by=query.from_user.id,
            )
            log_admin_action(
                "add_channel", query.from_user.id, details=f"@{username}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            warning = await _check_bot_can_verify_channel(context, username)
            channel = get_required_channel(channel_id)
            await _cb_answer("✅ تمت إضافة القناة بنجاح")
            text, entities = await build_owner_sub_channel_message(context, channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_keyboard(channel),
            )
            if warning:
                try:
                    await context.bot.send_message(chat_id=query.from_user.id, text=warning)
                except Exception:
                    pass
            return

        if query.data.startswith("owner_sub_list:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            page = int(query.data.split(":", 1)[1])
            channels = get_required_channels()
            text, entities = build_owner_sub_list_message(channels)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_list_keyboard(channels, page),
            )
            return

        if query.data.startswith("owner_sub_check_target_now:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            status, info = await _check_and_maybe_delete_channel_target(context, channel)
            if status == "error":
                await _cb_answer(
                    f"⚠️ تعذّر التحقق ({info}). الأرجح أن البوت غير مضاف كمشرف في هذه القناة.",
                    show_alert=True,
                )
                return
            if status == "skipped":
                await _cb_answer("⚠️ لا يوجد هدف محدد أو الحذف التلقائي غير مفعّل لهذه القناة.", show_alert=True)
                return
            if status == "not_reached":
                await _cb_answer(
                    f"📊 لم يصل الهدف بعد ({info}/{channel.get('target_count')} عضو).",
                    show_alert=True,
                )
                return
            # status == "deleted"
            await _cb_answer(f"✅ تم بلوغ الهدف ({info} عضو) — حُذفت القناة من الاشتراك الإجباري.", show_alert=True)
            text, entities = build_owner_sub_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_section_keyboard(),
            )
            return

        if query.data.startswith("owner_sub_edit_button_text:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            context.user_data["awaiting"] = "admin_channel_edit_button_text"
            context.user_data["admin_channel_id"] = channel_id
            await query.edit_message_text(
                "✍️ أرسل الآن الاسم الذي تريد أن يظهر في زر هذه القناة بدل اليوزر الخام "
                "(مثال: 𝐑𝐎𝐔𝐋𝐄𝐓𝐓𝐄 𝐕𝐎𝐑𝐓𝐄𝐗)، أو أرسل - لحذف الاسم المخصص والعودة لعرض اليوزر ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_sub_channel:{channel_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_sub_edit_username:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            context.user_data["awaiting"] = "admin_channel_edit_username"
            context.user_data["admin_channel_id"] = channel_id
            await query.edit_message_text(
                "✍️ أرسل الآن اليوزر الجديد لهذه القناة (مثال: @channel أو رابط t.me/channel) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_sub_channel:{channel_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_sub_edit_link:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            context.user_data["awaiting"] = "admin_channel_edit_link"
            context.user_data["admin_channel_id"] = channel_id
            await query.edit_message_text(
                "✍️ أرسل الآن رابط الانضمام الجديد لهذه القناة (مثال: https://t.me/channel أو رابط دعوة خاص) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_sub_channel:{channel_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_sub_edit_target:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            context.user_data["awaiting"] = "admin_channel_edit_target"
            context.user_data["admin_channel_id"] = channel_id
            await query.edit_message_text(
                "✍️ أرسل الآن عدد الأعضاء المستهدف لهذه القناة (رقم)، أو أرسل 0 لإلغاء الهدف ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_sub_channel:{channel_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_sub_toggle_autodel:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            new_value = not bool(channel.get("auto_delete_on_target"))
            update_required_channel(channel_id, auto_delete_on_target=new_value)
            channel["auto_delete_on_target"] = new_value
            await _cb_answer("🔄 سيتم حذفها تلقائيًا عند الهدف" if new_value else "♾️ ستبقى دائمًا بدون حذف")
            text, entities = await build_owner_sub_channel_message(context, channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_keyboard(channel),
            )
            return

        if query.data.startswith("owner_sub_toggle_enabled:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            new_value = not channel.get("enabled", True)
            update_required_channel(channel_id, enabled=new_value)
            channel["enabled"] = new_value
            await _cb_answer("🟢 تم تفعيل القناة" if new_value else "🔴 تم تعطيل القناة")
            text, entities = await build_owner_sub_channel_message(context, channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_keyboard(channel),
            )
            return

        if query.data.startswith("owner_sub_channel_stats:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            text, entities = await build_owner_sub_channel_stats_message(context, channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_stats_keyboard(channel_id),
            )
            return

        if query.data.startswith("owner_sub_delete_confirm:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            _deleted_channel = get_required_channel(channel_id)
            delete_required_channel(channel_id)
            _deleted_username = _deleted_channel.get("username") if _deleted_channel else None
            log_admin_action(
                "delete_channel", query.from_user.id,
                details=f"@{_deleted_username}" if _deleted_username else f"معرف القناة: {channel_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🗑️ تم حذف القناة بنجاح")
            channels = get_required_channels()
            text, entities = build_owner_sub_list_message(channels)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_list_keyboard(channels, 1),
            )
            return

        if query.data.startswith("owner_sub_delete:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            text, entities = build_owner_sub_delete_confirm_message(channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_delete_confirm_keyboard(channel_id),
            )
            return

        if query.data.startswith("owner_sub_channel:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            channel = get_required_channel(channel_id)
            if not channel:
                await _cb_answer("⚠️ هذه القناة لم تعد موجودة.", show_alert=True)
                return
            text, entities = await build_owner_sub_channel_message(context, channel)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_keyboard(channel),
            )
            return

        if query.data == "owner_sub_reorder":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channels = get_required_channels()
            text, entities = build_owner_sub_reorder_message(channels)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_reorder_keyboard(channels),
            )
            return

        if query.data.startswith("owner_sub_move_up:") or query.data.startswith("owner_sub_move_down:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            channel_id = int(query.data.split(":", 1)[1])
            direction = -1 if query.data.startswith("owner_sub_move_up:") else 1
            move_required_channel(channel_id, direction)
            await _cb_answer("✅ تم تحديث الترتيب")
            channels = get_required_channels()
            text, entities = build_owner_sub_reorder_message(channels)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_reorder_keyboard(channels),
            )
            return

        if query.data == "owner_sub_stats_all":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = await build_owner_sub_stats_all_message(context)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_stats_all_keyboard(),
            )
            return

        if query.data == "owner_sub_noop":
            await _cb_answer()
            return

        if query.data == "owner_users_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_users_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_users_section_keyboard(),
            )
            return

        if query.data in ("owner_users_search", "owner_users_view"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "admin_user_lookup"
            await query.edit_message_text(
                "✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger")
                ]]),
            )
            return

        if query.data == "owner_users_ban":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "admin_user_ban_lookup"
            await query.edit_message_text(
                "✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) المراد حظره ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger")
                ]]),
            )
            return

        if query.data == "owner_users_unban":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "admin_user_unban_lookup"
            await query.edit_message_text(
                "✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) المراد فك حظره ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_users_section", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_users_banned:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            page = int(query.data.split(":", 1)[1])
            banned_users = get_banned_bot_users()
            text, entities = build_owner_users_banned_list_message(banned_users)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_users_banned_list_keyboard(banned_users, page),
            )
            return

        if query.data == "owner_users_stats":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            stats = get_bot_users_stats()
            text, entities = build_owner_users_stats_message(stats)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_users_stats_keyboard(),
            )
            return

        if query.data.startswith("owner_users_profile_ban:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            if target_id in OWNER_IDS:
                await _cb_answer("⚠️ لا يمكن حظر مالك البوت.", show_alert=True)
                return
            context.user_data["awaiting"] = "admin_user_ban_reason"
            context.user_data["admin_ban_target_id"] = target_id
            await query.edit_message_text(
                "✍️ أرسل الآن سبب الحظر، أو أرسل - لتركه بدون سبب ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_users_profile:{target_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_users_profile_unban:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            unban_bot_user(target_id)
            log_admin_action(
                "unban_user", query.from_user.id, details=f"معرف المستخدم: {target_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("✅ تم فك الحظر بنجاح")
            row = get_bot_user(target_id) or FSRow({"user_id": target_id})
            text, entities = build_user_profile_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_user_profile_keyboard(row),
            )
            return

        if query.data.startswith("owner_users_profile:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            row = get_bot_user(target_id) or FSRow({"user_id": target_id})
            text, entities = build_user_profile_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_user_profile_keyboard(row),
            )
            return

        if query.data == "owner_users_noop":
            await _cb_answer()
            return

        if query.data == "owner_admins_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_admins_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_admins_section_keyboard(),
            )
            return

        if query.data == "owner_admins_add":
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "add_admins")):
                await _cb_answer("⛔ ليس لديك صلاحية إضافة مشرفين.", show_alert=True)
                return
            context.user_data["awaiting"] = "mod_add_lookup"
            await query.edit_message_text(
                "✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) لإضافته كمشرف ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_admins_section", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_admins_list:"):
            _, mode, page_str = query.data.split(":", 2)
            needs_owner = mode in ("perms", "remove")
            if needs_owner and not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            if not needs_owner and not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "add_admins")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            page = int(page_str) if page_str.isdigit() else 1
            mods = list_moderators()
            text, entities = build_owner_admins_list_message(mods, mode)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_admins_list_keyboard(mods, mode, page),
            )
            return

        if query.data == "owner_admins_noop":
            await _cb_answer()
            return

        if query.data.startswith("owner_admins_pick:"):
            _, mode, uid_str = query.data.split(":", 2)
            target_id = int(uid_str)
            if mode == "view":
                if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "add_admins")):
                    await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                    return
            elif not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            row = get_moderator(target_id)
            if not row:
                await _cb_answer("⚠️ هذا المشرف لم يعد موجودًا.", show_alert=True)
                return
            if mode == "remove":
                text, entities = build_moderator_delete_confirm_message(row)
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_moderator_delete_confirm_keyboard(target_id),
                )
            elif mode == "perms":
                text, entities = build_moderator_perms_message(row)
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_moderator_perms_keyboard(row),
                )
            else:
                text, entities = build_moderator_profile_message(row)
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_moderator_profile_keyboard(target_id),
                )
            return

        if query.data.startswith("owner_admins_toggle:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            _, uid_str, perm_key = query.data.split(":", 2)
            target_id = int(uid_str)
            row = get_moderator(target_id)
            if not row:
                await _cb_answer("⚠️ هذا المشرف لم يعد موجودًا.", show_alert=True)
                return
            current = bool(row.get("permissions", {}).get(perm_key))
            set_moderator_permission(target_id, perm_key, not current)
            row = get_moderator(target_id)
            text, entities = build_moderator_perms_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_moderator_perms_keyboard(row),
            )
            return

        if query.data.startswith("owner_admins_remove_do:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            remove_moderator(target_id)
            log_admin_action(
                "remove_admin", query.from_user.id, details=f"معرف المشرف: {target_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("✅ تم حذف المشرف بنجاح")
            mods = list_moderators()
            text, entities = build_owner_admins_list_message(mods, "view")
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_admins_list_keyboard(mods, "view", 1),
            )
            return

        if query.data == "owner_referrals_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_referrals_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_referrals_section_keyboard(),
            )
            return

        if query.data == "owner_referrals_add":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "referral_add_lookup"
            await query.edit_message_text(
                "✍️ أرسل الآن معرف المستخدم (ID) أو يوزره (@username) لمنحه رابط دعوة ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_section", style="danger")
                ]]),
            )
            return

        if query.data == "owner_referrals_search":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "referral_search_lookup"
            await query.edit_message_text(
                "🔍 أرسل الآن معرف المستخدم (ID) أو يوزره (@username) للبحث عنه ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_section", style="danger")
                ]]),
            )
            return

        if query.data == "owner_referrals_stats":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            text, entities = build_owner_referrals_stats_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_referrals_stats_keyboard(),
            )
            return

        if query.data == "owner_referrals_settings":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_referrals_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_referrals_settings_keyboard(),
            )
            return

        if query.data == "owner_referrals_edit_default_pct":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "referral_default_pct"
            await query.edit_message_text(
                "✍️ أرسل الآن النسبة الافتراضية الجديدة (رقم من 0 إلى 100) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_settings", style="danger")
                ]]),
            )
            return

        if query.data == "owner_referrals_edit_signup_points":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "referral_signup_points"
            await query.edit_message_text(
                "✍️ أرسل الآن عدد نقاط كل إحالة جديدة عند نسبة 100% (رقم صحيح) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_referrals_settings", style="danger")
                ]]),
            )
            return

        if query.data == "owner_referrals_noop":
            await _cb_answer()
            return

        if query.data.startswith("owner_referrals_list:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, mode, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            rows = list_referrers()
            text, entities = build_owner_referrals_list_message(rows, mode)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_referrals_list_keyboard(rows, mode, page),
            )
            return

        if query.data.startswith("owner_referrals_pick:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, mode, uid_str = query.data.split(":", 2)
            target_id = int(uid_str)
            row = get_referral(target_id)
            if not row:
                await _cb_answer("⚠️ هذا المستخدم لم يعد صاحب رابط دعوة.", show_alert=True)
                return
            if mode == "remove":
                text, entities = build_referrer_delete_confirm_message(row)
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_referrer_delete_confirm_keyboard(target_id),
                )
            else:
                text, entities = build_referrer_profile_message(row)
                await query.edit_message_text(
                    text=text, entities=entities,
                    reply_markup=build_referrer_profile_keyboard(row),
                )
            return

        if query.data.startswith("owner_referrals_toggle:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            row = get_referral(target_id)
            if not row:
                await _cb_answer("⚠️ هذا المستخدم لم يعد صاحب رابط دعوة.", show_alert=True)
                return
            new_state = not row.get("active")
            set_referrer_active(target_id, new_state)
            log_admin_action(
                "toggle_referrer", query.from_user.id,
                details=f"معرف المستخدم: {target_id} — الحالة الجديدة: {'مفعّل' if new_state else 'معطّل'}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            row = get_referral(target_id)
            text, entities = build_referrer_profile_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_referrer_profile_keyboard(row),
            )
            return

        if query.data.startswith("owner_referrals_edit_pct:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            if not get_referral(target_id):
                await _cb_answer("⚠️ هذا المستخدم لم يعد صاحب رابط دعوة.", show_alert=True)
                return
            context.user_data["awaiting"] = "referral_edit_percentage"
            context.user_data["referral_target_id"] = target_id
            await query.edit_message_text(
                "✍️ أرسل الآن نسبة الإحالة الجديدة لهذا المستخدم (رقم من 0 إلى 100) ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"owner_referrals_pick:view:{target_id}", style="danger")
                ]]),
            )
            return

        if query.data.startswith("owner_referrals_remove_do:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا الإجراء خاص بمالك البوت فقط.", show_alert=True)
                return
            target_id = int(query.data.split(":", 1)[1])
            remove_referrer(target_id)
            log_admin_action(
                "remove_referrer", query.from_user.id, details=f"معرف المستخدم: {target_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("✅ تمت إزالة صاحب رابط الدعوة بنجاح")
            rows = list_referrers()
            text, entities = build_owner_referrals_list_message(rows, "view")
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_referrals_list_keyboard(rows, "view", 1),
            )
            return

        if query.data == "owner_stats_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            # يُنفَّذ عبر asyncio.to_thread في خيط منفصل حتى لا تُجمِّد قراءة كل
            # مستخدمي/قنوات البوت من Firestore حلقة أحداث البوت (event loop)
            # وتُعلِّق باقي المستخدمين لحين انتهائها — نفس النمط المتّبع أصلًا
            # في هذا المشروع لأي عملية Firestore ثقيلة داخل async handler.
            stats = await asyncio.to_thread(get_full_bot_statistics)
            required_members = await get_required_channels_total_members(context)
            text, entities = build_owner_stats_message(stats, required_members)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_stats_keyboard(),
            )
            return

        if query.data == "owner_logs_noop":
            await _cb_answer()
            return

        if query.data.startswith("owner_logs:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            page = int(query.data.split(":", 1)[1])
            logs = get_admin_logs()
            text, entities = build_owner_logs_section_message(logs, page)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_logs_section_keyboard(logs, page),
            )
            return

        if query.data == "owner_maintenance_noop":
            await _cb_answer()
            return

        if query.data == "owner_maintenance_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            text, entities = build_owner_maintenance_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_maintenance_section_keyboard(),
            )
            return

        if query.data == "owner_maintenance_toggle":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            new_state = not is_maintenance_mode()
            set_maintenance_mode(new_state)
            log_admin_action(
                "change_settings", query.from_user.id,
                details=f"وضع الصيانة: {'مفعّل' if new_state else 'معطّل'}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🔴 تم تفعيل وضع الصيانة" if new_state else "🟢 تم إيقاف وضع الصيانة", show_alert=True)
            text, entities = build_owner_maintenance_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_maintenance_section_keyboard(),
            )
            return

        if query.data == "owner_maintenance_speedtest":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer("⏳ جاري فحص السرعة ”")
            try:
                elapsed_ms, label = measure_bot_response_time()
            except Exception:
                logger.exception("تعذّر إجراء فحص سرعة الاستجابة")
                await _cb_answer("⚠️ تعذّر إجراء الفحص، حاول مجددًا.", show_alert=True)
                return
            text, entities = build_owner_maintenance_speedtest_message(elapsed_ms, label)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_maintenance_section_keyboard(),
            )
            return

        if query.data == "owner_maintenance_status":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            text, entities = build_owner_maintenance_status_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_maintenance_section_keyboard(),
            )
            return

        if query.data == "owner_reset_test_user":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            context.user_data["awaiting"] = "reset_test_user_lookup"
            _bt, _be = bold_notice(
                "✍️ أرسل الآن يوزر المستخدم الذي تريد حذف بياناته (مثال: @Jzllzjzjzjjz)، "
                "أو أرسل معرّفه الرقمي مباشرة ”"
            )
            await query.edit_message_text(
                text=_bt, entities=_be,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_maintenance_section", style="danger"),
                ]]),
            )
            return

        if query.data == "owner_new_user_notify_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            await _cb_answer()
            text, entities = build_new_user_notify_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_new_user_notify_section_keyboard(),
            )
            return

        if query.data == "owner_newuser_toggle":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            if not is_new_user_notify_enabled():
                if not get_new_user_notify_channel():
                    await _cb_answer("⚠️ حدّد قناة الإشعارات أولًا قبل التفعيل.", show_alert=True)
                    return
                set_new_user_notify_enabled(True)
                msg = "🟢 تم تفعيل إشعارات دخول المستخدمين."
            else:
                set_new_user_notify_enabled(False)
                msg = "🔴 تم إيقاف إشعارات دخول المستخدمين."
            log_admin_action(
                "change_settings", query.from_user.id, details=msg,
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer(msg, show_alert=True)
            text, entities = build_new_user_notify_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_new_user_notify_section_keyboard(),
            )
            return

        if query.data == "owner_newuser_channel_set":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data["awaiting"] = "new_user_notify_channel_set"
            await query.edit_message_text(
                "✍️ أرسل الآن يوزر القناة (مثال: @channel أو رابط t.me/channel).\n"
                "⚠️ تأكد من إضافة البوت كمشرف (Admin) في القناة أولًا حتى يتمكن من الإرسال إليها ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="owner_new_user_notify_section", style="danger"),
                ]]),
            )
            return

        if query.data == "owner_newuser_channel_clear":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            clear_new_user_notify_channel()
            # إجراء ذكي: إن أُلغيت القناة أثناء تفعيل الإشعارات، تُوقَف الإشعارات
            # تلقائيًا تجنبًا لحالة "مفعّلة بلا قناة" التي لن تُرسِل شيئًا بصمت.
            was_enabled = is_new_user_notify_enabled()
            if was_enabled:
                set_new_user_notify_enabled(False)
            log_admin_action(
                "change_settings", query.from_user.id, details="إلغاء قناة إشعارات دخول المستخدمين",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer(
                "✅ تم إلغاء قناة الإشعارات." + (" وتم إيقاف الإشعارات تلقائيًا." if was_enabled else ""),
                show_alert=True,
            )
            text, entities = build_new_user_notify_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_new_user_notify_section_keyboard(),
            )
            return

        if query.data == "owner_draws_section":
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_draws_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_draws_section_keyboard(),
            )
            return

        if query.data.startswith("admgw_list:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            giveaways = _admgw_filter_giveaways(get_all_giveaways(), filt)
            total_pages = max(1, -(-len(giveaways) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admgw_list_message(filt, page, total_pages, len(giveaways))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admgw_list_keyboard(giveaways, filt, page, total_pages),
            )
            return

        if query.data.startswith("admgw_detail:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, gw_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            giveaway = get_giveaway(gw_code)
            if not giveaway:
                await _cb_answer("⚠️ هذا السحب لم يعد موجودًا.", show_alert=True)
                return
            giveaways = _admgw_filter_giveaways(get_all_giveaways(), filt)
            index = next((i + 1 for i, g in enumerate(giveaways) if g["gw_code"] == gw_code), 0)
            channel_title = get_chat_title_by_id(giveaway["chat_id"])
            participants_total = count_giveaway_participants(gw_code)
            channel_url = await build_contest_post_link(context, giveaway["chat_id"], giveaway.get("channel_message_id"))
            text, entities = build_admgw_detail_message(giveaway, index, channel_title, participants_total)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admgw_detail_keyboard(gw_code, filt, page, channel_url=channel_url),
            )
            return

        if query.data.startswith("admgw_search:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            context.user_data["awaiting"] = "admgw_search_lookup"
            context.user_data["admgw_search_filt"] = filt
            context.user_data["admgw_search_page"] = page
            await query.edit_message_text(
                "🔍 أرسل الآن كود السحب الذي تريد البحث عنه ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admgw_list:{filt}:{page}", style="danger",
                                          **emoji_kwargs("back_section_btn")),
                ]]),
            )
            return

        if query.data.startswith("admgw_delc:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, gw_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            giveaway = get_giveaway(gw_code)
            if not giveaway:
                await _cb_answer("⚠️ هذا السحب لم يعد موجودًا.", show_alert=True)
                return
            text, entities = build_admgw_delete_confirm_message(giveaway)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admgw_delete_confirm_keyboard(gw_code, filt, page),
            )
            return

        if query.data.startswith("admgw_delete_do:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, gw_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            delete_giveaway_admin(gw_code)
            log_admin_action(
                "delete_giveaway", query.from_user.id, details=f"كود السحب: {gw_code}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🗑️ تم حذف السحب بنجاح")
            giveaways = _admgw_filter_giveaways(get_all_giveaways(), filt)
            total_pages = max(1, -(-len(giveaways) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admgw_list_message(filt, page, total_pages, len(giveaways))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admgw_list_keyboard(giveaways, filt, page, total_pages),
            )
            return

        if query.data == "admgw_stats":
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_giveaways")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            stats = await asyncio.to_thread(get_giveaways_statistics)
            text, entities = build_admgw_stats_message(stats)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admgw_stats_keyboard(),
            )
            return

        if query.data == "admgw_noop":
            await _cb_answer()
            return

        if query.data == "owner_contests_section":
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_contests_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_contests_section_keyboard(),
            )
            return

        if query.data.startswith("admct_list:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            contests = _admct_filter_contests(get_all_contests(), filt)
            total_pages = max(1, -(-len(contests) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admct_list_message(filt, page, total_pages, len(contests))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admct_list_keyboard(contests, filt, page, total_pages),
            )
            return

        if query.data.startswith("admct_detail:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, contest_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            contest = get_contest(contest_code)
            if not contest:
                await _cb_answer("⚠️ هذه المسابقة لم تعد موجودة.", show_alert=True)
                return
            contests = _admct_filter_contests(get_all_contests(), filt)
            index = next((i + 1 for i, c in enumerate(contests) if c["contest_code"] == contest_code), 0)
            channel_title = get_chat_title_by_id(contest["chat_id"])
            participants_total = count_contest_participants(contest_code)
            channel_url = await build_contest_post_link(context, contest["chat_id"], contest.get("channel_message_id"))
            text, entities = build_admct_detail_message(contest, index, channel_title, participants_total)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admct_detail_keyboard(contest_code, filt, page, channel_url=channel_url),
            )
            return

        if query.data.startswith("admct_search:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            context.user_data["awaiting"] = "admct_search_lookup"
            context.user_data["admct_search_filt"] = filt
            context.user_data["admct_search_page"] = page
            await query.edit_message_text(
                "🔍 أرسل الآن كود المسابقة الذي تريد البحث عنها ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admct_list:{filt}:{page}", style="danger",
                                          **emoji_kwargs("back_section_btn")),
                ]]),
            )
            return

        if query.data.startswith("admct_delc:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, contest_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            contest = get_contest(contest_code)
            if not contest:
                await _cb_answer("⚠️ هذه المسابقة لم تعد موجودة.", show_alert=True)
                return
            text, entities = build_admct_delete_confirm_message(contest)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admct_delete_confirm_keyboard(contest_code, filt, page),
            )
            return

        if query.data.startswith("admct_delete_do:"):
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, contest_code, filt, page_str = query.data.split(":", 3)
            page = int(page_str) if page_str.isdigit() else 1
            delete_contest_admin(contest_code)
            log_admin_action(
                "delete_contest", query.from_user.id, details=f"كود المسابقة: {contest_code}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🗑️ تم حذف المسابقة بنجاح")
            contests = _admct_filter_contests(get_all_contests(), filt)
            total_pages = max(1, -(-len(contests) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admct_list_message(filt, page, total_pages, len(contests))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admct_list_keyboard(contests, filt, page, total_pages),
            )
            return

        if query.data == "admct_stats":
            if not (is_owner(query.from_user.id) or moderator_can(query.from_user.id, "delete_contests")):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            stats = await asyncio.to_thread(get_contests_statistics)
            text, entities = build_admct_stats_message(stats)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admct_stats_keyboard(),
            )
            return

        if query.data == "admct_noop":
            await _cb_answer()
            return

        if query.data == "owner_quick_roulette_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_quick_roulette_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_quick_roulette_section_keyboard(),
            )
            return

        if query.data.startswith("admrr_list:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            roulettes = _admrr_filter_roulettes(get_all_quick_roulettes(), filt)
            total_pages = max(1, -(-len(roulettes) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admrr_list_message(filt, page, total_pages, len(roulettes))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admrr_list_keyboard(roulettes, filt, page, total_pages),
            )
            return

        if query.data.startswith("admrr_detail:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, rid_str, filt, page_str = query.data.split(":", 3)
            roulette_id = int(rid_str)
            page = int(page_str) if page_str.isdigit() else 1
            roulette = get_roulette(roulette_id)
            if not roulette:
                await _cb_answer("⚠️ هذا السحب لم يعد موجودًا.", show_alert=True)
                return
            roulettes = _admrr_filter_roulettes(get_all_quick_roulettes(), filt)
            index = next((i + 1 for i, r in enumerate(roulettes) if r["roulette_id"] == roulette_id), 0)
            participants_total = count_participants(roulette_id)
            text, entities = build_admrr_detail_message(roulette, index, participants_total)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admrr_detail_keyboard(roulette_id, filt, page),
            )
            return

        if query.data.startswith("admrr_search:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, filt, page_str = query.data.split(":", 2)
            page = int(page_str) if page_str.isdigit() else 1
            context.user_data["awaiting"] = "admrr_search_lookup"
            context.user_data["admrr_search_filt"] = filt
            context.user_data["admrr_search_page"] = page
            await query.edit_message_text(
                "🔍 أرسل الآن كود السحب السريع الذي تريد البحث عنه ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admrr_list:{filt}:{page}", style="danger",
                                          **emoji_kwargs("back_section_btn")),
                ]]),
            )
            return

        if query.data.startswith("admrr_delc:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, rid_str, filt, page_str = query.data.split(":", 3)
            roulette_id = int(rid_str)
            page = int(page_str) if page_str.isdigit() else 1
            roulette = get_roulette(roulette_id)
            if not roulette:
                await _cb_answer("⚠️ هذا السحب لم يعد موجودًا.", show_alert=True)
                return
            text, entities = build_admrr_delete_confirm_message(roulette)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admrr_delete_confirm_keyboard(roulette_id, filt, page),
            )
            return

        if query.data.startswith("admrr_delete_do:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, rid_str, filt, page_str = query.data.split(":", 3)
            roulette_id = int(rid_str)
            page = int(page_str) if page_str.isdigit() else 1
            delete_quick_roulette_admin(roulette_id)
            log_admin_action(
                "delete_quick_roulette", query.from_user.id, details=f"معرف السحب السريع: {roulette_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🗑️ تم حذف السحب السريع بنجاح")
            roulettes = _admrr_filter_roulettes(get_all_quick_roulettes(), filt)
            total_pages = max(1, -(-len(roulettes) // GW_LIST_PAGE_SIZE))
            page = max(1, min(page, total_pages))
            text, entities = build_admrr_list_message(filt, page, total_pages, len(roulettes))
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admrr_list_keyboard(roulettes, filt, page, total_pages),
            )
            return

        if query.data == "admrr_stats":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            stats = await asyncio.to_thread(get_quick_roulette_statistics)
            text, entities = build_admrr_stats_message(stats)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_admrr_stats_keyboard(),
            )
            return

        if query.data == "admrr_noop":
            await _cb_answer()
            return

        if query.data == "owner_broadcast_section":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            text, entities = build_owner_broadcast_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_broadcast_section_keyboard(),
            )
            return

        if query.data == "broadcast_send_menu":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            # ⚠️ يجب أن تتم كل خطوات إعداد/تعديل الإذاعة من داخل محادثة المالك
            # الخاصة مع البوت فقط، تجنبًا لأي التباس إذا وصلت هذه الرسالة بطريقة
            # ما داخل مجموعة (حماية إضافية فوق قيد ChatType.PRIVATE على المعالجات).
            if query.message and query.message.chat.type != "private":
                await _cb_answer("⛔ إعداد الإذاعة متاح فقط من داخل محادثتك الخاصة مع البوت.", show_alert=True)
                return
            if _BROADCAST_STATE["running"]:
                await _cb_answer("⚠️ توجد إذاعة قيد التنفيذ بالفعل، أوقفها أولاً إن أردت إرسال إذاعة جديدة.",
                                   show_alert=True)
                return
            context.user_data["awaiting"] = "broadcast_await_content"
            text, entities = build_broadcast_universal_prompt_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_universal_prompt_keyboard(),
            )
            return

        if query.data == "broadcast_confirm_send":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            if query.message and query.message.chat.type != "private":
                await _cb_answer("⛔ إعداد الإذاعة متاح فقط من داخل محادثتك الخاصة مع البوت.", show_alert=True)
                return
            pending = context.user_data.get("broadcast_pending")
            if not pending:
                await _cb_answer("⚠️ لا توجد رسالة إذاعة قيد الانتظار (ربما انتهت صلاحيتها).", show_alert=True)
                return
            if _BROADCAST_STATE["running"]:
                await _cb_answer("⚠️ توجد إذاعة قيد التنفيذ بالفعل.", show_alert=True)
                return
            context.user_data.pop("broadcast_pending", None)
            await _cb_answer("📣 بدأت عملية الإذاعة الآن، سيصلك إشعار عند الانتهاء ”", show_alert=True)
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            asyncio.create_task(run_broadcast(
                context, pending["content_type"], query.from_user.id,
                source_chat_id=pending["source_chat_id"], source_message_id=pending["source_message_id"],
                text=pending.get("text"), caption=pending.get("caption"),
            ))
            return

        if query.data == "broadcast_cancel_send":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            context.user_data.pop("broadcast_pending", None)
            await _cb_answer("❌ تم إلغاء إرسال الإذاعة.")
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        if query.data == "broadcast_stop":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            if not _BROADCAST_STATE["running"]:
                await _cb_answer("ℹ️ لا توجد إذاعة قيد التنفيذ حاليًا.", show_alert=True)
            else:
                _BROADCAST_STATE["stop_requested"] = True
                await _cb_answer("⏹️ سيتم إيقاف الإذاعة خلال لحظات ”", show_alert=True)
            return

        if query.data == "broadcast_stats":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            stats = get_broadcast_stats()
            text, entities = build_broadcast_stats_message(stats)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_stats_keyboard(),
            )
            return

        if query.data == "broadcast_logs:noop":
            await _cb_answer()
            return

        if query.data.startswith("broadcast_logs:list:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            page_str = query.data.split(":", 2)[2]
            page = int(page_str) if page_str.isdigit() else 1
            rows = get_broadcast_logs()
            text, entities = build_broadcast_logs_list_message(rows)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_logs_list_keyboard(rows, page),
            )
            return

        if query.data.startswith("broadcast_logs:pick:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_broadcast_log(log_id)
            if not row:
                await _cb_answer("⚠️ هذا السجل لم يعد موجودًا.", show_alert=True)
                return
            text, entities = build_broadcast_log_detail_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_log_detail_keyboard(log_id, back_page),
            )
            return

        if query.data.startswith("broadcast_logs:edit:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            if query.message and query.message.chat.type != "private":
                await _cb_answer("⛔ تعديل الإذاعة متاح فقط من داخل محادثتك الخاصة مع البوت.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_broadcast_log(log_id)
            if not row:
                await _cb_answer("⚠️ هذا السجل لم يعد موجودًا.", show_alert=True)
                return
            context.user_data["awaiting"] = "broadcast_log_edit_text"
            context.user_data["broadcast_log_edit_id"] = log_id
            context.user_data["broadcast_log_edit_back_page"] = back_page
            await query.edit_message_text(
                "✍️ أرسل الآن النص الجديد الذي سيحل محل النص/التعليق المؤرشف لهذا السجل.\n"
                "⚠️ هذا يعدّل الأرشيف فقط ولا يعيد إرسال أي رسالة للمستخدمين ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"broadcast_logs:pick:{log_id}:{back_page}", style="danger"),
                ]]),
            )
            return

        if query.data.startswith("broadcast_logs:delete_confirm:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            delete_broadcast_log(log_id)
            log_admin_action(
                "delete_broadcast_log", query.from_user.id, details=f"معرف السجل: {log_id}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("🗑️ تم حذف السجل بنجاح")
            rows = get_broadcast_logs()
            text, entities = build_broadcast_logs_list_message(rows)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_logs_list_keyboard(rows, back_page),
            )
            return

        if query.data.startswith("broadcast_logs:delete:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_broadcast_log(log_id)
            if not row:
                await _cb_answer("⚠️ هذا السجل لم يعد موجودًا.", show_alert=True)
                return
            text, entities = build_broadcast_log_delete_confirm_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_log_delete_confirm_keyboard(log_id, back_page),
            )
            return

        if query.data.startswith("broadcast_logs:delete_actual:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_broadcast_log(log_id)
            if not row:
                await _cb_answer("⚠️ هذا السجل لم يعد موجودًا.", show_alert=True)
                return
            text, entities = build_broadcast_log_delete_actual_confirm_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_log_delete_actual_confirm_keyboard(log_id, back_page),
            )
            return

        if query.data.startswith("broadcast_logs:delete_actual_confirm:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بمالك البوت فقط.", show_alert=True)
                return
            _, _, log_id, page_str = query.data.split(":", 3)
            back_page = int(page_str) if page_str.isdigit() else 1
            row = get_broadcast_log(log_id)
            if not row:
                await _cb_answer("⚠️ هذا السجل لم يعد موجودًا.", show_alert=True)
                return
            await _cb_answer("🚫 جاري حذف الرسائل من عند المستخدمين، قد يستغرق هذا بعض الوقت ”")
            deleted, failed = await delete_broadcast_actual_messages(context, log_id)
            log_admin_action(
                "delete_broadcast_actual", query.from_user.id,
                details=f"معرف السجل: {log_id} — نجح: {deleted} — تعذّر: {failed}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            row = get_broadcast_log(log_id)
            text, entities = build_broadcast_log_detail_message(row)
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_broadcast_log_detail_keyboard(log_id, back_page),
            )
            return


        if query.data == "points_settings":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بالمشرف.", show_alert=True)
                return
            text, entities = build_points_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_settings_keyboard(),
            )
            return

        if query.data == "points_text_settings":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بالمشرف.", show_alert=True)
                return
            text, entities = build_points_text_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_text_settings_keyboard(),
            )
            return

        if query.data == "points_restore_defaults":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بالمشرف.", show_alert=True)
                return
            set_setting("points_title", DEFAULT_POINTS_TITLE)
            set_setting("points_conditions", DEFAULT_POINTS_CONDITIONS)
            log_admin_action(
                "change_settings", query.from_user.id, details="إعادة نصوص قسم ربح للوضع الافتراضي",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            await _cb_answer("✅ تمت إعادة نصوص قسم ربح للوضع الافتراضي.")
            text, entities = build_points_text_settings_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_points_text_settings_keyboard(),
            )
            return

        if query.data == "points_toggle":
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بالمشرف.", show_alert=True)
                return
            new_value = "0" if get_setting("points_enabled") == "1" else "1"
            set_setting("points_enabled", new_value)
            log_admin_action(
                "change_settings", query.from_user.id,
                details=f"تفعيل قسم ربح: {'مفعّل' if new_value == '1' else 'معطّل'}",
                actor_name=query.from_user.full_name, actor_username=query.from_user.username,
            )
            text, entities = build_owner_points_section_message()
            await query.edit_message_text(
                text=text, entities=entities,
                reply_markup=build_owner_points_section_keyboard(),
            )
            return

        if query.data.startswith("points_edit:"):
            if not is_owner(query.from_user.id):
                await _cb_answer("⛔ هذا القسم خاص بالمشرف.", show_alert=True)
                return
            field = query.data.split(":", 1)[1]
            labels = {
                "points_per_user": "عدد النقاط لكل مستخدم جديد",
                "points_required": "عدد النقاط المطلوبة للمكافأة",
                "reward_type": "نوع أو عملة المكافأة",
                "reward_value": "قيمة المكافأة",
                "points_title": "عنوان قسم ربح",
                "points_conditions": "شروط قسم ربح",
            }
            context.user_data["awaiting_setting"] = field
            await query.edit_message_text(
                f"✍️ أرسل الآن {labels.get(field, 'القيمة الجديدة')} ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="points_settings", style="danger")
                ]]),
            )
            return

        if query.data == "remind_win":
            enabled = toggle_remind_win(query.from_user.id)
            try:
                await query.edit_message_reply_markup(
                    reply_markup=build_main_keyboard(enabled, query.from_user.id)
                )
            except Exception:
                pass
            return

        if query.data == "create_contest":
            text, entities = build_contest_section_message()
            await query.edit_message_text(
                text=text,
                entities=entities,
                reply_markup=build_contest_section_keyboard(),
            )
            return

        if query.data == "terms":
            text, entities = build_terms_message()
            await query.edit_message_text(
                text=text,
                entities=entities,
                reply_markup=build_terms_keyboard(),
            )
            return

        if query.data == "support_bot":
            text, entities = build_support_bot_message()
            await query.edit_message_text(
                text=text,
                entities=entities,
                reply_markup=build_support_bot_keyboard(),
            )
            return

        if query.data == "support_pay_stars":
            await context.bot.send_invoice(
                chat_id=query.message.chat_id,
                title="دعم البوت ⭐",
                description=(
                    f"ادفع {SUPPORT_BOT_STARS_AMOUNT} نجوم تيليجرام لدعم تطوير البوت 💖\n\n"
                    "كل نجمة تساعدنا في الاستمرار وتطوير ميزات جديدة!"
                ),
                payload="support_bot_stars",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice("دعم البوت", SUPPORT_BOT_STARS_AMOUNT)],
            )
            return

        replies = {}
        if query.data in replies:
            emoji_char, emoji_key = replies[query.data]
            text, entities = build_under_development_message(emoji_key=emoji_key, emoji_char=emoji_char)
            await query.message.reply_text(text=text, entities=entities)
    finally:
        # ضمان: إن لم يُرسَل أي رد على الضغطة داخل الفروع أعلاه (مثل فروع لا تعرض
        # تنبيهًا وتعتمد على رد فارغ)، نرسل ردًا فارغًا هنا حتى لا يبقى الزر
        # "معلّقًا" على تيليجرام. إن كان قد أُرسل رد بالفعل (خصوصًا تنبيه)، لا نكرره.
        if not _cb_answered:
            try:
                await query.answer()
            except Exception:
                pass

async def support_precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يوافق تلقائيًا على أي طلب دفع بنجوم تيليجرام (XTR) قبل تأكيد الشراء النهائي."""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def support_successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستدعى بعد اكتمال عملية الدفع بنجوم تيليجرام بنجاح."""
    await update.message.reply_text(
        f"✅ شكرًا لدعمك! تم استلام {SUPPORT_BOT_STARS_AMOUNT} نجوم بنجاح 💖"
    )

async def get_id_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "emoji_id"
    _bt, _be = bold_notice("أرسل الآن الإيموجي المتحرك الذي تريد معرفة رقمه 👇")
    await update.message.reply_text(text=_bt, entities=_be)

async def reset_test_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر خاص بمالك البوت فقط: /reset_test @username أو /reset_test user_id
    يحذف كل بيانات هذا المستخدم من Firestore (users + withdraw_requests) —
    تمامًا مثل سكربت الحذف الخارجي — لكن الفارق الجوهري هنا أنه يُفرغ أيضًا
    كاش المستخدم بالذاكرة (_USER_CACHE) *داخل نفس تشغيلة البوت الحيّة*.
    ⚠️ هذا هو سبب عدم احتساب النقطة عند تجربتك السابقة عبر السكربت الخارجي:
    ذلك السكربت يحذف من Firestore فعليًا، لكنه عملية منفصلة تمامًا عن عملية
    البوت نفسها، فلا يمكنه لمس _USER_CACHE داخل ذاكرة البوت — يبقى البوت
    "يتذكر" أن هذا المستخدم already `has_started`، فلا يُحتسَب كـ"مستخدم
    جديد فعليًا" (is_genuinely_new) عند دخوله من جديد، وبالتالي لا تُمنح
    نقطة صاحب السحب حتى مع تفعيل «منع الرشق». استخدام هذا الأمر من داخل
    البوت نفسه يحل المشكلة دون الحاجة لإعادة تشغيل البوت بعد كل تجربة.
    """
    if not is_owner(update.effective_user.id):
        return
    if not context.args:
        _bt, _be = bold_notice("الاستخدام: /reset_test @username أو /reset_test user_id")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    identifier = context.args[0].strip()
    if identifier.lstrip("-").isdigit():
        user_id = int(identifier)
    else:
        found = find_bot_user_by_username(identifier)
        user_id = found.get("user_id") if found else None

    if user_id is None:
        _bt, _be = bold_notice(f"❌ لم يتم العثور على أي مستخدم بهذا اليوزر: {identifier}")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    withdraw_docs = list(
        fs_db().collection("withdraw_requests").where("user_id", "==", user_id).stream()
    )
    for doc in withdraw_docs:
        doc.reference.delete()

    user_ref = _user_doc_ref(user_id)
    existed = user_ref.get().exists
    if existed:
        user_ref.delete()

    # 🔑 الخطوة الحاسمة: تفريغ الكاش الحيّ بالذاكرة لهذا المستخدم، وإلا
    # سيبقى البوت يعامله كمستخدم قديم رغم حذف بياناته من قاعدة البيانات.
    _invalidate_moderator_cache(user_id)

    _bt, _be = bold_notice(
        f"✅ تم حذف كل بيانات المستخدم {user_id} من القاعدة، "
        "وتم تفريغ كاش الذاكرة الخاص به.\n"
        "يمكنك الآن تجربة /start معه من جديد كأنه مستخدم جديد فعليًا."
    )
    await update.message.reply_text(text=_bt, entities=_be)

async def channel_forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يلتقط رسالة مُعاد توجيهها من قناة إلى خاص البوت (الخطوة 2 في شاشة تسجيل القناة)،
    يتأكد أن البوت مشرف فيها وأن المُرسل مشرف فيها أيضًا، ثم يسجّلها له.
    هذا مسار تسجيل احتياطي ضروري لأن حدث my_chat_member لا يُعاد إرساله للقنوات
    التي كان البوت مشرفًا فيها بالفعل قبل تشغيل هذا الإصدار من الكود.
    """
    message = update.effective_message
    if message is None or message.chat.type != "private":
        return

    origin_chat = None
    forward_origin = getattr(message, "forward_origin", None)
    if forward_origin is not None and getattr(forward_origin, "type", None) == "channel":
        origin_chat = forward_origin.chat
    elif getattr(message, "forward_from_chat", None) is not None:
        origin_chat = message.forward_from_chat

    if origin_chat is None or origin_chat.type != "channel":
        return

    async def delete_forwarded_message():
        try:
            await message.delete()
        except Exception as exc:
            logger.warning("تعذر حذف رسالة القناة المُعادة: %s", exc)

    if origin_chat.username and origin_chat.username.lower() == ANNOUNCE_CHANNEL_USERNAME.lower():
        _bt, _be = bold_notice("⚠️ لا يمكن تسجيل هذه القناة.")
        await message.reply_text(text=_bt, entities=_be)
        await delete_forwarded_message()
        return

    user = update.effective_user
    try:
        bot_member = await context.bot.get_chat_member(origin_chat.id, context.bot.id)
        user_member = await context.bot.get_chat_member(origin_chat.id, user.id)
    except Exception:
        _bt, _be = bold_notice("⚠️ تعذر التحقق من القناة، أعد المحاولة.")
        await message.reply_text(text=_bt, entities=_be)
        await delete_forwarded_message()
        return

    if bot_member.status not in ("administrator", "creator"):
        _bt, _be = bold_notice("⚠️ البوت ليس مشرفًا في هذه القناة.")
        await message.reply_text(text=_bt, entities=_be)
        await delete_forwarded_message()
        return

    if user_member.status not in ("administrator", "creator"):
        _bt, _be = bold_notice("يجب أن تكون مشرفًا في هذه القناة لتسجيلها.")
        await message.reply_text(text=_bt, entities=_be)
        await delete_forwarded_message()
        return

    if context.user_data.get("awaiting") == "gw_condition_channel_private":
        pending = context.user_data.setdefault("gw_condition_channels_pending", [])
        if any(str(c.get("ref")) == str(origin_chat.id) for c in pending):
            _bt, _be = bold_notice("⚠️ هذه القناة مضافة بالفعل كشرط.")
            await message.reply_text(text=_bt, entities=_be)
            await delete_forwarded_message()
            return
        if len(pending) >= GW_CONDITION_CHANNELS_MAX:
            _bt, _be = bold_notice("❌ يمكنك إضافة قناتين كحد أقصى!")
            await message.reply_text(text=_bt, entities=_be)
            await delete_forwarded_message()
            return

        chat_title = origin_chat.title or str(origin_chat.id)
        invite_url = None
        try:
            invite_link = await context.bot.create_chat_invite_link(origin_chat.id)
            invite_url = invite_link.invite_link
        except Exception:
            try:
                invite_url = await context.bot.export_chat_invite_link(origin_chat.id)
            except Exception:
                invite_url = None

        pending.append({"ref": origin_chat.id, "title": chat_title, "url": invite_url})

        if len(pending) >= GW_CONDITION_CHANNELS_MAX:
            context.user_data["gw_condition_channels"] = pending
            context.user_data.pop("gw_condition_channels_pending", None)
            context.user_data.pop("awaiting", None)
            for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
                context.user_data.setdefault(key, default)

            confirm_text, confirm_entities = build_giveaway_condition_linked_message(
                [c["title"] for c in pending],
            )
            await message.reply_text(text=confirm_text, entities=confirm_entities)

            settings_text, settings_entities = build_giveaway_settings_message()
            await message.reply_text(
                text=settings_text,
                entities=settings_entities,
                reply_markup=build_giveaway_settings_keyboard(context.user_data),
            )
        else:
            text, entities = build_giveaway_condition_private_message(added_count=len(pending))
            await message.reply_text(
                text=text,
                entities=entities,
                reply_markup=build_giveaway_condition_private_keyboard(added_count=len(pending)),
            )
        await delete_forwarded_message()
        return

    chat_title = origin_chat.title or (f"@{origin_chat.username}" if origin_chat.username else str(origin_chat.id))
    save_registered_chat(
        chat_id=origin_chat.id,
        owner_id=user.id,
        chat_title=chat_title,
        chat_type="channel",
    )
    _bt, _be = bold_notice(f"✅ تم تسجيل القناة «{chat_title}» بنجاح ")
    await message.reply_text(text=_bt, entities=_be)
    await delete_forwarded_message()


async def group_activation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    يلتقط كتابة «تفعيل روليت» داخل الجروب نفسه (الخطوة 2 في شاشة تسجيل الجروب)،
    يتأكد أن البوت والمُرسل مشرفان في الجروب، ثم يسجّله.
    """
    message = update.effective_message
    if message is None or message.chat.type not in ("group", "supergroup"):
        return
    if not message.text or "تفعيل روليت" not in message.text:
        return

    chat = message.chat
    user = update.effective_user
    try:
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        user_member = await context.bot.get_chat_member(chat.id, user.id)
    except Exception:
        _bt, _be = bold_notice("تعذر التحقق من الصلاحيات، تأكد أن البوت مشرف في الجروب.")
        await message.reply_text(text=_bt, entities=_be)
        return

    if bot_member.status != "administrator":
        _bt, _be = bold_notice("يجب إضافة البوت كمشرف في الجروب أولاً.")
        await message.reply_text(text=_bt, entities=_be)
        return

    if user_member.status not in ("administrator", "creator"):
        _bt, _be = bold_notice("يجب أن تكون مشرفًا في هذا الجروب لتفعيله.")
        await message.reply_text(text=_bt, entities=_be)
        return

    chat_title = chat.title or str(chat.id)
    save_registered_chat(
        chat_id=chat.id,
        owner_id=user.id,
        chat_title=chat_title,
        chat_type=chat.type,
    )
    _bt, _be = bold_notice(f"✅ تم تفعيل الروليت لجروب «{chat_title}» بنجاح.")
    await message.reply_text(text=_bt, entities=_be)


_ADMIN_QUERY_INVISIBLE_CHARS = (
    "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\ufeff"
)
_ADMIN_QUERY_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩" "۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


def _sanitize_admin_query_input(raw: str) -> str:
    """ينظّف نص الإدخال (معرف/يوزر) من محارف التحكم غير المرئية الشائعة عند
    اللصق من كيبورد عربي (علامات اتجاه RTL/LTR وما شابه)، ويحوّل الأرقام
    العربية/الفارسية إلى أرقام إنجليزية عادية — حتى لا يفشل التعرف على معرف
    رقمي صحيح بصمت لمجرد وجود محارف خفية لا تظهر للمستخدم."""
    if not raw:
        return ""
    cleaned = "".join(ch for ch in raw if ch not in _ADMIN_QUERY_INVISIBLE_CHARS)
    cleaned = cleaned.translate(_ADMIN_QUERY_DIGIT_TRANSLATION)
    return cleaned.strip()


def _resolve_admin_user_query(raw: str):
    """يحاول تحويل نص أرسله المالك (معرف رقمي أو يوزر) إلى بيانات مستخدم بوت
    معروفة. يعيد (row, user_id):
    - (FSRow, user_id) إن وُجد المستخدم في قاعدة بيانات البوت.
    - (None, user_id) إن كان المدخل معرفًا رقميًا صحيحًا لكن المستخدم لم يبدأ
      محادثة مع البوت بعد (يسمح هذا بحظر استباقي بالمعرف فقط).
    - (None, None) إن تعذّر التعرف على المدخل إطلاقًا (يوزر غير معروف مثلاً).
    """
    raw = _sanitize_admin_query_input(raw)
    if not raw:
        return None, None
    if raw.lstrip("-").isdigit():
        user_id = int(raw)
        return get_bot_user(user_id), user_id
    row = find_bot_user_by_username(raw)
    if row:
        return row, row.get("user_id")
    return None, None


def _detect_broadcast_content(message) -> tuple:
    """يكتشف تلقائيًا نوع محتوى رسالة المالك (لأغراض العرض/الأرشفة والإحصائيات
    فقط — الإرسال الفعلي عبر copy_message لا يحتاج معرفة النوع أصلًا). يعيد
    (content_type, caption_or_text) — يدعم أي نوع رسالة يقبله تيليجرام."""
    if message.text:
        return "text", message.text
    if message.photo:
        return "photo", message.caption
    if message.video:
        return "video", message.caption
    if message.document:
        return "document", message.caption
    if message.audio:
        return "audio", message.caption
    if message.voice:
        return "voice", message.caption
    if message.animation:
        return "animation", message.caption
    if message.video_note:
        return "video_note", None
    if message.sticker:
        return "sticker", None
    if message.poll:
        return "poll", None
    return "other", message.caption


async def handle_broadcast_content_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يلتقط أي نوع محتوى (صورة/فيديو/ملف/صوت/رسالة صوتية/GIF/ملصق/فيديو دائري/
    استطلاع...) عندما يكون المالك بصدد إعداد إذاعة جديدة — بلا حاجة لاختيار
    النوع مسبقًا. الرسائل النصية الصِرفة يلتقطها text_router بنفس awaiting."""
    awaiting = context.user_data.get("awaiting")
    if awaiting != "broadcast_await_content":
        return
    if not is_owner(update.effective_user.id):
        context.user_data.pop("awaiting", None)
        return
    # ⚠️ حماية إضافية: تجهيز الإذاعة لا يُقبل إلا من داخل محادثة المالك الخاصة
    # مع البوت، وليس من أي مجموعة، تجنبًا لأي التباس (المعالج أصلًا مسجَّل بقيد
    # ChatType.PRIVATE فقط، وهذا فحص مضاعف عند مستوى المنطق نفسه).
    if update.effective_chat.type != "private":
        return

    message = update.message
    content_type, caption = _detect_broadcast_content(message)
    if content_type == "text":
        # الرسائل النصية الصِرفة (بلا وسائط) يعالجها text_router حصرًا، تجنبًا
        # لالتقاطها مرتين من معالجين مختلفين.
        return

    if _BROADCAST_STATE["running"]:
        await message.reply_text("⚠️ توجد إذاعة قيد التنفيذ بالفعل، انتظر حتى تنتهي أو أوقفها أولاً.")
        return

    context.user_data.pop("awaiting", None)
    # لا تبدأ الإرسال فورًا: تُحفظ مرجعية الرسالة (chat_id/message_id) مؤقتًا
    # وتُعرض معاينة فعلية طبق الأصل عبر copy_message (تدعم أي نوع محتوى دون
    # أي فرع خاص لكل نوع) مع زرّي «تأكيد» و«إلغاء» قبل إذاعتها للجميع.
    context.user_data["broadcast_pending"] = {
        "content_type": content_type,
        "source_chat_id": message.chat_id,
        "source_message_id": message.message_id,
        "caption": caption,
    }
    try:
        await context.bot.copy_message(
            chat_id=message.chat_id, from_chat_id=message.chat_id, message_id=message.message_id,
        )
    except Exception:
        pass
    text, entities = build_broadcast_confirm_message(content_type)
    await message.reply_text(
        text=text, entities=entities,
        reply_markup=build_broadcast_confirm_keyboard(),
    )


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ملاحظة: فحص الاشتراك الإجباري يتم مركزيًا عبر _subscription_gate_handler
    # (group=-1) قبل الوصول إلى هذا المعالج أصلاً — لا حاجة لتكراره هنا.
    awaiting = context.user_data.get("awaiting")
    awaiting_setting = context.user_data.get("awaiting_setting")

    if awaiting_setting:
        await handle_setting_input(update, context)
        return

    if awaiting == "broadcast_await_content":
        if not is_owner(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return
        if _BROADCAST_STATE["running"]:
            await update.message.reply_text("⚠️ توجد إذاعة قيد التنفيذ بالفعل، انتظر حتى تنتهي أو أوقفها أولاً.")
            return
        context.user_data.pop("awaiting", None)
        # لا تبدأ الإرسال فورًا: تُحفظ مرجعية الرسالة (chat_id/message_id) مؤقتًا
        # وتُعرض للمالك معاينة عبر copy_message مع زرّي «تأكيد» و«إلغاء» —
        # الإرسال الفعلي لا يبدأ إلا بعد الضغط الصريح على «تأكيد الإرسال للجميع».
        context.user_data["broadcast_pending"] = {
            "content_type": "text",
            "source_chat_id": update.message.chat_id,
            "source_message_id": update.message.message_id,
            "text": update.message.text,
        }
        try:
            await context.bot.copy_message(
                chat_id=update.message.chat_id, from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
            )
        except Exception:
            pass
        text, entities = build_broadcast_confirm_message("text")
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_broadcast_confirm_keyboard(),
        )
        return

    if awaiting == "broadcast_log_edit_text":
        if not is_owner(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return
        log_id = context.user_data.get("broadcast_log_edit_id")
        back_page = context.user_data.get("broadcast_log_edit_back_page", 1)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("broadcast_log_edit_id", None)
        context.user_data.pop("broadcast_log_edit_back_page", None)
        new_text = update.message.text
        if not log_id or not edit_broadcast_log_content(log_id, new_text):
            await update.message.reply_text("⚠️ تعذّر تعديل هذا السجل (ربما لم يعد موجودًا).")
            return
        row = get_broadcast_log(log_id)
        await update.message.reply_text("✅ تم تعديل النص المؤرشف بنجاح.")
        text, entities = build_broadcast_log_detail_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_broadcast_log_detail_keyboard(log_id, back_page),
        )
        return

    if awaiting == "star_cost_edit":
        if not is_owner(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            context.user_data.pop("star_cost_edit_tier", None)
            return
        tier = context.user_data.pop("star_cost_edit_tier", None)
        context.user_data.pop("awaiting", None)
        value = update.message.text.strip()
        if tier not in STAR_WITHDRAW_TIERS or not value.isdigit():
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا أكبر من أو يساوي صفر ”")
            return
        set_star_cost(tier, int(value))
        log_admin_action(
            "change_settings", update.effective_user.id, details=f"star_cost_{tier} = {value}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        text, entities = build_star_settings_message()
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_star_settings_keyboard(),
        )
        return

    if awaiting == "withdraw_channel_set":
        if not is_owner(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return
        username = _normalize_channel_username(update.message.text)
        if not username:
            await update.message.reply_text("⚠️ أرسل يوزر صحيح للقناة (مثال: @channel أو رابط t.me/channel) ”")
            return
        context.user_data.pop("awaiting", None)
        try:
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            await update.message.reply_text(
                f"⚠️ تعذّر العثور على القناة @{username} ({exc}). تأكد من صحة اليوزر وأن القناة عامة، ثم حاول مجددًا.",
            )
            text, entities = build_withdraw_channel_settings_message()
            await update.message.reply_text(
                text=text, entities=entities,
                reply_markup=build_withdraw_channel_settings_keyboard(),
            )
            return
        warning = ""
        try:
            member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if member.status not in ("administrator", "creator"):
                warning = (
                    "⚠️ تنبيه: البوت ليس مشرفًا في هذه القناة، يجب ترقيته إلى مشرف "
                    "حتى يتمكن من إرسال طلبات السحب إليها."
                )
        except Exception as exc:
            warning = f"⚠️ تنبيه: تعذّر التحقق من صلاحيات البوت في القناة ({exc})."
        set_withdraw_channel(chat.id, username, chat.title or "")
        log_admin_action(
            "change_settings", update.effective_user.id, details=f"تحديد قناة استقبال السحب: @{username}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        await update.message.reply_text(
            f"✅ تم تحديد قناة استقبال طلبات السحب: @{username}" + (f"\n\n{warning}" if warning else ""),
        )
        text, entities = build_withdraw_channel_settings_message()
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_withdraw_channel_settings_keyboard(),
        )
        return

    if awaiting == "new_user_notify_channel_set":
        if not is_owner(update.effective_user.id):
            context.user_data.pop("awaiting", None)
            return
        username = _normalize_channel_username(update.message.text)
        if not username:
            await update.message.reply_text("⚠️ أرسل يوزر صحيح للقناة (مثال: @channel أو رابط t.me/channel) ”")
            return
        context.user_data.pop("awaiting", None)
        try:
            chat = await context.bot.get_chat(f"@{username}")
        except Exception as exc:
            await update.message.reply_text(
                f"⚠️ تعذّر العثور على القناة @{username} ({exc}). تأكد من صحة اليوزر وأن القناة عامة، ثم حاول مجددًا.",
            )
            text, entities = build_new_user_notify_section_message()
            await update.message.reply_text(
                text=text, entities=entities,
                reply_markup=build_new_user_notify_section_keyboard(),
            )
            return
        warning = ""
        try:
            member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if member.status not in ("administrator", "creator"):
                warning = (
                    "⚠️ تنبيه: البوت ليس مشرفًا في هذه القناة، يجب ترقيته إلى مشرف "
                    "حتى يتمكن من إرسال الإشعارات إليها."
                )
        except Exception as exc:
            warning = f"⚠️ تنبيه: تعذّر التحقق من صلاحيات البوت في القناة ({exc})."
        set_new_user_notify_channel(chat.id, username, chat.title or "")
        log_admin_action(
            "change_settings", update.effective_user.id,
            details=f"تحديد قناة إشعارات دخول المستخدمين: @{username}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        await update.message.reply_text(
            f"✅ تم تحديد قناة إشعارات دخول المستخدمين: @{username}" + (f"\n\n{warning}" if warning else ""),
        )
        text, entities = build_new_user_notify_section_message()
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_new_user_notify_section_keyboard(),
        )
        return

    if awaiting == "admin_channel_add_username":
        username = _normalize_channel_username(update.message.text)
        if not username:
            await update.message.reply_text("⚠️ أرسل يوزر صحيح للقناة (مثال: @channel أو رابط t.me/channel) ”")
            return
        context.user_data["admin_new_channel_username"] = username
        context.user_data["awaiting"] = "admin_channel_add_target"
        await update.message.reply_text(
            "🎯 أرسل الآن عدد الأعضاء المستهدف لهذه القناة (رقم)، أو أرسل 0 إن كنت لا تريد تحديد هدف ”",
        )
        return

    if awaiting == "admin_channel_add_target":
        raw = (update.message.text or "").strip()
        if not raw.isdigit():
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا (أو 0 لعدم تحديد هدف) ”")
            return
        target = int(raw)
        username = context.user_data.get("admin_new_channel_username")
        context.user_data.pop("awaiting", None)
        if not username:
            return
        if target <= 0:
            channel_id = create_required_channel(
                username=username, target_count=None, auto_delete_on_target=False,
                added_by=update.effective_user.id,
            )
            log_admin_action(
                "add_channel", update.effective_user.id, details=f"@{username}",
                actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
            )
            context.user_data.pop("admin_new_channel_username", None)
            warning = await _check_bot_can_verify_channel(context, username)
            channel = get_required_channel(channel_id)
            text, entities = await build_owner_sub_channel_message(context, channel)
            await update.message.reply_text(
                f"✅ تمت إضافة القناة @{username} بنجاح." + (f"\n\n{warning}" if warning else ""),
            )
            await update.message.reply_text(
                text=text, entities=entities,
                reply_markup=build_owner_sub_channel_keyboard(channel),
            )
            return
        context.user_data["admin_new_channel_target"] = target
        await update.message.reply_text(
            f"⚙️ عند وصول القناة إلى {target} عضو، ماذا تريد أن يحدث؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔄 حذفها تلقائيًا من القائمة", callback_data="owner_sub_add_autodel_yes", style="primary",
                )],
                [InlineKeyboardButton(
                    "♾️ إبقاؤها دائمًا بدون حذف", callback_data="owner_sub_add_autodel_no", style="primary",
                )],
            ]),
        )
        return

    if awaiting == "admin_channel_edit_button_text":
        channel_id = context.user_data.get("admin_channel_id")
        channel = get_required_channel(channel_id) if channel_id else None
        raw = (update.message.text or "").strip()
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admin_channel_id", None)
        if not channel:
            return
        new_button_text = "" if raw == "-" else raw
        update_required_channel(channel_id, button_text=new_button_text)
        channel = get_required_channel(channel_id)
        text, entities = await build_owner_sub_channel_message(context, channel)
        await update.message.reply_text(
            "✅ تم حذف الاسم المخصص، سيظهر اليوزر الخام في الزر." if not new_button_text
            else f"✅ تم تحديث الاسم المعروض إلى: {new_button_text}",
        )
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_sub_channel_keyboard(channel),
        )
        return

    if awaiting == "admin_channel_edit_username":
        channel_id = context.user_data.get("admin_channel_id")
        channel = get_required_channel(channel_id) if channel_id else None
        username = _normalize_channel_username(update.message.text)
        if not username:
            await update.message.reply_text("⚠️ أرسل يوزر صحيح للقناة (مثال: @channel أو رابط t.me/channel) ”")
            return
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admin_channel_id", None)
        if not channel:
            return
        old_username = channel.get("username", "")
        updates = {"username": username}
        if channel.get("url") in (f"https://t.me/{old_username}", "", None):
            updates["url"] = f"https://t.me/{username}"
        update_required_channel(channel_id, **updates)
        warning = await _check_bot_can_verify_channel(context, username)
        channel = get_required_channel(channel_id)
        text, entities = await build_owner_sub_channel_message(context, channel)
        await update.message.reply_text(
            f"✅ تم تعديل يوزر القناة إلى @{username} بنجاح." + (f"\n\n{warning}" if warning else ""),
        )
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_sub_channel_keyboard(channel),
        )
        return

    if awaiting == "admin_channel_edit_link":
        channel_id = context.user_data.get("admin_channel_id")
        channel = get_required_channel(channel_id) if channel_id else None
        url = (update.message.text or "").strip()
        if not url:
            await update.message.reply_text("⚠️ أرسل رابطًا صحيحًا ”")
            return
        if not url.startswith("http"):
            url = f"https://{url}"
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admin_channel_id", None)
        if not channel:
            return
        update_required_channel(channel_id, url=url)
        channel = get_required_channel(channel_id)
        text, entities = await build_owner_sub_channel_message(context, channel)
        await update.message.reply_text("✅ تم تعديل رابط القناة بنجاح.")
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_sub_channel_keyboard(channel),
        )
        return

    if awaiting == "admin_channel_edit_target":
        channel_id = context.user_data.get("admin_channel_id")
        channel = get_required_channel(channel_id) if channel_id else None
        raw = (update.message.text or "").strip()
        if not raw.isdigit():
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا (أو 0 لإلغاء الهدف) ”")
            return
        target = int(raw)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admin_channel_id", None)
        if not channel:
            return
        update_required_channel(channel_id, target_count=(target if target > 0 else None))
        channel = get_required_channel(channel_id)
        text, entities = await build_owner_sub_channel_message(context, channel)
        await update.message.reply_text(
            "✅ تم إلغاء الهدف." if target <= 0 else f"✅ تم تحديد الهدف: {target} عضو.",
        )
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_sub_channel_keyboard(channel),
        )
        return

    if awaiting == "mod_add_lookup":
        context.user_data.pop("awaiting", None)
        if not (is_owner(update.effective_user.id) or moderator_can(update.effective_user.id, "add_admins")):
            return
        row, target_id = _resolve_admin_user_query(update.message.text)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        if is_owner(target_id):
            await update.message.reply_text("⚠️ هذا المستخدم أصلًا أحد ملّاك البوت.")
            return
        if is_moderator(target_id):
            await update.message.reply_text("ℹ️ هذا المستخدم مشرف بالفعل.")
            return
        username = row.get("username") if row else None
        first_name = row.get("first_name") if row else None
        add_moderator(target_id, added_by=update.effective_user.id, username=username, first_name=first_name)
        log_admin_action(
            "add_admin", update.effective_user.id, details=f"معرف المشرف الجديد: {target_id}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        new_row = get_moderator(target_id)
        if is_owner(update.effective_user.id):
            await update.message.reply_text("✅ تمت إضافة المشرف بنجاح. الآن حدّد صلاحياته:")
            text, entities = build_moderator_perms_message(new_row)
            await update.message.reply_text(
                text=text, entities=entities,
                reply_markup=build_moderator_perms_keyboard(new_row),
            )
        else:
            await update.message.reply_text(
                "✅ تمت إضافة المشرف بنجاح. سيقوم مالك البوت بتحديد صلاحياته.",
            )
        return

    if awaiting == "referral_add_lookup":
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        row, target_id = _resolve_admin_user_query(update.message.text)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        if get_referral(target_id):
            await update.message.reply_text("ℹ️ هذا المستخدم يملك رابط دعوة بالفعل.")
            return
        context.user_data["awaiting"] = "referral_add_percentage"
        context.user_data["referral_target_id"] = target_id
        context.user_data["referral_target_username"] = row.get("username") if row else None
        context.user_data["referral_target_first_name"] = row.get("first_name") if row else None
        await update.message.reply_text(
            "✍️ أرسل الآن نسبة الإحالة لهذا المستخدم (رقم من 0 إلى 100)، "
            f"أو أرسل - لاستخدام النسبة الافتراضية ({get_referral_default_percentage()}%) ”",
        )
        return

    if awaiting == "referral_add_percentage":
        context.user_data.pop("awaiting", None)
        target_id = context.user_data.pop("referral_target_id", None)
        username = context.user_data.pop("referral_target_username", None)
        first_name = context.user_data.pop("referral_target_first_name", None)
        if not target_id or not is_owner(update.effective_user.id):
            return
        raw = (update.message.text or "").strip()
        if raw == "-":
            percentage = None
        elif raw.isdigit() and 0 <= int(raw) <= 100:
            percentage = int(raw)
        else:
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا من 0 إلى 100، أو - لاستخدام النسبة الافتراضية.")
            return
        add_referrer(target_id, added_by=update.effective_user.id, percentage=percentage,
                      username=username, first_name=first_name)
        applied_pct = percentage if percentage is not None else get_referral_default_percentage()
        log_admin_action(
            "add_referrer", update.effective_user.id,
            details=f"معرف المستخدم: {target_id} — النسبة: {applied_pct}%",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        row = get_referral(target_id)
        await update.message.reply_text("✅ تمت إضافة رابط الدعوة بنجاح.")
        text, entities = build_referrer_profile_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_referrer_profile_keyboard(row),
        )
        return

    if awaiting == "referral_search_lookup":
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        _, target_id = _resolve_admin_user_query(update.message.text)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        row = get_referral(target_id)
        if not row:
            await update.message.reply_text("⚠️ هذا المستخدم ليس صاحب رابط دعوة.")
            return
        text, entities = build_referrer_profile_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_referrer_profile_keyboard(row),
        )
        return

    if awaiting == "referral_edit_percentage":
        target_id = context.user_data.pop("referral_target_id", None)
        context.user_data.pop("awaiting", None)
        if not target_id or not is_owner(update.effective_user.id):
            return
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or not (0 <= int(raw) <= 100):
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا من 0 إلى 100.")
            return
        set_referrer_percentage(target_id, int(raw))
        log_admin_action(
            "edit_referrer_percentage", update.effective_user.id,
            details=f"معرف المستخدم: {target_id} — النسبة الجديدة: {raw}%",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        row = get_referral(target_id)
        if not row:
            await update.message.reply_text("⚠️ هذا المستخدم لم يعد صاحب رابط دعوة.")
            return
        text, entities = build_referrer_profile_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_referrer_profile_keyboard(row),
        )
        return

    if awaiting == "referral_default_pct":
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or not (0 <= int(raw) <= 100):
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا من 0 إلى 100.")
            return
        set_referral_default_percentage(int(raw))
        log_admin_action(
            "change_settings", update.effective_user.id, details=f"النسبة الافتراضية للإحالة: {raw}%",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        text, entities = build_owner_referrals_settings_message()
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_referrals_settings_keyboard(),
        )
        return

    if awaiting == "referral_signup_points":
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        raw = (update.message.text or "").strip()
        if not raw.isdigit():
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا.")
            return
        set_referral_signup_points(int(raw))
        log_admin_action(
            "change_settings", update.effective_user.id, details=f"نقاط الإحالة عند 100%: {raw}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        text, entities = build_owner_referrals_settings_message()
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_owner_referrals_settings_keyboard(),
        )
        return

    if awaiting in ("points_manual_add_lookup", "points_manual_deduct_lookup"):
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        action = "add" if awaiting == "points_manual_add_lookup" else "deduct"
        row, target_id = _resolve_admin_user_query(update.message.text)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        context.user_data["awaiting"] = f"points_manual_{action}_amount"
        context.user_data["points_manual_target_id"] = target_id
        context.user_data["points_manual_back_page"] = 1
        context.user_data["points_manual_browse_prefix"] = "points_browse"
        verb = "إضافتها" if action == "add" else "خصمها"
        current = get_points(target_id)
        await update.message.reply_text(
            f"💎 رصيده الحالي: {current} نقطة\n"
            f"✍️ أرسل الآن عدد النقاط المراد {verb} (رقم صحيح موجب) ”",
        )
        return

    if awaiting in ("points_manual_add_amount", "points_manual_deduct_amount"):
        target_id = context.user_data.pop("points_manual_target_id", None)
        back_page = context.user_data.pop("points_manual_back_page", 1)
        browse_prefix = context.user_data.pop("points_manual_browse_prefix", "points_browse")
        context.user_data.pop("awaiting", None)
        if not target_id or not is_owner(update.effective_user.id):
            return
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            await update.message.reply_text("⚠️ أرسل رقمًا صحيحًا موجبًا أكبر من صفر.")
            return
        amount = int(raw)
        if awaiting == "points_manual_add_amount":
            new_balance = add_points_to_user(target_id, amount)
            log_admin_action(
                "add_points_manual", update.effective_user.id,
                details=f"معرف المستخدم: {target_id} — إضافة: {amount} نقطة — الرصيد الجديد: {new_balance}",
                actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
            )
            await update.message.reply_text(f"✅ تمت إضافة {amount} نقطة بنجاح. الرصيد الجديد: {new_balance} نقطة.")
        else:
            new_balance = deduct_points_from_user(target_id, amount)
            log_admin_action(
                "deduct_points_manual", update.effective_user.id,
                details=f"معرف المستخدم: {target_id} — خصم: {amount} نقطة — الرصيد الجديد: {new_balance}",
                actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
            )
            await update.message.reply_text(f"✅ تم خصم {amount} نقطة بنجاح. الرصيد الجديد: {new_balance} نقطة.")

        row = get_bot_user(target_id) or FSRow({"user_id": target_id})
        referral = get_referral(target_id)
        row = FSRow({
            "user_id": target_id,
            "username": row.get("username"),
            "first_name": row.get("first_name"),
            "points": new_balance,
            "referred_count": int(referral.get("referred_count") or 0) if referral else 0,
        })
        text, entities = build_user_points_profile_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_user_points_profile_keyboard(target_id, back_page, browse_prefix=browse_prefix),
        )
        return

    if awaiting == "admin_user_lookup":
        row, target_id = _resolve_admin_user_query(update.message.text)
        context.user_data.pop("awaiting", None)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        if row is None:
            await update.message.reply_text(
                "⚠️ لا توجد بيانات لهذا المعرف — لم يبدأ هذا المستخدم محادثة مع البوت بعد.",
            )
            return
        text, entities = build_user_profile_message(row)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_user_profile_keyboard(row),
        )
        return

    if awaiting == "reset_test_user_lookup":
        context.user_data.pop("awaiting", None)
        if not is_owner(update.effective_user.id):
            return
        row, target_id = _resolve_admin_user_query(update.message.text)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        # 🔑 حذف من قاعدة البيانات: طلبات السحب المرتبطة بهذا المستخدم +
        # مستند المستخدم نفسه users/{id}.
        withdraw_docs = list(
            fs_db().collection("withdraw_requests").where("user_id", "==", target_id).stream()
        )
        for doc in withdraw_docs:
            doc.reference.delete()
        user_ref = _user_doc_ref(target_id)
        if user_ref.get().exists:
            user_ref.delete()
        # 🔑 وتفريغ كاش الذاكرة الحيّ لنفس المستخدم — بدون هذه الخطوة يبقى
        # البوت يعامله كمستخدم قديم رغم حذفه من القاعدة (هذا كان سبب عدم
        # احتساب نقطة عند تجربته من جديد كمستخدم "جديد فعليًا").
        _invalidate_moderator_cache(target_id)
        await update.message.reply_text(
            f"✅ تم حذف كل بيانات المستخدم {target_id} من القاعدة، وتفريغ كاش الذاكرة الخاص به.\n"
            "يمكنك الآن تجربة /start معه من جديد كأنه مستخدم جديد فعليًا.",
        )
        return

    if awaiting == "admin_user_ban_lookup":
        row, target_id = _resolve_admin_user_query(update.message.text)
        context.user_data.pop("awaiting", None)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        if target_id in OWNER_IDS:
            await update.message.reply_text("⚠️ لا يمكن حظر مالك البوت.")
            return
        if row and row.get("banned"):
            await update.message.reply_text("ℹ️ هذا المستخدم محظور بالفعل.")
            return
        context.user_data["awaiting"] = "admin_user_ban_reason"
        context.user_data["admin_ban_target_id"] = target_id
        await update.message.reply_text("✍️ أرسل الآن سبب الحظر، أو أرسل - لتركه بدون سبب ”")
        return

    if awaiting == "admin_user_ban_reason":
        target_id = context.user_data.get("admin_ban_target_id")
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admin_ban_target_id", None)
        if not target_id:
            return
        reason = (update.message.text or "").strip()
        if reason == "-":
            reason = ""
        ban_bot_user(target_id, reason, update.effective_user.id)
        log_admin_action(
            "ban_user", update.effective_user.id,
            details=f"معرف المستخدم: {target_id}" + (f" — السبب: {reason}" if reason else ""),
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        row = get_bot_user(target_id) or FSRow({"user_id": target_id, "banned": True, "ban_reason": reason})
        text, entities = build_user_profile_message(row)
        await update.message.reply_text("🚫 تم حظر المستخدم بنجاح.")
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_user_profile_keyboard(row),
        )
        return

    if awaiting == "admin_user_unban_lookup":
        row, target_id = _resolve_admin_user_query(update.message.text)
        context.user_data.pop("awaiting", None)
        if target_id is None:
            await update.message.reply_text(
                "⚠️ لم يتم التعرف على هذا المدخل. أرسل معرفًا رقميًا، أو يوزر مستخدم استخدم البوت من قبل ”",
            )
            return
        if not row or not row.get("banned"):
            await update.message.reply_text("ℹ️ هذا المستخدم غير محظور أصلاً.")
            return
        unban_bot_user(target_id)
        log_admin_action(
            "unban_user", update.effective_user.id, details=f"معرف المستخدم: {target_id}",
            actor_name=update.effective_user.full_name, actor_username=update.effective_user.username,
        )
        row = get_bot_user(target_id)
        text, entities = build_user_profile_message(row)
        await update.message.reply_text("✅ تم فك حظر المستخدم بنجاح.")
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_user_profile_keyboard(row),
        )
        return

    if awaiting == "admgw_search_lookup":
        raw_code = (update.message.text or "").strip()
        # يسمح بلصق الكود مع أو بدون بادئة # أو مسافات زائدة، ويقارن دون حساسية لحالة الأحرف.
        code = raw_code.lstrip("#").strip()
        filt = context.user_data.get("admgw_search_filt", "all")
        page = context.user_data.get("admgw_search_page", 1)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admgw_search_filt", None)
        context.user_data.pop("admgw_search_page", None)
        giveaway = get_giveaway(code) or get_giveaway(code.lower())
        if not giveaway:
            await update.message.reply_text(
                "⚠️ لم يتم العثور على أي سحب بهذا الكود ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admgw_list:{filt}:{page}", style="danger"),
                ]]),
            )
            return
        gw_code = giveaway["gw_code"]
        channel_title = get_chat_title_by_id(giveaway["chat_id"])
        participants_total = count_giveaway_participants(gw_code)
        channel_url = await build_contest_post_link(context, giveaway["chat_id"], giveaway.get("channel_message_id"))
        text, entities = build_admgw_detail_message(giveaway, None, channel_title, participants_total)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_admgw_detail_keyboard(gw_code, filt, page, channel_url=channel_url),
        )
        return

    if awaiting == "admct_search_lookup":
        raw_code = (update.message.text or "").strip()
        # يسمح بلصق الكود مع أو بدون بادئة # أو مسافات زائدة.
        code = raw_code.lstrip("#").strip()
        filt = context.user_data.get("admct_search_filt", "all")
        page = context.user_data.get("admct_search_page", 1)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admct_search_filt", None)
        context.user_data.pop("admct_search_page", None)
        contest = get_contest(code)
        if not contest:
            await update.message.reply_text(
                "⚠️ لم يتم العثور على أي مسابقة بهذا الكود ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admct_list:{filt}:{page}", style="danger"),
                ]]),
            )
            return
        contest_code = contest["contest_code"]
        channel_title = get_chat_title_by_id(contest["chat_id"])
        participants_total = count_contest_participants(contest_code)
        channel_url = await build_contest_post_link(context, contest["chat_id"], contest.get("channel_message_id"))
        text, entities = build_admct_detail_message(contest, None, channel_title, participants_total)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_admct_detail_keyboard(contest_code, filt, page, channel_url=channel_url),
        )
        return

    if awaiting == "admrr_search_lookup":
        raw_code = (update.message.text or "").strip().lstrip("#").strip()
        filt = context.user_data.get("admrr_search_filt", "all")
        page = context.user_data.get("admrr_search_page", 1)
        context.user_data.pop("awaiting", None)
        context.user_data.pop("admrr_search_filt", None)
        context.user_data.pop("admrr_search_page", None)
        try:
            roulette_id = int(raw_code)
        except ValueError:
            roulette_id = None
        roulette = get_roulette(roulette_id) if roulette_id is not None else None
        if not roulette:
            await update.message.reply_text(
                "⚠️ لم يتم العثور على أي سحب سريع بهذا الكود ”",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data=f"admrr_list:{filt}:{page}", style="danger"),
                ]]),
            )
            return
        participants_total = count_participants(roulette_id)
        text, entities = build_admrr_detail_message(roulette, None, participants_total)
        await update.message.reply_text(
            text=text, entities=entities,
            reply_markup=build_admrr_detail_keyboard(roulette_id, filt, page),
        )
        return

    if awaiting == "contest_cliche":
        context.user_data["contest_cliche_text"] = update.message.text
        context.user_data["contest_cliche_entities"] = update.message.entities
        context.user_data["awaiting"] = "contest_count"
        text, entities = build_contest_count_message()
        await update.message.reply_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_count_keyboard(),
        )
        return

    if awaiting == "contest_count":
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            _bt, _be = bold_notice("من فضلك أرسل رقمًا صحيحًا أكبر من صفر لعدد المتسابقين.")
            await update.message.reply_text(text=_bt, entities=_be)
            return
        context.user_data["contest_target_count"] = int(raw)
        context.user_data.pop("awaiting", None)
        text, entities = build_contest_end_method_message()
        await update.message.reply_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_end_method_keyboard(),
        )
        return

    if awaiting == "contest_votes_target":
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            _bt, _be = bold_notice("من فضلك أرسل رقمًا صحيحًا أكبر من صفر لعدد الأصوات.")
            await update.message.reply_text(text=_bt, entities=_be)
            return
        context.user_data["contest_votes_target"] = int(raw)
        context.user_data["awaiting"] = "contest_winners_count"
        text, entities = build_contest_winners_message()
        await update.message.reply_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_winners_keyboard(),
        )
        return

    if awaiting == "contest_winners_count":
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            _bt, _be = bold_notice("من فضلك أرسل رقمًا صحيحًا أكبر من صفر لعدد الفائزين.")
            await update.message.reply_text(text=_bt, entities=_be)
            return
        context.user_data["contest_winners_count"] = int(raw)
        context.user_data.pop("awaiting", None)
        for key, default in CONTEST_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)

        confirm_text, confirm_entities = build_contest_winners_confirm_message()
        await update.message.reply_text(text=confirm_text, entities=confirm_entities)

        settings_text, settings_entities = build_contest_settings_message()
        await update.message.reply_text(
            text=settings_text,
            entities=settings_entities,
            reply_markup=build_contest_settings_keyboard(context.user_data),
        )
        return

    if awaiting == "gw_cliche":
        context.user_data["gw_cliche_text"] = update.message.text
        context.user_data["gw_cliche_entities"] = update.message.entities
        context.user_data.pop("awaiting", None)
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        text, entities = build_giveaway_settings_message()
        await update.message.reply_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if awaiting == "gw_vote_code":
        raw_code = (update.message.text or "").strip()
        participant = get_participant_by_code(raw_code) if raw_code else None
        contest = get_contest(participant["contest_code"]) if participant else None
        if not participant or not contest or contest["status"] != "open":
            text, entities = build_giveaway_vote_code_error_message()
            await update.message.reply_text(
                text=text,
                entities=entities,
                reply_markup=build_giveaway_vote_code_error_keyboard(),
            )
            return

        context.user_data["gw_vote_contest_code"] = contest["contest_code"]
        context.user_data["gw_vote_participant_id"] = participant["user_id"]
        context.user_data["gw_vote_participant_code"] = raw_code
        context.user_data["gw_vote_display_name"] = participant.get("display_name") or "متسابق"
        context.user_data.pop("awaiting", None)
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)

        confirm_text, confirm_entities = build_giveaway_vote_linked_message(raw_code)
        await update.message.reply_text(text=confirm_text, entities=confirm_entities)

        settings_text, settings_entities = build_giveaway_settings_message()
        await update.message.reply_text(
            text=settings_text,
            entities=settings_entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if awaiting == "gw_condition_channel_public":
        raw_lines = [
            line.strip() for line in (update.message.text or "").splitlines() if line.strip()
        ]
        if not raw_lines:
            text, entities = build_giveaway_condition_error_message()
            await update.message.reply_text(
                text=text, entities=entities, reply_markup=build_giveaway_condition_public_keyboard(),
            )
            return
        if len(raw_lines) > GW_CONDITION_CHANNELS_MAX:
            text, entities = build_giveaway_condition_max_error_message()
            await update.message.reply_text(
                text=text, entities=entities, reply_markup=build_giveaway_condition_public_keyboard(),
            )
            return

        resolved = []
        for raw in raw_lines:
            username = _normalize_channel_username(raw)
            if not username or " " in username:
                resolved = None
                break
            try:
                chat = await context.bot.get_chat(f"@{username}")
                bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
                if bot_member.status not in ("administrator", "creator"):
                    resolved = None
                    break
            except Exception:
                resolved = None
                break
            resolved.append({
                "ref": f"@{username}",
                "title": chat.title or f"@{username}",
                "url": f"https://t.me/{username}",
            })

        if resolved is None or not resolved:
            text, entities = build_giveaway_condition_error_message()
            await update.message.reply_text(
                text=text,
                entities=entities,
                reply_markup=build_giveaway_condition_public_keyboard(),
            )
            return

        context.user_data["gw_condition_channels"] = resolved
        context.user_data.pop("awaiting", None)
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)

        confirm_text, confirm_entities = build_giveaway_condition_linked_message(
            [c["title"] for c in resolved],
        )
        await update.message.reply_text(text=confirm_text, entities=confirm_entities)

        settings_text, settings_entities = build_giveaway_settings_message()
        await update.message.reply_text(
            text=settings_text,
            entities=settings_entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if awaiting == "gw_autospin_count":
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            _bt, _be = bold_notice("من فضلك أرسل رقمًا صحيحًا أكبر من صفر لعدد المشاركين.")
            await update.message.reply_text(text=_bt, entities=_be)
            return
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        context.user_data["gw_autospin_mode"] = "count"
        context.user_data["gw_autospin_target"] = int(raw)
        context.user_data.pop("awaiting", None)

        text, entities = build_giveaway_settings_message()
        await update.message.reply_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if awaiting == "gw_winners_count":
        raw = (update.message.text or "").strip()
        if not raw.isdigit() or int(raw) <= 0:
            _bt, _be = bold_notice("من فضلك أرسل رقمًا صحيحًا أكبر من صفر لعدد الفائزين.")
            await update.message.reply_text(text=_bt, entities=_be)
            return
        context.user_data["gw_winners_count"] = int(raw)
        context.user_data.pop("awaiting", None)
        await publish_giveaway(update, context)
        return

    if awaiting == "emoji_id":
        entities = update.message.entities or []
        found = False
        for entity in entities:
            if entity.type == "custom_emoji":
                found = True
                emoji_text = update.message.text[entity.offset: entity.offset + entity.length]
                await update.message.reply_text(
                    f"الإيموجي: {emoji_text}\nرقمه: `{entity.custom_emoji_id}`",
                    parse_mode="Markdown",
                )
        if not found:
            _bt, _be = bold_notice("لم أجد إيموجي متحرك في رسالتك.")
            await update.message.reply_text(text=_bt, entities=_be)
        context.user_data.pop("awaiting", None)
        return

async def _go_to_quick_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=QUICK_ROULETTE_TEXT,
        reply_markup=build_quick_roulette_keyboard(),
    )

async def show_contest_detail(query, context: ContextTypes.DEFAULT_TYPE, contest):
    """يعرض شاشة إعدادات مسابقة واحدة (تُستخدم من قائمة المسابقات الحديثة)."""
    channel_title = get_chat_title_by_id(contest["chat_id"])
    post_link = await build_contest_post_link(context, contest["chat_id"], contest["channel_message_id"])
    participants_count = count_contest_participants(contest["contest_code"])
    text, entities = build_contest_detail_message(contest, channel_title, post_link, participants_count)
    await query.edit_message_text(
        text=text,
        entities=entities,
        reply_markup=build_contest_detail_keyboard(contest),
    )


async def contest_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعرض تفاصيل مسابقة محددة عند اختيارها من قائمة «المسابقات الحديثة»."""
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    contest = get_contest(code)
    if not contest or contest["owner_id"] != query.from_user.id:
        await query.answer("تعذر العثور على هذه المسابقة.", show_alert=True)
        return
    await show_contest_detail(query, context, contest)


async def contest_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج أزرار إدارة مسابقة محددة: الإيقاف/الاستئناف، الحذف، وغيرها."""
    query = update.callback_query
    action, _, code = query.data.partition(":")
    contest = get_contest(code)
    if not contest or contest["owner_id"] != query.from_user.id:
        await query.answer("تعذر العثور على هذه المسابقة.", show_alert=True)
        return

    if action == "comp_toggle_active":
        new_status = "paused" if contest["status"] == "open" else "open"
        set_contest_status(code, new_status)
        contest = get_contest(code)
        await query.answer("تم إيقاف المسابقة." if new_status == "paused" else "تم استئناف المسابقة.")
        await show_contest_detail(query, context, contest)
        return

    if action == "comp_delete_all":
        delete_contest_completely(code)
        log_admin_action(
            "delete_contest", query.from_user.id, details=f"كود المسابقة: {code}",
            actor_name=query.from_user.full_name, actor_username=query.from_user.username,
        )
        await query.answer("تم حذف المسابقة بالكامل.", show_alert=True)
        text, entities = build_contest_section_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_section_keyboard(),
        )
        return

    await query.answer("🚧 هذه الميزة قيد التطوير حاليًا.", show_alert=True)


async def contest_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back_main_menu":
        text, entities = build_welcome_message(query.from_user)
        remind_state = get_remind_win_state(query.from_user.id)
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_main_keyboard(remind_state, query.from_user.id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    if query.data == "section_competition":
        text, entities = build_contest_section_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_section_keyboard(),
        )
        return

    if query.data == "comp_start_create":
        context.user_data.pop("awaiting", None)
        context.user_data.pop("contest_target_chat_id", None)
        context.user_data.pop("contest_cliche_text", None)
        context.user_data.pop("contest_cliche_entities", None)
        context.user_data.pop("contest_target_count", None)
        text, entities = build_contest_target_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_target_keyboard(query.from_user.id),
        )
        return

    if query.data == "comp_recent":
        contests = get_contests_by_owner(query.from_user.id)
        if not contests:
            await query.answer("لا توجد مسابقات جارية حاليًا.", show_alert=True)
            return
        if len(contests) == 1:
            await show_contest_detail(query, context, contests[0])
            return
        text, entities = build_recent_contests_list_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_recent_contests_list_keyboard(contests),
        )
        return

    if query.data.startswith("comp_pick_chat_"):
        chat_id = int(query.data.replace("comp_pick_chat_", ""))
        context.user_data["contest_target_chat_id"] = chat_id
        context.user_data["awaiting"] = "contest_cliche"
        text, entities = build_contest_cliche_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_cliche_keyboard(),
        )
        return

    if query.data == "comp_back_to_klesha":
        context.user_data["awaiting"] = "contest_cliche"
        text, entities = build_contest_cliche_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_cliche_keyboard(),
        )
        return

    if query.data == "comp_back_to_count":
        context.user_data["awaiting"] = "contest_count"
        text, entities = build_contest_count_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_count_keyboard(),
        )
        return

    if query.data == "comp_end_votes":
        context.user_data.pop("awaiting_setting", None)
        context.user_data["contest_end_type"] = "votes"
        context.user_data["awaiting"] = "contest_votes_target"
        text, entities = build_contest_votes_target_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_votes_target_keyboard(),
        )
        return

    if query.data == "comp_end_time":
        context.user_data.pop("awaiting", None)
        context.user_data["contest_end_type"] = "time"
        text, entities = build_contest_time_menu_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_time_menu_keyboard(),
        )
        return

    if query.data == "comp_back_to_end_type":
        context.user_data.pop("awaiting", None)
        context.user_data.pop("contest_time_minutes", None)
        context.user_data.pop("contest_time_custom_minutes", None)
        context.user_data.pop("contest_votes_target", None)
        text, entities = build_contest_end_method_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_end_method_keyboard(),
        )
        return

    if query.data.startswith("comp_atime_set_"):
        minutes = int(query.data.replace("comp_atime_set_", ""))
        context.user_data["contest_time_minutes"] = minutes
        context.user_data.pop("contest_time_custom_minutes", None)
        context.user_data["awaiting"] = "contest_winners_count"
        text, entities = build_contest_winners_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_winners_keyboard(),
        )
        return

    if query.data == "comp_atime_show_custom":
        context.user_data["contest_time_custom_minutes"] = context.user_data.get("contest_time_minutes") or 0
        text, entities = build_contest_time_menu_message(
            format_duration_label(context.user_data["contest_time_custom_minutes"]),
        )
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_time_custom_keyboard(),
        )
        return

    if query.data.startswith("comp_atime_custom_delta:"):
        delta = int(query.data.split(":", 1)[1])
        current = context.user_data.get("contest_time_custom_minutes", 0)
        context.user_data["contest_time_custom_minutes"] = max(0, current + delta)
        text, entities = build_contest_time_menu_message(
            format_duration_label(context.user_data["contest_time_custom_minutes"]),
        )
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_time_custom_keyboard(),
        )
        return

    if query.data == "comp_atime_custom_reset":
        context.user_data["contest_time_custom_minutes"] = 0
        text, entities = build_contest_time_menu_message("غير محدد")
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_time_custom_keyboard(),
        )
        return

    if query.data == "comp_atime_custom_confirm":
        total = context.user_data.get("contest_time_custom_minutes", 0)
        if not total or total <= 0:
            await query.answer("⚠️ اختر وقتًا أولاً باستخدام أزرار التعديل.", show_alert=True)
            return
        context.user_data["contest_time_minutes"] = total
        context.user_data.pop("contest_time_custom_minutes", None)
        context.user_data["awaiting"] = "contest_winners_count"
        text, entities = build_contest_winners_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_winners_keyboard(),
        )
        return

    if query.data in (
        "comp_toggle_notify_win",
        "comp_toggle_announce_results",
        "comp_toggle_approve_participants",
        "comp_toggle_premium_only",
    ):
        key = query.data.replace("comp_toggle_", "contest_")
        for k, default in CONTEST_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(k, default)
        context.user_data[key] = not context.user_data.get(key, CONTEST_SETTINGS_DEFAULTS[key])
        text, entities = build_contest_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_settings_keyboard(context.user_data),
        )
        return

    if query.data == "comp_back_to_winners":
        context.user_data["awaiting"] = "contest_winners_count"
        text, entities = build_contest_winners_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_contest_winners_keyboard(),
        )
        return

    if query.data == "comp_publish":
        ud = context.user_data
        chat_id = ud.get("contest_target_chat_id")
        target_count = ud.get("contest_target_count")

        if not chat_id or not target_count:
            await query.answer("⚠️ حدث خطأ، لم يتم تحديد جميع بيانات المسابقة.", show_alert=True)
            return

        cliche_text = ud.get("contest_cliche_text") or ""
        cliche_entities = ud.get("contest_cliche_entities") or []
        end_type = ud.get("contest_end_type")
        time_minutes = ud.get("contest_time_minutes")
        votes_target = ud.get("contest_votes_target")
        winners_count = ud.get("contest_winners_count")
        settings = {k: ud.get(k, d) for k, d in CONTEST_SETTINGS_DEFAULTS.items()}

        await query.answer()

        success_text, success_entities = build_publish_success_message()
        await query.edit_message_text(text=success_text, entities=success_entities)

        contest_code = generate_contest_code()
        create_contest(
            contest_code=contest_code,
            owner_id=query.from_user.id,
            chat_id=chat_id,
            cliche_text=cliche_text,
            cliche_entities=cliche_entities,
            target_count=target_count,
            end_type=end_type,
            time_minutes=time_minutes,
            winners_count=winners_count,
            settings=settings,
            votes_target=votes_target,
        )

        post_text, post_entities = build_contest_channel_message(
            cliche_text, cliche_entities, target_count, end_type, time_minutes, votes_target,
            contest_code=contest_code,
        )
        post_keyboard = build_contest_channel_keyboard(contest_code)
        try:
            sent = await context.bot.send_message(
                chat_id=chat_id,
                text=post_text,
                entities=post_entities,
                reply_markup=post_keyboard,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            set_contest_channel_message(contest_code, sent.message_id)
            asyncio.create_task(announce_new_post(context, chat_id, sent.message_id, "contest", {"code": contest_code}))
        except Exception:
            await query.message.reply_text(
                "⚠️ تعذر نشر المسابقة في القناة/القروب المحدد، تأكد من أن البوت مايزال مشرفًا هناك."
            )

        if end_type == "time" and time_minutes:
            schedule_contest_time_end(context.job_queue, contest_code, time_minutes * 60)

        for key in list(ud.keys()):
            if key.startswith("contest_"):
                ud.pop(key, None)
        ud.pop("awaiting", None)
        return

    if query.data == "comp_reg_channel":
        text, entities = build_channel_registration_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_back_to_competition_keyboard(),
        )
        return

    if query.data == "comp_reg_group":
        text, entities = build_group_registration_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_back_to_competition_keyboard(),
        )
        return


async def publish_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ينشر السحب فور إرسال عدد الفائزين مباشرة (يُستدعى من text_router)."""
    ud = context.user_data
    chat_id = ud.get("gw_target_chat_id")
    if not chat_id:
        _bt, _be = bold_notice("⚠️ حدث خطأ، لم يتم تحديد قناة أو جروب السحب.")
        await update.message.reply_text(text=_bt, entities=_be)
        return

    cliche_text = ud.get("gw_cliche_text") or ""
    cliche_entities = ud.get("gw_cliche_entities") or []
    winners_count = ud.get("gw_winners_count")
    settings = {k: ud.get(k, d) for k, d in GIVEAWAY_SETTINGS_DEFAULTS.items()}

    success_text, success_entities = build_giveaway_publish_success_message()
    await update.message.reply_text(text=success_text, entities=success_entities)

    gw_code = generate_gw_code()
    create_giveaway(
        gw_code=gw_code,
        owner_id=update.effective_user.id,
        chat_id=chat_id,
        cliche_text=cliche_text,
        cliche_entities=cliche_entities,
        winners_count=winners_count,
        settings=settings,
    )

    vote_contest_code = settings.get("gw_vote_contest_code")
    vote_participant_id = settings.get("gw_vote_participant_id")
    vote_link = (
        build_giveaway_vote_condition_link(vote_contest_code, vote_participant_id)
        if vote_contest_code and vote_participant_id else None
    )
    condition_channels = settings.get("gw_condition_channels") or []
    boost_link = (
        await build_giveaway_boost_link(context, chat_id) if settings.get("gw_boost") else ""
    )

    autospin_mode = settings.get("gw_autospin_mode")
    autospin_notice = None
    if autospin_mode == "count" and settings.get("gw_autospin_target"):
        autospin_notice = {"mode": "count", "notice_text": f"يُسحب تلقائيًا عند اكتمال {settings['gw_autospin_target']} مشارك"}
    elif autospin_mode == "time" and settings.get("gw_autospin_minutes"):
        autospin_notice = {
            "mode": "time",
            "notice_text": f"يُسحب تلقائيًا بعد {format_duration_label(settings['gw_autospin_minutes'])}",
        }

    post_text, post_entities = build_giveaway_channel_message(
        cliche_text, cliche_entities, gw_code=gw_code, vote_link=vote_link, condition_channels=condition_channels,
        boost_link=boost_link, autospin=autospin_notice,
    )
    post_keyboard = build_giveaway_channel_keyboard(gw_code, 0, antispam=bool(settings.get("gw_antispam", False)))
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=post_text,
            entities=post_entities,
            reply_markup=post_keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        set_giveaway_channel_message(gw_code, sent.message_id)
        asyncio.create_task(announce_new_post(
            context, chat_id, sent.message_id, "giveaway",
            {"winners_count": winners_count, "code": gw_code},
        ))
        if autospin_mode == "time" and settings.get("gw_autospin_minutes"):
            schedule_giveaway_autospin_time(
                context.job_queue, gw_code, settings["gw_autospin_minutes"] * 60,
            )
    except Exception:
        await update.message.reply_text(
            "⚠️ تعذر نشر السحب في القناة/القروب المحدد، تأكد من أن البوت مايزال مشرفًا هناك."
        )

    for key in list(ud.keys()):
        if key.startswith("gw_"):
            ud.pop(key, None)
    ud.pop("awaiting", None)


async def show_my_giveaways_list(query, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """يعرض قائمة سحوبات المستخدم (كل الحالات)، مقسّمة إلى صفحات عند الحاجة."""
    giveaways = get_giveaways_by_owner(query.from_user.id)
    if not giveaways:
        text, entities = bold_notice("لا توجد لديك أي سحوبات حتى الآن.")
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
                "رجوع", callback_data="back_main_menu",
                style="danger", **emoji_kwargs("back_section_btn"),
            )]]),
        )
        return

    total_pages = max(1, -(-len(giveaways) // GW_LIST_PAGE_SIZE))
    page = max(1, min(page, total_pages))
    text, entities = build_my_giveaways_list_message(page, total_pages)
    await query.edit_message_text(
        text=text,
        entities=entities,
        reply_markup=build_my_giveaways_list_keyboard(giveaways, page, total_pages),
    )


async def gw_my_draws_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج زر «سحوباتي»: عرض قائمة السحوبات، التنقّل بين الصفحات، وعرض تفاصيل كل سحب."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "my_draws":
        await show_my_giveaways_list(query, context, page=1)
        return

    if data.startswith("gwmy_page:"):
        page_str = data.split(":", 1)[1]
        page = int(page_str) if page_str.isdigit() else 1
        await show_my_giveaways_list(query, context, page=page)
        return

    if data.startswith("gwmy_detail:"):
        _, gw_code, page_str = data.split(":", 2)
        giveaway = get_giveaway(gw_code)
        if not giveaway or giveaway["owner_id"] != query.from_user.id:
            await query.answer("تعذر العثور على هذا السحب.", show_alert=True)
            return
        giveaways = get_giveaways_by_owner(query.from_user.id)
        index = next((i + 1 for i, g in enumerate(giveaways) if g["gw_code"] == gw_code), 0)
        channel_title = get_chat_title_by_id(giveaway["chat_id"])
        participants_total = count_giveaway_participants(gw_code)
        new_rewarded_count = count_giveaway_new_rewarded(gw_code)
        text, entities = build_my_giveaway_detail_message(
            giveaway, index, channel_title, participants_total, new_rewarded_count,
        )
        page = int(page_str) if page_str.isdigit() else 1
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_my_giveaway_detail_keyboard(page),
        )
        return


async def gw_section_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يعالج جميع أزرار قسم إنشاء السحب (Image 1 إلى Image 4)."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ("create_draw", "gw_start_create"):
        for key in list(context.user_data.keys()):
            if key.startswith("gw_"):
                context.user_data.pop(key, None)
        context.user_data.pop("awaiting", None)
        text, entities = build_giveaway_target_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_target_keyboard(query.from_user.id),
        )
        return

    if data == "gw_reg_channel":
        text, entities = build_channel_registration_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_back_to_giveaway_keyboard(),
        )
        return

    if data == "gw_reg_group":
        text, entities = build_group_registration_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_back_to_giveaway_keyboard(),
        )
        return

    if data == "gw_del_channels":
        text, entities = build_giveaway_delete_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_delete_keyboard(query.from_user.id),
        )
        return

    if data == "gw_noop":
        return

    if data.startswith("gw_delc:"):
        chat_id = int(data.split(":", 1)[1])
        remove_registered_chat(chat_id)
        await query.answer("🗑️ تم حذف القناة/الجروب.", show_alert=True)
        text, entities = build_giveaway_delete_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_delete_keyboard(query.from_user.id),
        )
        return

    if data.startswith("gw_sel:"):
        chat_id = int(data.split(":", 1)[1])
        context.user_data["gw_target_chat_id"] = chat_id
        context.user_data["awaiting"] = "gw_cliche"
        text, entities = build_giveaway_cliche_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_cliche_keyboard(),
        )
        return

    if data == "gw_back_main":
        text, entities = build_welcome_message(query.from_user)
        remind_state = get_remind_win_state(query.from_user.id)
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_main_keyboard(remind_state, query.from_user.id),
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    if data in ("gw_toggle_boost", "gw_toggle_premium", "gw_toggle_antispam"):
        key = data.replace("gw_toggle_", "gw_")
        for k, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(k, default)
        context.user_data[key] = not context.user_data.get(key, GIVEAWAY_SETTINGS_DEFAULTS[key])
        text, entities = build_giveaway_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if data == "gw_opt_vote":
        context.user_data["awaiting"] = "gw_vote_code"
        text, entities = build_giveaway_vote_code_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_vote_code_keyboard(),
        )
        return

    if data == "gw_opt_autospin":
        text, entities = build_giveaway_autospin_end_method_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_end_method_keyboard(),
        )
        return

    if data == "gw_atime_back":
        context.user_data.pop("awaiting", None)
        text, entities = build_giveaway_autospin_end_method_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_end_method_keyboard(),
        )
        return

    if data == "gw_atime_end_count":
        context.user_data["awaiting"] = "gw_autospin_count"
        text, entities = build_giveaway_autospin_count_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_count_keyboard(),
        )
        return

    if data == "gw_atime_end_time":
        context.user_data.pop("awaiting", None)
        text, entities = build_giveaway_autospin_time_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_time_keyboard(),
        )
        return

    if data.startswith("gw_atime_set_"):
        minutes = int(data.replace("gw_atime_set_", ""))
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        context.user_data["gw_autospin_mode"] = "time"
        context.user_data["gw_autospin_minutes"] = minutes
        context.user_data.pop("awaiting", None)
        text, entities = build_giveaway_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if data == "gw_atime_show_custom":
        if context.user_data.get("gw_autospin_mode") == "time":
            context.user_data["gw_autospin_custom_minutes"] = context.user_data.get("gw_autospin_minutes") or 0
        else:
            context.user_data["gw_autospin_custom_minutes"] = 0
        text, entities = build_giveaway_autospin_time_message(
            format_duration_label(context.user_data["gw_autospin_custom_minutes"]),
        )
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_custom_keyboard(),
        )
        return

    if data.startswith("gw_atime_custom_delta:"):
        delta = int(data.split(":", 1)[1])
        current = context.user_data.get("gw_autospin_custom_minutes", 0)
        context.user_data["gw_autospin_custom_minutes"] = max(0, current + delta)
        text, entities = build_giveaway_autospin_time_message(
            format_duration_label(context.user_data["gw_autospin_custom_minutes"]),
        )
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_custom_keyboard(),
        )
        return

    if data == "gw_atime_custom_reset":
        context.user_data["gw_autospin_custom_minutes"] = 0
        text, entities = build_giveaway_autospin_time_message("غير محدد")
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_autospin_custom_keyboard(),
        )
        return

    if data == "gw_atime_custom_confirm":
        total = context.user_data.get("gw_autospin_custom_minutes", 0)
        if not total or total <= 0:
            await query.answer("⚠️ اختر وقتًا أولاً باستخدام أزرار التعديل.", show_alert=True)
            return
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        context.user_data["gw_autospin_mode"] = "time"
        context.user_data["gw_autospin_minutes"] = total
        context.user_data.pop("gw_autospin_custom_minutes", None)
        text, entities = build_giveaway_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if data == "gw_opt_condition":
        context.user_data.pop("awaiting", None)
        context.user_data.pop("gw_condition_channels_pending", None)
        text, entities = build_giveaway_condition_type_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_condition_type_keyboard(),
        )
        return

    if data == "gw_cond_public":
        context.user_data["awaiting"] = "gw_condition_channel_public"
        text, entities = build_giveaway_condition_public_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_condition_public_keyboard(),
        )
        return

    if data == "gw_cond_private":
        context.user_data["awaiting"] = "gw_condition_channel_private"
        context.user_data["gw_condition_channels_pending"] = []
        text, entities = build_giveaway_condition_private_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_condition_private_keyboard(),
        )
        return

    if data == "gw_cond_private_done":
        pending = context.user_data.get("gw_condition_channels_pending") or []
        if not pending:
            await query.answer("⚠️ لم تُضِف أي قناة بعد.", show_alert=True)
            return
        context.user_data["gw_condition_channels"] = pending
        context.user_data.pop("gw_condition_channels_pending", None)
        context.user_data.pop("awaiting", None)
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        text, entities = build_giveaway_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return

    if data == "gw_opt_create":
        context.user_data["awaiting"] = "gw_winners_count"
        text, entities = build_giveaway_winners_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_winners_keyboard(),
        )
        return

    if data == "gw_back_to_options":
        context.user_data.pop("awaiting", None)
        context.user_data.pop("gw_condition_channels_pending", None)
        for key, default in GIVEAWAY_SETTINGS_DEFAULTS.items():
            context.user_data.setdefault(key, default)
        text, entities = build_giveaway_settings_message()
        await query.edit_message_text(
            text=text,
            entities=entities,
            reply_markup=build_giveaway_settings_keyboard(context.user_data),
        )
        return


async def _go_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, entities = build_welcome_message(query.from_user)
    remind_state = get_remind_win_state(query.from_user.id)
    await query.edit_message_text(
        text=text,
        entities=entities,
        reply_markup=build_main_keyboard(remind_state, query.from_user.id),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )

async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """يسجّل أي خطأ غير متوقع بدل أن يختفي بصمت — هذا كان السبب في تعذّر تشخيص
    مشاكل مثل «الزر لا يستجيب أحيانًا» أو «لم تُرسل رسالة عند انتهاء الوقت».
    يُسجَّل الخطأ في السجلّ المحلي (logger) فقط — لم يعد يُكتب في Firestore
    (مجموعة bot_errors حُذفت) حتى لا تُستهلك حصة الكتابة اليومية بسبب أخطاء
    متكررة."""
    logger.exception("خطأ غير متوقع أثناء معالجة تحديث: %s", update, exc_info=context.error)


def main():
    init_db()
    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=10.0,
        read_timeout=10.0,
        write_timeout=10.0,
        pool_timeout=10.0,
    )
    get_updates_request = HTTPXRequest(
        connection_pool_size=4,
        connect_timeout=10.0,
        read_timeout=40.0,
    )
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .concurrent_updates(True)
        .build()
    )

    if app.job_queue is None:
        logger.error(
            "JobQueue غير مفعّلة! مسابقات «وقت محدد» لن تُنهى تلقائيًا أبدًا. "
            "ثبّت المكتبة عبر: pip install \"python-telegram-bot[job-queue]\" ثم أعد التشغيل."
        )
    else:
        logger.info("JobQueue مفعّلة بنجاح.")
        app.job_queue.run_repeating(
            check_required_channels_targets, interval=120, first=15,
            name="required_channels_targets",
        )
        app.job_queue.run_repeating(
            giveaway_autospin_countdown_tick, interval=600, first=60,
            name="giveaway_autospin_countdown_tick",
        )
        app.job_queue.run_repeating(
            contest_votes_subscription_audit, interval=300, first=60,
            name="contest_votes_subscription_audit",
        )

    app.add_error_handler(_global_error_handler)

    # البوابات العامة الثلاث (حظر ← صيانة ← اشتراك إجباري): تُسجَّل كمعالج
    # *واحد* فقط في مجموعة أولوية أعلى (group=-1) فيُنفَّذ قبل أي معالج آخر
    # لأي تحديث. هام: لا يجوز تسجيلها كـ TypeHandler منفصلة في نفس المجموعة —
    # مكتبة python-telegram-bot تُنفّذ أول معالج مطابق فقط في كل مجموعة ثم
    # تنتقل للمجموعة التالية، فكانت ثلاث TypeHandler منفصلة هنا تجعل الأولى
    # فقط (الحظر) تعمل فعليًا وتُعطِّل بوابتي الصيانة والاشتراك بصمت. راجع
    # توثيق _global_gates_handler لتفاصيل كل بوابة على حدة.
    app.add_handler(TypeHandler(Update, _global_gates_handler), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getid", get_id_prompt))
    app.add_handler(CommandHandler("reset_test", reset_test_user_command))

    app.add_handler(CallbackQueryHandler(_go_to_quick_roulette, pattern=r"^quick_roulette_menu$"))
    app.add_handler(CallbackQueryHandler(_go_back_to_main, pattern=r"^back_to_main$"))

    app.add_handler(InlineQueryHandler(inline_query_handler))
    app.add_handler(ChosenInlineResultHandler(chosen_result_handler))

    app.add_handler(CallbackQueryHandler(rr_spin_callback, pattern=r"^rr_spin_\d+$"))
    app.add_handler(CallbackQueryHandler(rr_respin_callback, pattern=r"^rr_respin_\d+$"))
    app.add_handler(CallbackQueryHandler(rr_join_callback, pattern=r"^rr_join_\d+$"))

    app.add_handler(CallbackQueryHandler(qr_settings_callback, pattern=r"^qr_settings$"))
    app.add_handler(CallbackQueryHandler(
        roulette_privacy_settings_callback,
        pattern=r"^(toggle_hide_participants_internal|edit_game_cliche|restore_defaults_roulette|section_roulette)$",
    ))

    app.add_handler(CallbackQueryHandler(
        contest_section_callback,
        pattern=r"^(comp_start_create|comp_reg_group|comp_reg_channel|back_main_menu|section_competition"
                r"|comp_pick_chat_-?\d+|comp_back_to_klesha|comp_back_to_count|comp_end_votes|comp_end_time"
                r"|comp_back_to_end_type|comp_atime_set_\d+|comp_atime_show_custom"
                r"|comp_atime_custom_delta:-?\d+|comp_atime_custom_reset|comp_atime_custom_confirm"
                r"|comp_toggle_notify_win|comp_toggle_announce_results|comp_toggle_approve_participants"
                r"|comp_toggle_premium_only|comp_back_to_winners|comp_publish|comp_recent)$",
    ))

    app.add_handler(CallbackQueryHandler(
        contest_detail_callback,
        pattern=r"^comp_detail:",
    ))
    app.add_handler(CallbackQueryHandler(
        contest_management_callback,
        pattern=r"^(comp_toggle_active:|comp_delete_all:|comp_change_seats:|comp_edit_settings:|comp_remove_contestant:)",
    ))

    app.add_handler(CallbackQueryHandler(
        contest_participation_callback,
        pattern=r"^(comp_reject_join:|comp_confirm_join:|comp_withdraw:|comp_appjoin_ok:|comp_appjoin_no:)",
    ))
    app.add_handler(CallbackQueryHandler(vote_captcha_callback, pattern=r"^compcap:"))
    app.add_handler(CallbackQueryHandler(contest_vote_gate_check_callback, pattern=r"^compcond:"))
    app.add_handler(CallbackQueryHandler(contest_channel_gate_check_callback, pattern=r"^compjoinchk:"))
    app.add_handler(CallbackQueryHandler(compjoin_button_callback, pattern=r"^compjoinbtn:"))
    app.add_handler(CallbackQueryHandler(compvote_button_callback, pattern=r"^compvotebtn:"))
    app.add_handler(CallbackQueryHandler(contest_results_callback, pattern=r"^comp_view_results:"))

    app.add_handler(CallbackQueryHandler(
        gw_section_callback,
        pattern=r"^(create_draw|gw_start_create|gw_reg_channel|gw_reg_group|gw_del_channels|gw_noop"
                r"|gw_delc:-?\d+|gw_sel:-?\d+|gw_back_main|gw_toggle_boost|gw_toggle_premium"
                r"|gw_toggle_antispam|gw_opt_condition|gw_cond_public|gw_cond_private|gw_cond_private_done"
                r"|gw_opt_vote|gw_opt_autospin|gw_opt_create"
                r"|gw_atime_back|gw_atime_end_count|gw_atime_end_time|gw_atime_set_\d+|gw_atime_show_custom"
                r"|gw_atime_custom_delta:-?\d+|gw_atime_custom_reset|gw_atime_custom_confirm"
                r"|gw_back_to_options)$",
    ))
    app.add_handler(CallbackQueryHandler(
        gw_my_draws_callback,
        pattern=r"^(my_draws|gwmy_page:\d+|gwmy_detail:)",
    ))
    app.add_handler(CallbackQueryHandler(gw_join_callback, pattern=r"^gw_join:"))
    app.add_handler(CallbackQueryHandler(gwcond_check_callback, pattern=r"^gwcond:"))
    app.add_handler(CallbackQueryHandler(gw_captcha_callback, pattern=r"^gwcap:"))
    app.add_handler(CallbackQueryHandler(gw_kick_callback, pattern=r"^gw_kick:"))
    app.add_handler(CallbackQueryHandler(gw_repost_callback, pattern=r"^gw_repost:"))
    app.add_handler(CallbackQueryHandler(gw_pause_callback, pattern=r"^gw_pause:"))
    app.add_handler(CallbackQueryHandler(gw_resume_callback, pattern=r"^gw_resume:"))
    app.add_handler(CallbackQueryHandler(gw_draw_callback, pattern=r"^gw_draw:"))
    app.add_handler(CallbackQueryHandler(gw_reroll_callback, pattern=r"^gw_reroll:"))

    app.add_handler(CallbackQueryHandler(check_sub_status_callback, pattern=r"^check_sub_status$"))
    app.add_handler(CallbackQueryHandler(main_menu_callback))
    app.add_handler(PreCheckoutQueryHandler(support_precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, support_successful_payment_callback))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, channel_forward_handler))
    app.add_handler(MessageHandler(filters.Regex("تفعيل روليت") & filters.ChatType.GROUPS, group_activation_handler))
    app.add_handler(MessageHandler(
        (
            filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.VOICE
            | filters.ANIMATION | filters.VIDEO_NOTE | filters.Sticker.ALL | filters.POLL
        ) & filters.ChatType.PRIVATE,
        handle_broadcast_content_input,
    ))
    # ⚠️ يجب أن يبقى هذا المعالج مقيّدًا بالمحادثة الخاصة مع البوت فقط
    # (ChatType.PRIVATE) — لأنه يحتوي على كل تدفقات «awaiting» الخاصة بالمالك
    # (الإذاعة، الإعدادات، إلخ). بدون هذا القيد، أي رسالة نصية يرسلها المالك في
    # أي مجموعة أخرى أثناء وجود حالة «awaiting» عالقة (مثل انتظار نص الإذاعة)
    # كانت تُفهم خطأً على أنها محتوى الإذاعة وتُرسَل فورًا لكل المستخدمين.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_router))
    app.add_handler(ChatMemberHandler(bot_chat_status_update, ChatMemberHandler.MY_CHAT_MEMBER))
    # اكتشاف فوري لخروج أي مستخدم من أي قناة/قروب البوت مشرف فيه، لتطبيق
    # خصم المتسابقين/المشاركين في المسابقات والسحوبات المستضافة هناك لحظة
    # الخروج مباشرة (بدل انتظار أي فحص دوري لاحق).
    app.add_handler(ChatMemberHandler(_chat_member_leave_handler, ChatMemberHandler.CHAT_MEMBER))

    async def _post_init(app_):
        await app_.bot.set_my_commands([
            BotCommand("start", "رسالة البدء"),
        ])
        await reschedule_pending_contest_timers(app_)
        await reschedule_pending_giveaway_timers(app_)
        try:
            announce_chat = await app_.bot.get_chat(f"@{ANNOUNCE_CHANNEL_USERNAME}")
            remove_registered_chat(announce_chat.id)
        except Exception:
            pass
    app.post_init = _post_init

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
