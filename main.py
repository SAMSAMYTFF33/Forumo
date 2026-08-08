import logging
import asyncio
import urllib.parse
import time
import random
import aiohttp
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut

# تقليل السجلات المزعجة
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# توكن بوت التيليجرام الخاص بك
BOT_TOKEN = "8976290159:AAH10zmWMqZ2QbSx5bBxf9ckoUAwuU0Rhic"

TARGET_BOT_USERNAME_MONSTER = "monsterland_bot"
WEB_APP_URL_MONSTER = "https://lets.playmonsterland.com"
API_USER = "https://lets.playmonsterland.com/api/user?include=monsters"

API_VITALS_DIRECT = "https://lets.playmonsterland.com/api/vitals"
API_CREATE_AD = "https://lets.playmonsterland.com/api/ads/create-task"
API_TASK_RESULT = "https://lets.playmonsterland.com/api/ads/task-result"
API_COMPLETE_AD = "https://lets.playmonsterland.com/api/ads/complete"

VITAL_ITEMS = {
    "food": "magic_apple",
    "hygiene": "magic_towel",
    "energy": "wizard_coffee"
}

WAITING_CREDENTIALS, SET_THRESHOLD, SET_DELAY = range(3)

# هيكلة قاعدة البيانات المحلية
users_db = {}

def get_user_db(user_id: int) -> dict:
    if user_id not in users_db:
        users_db[user_id] = {
            "active_index": 0,
            "accounts": []
        }
    return users_db[user_id]

def get_active_account(user_id: int):
    udata = get_user_db(user_id)
    accs = udata["accounts"]
    if not accs:
        return None
    idx = udata["active_index"]
    if idx >= len(accs):
        udata["active_index"] = 0
        idx = 0
    return accs[idx]

def parse_credentials_text(text: str):
    """تحليل ذكي لمكونات الحساب"""
    api_id, api_hash, session = None, None, None
    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "=" in line or ":" in line:
            delimiter = "=" if "=" in line else ":"
            parts = line.split(delimiter, 1)
            key = parts[0].strip().lower()
            val = parts[1].strip().strip('"').strip("'")

            if "id" in key and val.isdigit():
                api_id = val
            elif "hash" in key:
                api_hash = val
            elif "session" in key:
                session = val

    if not (api_id and api_hash and session):
        tokens = [t.strip('"').strip("'").strip(',') for t in text.replace('=', ' ').replace(':', ' ').split()]
        keywords = {'api_id', 'api_hash', 'session_string', 'session', 'id', 'hash'}
        clean_tokens = [t for t in tokens if t.lower() not in keywords]

        for t in clean_tokens:
            if t.isdigit() and 5 <= len(t) <= 12 and not api_id:
                api_id = t
            elif len(t) == 32 and all(c in '0123456789abcdefABCDEF' for c in t) and not api_hash:
                api_hash = t
            elif len(t) > 50 and not session:
                session = t

    return api_id, api_hash, session

def build_headers(token: str) -> dict:
    return {
        "authority": "lets.playmonsterland.com",
        "accept": "*/*",
        "authorization": token,
        "content-type": "application/json",
        "origin": "https://lets.playmonsterland.com",
        "referer": "https://lets.playmonsterland.com/",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
    }

# ===================== لوحات التحكم والواجهات =====================

def build_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    acc = get_active_account(user_id)
    if not acc:
        return InlineKeyboardMarkup([[InlineKeyboardButton("➕ إضافة حساب", callback_data="add_new_account")]])

    monster_name = acc.get("monster_name", "وحش بدون اسم")
    ads_text = "الخدمة ADS قيد تشغيل 🟢" if acc["ads_status"] else "الخدمة ADS متوقفة 🔴"
    no_ads_text = "تنفيد بدون ADS مشغل 🟢" if acc["no_ads_status"] else "تنفيد بدون ADS متوقف 🔴"

    keyboard = [
        [InlineKeyboardButton(f"👤 الحساب الحالي: {monster_name} 🔄", callback_data="open_accounts_menu")],
        [InlineKeyboardButton(ads_text, callback_data="toggle_ads")],
        [InlineKeyboardButton(no_ads_text, callback_data="toggle_no_ads")],
        [InlineKeyboardButton("📊 معلومات الوحش الحالية", callback_data="refresh_monster_info")],
        [InlineKeyboardButton("Setting ⚙️", callback_data="open_settings")],
        [InlineKeyboardButton("🎯 تنفيذ مباشر", callback_data="direct_execute")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_accounts_keyboard(user_id: int) -> InlineKeyboardMarkup:
    udata = get_user_db(user_id)
    accs = udata["accounts"]
    active_idx = udata["active_index"]
    keyboard = []
    for idx, acc in enumerate(accs):
        icon = "✅" if idx == active_idx else "🔘"
        m_name = acc.get("monster_name", f"حساب {idx+1}")
        keyboard.append([InlineKeyboardButton(f"{icon} الوحش: {m_name}", callback_data=f"switch_acc_{idx}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add_new_account")])
    if accs:
        keyboard.append([InlineKeyboardButton("🗑️ حذف حساب", callback_data="open_delete_menu")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def build_delete_keyboard(user_id: int) -> InlineKeyboardMarkup:
    udata = get_user_db(user_id)
    accs = udata["accounts"]
    keyboard = []
    for idx, acc in enumerate(accs):
        m_name = acc.get("monster_name", f"حساب {idx+1}")
        keyboard.append([InlineKeyboardButton(f"❌ حذف {m_name}", callback_data=f"confirm_delete_{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 إلغاء ورجوع", callback_data="open_accounts_menu")])
    return InlineKeyboardMarkup(keyboard)

def format_monster_info(monster: dict, profile_data: dict, acc: dict) -> str:
    """صياغة نص القائمة مع إضافة عداد الوقت المتبقي"""
    vitals = monster.get("vitals", {}) if monster else {}
    lumis = profile_data.get("lumis", 0) if profile_data else 0
        
    text = (
        f"📊 **معلومات الحساب:**\n\n"
        f"🍎 **نسبة magic food:** `{vitals.get('food', 0):.2f}%`\n"
        f"🧻 **نسبة wash:** `{vitals.get('hygiene', 0):.2f}%`\n"
        f"☕️ **نسبة energy:** `{vitals.get('energy', 0):.2f}%`\n"
        f"💰 **عدد Lumis:** `{lumis}`\n"
    )

    # عرض الوقت المتبقي إذا كانت الأتمتة مجدولة
    if acc and acc.get("scheduled_time", 0) > 0:
        remaining = int(acc["scheduled_time"] - time.time())
        if remaining > 0:
            vital_name = acc.get("scheduled_vital", "عنصر")
            text += f"\n⏳ **سيتم شراء {vital_name} تلقائياً بعد:** `{remaining}` **ثانية**"
        else:
            text += f"\n⏳ **جاري تنفيذ عملية شراء الآن...**"
            
    return text

async def verify_account_and_get_monster(api_id_raw, api_hash_raw, session_raw, cached_token=None):
    """دالة محسنة تستخدم التوكن المحفوظ أولاً للسرعة القصوى، وتجدده إذا لزم الأمر مع معالجة الأخطاء"""
    try:
        api_id = int(str(api_id_raw).strip())
    except (ValueError, TypeError):
        return False, None, None, None, "قيمة API_ID غير صالحة."

    api_hash = str(api_hash_raw).strip()
    session_str = str(session_raw).strip()

    # محاولة استخدام التوكن المحفوظ أولاً (فائقة السرعة)
    if cached_token:
        headers = build_headers(cached_token)
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(API_USER, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        data = await r.json()
                        monsters = data.get("monsters", [])
                        profile = data.get("profile", {})
                        if monsters:
                            return True, monsters[0], profile, cached_token, None
        except Exception:
            pass # في حال الفشل ننتقل لاستخراج توكن جديد عبر تيليجرام

    # إذا لم يوجد توكن أو انتهت صلاحيته (نفتح اتصال تيليجرام للحصول على جديد)
    try:
        async with TelegramClient(StringSession(session_str), api_id, api_hash, connection_retries=3) as client:
            bot = await client.get_input_entity(TARGET_BOT_USERNAME_MONSTER)
            web_view = await client(RequestWebViewRequest(
                peer=bot, bot=bot, platform="android", from_bot_menu=False, url=WEB_APP_URL_MONSTER
            ))
            init_data = web_view.url.split("tgWebAppData=")[1].split("&tgWebAppVersion")[0]
            new_token = f"tma {urllib.parse.unquote(init_data)}"

            headers = build_headers(new_token)
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(API_USER, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        return False, None, None, None, f"خطأ في سيرفر اللعبة (كود: {r.status})"
                    data = await r.json()
                    monsters = data.get("monsters", [])
                    profile = data.get("profile", {})
                    if not monsters:
                        return False, None, None, None, "لا يوجد وحش في هذا الحساب."
                    return True, monsters[0], profile, new_token, None
    except Exception as e:
        return False, None, None, None, f"فشل الاتصال بالحساب: {str(e)}"

# ===================== الأتمتة والخلفية =====================

async def execute_without_ads(session: aiohttp.ClientSession, token: str, monster_id: str, item_id: str):
    headers = build_headers(token)
    payload = {"monsterId": monster_id, "itemId": item_id, "action": "purchase"}
    try:
        async with session.post(API_VITALS_DIRECT, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
            return r.status
    except Exception:
        return None

async def execute_with_ads(session: aiohttp.ClientSession, token: str, monster_id: str, item_id: str):
    headers = build_headers(token)
    payload = {"action": "vitals", "metadata": {"monsterId": monster_id, "itemId": item_id}}
    try:
        async with session.post(API_CREATE_AD, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as res_create:
            if res_create.status != 200:
                return res_create.status
            tx_id = (await res_create.json()).get("adTxId")
        if not tx_id:
            return None
        await asyncio.sleep(random.randint(8, 12))
        async with session.get(f"{API_TASK_RESULT}?txId={tx_id}", headers=headers, timeout=aiohttp.ClientTimeout(total=15)):
            pass
        payload_complete = {"adTxId": tx_id, "provider": "gigapub"}
        async with session.post(API_COMPLETE_AD, headers=headers, json=payload_complete, timeout=aiohttp.ClientTimeout(total=15)) as res_comp:
            return res_comp.status
    except Exception:
        return None

async def global_background_worker():
    """خيط خلفي سريع محمّي ضد الانقطاع المباشر للشبكة"""
    while True:
        try:
            for user_id, udata in list(users_db.items()):
                for acc in udata.get("accounts", []):
                    if not acc["ads_status"] and not acc["no_ads_status"]:
                        acc["scheduled_time"] = 0
                        continue

                    # فحص سريع للوحش باستخدام التوكن المحفوظ
                    success, monster, profile, token, err = await verify_account_and_get_monster(
                        acc["api_id"], acc["api_hash"], acc["session"], acc.get("token")
                    )

                    if success and monster:
                        acc["token"] = token # تحديث التوكن إن تغير
                        monster_id = monster.get("_id")
                        vitals = monster.get("vitals", {})
                        threshold = acc["threshold"]
                        current_time = time.time()

                        # البحث عن أول عنصر أقل من النسبة المطلوبة
                        vital_to_fix = None
                        item_to_buy = None
                        for v_type, item_id in VITAL_ITEMS.items():
                            if vitals.get(v_type, 100) < threshold:
                                vital_to_fix = v_type
                                item_to_buy = item_id
                                break

                        if vital_to_fix:
                            # إذا لم تكن مجدولة من قبل، قم بجدولتها بالمهلة العشوائية
                            if acc.get("scheduled_time", 0) == 0:
                                min_d, max_d = acc.get("delay_range", (8, 16))
                                acc["scheduled_time"] = current_time + random.randint(min_d, max_d)
                                acc["scheduled_vital"] = vital_to_fix
                            
                            # إذا حان وقت التنفيذ المجدول
                            elif current_time >= acc["scheduled_time"]:
                                async with aiohttp.ClientSession() as http_session:
                                    if acc["no_ads_status"]:
                                        await execute_without_ads(http_session, acc["token"], monster_id, item_to_buy)
                                    elif acc["ads_status"]:
                                        await execute_with_ads(http_session, acc["token"], monster_id, item_to_buy)
                                # تصفير الجدولة لكي يفحص النسب مجدداً الدورة القادمة
                                acc["scheduled_time"] = 0
                                acc["scheduled_vital"] = None
                        else:
                            # كل شيء فوق النسبة، قم بإلغاء أي جدولة
                            acc["scheduled_time"] = 0
                            acc["scheduled_vital"] = None

            await asyncio.sleep(10) # فحص كل 10 ثواني
        except Exception as e:
            logger.error(f"خطأ غير متوقع في الخيط الخلفي تم تجاوزه بنجاح: {e}")
            await asyncio.sleep(10)

# ===================== المعالجة والواجهة =====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    acc = get_active_account(user_id)

    if not acc:
        await update.message.reply_text(
            "أهلاً بك! يرجى إرسال بيانات الحساب بالترتيب أو في رسالة واحدة تفصل بينها مسافات:\n\n"
            "`API_ID API_HASH SESSION_STRING`",
            parse_mode="Markdown"
        )
        return WAITING_CREDENTIALS
    else:
        success, monster, profile, token, err = await verify_account_and_get_monster(
            acc["api_id"], acc["api_hash"], acc["session"], acc.get("token")
        )
        if success:
            acc["token"] = token
            text = format_monster_info(monster, profile, acc)
        else:
            text = "🏠 القائمة الرئيسية:"
        
        await update.message.reply_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
        return ConversationHandler.END

async def process_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    parsed_id, parsed_hash, parsed_session = parse_credentials_text(text)
    if not (parsed_id and parsed_hash and parsed_session):
        await update.message.reply_text("⚠️ البيانات غير مكتملة. يرجى إرسالها كاملاً.")
        return WAITING_CREDENTIALS

    status_msg = await update.message.reply_text("⏳ جاري التحقق من الحساب واستخراج البيانات (يتم مرة واحدة فقط)...")

    success, monster, profile, token, err_msg = await verify_account_and_get_monster(parsed_id, parsed_hash, parsed_session)

    if success:
        udata = get_user_db(user_id)
        new_account = {
            "api_id": parsed_id,
            "api_hash": parsed_hash,
            "session": parsed_session,
            "token": token,  # حفظ التوكن للسرعة
            "monster_name": monster.get("name", "وحش بدون اسم"),
            "monster_id": monster.get("_id"),
            "ads_status": False,
            "no_ads_status": False,
            "threshold": 55,
            "delay_range": (8, 16),
            "scheduled_time": 0,
            "scheduled_vital": None
        }
        
        udata["accounts"].append(new_account)
        udata["active_index"] = len(udata["accounts"]) - 1

        info_text = format_monster_info(monster, profile, new_account)
        await status_msg.edit_text(
            f"✅ **تم إضافة الحساب واستخراج الرابط بنجاح!**\n\n{info_text}",
            parse_mode="Markdown"
        )
        await update.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=build_main_keyboard(user_id))
        return ConversationHandler.END
    else:
        await status_msg.edit_text(f"❌ {err_msg}\n\nيرجى إعادة إرسال البيانات الصحيحة:")
        return WAITING_CREDENTIALS

async def button_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    udata = get_user_db(user_id)
    acc = get_active_account(user_id)

    # -------------------- التنفيذ المباشر (فوري بالتوكن) --------------------
    if data == "direct_execute":
        if not acc:
            await query.edit_message_text("❌ لا يوجد حساب نشط.", reply_markup=build_main_keyboard(user_id))
            return
        keyboard = [
            [InlineKeyboardButton("🍎 Magic Food", callback_data="direct_buy_food")],
            [InlineKeyboardButton("🧻 Wash", callback_data="direct_buy_hygiene")],
            [InlineKeyboardButton("☕️ Energy", callback_data="direct_buy_energy")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "🎯 **اختر العنصر لشرائه مباشرة (تنفيذ فوري بالتوكن):**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    elif data.startswith("direct_buy_"):
        if not acc: return
        vital_type = data.replace("direct_buy_", "")
        item_id = VITAL_ITEMS.get(vital_type)
        item_name = vital_type

        await query.edit_message_text(f"⚡ جاري تنفيذ شراء **{item_name}** فورياً...", parse_mode="Markdown")

        try:
            async with aiohttp.ClientSession() as http_session:
                status = await execute_without_ads(http_session, acc["token"], acc["monster_id"], item_id)

            if status == 200:
                await query.edit_message_text(
                    f"✅ تم شراء **{item_name}** بنجاح وفورياً!",
                    parse_mode="Markdown",
                    reply_markup=build_main_keyboard(user_id)
                )
            else:
                await query.edit_message_text(
                    f"⚠️ فشل الشراء. كود: {status} (قد تحتاج رصيداً).",
                    reply_markup=build_main_keyboard(user_id)
                )
        except Exception as e:
            await query.edit_message_text(f"❌ خطأ: {str(e)}", reply_markup=build_main_keyboard(user_id))
        return

    # -------------------- أزرار الإعدادات --------------------
    if data == "open_settings":
        if not acc: return
        min_d, max_d = acc.get("delay_range", (8, 16))
        keyboard = [
            [InlineKeyboardButton("📊 تعديل النسبة المئوية", callback_data="menu_set_threshold")],
            [InlineKeyboardButton("⏱️ تعديل مهلة التنفيذ", callback_data="menu_set_delay")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]
        ]
        await query.edit_message_text(
            f"⚙️ **إعدادات ({acc.get('monster_name')})**\n\n"
            f"🔹 **النسبة الحالية:** `{acc['threshold']}%`\n"
            f"🔹 **المهلة الحالية:** بين `{min_d}` و `{max_d}` ثوانٍ",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    elif data == "menu_set_threshold":
        keyboard = [[InlineKeyboardButton("إلغاء ❌", callback_data="cancel_settings")]]
        await query.edit_message_text(
            "📊 **أدخل نسبة الشراء الجديدة** (مثال: 55):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SET_THRESHOLD

    elif data == "menu_set_delay":
        keyboard = [[InlineKeyboardButton("إلغاء ❌", callback_data="cancel_settings")]]
        await query.edit_message_text(
            "⏱️ **أدخل المهلة الزمنية العشوائية بالثواني**\n"
            "يجب كتابتها بصيغة: `الحد_الأدنى-الحد_الأقصى`\n"
            "مثال: `8-16` (علماً أن أقل رقم مسموح هو 3):",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SET_DELAY

    elif data == "cancel_settings":
        await query.edit_message_text("تم إلغاء العملية. القائمة الرئيسية:", reply_markup=build_main_keyboard(user_id))
        return ConversationHandler.END

    # -------------------- باقي القوائم --------------------
    if data == "open_accounts_menu":
        await query.edit_message_text(
            "🔄 **إدارة الحسابات المضافة**", reply_markup=build_accounts_keyboard(user_id), parse_mode="Markdown"
        )
    elif data.startswith("switch_acc_"):
        idx = int(data.replace("switch_acc_", ""))
        if 0 <= idx < len(udata["accounts"]):
            udata["active_index"] = idx
            await query.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=build_main_keyboard(user_id))
    elif data == "add_new_account":
        await query.edit_message_text("📥 أرسل بيانات الحساب الجديد:\n`API_ID API_HASH SESSION`", parse_mode="Markdown")
        return WAITING_CREDENTIALS
    elif data == "open_delete_menu":
        await query.edit_message_text("🗑️ **اختر الحساب للحذف:**", reply_markup=build_delete_keyboard(user_id))
    elif data.startswith("confirm_delete_"):
        idx = int(data.replace("confirm_delete_", ""))
        if 0 <= idx < len(udata["accounts"]):
            udata["accounts"].pop(idx)
            udata["active_index"] = 0
            await query.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=build_main_keyboard(user_id))
    
    elif data == "back_main" or data == "refresh_monster_info":
        if acc:
            success, monster, profile, token, err = await verify_account_and_get_monster(
                acc["api_id"], acc["api_hash"], acc["session"], acc.get("token")
            )
            if success:
                acc["token"] = token
                text = format_monster_info(monster, profile, acc)
                await query.edit_message_text(text, reply_markup=build_main_keyboard(user_id), parse_mode="Markdown")
                return
        await query.edit_message_text("🏠 القائمة الرئيسية:", reply_markup=build_main_keyboard(user_id))

    elif data == "toggle_ads":
        if acc:
            acc["ads_status"] = not acc["ads_status"]
            if acc["ads_status"]: acc["no_ads_status"] = False
            await query.edit_message_reply_markup(reply_markup=build_main_keyboard(user_id))

    elif data == "toggle_no_ads":
        if acc:
            acc["no_ads_status"] = not acc["no_ads_status"]
            if acc["no_ads_status"]: acc["ads_status"] = False
            await query.edit_message_reply_markup(reply_markup=build_main_keyboard(user_id))

# -------------------- دوال الإدخال النصي للإعدادات --------------------
async def process_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if text in ["إلغاء", "/cancel"]:
        await update.message.reply_text("تم الإلغاء.", reply_markup=build_main_keyboard(user_id))
        return ConversationHandler.END
    if not text.isdigit() or int(text) > 70:
        await update.message.reply_text("⚠️ يرجى إدخال رقم صحيح (لا يتجاوز 70).")
        return SET_THRESHOLD
    acc = get_active_account(user_id)
    if acc:
        acc["threshold"] = int(text)
    await update.message.reply_text(f"✅ تم التحديث.\n\nالرئيسية:", reply_markup=build_main_keyboard(user_id))
    return ConversationHandler.END

async def process_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if text in ["إلغاء", "/cancel"]:
        await update.message.reply_text("تم الإلغاء.", reply_markup=build_main_keyboard(user_id))
        return ConversationHandler.END
    
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError
        min_val = int(parts[0].strip())
        max_val = int(parts[1].strip())
        
        if min_val < 3:
            await update.message.reply_text("⚠️ الحد الأدنى المسموح به هو 3 ثوانٍ. أعد الإدخال:")
            return SET_DELAY
        if max_val < min_val:
            await update.message.reply_text("⚠️ يجب أن يكون الحد الأقصى أكبر من أو يساوي الحد الأدنى. أعد الإدخال:")
            return SET_DELAY

        acc = get_active_account(user_id)
        if acc:
            acc["delay_range"] = (min_val, max_val)
        
        await update.message.reply_text(f"✅ تم تحديث المهلة لتكون بين {min_val} و {max_val} ثوانٍ.\n\nالرئيسية:", reply_markup=build_main_keyboard(user_id))
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("⚠️ صيغة غير صحيحة. يرجى كتابتها هكذا: `8-16`", parse_mode="Markdown")
        return SET_DELAY

async def on_startup(app):
    asyncio.create_task(global_background_worker())

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالج الأخطاء العام لامتصاص انقطاعات شبكة تيليجرام وتجنب انهيار التطبيق"""
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning("تم اكتشاف ضعف/انقطاع وقتي في شبكة الاتصال، جاري إعادة المحاولة تلقائياً...")
    else:
        logger.error(f"حدث خطأ غريب غير معالج: {context.error}")

def main():
    # تكوين طلبات HTTP بمهلة زمنية مرنة لاستيعاب ضعف شبكة Pydroid
    custom_request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(custom_request)
        .post_init(on_startup)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(button_click_handler)
        ],
        states={
            WAITING_CREDENTIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_credentials)],
            SET_THRESHOLD: [
                CallbackQueryHandler(button_click_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_threshold)
            ],
            SET_DELAY: [
                CallbackQueryHandler(button_click_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_delay)
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(button_click_handler)
        ],
        allow_reentry=True,
        per_message=False  # منع تحذير PTBUserWarning
    )

    app.add_handler(conv_handler)
    app.add_error_handler(global_error_handler)

    print("🚀 البوت يعمل الآن بنظام الحماية ضد انقطاع الشبكة...")

    # تشغيل البوت مع وضع إعادة المحاولة المفتوحة للاتصال (bootstrap_retries=-1)
    app.run_polling(
        bootstrap_retries=-1,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30,
    )

if __name__ == "__main__":
    main()
