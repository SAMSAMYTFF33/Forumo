import asyncio
import time
import random
import urllib.parse
import aiohttp
import sys
import subprocess
import json
import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

# Telethon Imports
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    KeyboardButtonWebView,
    KeyboardButtonSimpleWebView,
    BotMenuButton,
)

# Telegram Bot Imports (python-telegram-bot v20+)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ==============================================================================
# 1. إعداد التسجيل (Logging Configuration)
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("UnifiedAutomationBot")

# ==============================================================================
# 2. إعدادات وثوابت بوت GramBux (ADS BUX)
# ==============================================================================
BOT_TOKEN = "8773555517:AAHv8Wyrgizmy9iZfnYQJu8tELpZWca_v5M"

TARGET_GRAMBUX_BOT = "grambuxbot"
BACKEND_URL_GRAMBUX = "https://grambux-backend.ankisaw1003.workers.dev"

TOTAL_BLOCKS = 5
MAX_WATCH_COUNT = 10
ONE_HOUR_SEC = 3600
DB_FILE = "grambux_accounts.json"

INPUT_CREDS = 1

db = {}
bot_app = None
account_locks = {}

def get_account_lock(sess_str: str) -> asyncio.Lock:
    return account_locks.setdefault(sess_str, asyncio.Lock())

# ==============================================================================
# 3. إعدادات وثوابت بوت ATF Airdrop
# ==============================================================================
TARGET_BOT_USERNAME_ATF = "ATF_AIRDROP_bot"
WEB_APP_URL_ATF = "https://atfminers.asloni.online/miner/index.html"
BASE_URL_ATF = "https://atfminers.asloni.online"

LOGIN_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=login"
START_MINE_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=start_mine"
ACTIVATE_BOOST_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=activate_boost"
START_TASK_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=claim_task"

CYCLE_INTERVAL_ATF = 7500
RETRY_CLAIM_DELAY_ATF = 30
MAX_CLAIM_RETRY_TIME_ATF = 600

TASKS_ATF = [
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube Like & Comment"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "X (Twitter) Retweet"},
    {"id": "website_visit", "min_seconds": 0, "name": "Visit Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React to latest post"}
]

ACCOUNTS_CONFIG_ATF = [
    {
        "account_name": "ATF - الحساب الأول",
        "api_id": 31514497,
        "api_hash": "98d779341dd063307994de23cfd9796d",
        "session_string": "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww=",
        "device_prefix": "dev-A",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    },
    {
        "account_name": "ATF - الحساب الثاني",
        "api_id": 31568734,
        "api_hash": "7286e8c92ccc4dc698d771664bf71700",
        "session_string": "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU=",
        "device_prefix": "dev-B",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.72 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not=A?Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "en-US,en;q=0.9,ar;q=0.8"
        }
    },
    {
        "account_name": "ATF - الحساب الثالث",
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu6E163KHvlWxvFMB8CJa3BozQdoNy-SaM35r6cIDE4AEnw84J5EufYhMXmliVmRPg0vYpQbKBEKGhKgugLK6V-JZL09a7g-T77PHK9UA9ERCfpG4cxLK26IRI-nMw81WcH-q83TUT3XvTCOrqSJBd4WnIGo2MH8d52F_5jbj1tgvwcFvkCjIYkr0qhSx5oPbWz9gMvpIX0Rwp8vUd1yVX6pvy5-u3AIqqabkgn7JgC5-7I_B7uMTnY2vQb0_rnvkn2SoZQYXFt1yWZyWaUwJvCqlAKSYihCGc5l3yQCzMRsm4xhkC-SGsjxyncEePn5KO8_ZVM22zA_rfEqs1PqSz14=",
        "device_prefix": "dev-C",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="123", "Google Chrome";v="123"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    },
    {
        "account_name": "ATF - الحساب الرابع",
        "api_id": 39861404,
        "api_hash": "4cb96e0a355d9eabec3f5f2cd4b67a5c",
        "session_string": "1BJWap1sBu1xhskVGuKzHuU5Bh2osGc406eWhbkMYvmKpvU4yFfD9p0v8SiJe7jcU88Mk7fMTwoT7NFZy8fWRdRUhTw3ox1hoeL0vFdcs5OKxXYcjmBpbc4MpQCDplAJiQcv8m2cMar0QM-gkXK3q6tmltTei5ny4uvpEPVSB3-23ogPpy3CjLkWjeegoJX6IOE3ir9b-GM8eEe1Z7WXj_wsiOohuyjUxQh4X9Sd3-63toHlqmL3b7GPkFKe07MBSiCeqA5o8aOk3ZybTYD1-N4wLbYCJHeKaM2Y_KBSabN09m7QVCA2aovDCL-mXU-ElSFRy1B-MOcysV5mHY5JQzIk0ZHyAw40=",
        "device_prefix": "dev-D",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; CPH2581) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    }
]

# ==============================================================================
# 4. إدارة قاعدة البيانات لبوت GramBux
# ==============================================================================
def save_db():
    try:
        tmp_file = DB_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DB_FILE)
    except Exception as e:
        logger.error(f"⚠️ فشل حفظ قاعدة البيانات: {e}")

def load_db():
    global db
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                db = {int(k): v for k, v in loaded.items()}
            total_accs = sum(len(v.get("accs", [])) for v in db.values())
            logger.info(f"✅ تم تحميل قاعدة البيانات: {len(db)} مستخدم، {total_accs} حساب")
        else:
            logger.info("ℹ️ ملف قاعدة البيانات غير موجود، بدء جلسة جديدة.")
    except Exception as e:
        logger.error(f"⚠️ فشل تحميل قاعدة البيانات: {e}")

def udb(uid: int) -> dict:
    return db.setdefault(uid, {"idx": 0, "accs": []})

def get_current_acc(uid: int) -> Optional[dict]:
    d = udb(uid)
    if not d["accs"]:
        return None
    d["idx"] = min(d["idx"], len(d["accs"]) - 1)
    return d["accs"][d["idx"]]

# ==============================================================================
# 5. منطق GramBux: استخراج initData والتفاعل مع API
# ==============================================================================
def parse_telethon_creds(text: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    cleaned = []
    
    for l in lines:
        if "=" in l:
            val = l.split("=", 1)[1].strip().strip('"\';')
            cleaned.append(val)
        else:
            cleaned.append(l.strip().strip('"\';'))

    if len(cleaned) == 1 and " " in cleaned[0]:
        cleaned = [c.strip('"\',:=;') for c in cleaned[0].split()]

    api_id, api_hash, session_str = None, None, None

    for t in cleaned:
        if t.isdigit() and 5 <= len(t) <= 12 and not api_id:
            api_id = int(t)
        elif len(t) == 32 and all(c in '0123456789abcdefABCDEF' for c in t) and not api_hash:
            api_hash = t
        elif len(t) > 50 and not session_str:
            session_str = t

    return api_id, api_hash, session_str

async def extract_init_data_via_telethon(api_id: int, api_hash: str, session_str: str) -> Tuple[bool, Optional[str], Optional[int], Optional[str], Optional[str]]:
    async with get_account_lock(session_str):
        try:
            logger.info(f"🔄 [Telethon GramBux] الاتصال بالحساب (API_ID: {api_id})...")
            async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
                me = await client.get_me()
                user_id = me.id
                user_name = me.first_name or me.username or str(user_id)

                bot = await client.get_input_entity(TARGET_GRAMBUX_BOT)

                await client.send_message(bot, "/start")
                await asyncio.sleep(2)

                target_url = None
                from_menu = False

                async for message in client.iter_messages(bot, limit=2):
                    if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                        for row in message.reply_markup.rows:
                            for button in row.buttons:
                                if isinstance(button, (KeyboardButtonWebView, KeyboardButtonSimpleWebView)):
                                    target_url = getattr(button, 'url', None)

                if not target_url:
                    full = await client(GetFullUserRequest(bot))
                    bot_info = getattr(full.full_user, 'bot_info', None)
                    menu_button = getattr(bot_info, 'menu_button', None) if bot_info else None

                    if isinstance(menu_button, BotMenuButton) and getattr(menu_button, 'url', None):
                        target_url = menu_button.url
                        from_menu = True

                if not target_url:
                    target_url = BACKEND_URL_GRAMBUX

                web_view = await client(RequestWebViewRequest(
                    peer=bot,
                    bot=bot,
                    platform="android",
                    from_bot_menu=from_menu,
                    url=target_url
                ))

                raw_url = web_view.url

                if "#tgWebAppData=" in raw_url:
                    init_data = raw_url.split("#tgWebAppData=")[1].split("&")[0]
                elif "tgWebAppData=" in raw_url:
                    init_data = raw_url.split("tgWebAppData=")[1].split("&")[0]
                else:
                    return False, None, user_id, user_name, "تعذر استخراج initData من الرابط."

                decoded_init_data = urllib.parse.unquote(init_data)
                logger.info(f"✅ [Telethon GramBux] تم استخراج initData للحساب: {user_name}")
                return True, decoded_init_data, user_id, user_name, None

        except Exception as e:
            logger.error(f"❌ [Telethon GramBux] خطأ أثناء الاتصال: {e}")
            return False, None, None, None, str(e)

def build_grambux_headers(init_data: str) -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": init_data
    }

async def api_fetch_user(init_data: str, tg_id: int, username: str) -> tuple:
    url = f"{BACKEND_URL_GRAMBUX}/api/user"
    params = {
        "tg_id": tg_id,
        "username": username,
        "telegram_username": username,
        "referrer": "",
        "_t": int(time.time() * 1000)
    }
    headers = build_grambux_headers(init_data)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params, timeout=12) as r:
                if r.status == 200:
                    data = await r.json()
                    return True, data, None
                return False, None, f"status_{r.status}"
        except Exception as e:
            return False, None, str(e)

async def api_watch_ad(init_data: str, tg_id: int, block_id: int) -> tuple:
    url = f"{BACKEND_URL_GRAMBUX}/api/watch-ad/watch"
    payload = {"tg_id": tg_id, "block_id": block_id}
    headers = build_grambux_headers(init_data)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=15) as r:
                data = await r.json()
                return r.status == 200, data
        except Exception as e:
            return False, {"error": str(e)}

async def api_claim_ad(init_data: str, tg_id: int, block_id: int) -> tuple:
    url = f"{BACKEND_URL_GRAMBUX}/api/watch-ad/claim"
    payload = {"tg_id": tg_id, "block_id": block_id}
    headers = build_grambux_headers(init_data)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=15) as r:
                data = await r.json()
                return r.status == 200, data
        except Exception as e:
            return False, {"error": str(e)}

async def refresh_account_token_if_needed(a: dict) -> bool:
    ok, init_data, tg_id, name, err = await extract_init_data_via_telethon(a["api_id"], a["api_hash"], a["session_string"])
    if ok and init_data:
        a["init_data"] = init_data
        save_db()
        return True
    return False

def parse_date_utc(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None

def evaluate_block_status(block_id: int, watch_progress: dict, now_utc: datetime) -> dict:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def get_wp(b):
        return watch_progress.get(str(b)) or watch_progress.get(b) or {}

    wp = get_wp(block_id)
    claimed_at = parse_date_utc(wp.get("claimed_at"))
    is_claimed_today = bool(wp.get("claimed_today")) and claimed_at and claimed_at.strftime("%Y-%m-%d") == today_str
    watched_count = wp.get("watched_count", 0)

    if is_claimed_today:
        return {"status": "claimed", "msg": f"✅ الكتلة {block_id}: مكتملة اليوم", "watched": MAX_WATCH_COUNT}

    if block_id == 1:
        return {"status": "unlocked", "msg": f"🟢 الكتلة 1: جاهزة ({watched_count}/10)", "watched": watched_count}

    for prev in range(1, block_id):
        prev_wp = get_wp(prev)
        prev_claimed_at = parse_date_utc(prev_wp.get("claimed_at"))
        prev_is_today = prev_claimed_at and prev_claimed_at.strftime("%Y-%m-%d") == today_str
        if not (prev_wp.get("claimed_today") and prev_is_today):
            return {"status": "locked", "msg": f"🔒 الكتلة {block_id}: مقفلة (تنتظر الكتلة {prev})", "watched": watched_count}

    imm_prev_wp = get_wp(block_id - 1)
    imm_prev_claimed_at = parse_date_utc(imm_prev_wp.get("claimed_at"))

    if not imm_prev_claimed_at:
        return {"status": "locked", "msg": f"🔒 الكتلة {block_id}: مقفلة", "watched": watched_count}

    elapsed = (now_utc - imm_prev_claimed_at).total_seconds()
    remaining = ONE_HOUR_SEC - elapsed

    if remaining > 0:
        m, s = divmod(int(remaining), 60)
        return {"status": "cooldown", "msg": f"⏳ الكتلة {block_id}: مهلة ({m}m {s}s)", "remaining": int(remaining), "watched": watched_count}

    return {"status": "unlocked", "msg": f"🟢 الكتلة {block_id}: جاهزة ({watched_count}/10)", "watched": watched_count}

# ==============================================================================
# 6. أزرار وواجهات البوت (GramBux UI)
# ==============================================================================
def main_kb(uid: int) -> InlineKeyboardMarkup:
    a = get_current_acc(uid)
    if not a:
        return InlineKeyboardMarkup([[InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add")]])

    auto_status = "التشغيل التلقائي: 🟢 شغال" if a.get("auto_run") else "التشغيل التلقائي: 🔴 متوقف"
    
    kb = [
        [InlineKeyboardButton(f"👤 {a['name']} 🔄", callback_data="accs")],
        [InlineKeyboardButton(auto_status, callback_data="t_autorun")],
        [InlineKeyboardButton("🎯 مشاهدة إعلان يدوياً", callback_data="manual_watch")],
        [InlineKeyboardButton("🎁 المطالبة بالجائزة (Claim)", callback_data="manual_claim")],
        [InlineKeyboardButton("🔄 تحديث حالة الكتل", callback_data="refresh")],
    ]
    return InlineKeyboardMarkup(kb)

def accs_kb(uid: int) -> InlineKeyboardMarkup:
    d = udb(uid)
    kb = [[InlineKeyboardButton(("✅ " if i == d["idx"] else "🔘 ") + a["name"], callback_data=f"sw_{i}")]
          for i, a in enumerate(d["accs"])]
    kb.append([InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add")])
    if d["accs"]:
        kb.append([InlineKeyboardButton("🗑️ حذف حساب", callback_data="deltmenu")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    return InlineKeyboardMarkup(kb)

def del_kb(uid: int) -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(f"❌ حذف {a['name']}", callback_data=f"del_{i}")] for i, a in enumerate(udb(uid)["accs"])]
    kb.append([InlineKeyboardButton("🔙 إلغاء ورجوع", callback_data="accs")])
    return InlineKeyboardMarkup(kb)

def blocks_kb(action_prefix: str) -> InlineKeyboardMarkup:
    kb = [[InlineKeyboardButton(f"الكتلة {b}", callback_data=f"{action_prefix}_{b}")] for b in range(1, TOTAL_BLOCKS + 1)]
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="back")])
    return InlineKeyboardMarkup(kb)

def build_info_text(a: dict, user_data: dict) -> str:
    stars = user_data.get("stars", 0)
    wp = user_data.get("watchProgress", {})
    now_utc = datetime.now(timezone.utc)

    txt = f"👤 **الحساب:** `{a['name']}`\n"
    txt += f"⭐ **إجمالي النجوم:** `{stars}`\n"
    txt += "----------------------------------\n"
    txt += "📊 **حالة كتل الإعلانات:**\n"

    for b in range(1, TOTAL_BLOCKS + 1):
        res = evaluate_block_status(b, wp, now_utc)
        txt += f"• {res['msg']}\n"

    return txt

async def notify_user(uid: int, text: str, kb=None):
    if not bot_app:
        return
    try:
        await bot_app.bot.send_message(chat_id=uid, text=text, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logger.error(f"⚠️ فشل إرسال إشعار للمستخدم {uid}: {e}")

# ==============================================================================
# 7. محرك الخلفية الخاص بـ GramBux (مع المهل العشوائية والتوازي)
# ==============================================================================
async def process_account_automation(uid: int, a: dict):
    """معالجة حساب GramBux واحد بطريقة آمنة مع إضافة المهل العشوائية."""
    ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])
    if not ok:
        refreshed = await refresh_account_token_if_needed(a)
        if refreshed:
            ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])
        if not ok or not user_data:
            return

    wp = user_data.get("watchProgress", {})
    now_utc = datetime.now(timezone.utc)

    for b_id in range(1, TOTAL_BLOCKS + 1):
        res = evaluate_block_status(b_id, wp, now_utc)
        
        if res["status"] in ("claimed", "cooldown", "locked"):
            continue

        if res["status"] == "unlocked":
            watched = res["watched"]
            if watched < MAX_WATCH_COUNT:
                # إضافة مهلة زمنية عشوائية بين الطلبات لتفادي الحظر
                watch_delay = random.uniform(5.0, 10.0)
                logger.info(f"🤖 [GramBux] حساب {a['name']} - انتظار {watch_delay:.1f}s قبل مشاهدة إعلان كتلة {b_id} ({watched + 1}/{MAX_WATCH_COUNT})")
                await asyncio.sleep(watch_delay)

                success, w_data = await api_watch_ad(a["init_data"], a["tg_id"], b_id)
                
                if success:
                    new_count = w_data.get("watched_count", watched + 1)
                    logger.info(f"✅ [GramBux] حساب {a['name']} - نجحت المشاهدة للكتلة {b_id} ({new_count}/10)")
                    if a.get("notify", True) and new_count == MAX_WATCH_COUNT:
                        await notify_user(uid, f"🎉 **[{a['name']}]** اكتملت مشاهدات الكتلة {b_id}!")
                else:
                    err_msg = w_data.get("error", "")
                    match = re.search(r"wait (\d+) seconds?", err_msg, re.IGNORECASE)
                    if match:
                        wait_sec = int(match.group(1))
                        logger.info(f"⏳ [GramBux] السيرفر يطلب الانتظار {wait_sec} ثانية...")
                        await asyncio.sleep(wait_sec)
                return

            elif watched >= MAX_WATCH_COUNT:
                # مهلة عشوائية قبل المطالبة (Claim)
                claim_delay = random.uniform(4.0, 8.0)
                logger.info(f"🎁 [GramBux] حساب {a['name']} - انتظار {claim_delay:.1f}s قبل المطالبة بالكتلة {b_id}")
                await asyncio.sleep(claim_delay)

                success, c_data = await api_claim_ad(a["init_data"], a["tg_id"], b_id)
                if success:
                    stars = c_data.get("newStars", "غير معروف")
                    logger.info(f"🎉 [GramBux] حساب {a['name']} - تم مطالبة الكتلة {b_id} بنجاح! النجوم: {stars}")
                    await notify_user(uid, f"✅ **[{a['name']}]** تم استلام مكافأة الكتلة {b_id}!\n⭐ الرصيد: `{stars}`")
                else:
                    logger.error(f"❌ [GramBux] حساب {a['name']} - فشل مطالبة الكتلة {b_id}: {c_data.get('error')}")
                return

async def bg_worker_grambux():
    """حلقة الفحص التلقائي لحسابات GramBux المحدثة لتضمن التوازي بين الحسابات."""
    logger.info("🔄 [محرك GramBux] بدء حلقة المتابعة التلقائية لجميع الحسابات...")
    tick = 0
    while True:
        try:
            tasks = []
            for uid, d in list(db.items()):
                for a in d.get("accs", []):
                    if a.get("auto_run"):
                        tasks.append(process_account_automation(uid, a))

            if tasks:
                # تشغيل معالجة كافة الحسابات بالتوازي بدلاً من التتابع
                await asyncio.gather(*tasks, return_exceptions=True)

            tick += 1
            if tick % 5 == 0:
                save_db()

            await asyncio.sleep(15)
        except Exception as e:
            logger.error(f"💥 [محرك GramBux] خطأ غير متوقع: {e}")
            await asyncio.sleep(15)

# ==============================================================================
# 8. محرك الخلفية الخاص بـ ATF Airdrop (مستقل تماماً)
# ==============================================================================
async def get_init_data_atf(client, bot, acc_name):
    try:
        web_view = await client(RequestWebViewRequest(
            peer=bot, bot=bot, platform="android", from_bot_menu=True, url=WEB_APP_URL_ATF
        ))
        raw_url = web_view.url
        if "#tgWebAppData=" in raw_url:
            encoded = raw_url.split("#tgWebAppData=")[1].split("&")[0]
        elif "tgWebAppData=" in raw_url:
            encoded = raw_url.split("tgWebAppData=")[1].split("&")[0]
        else:
            return None
        return urllib.parse.unquote(encoded)
    except Exception as e:
        logger.error(f"⚠️ [{acc_name}] خطأ استخراج initData ATF: {e}")
        return None

async def login_atf(session, init_data, tg_id, username, acc_config):
    headers = {
        "User-Agent": acc_config["user_agent"],
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL_ATF,
        "Referer": f"{BASE_URL_ATF}/miner/index.html",
        "X-Requested-With": "XMLHttpRequest",
        "X-Telegram-Init-Data": init_data,
        **acc_config.get("extra_headers", {})
    }
    payload = {
        "initData": init_data,
        "tg_id": tg_id,
        "username": username or "",
        "request_id": f"rq-{int(time.time()*1000)}-{tg_id}",
        "device_id": f"{acc_config['device_prefix']}-{tg_id}-{int(time.time())}"
    }
    async with session.post(LOGIN_ENDPOINT_ATF, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("tma_session_token"), data.get("react_post"), headers
    return None, None, None

async def do_boost_atf(session, headers, payload, acc_name):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT_ATF, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                logger.info(f"⚡ [{acc_name}] تم تفعيل التسريع بنجاح (Boost)!")
            else:
                msg = data.get("message", "Unknown")
                if "already" in msg.lower() or "wait" in msg.lower():
                    logger.info(f"ℹ️ [{acc_name}] Boost: {msg}")
                else:
                    logger.warning(f"⚠️ [{acc_name}] Boost failed: {msg}")
            return data
    except Exception as e:
        logger.error(f"💥 [{acc_name}] Boost error: {e}")
        return None

async def attempt_claim_atf(session, headers, claim_payload, task_name, acc_name):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT_ATF, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                reward = data.get("reward", 0)
                logger.info(f"✅ [{acc_name}] {task_name} تمت المطالبة بنجاح! +{reward} ATF")
                return True, data
            else:
                return False, data
    except Exception as e:
        logger.error(f"❌ [{acc_name}] خطأ في claim_task لـ {task_name}: {e}")
        return False, {"status": "error", "message": str(e)}

async def do_task_atf(session, headers, task, tg_id, init_data, device_prefix, acc_name, react_post_link=None):
    task_id = task["id"]
    min_sec = task["min_seconds"]
    task_name = task["name"]

    if task_id == "telegram_react_latest" and not react_post_link:
        logger.info(f"⚠️ [{acc_name}] {task_name}: لا يوجد رابط للتحديث الأخير، تخطي")
        return

    logger.info(f"🔄 [{acc_name}] بدء المهمة: {task_name}")
    now = int(time.time())

    start_payload = {
        "tg_id": tg_id,
        "task_id": task_id,
        "client_started_at": now,
        "initData": init_data,
        "device_id": f"{device_prefix}-{tg_id}-{now}",
        "request_id": f"rq-{now}-{tg_id}"
    }
    try:
        async with session.post(START_TASK_ENDPOINT_ATF, json=start_payload, headers=headers) as resp:
            start_data = await resp.json()
            if start_data.get("status") != "success":
                logger.error(f"❌ [{acc_name}] فشل start_task لـ {task_name}: {start_data.get('message')}")
                return
            server_started_at = start_data.get("started_at")
            started_at = int(server_started_at) if server_started_at else now
            logger.info(f"✅ [{acc_name}] start_task لـ {task_name} تم، started_at={started_at}")
    except Exception as e:
        logger.error(f"❌ [{acc_name}] خطأ في start_task لـ {task_name}: {e}")
        return

    wait_time = min_sec + 3
    if wait_time > 0:
        logger.info(f"⏳ [{acc_name}] انتظار {wait_time} ثانية قبل المطالبة لـ {task_name}...")
        await asyncio.sleep(wait_time)

    claim_payload = {
        "tg_id": tg_id,
        "task_id": task_id,
        "client_started_at": started_at,
        "initData": init_data,
        "device_id": f"{device_prefix}-{tg_id}-{started_at}",
        "request_id": f"rq-{started_at}-{tg_id}"
    }

    success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name, acc_name)
    if success:
        return

    msg = claim_data.get("message", "").lower()
    keywords = ["wait", "try again", "not ready", "please wait", "seconds", "cooldown", "retry"]
    if not any(k in msg for k in keywords):
        logger.error(f"❌ [{acc_name}] فشل claim_task لـ {task_name}: {claim_data.get('message')}")
        return

    logger.info(f"⏳ [{acc_name}] {task_name}: إعادة محاولة claim كل {RETRY_CLAIM_DELAY_ATF} ثانية...")
    start_time = time.time()
    while True:
        if time.time() - start_time > MAX_CLAIM_RETRY_TIME_ATF:
            logger.error(f"❌ [{acc_name}] {task_name}: انتهى وقت إعادة المحاولة.")
            break
        await asyncio.sleep(RETRY_CLAIM_DELAY_ATF)
        success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name, acc_name)
        if success:
            return

async def atf_boost_worker(session, headers, me, init_data, lock, device_prefix, acc_name):
    await asyncio.sleep(2)
    while True:
        delay = round(random.uniform(9, 11), 2)
        try:
            async with lock:
                payload = {
                    "initData": init_data,
                    "tg_id": me.id,
                    "username": me.username or "",
                    "request_id": f"rq-{int(time.time()*1000)}-{me.id}",
                    "device_id": f"{device_prefix}-{me.id}-{int(time.time())}",
                    "display_preview": "0.0000"
                }
                async with session.post(START_MINE_ENDPOINT_ATF, json=payload, headers=headers) as resp:
                    pass
                await do_boost_atf(session, headers, payload, acc_name)
        except Exception as e:
            logger.error(f"💥 [{acc_name}] خطأ حلقة التسريع ATF: {e}")
        await asyncio.sleep(delay)

async def atf_tasks_worker(session, headers, me, init_data, react_post, lock, device_prefix, acc_name):
    while True:
        async with lock:
            logger.info(f"📝 [{acc_name}] بدء تنفيذ مهام ATF الدورية...")
            try:
                react_post_link = react_post.get("link") if isinstance(react_post, dict) else None
                for task in TASKS_ATF:
                    await do_task_atf(session, headers, task, me.id, init_data, device_prefix, acc_name, react_post_link)
                logger.info(f"✅ [{acc_name}] تم الانتهاء من جميع مهام ATF.")
            except Exception as e:
                logger.error(f"💥 [{acc_name}] خطأ حلقة المهام ATF: {e}")

        logger.info(f"⏳ [{acc_name}] انتظار دوره ATF القادمة خلال {CYCLE_INTERVAL_ATF} ثانية...")
        await asyncio.sleep(CYCLE_INTERVAL_ATF)

async def atf_account_worker(acc_config):
    acc_name = acc_config["account_name"]
    logger.info(f"🔄 [{acc_name}] الاتصال بجلسة تيليجرام...")
    
    async with aiohttp.ClientSession() as http_session:
        async with TelegramClient(StringSession(acc_config["session_string"]), acc_config["api_id"], acc_config["api_hash"]) as client:
            me = await client.get_me()
            logger.info(f"✅ [{acc_name}] تم تسجيل الدخول: {me.first_name} (@{me.username or me.id})")

            bot = await client.get_input_entity(TARGET_BOT_USERNAME_ATF)
            init_data = await get_init_data_atf(client, bot, acc_name)

            if not init_data:
                logger.error(f"❌ [{acc_name}] فشل استخراج initData ATF.")
                return

            token, react_post, _ = await login_atf(
                http_session, 
                init_data, 
                me.id, 
                me.username, 
                acc_config
            )

            if not token:
                logger.error(f"❌ [{acc_name}] فشل تسجيل الدخول في لعبة ATF.")
                return

            logger.info(f"✅ [{acc_name}] تم المصادقة بنجاح وجاهز للعمل!")
            headers = {
                "User-Agent": acc_config["user_agent"],
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": BASE_URL_ATF,
                "Referer": f"{BASE_URL_ATF}/miner/index.html",
                "X-Requested-With": "XMLHttpRequest",
                "X-Telegram-Init-Data": init_data,
                "X-ATF-TMA-Session": token,
                **acc_config.get("extra_headers", {})
            }
            lock = asyncio.Lock()

            await asyncio.gather(
                atf_tasks_worker(http_session, headers, me, init_data, react_post, lock, acc_config["device_prefix"], acc_name),
                atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"], acc_name)
            )

async def bg_worker_atf():
    """المحرك الرئيسي لتشغيل كافة حسابات ATF بالتوازي بالخلفية."""
    logger.info("🚀 [محرك ATF] بدء تشغيل جميع حسابات ATF في الخلفية...")
    try:
        await asyncio.gather(*(atf_account_worker(acc) for acc in ACCOUNTS_CONFIG_ATF), return_exceptions=True)
    except Exception as e:
        logger.error(f"💥 [محرك ATF] خطأ غير متوقع في محرك ATF: {e}")

# ==============================================================================
# 9. أحداث ومعالجات بوت التليجرام الرئيسي (Telegram Handlers)
# ==============================================================================
async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    a = get_current_acc(uid)
    
    if not a:
        msg = (
            "👋 **أهلاً بك في بوت إدارة حسابات GramBux الاحترافي!**\n\n"
            "أرسل الآن بيانات الحساب بالتنسيق التالي (كل قيمة بسطر أو المنسوخة ككود):\n\n"
            "`API_ID = 38197378`\n"
            "`API_HASH = \"1efeb1db16...\"`\n"
            "`SESSION_STRING = \"1BJWap1sBu...\"`"
        )
        await u.message.reply_text(msg, parse_mode="Markdown")
        return INPUT_CREDS

    ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])
    if not ok:
        await refresh_account_token_if_needed(a)
        ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])

    if ok:
        txt = build_info_text(a, user_data)
    else:
        txt = f"🏠 **القائمة الرئيسية**\n⚠️ فشل تحديث البيانات: {err}"

    await u.message.reply_text(txt, reply_markup=main_kb(uid), parse_mode="Markdown")
    return ConversationHandler.END

async def on_input_creds(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    text = u.message.text.strip()

    api_id, api_hash, session_str = parse_telethon_creds(text)

    if not (api_id and api_hash and session_str):
        await u.message.reply_text("⚠️ البيانات غير مكتملة! أعد إرسال `API_ID` و `API_HASH` و `SESSION_STRING` بشكل صحيح:")
        return INPUT_CREDS

    msg = await u.message.reply_text("⏳ جاري الاتصال بحساب التليجرام عبر Telethon واستخراج initData...")
    
    ok, init_data, tg_id, acc_name, err = await extract_init_data_via_telethon(api_id, api_hash, session_str)

    if not ok or not init_data:
        await msg.edit_text(f"❌ فشل الاتصال واستخراج الـ initData:\n`{err}`\n\nأعد إرسال البيانات بشكل صحيح:")
        return INPUT_CREDS

    ok_api, user_data, api_err = await api_fetch_user(init_data, tg_id, acc_name)
    if not ok_api:
        await msg.edit_text(f"❌ فشل جلب البيانات من GramBux API: `{api_err}`")
        return INPUT_CREDS

    d = udb(uid)
    new_acc = {
        "name": acc_name,
        "api_id": api_id,
        "api_hash": api_hash,
        "session_string": session_str,
        "init_data": init_data,
        "tg_id": tg_id,
        "username": acc_name,
        "auto_run": True,
        "notify": True,
        "key": f"{uid}_{len(d['accs'])}_{int(time.time())}"
    }

    d["accs"].append(new_acc)
    d["idx"] = len(d["accs"]) - 1
    save_db()

    txt = build_info_text(new_acc, user_data)
    await msg.edit_text(f"🎉 **تم إضافة الحساب بنجاح!**\n\n{txt}", reply_markup=main_kb(uid), parse_mode="Markdown")
    return ConversationHandler.END

async def on_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    data = q.data
    d = udb(uid)
    a = get_current_acc(uid)

    async def safe_edit(text=None, kb=None):
        try:
            if text:
                await q.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            else:
                await q.edit_message_reply_markup(reply_markup=kb)
        except Exception:
            pass

    if data == "t_autorun":
        if a:
            a["auto_run"] = not a.get("auto_run", False)
            save_db()
            await safe_edit(kb=main_kb(uid))
        return

    if data == "refresh":
        if not a:
            return
        ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])
        if not ok:
            await refresh_account_token_if_needed(a)
            ok, user_data, err = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])

        if ok:
            await safe_edit(build_info_text(a, user_data), main_kb(uid))
        else:
            await safe_edit(f"❌ فشل التحديث: {err}", main_kb(uid))
        return

    if data == "manual_watch":
        await safe_edit("🎯 **اختر رقم الكتلة لمشاهدة إعلان فيها:**", blocks_kb("do_watch"))
        return

    if data.startswith("do_watch_"):
        b_id = int(data.split("_")[2])
        await safe_edit(f"⏳ جاري إرسال طلب مشاهدة الإعلان للكتلة {b_id}...")
        ok, res = await api_watch_ad(a["init_data"], a["tg_id"], b_id)
        if ok:
            cnt = res.get("watched_count", "مكتمل")
            await safe_edit(f"✅ تم تسجيل المشاهدة للكتلة {b_id}! ({cnt}/{MAX_WATCH_COUNT})", main_kb(uid))
        else:
            await safe_edit(f"⚠️ فشلت المشاهدة: {res.get('error', 'خطأ غير معروف')}", main_kb(uid))
        return

    if data == "manual_claim":
        await safe_edit("🎁 **اختر رقم الكتلة للمطالبة بمكافأتها:**", blocks_kb("do_claim"))
        return

    if data.startswith("do_claim_"):
        b_id = int(data.split("_")[2])
        await safe_edit(f"⏳ جاري إرسال طلب المطالبة بالكتلة {b_id}...")
        ok, res = await api_claim_ad(a["init_data"], a["tg_id"], b_id)
        if ok:
            stars = res.get("newStars", "غير معروف")
            await safe_edit(f"🎉 تم استلام الجائزة بنجاح!\n⭐ إجمالي النجوم الجديد: `{stars}`", main_kb(uid))
        else:
            await safe_edit(f"❌ فشلت المطالبة: {res.get('error', 'خطأ غير معروف')}", main_kb(uid))
        return

    if data == "accs":
        await safe_edit("🔄 **إدارة الحسابات المسجلة:**", accs_kb(uid))
        return

    if data.startswith("sw_"):
        idx = int(data[3:])
        if 0 <= idx < len(d["accs"]):
            d["idx"] = idx
            save_db()
        await safe_edit("🔄 **إدارة الحسابات المسجلة:**", accs_kb(uid))
        return

    if data == "add":
        await safe_edit("📥 **أرسل بيانات Telethon للحساب الجديد:**\n\nAPI_ID\nAPI_HASH\nSESSION_STRING")
        return INPUT_CREDS

    if data == "deltmenu":
        await safe_edit("🗑️ **اختر الحساب المراد حذفه:**", del_kb(uid))
        return

    if data.startswith("del_"):
        idx = int(data[4:])
        if 0 <= idx < len(d["accs"]):
            removed = d["accs"].pop(idx)
            d["idx"] = 0
            save_db()
            await safe_edit(f"🗑️ تم حذف حساب **{removed['name']}** بنجاح.", main_kb(uid))
        else:
            await safe_edit("🏠 القائمة الرئيسية:", main_kb(uid))
        return

    if data == "back":
        if a:
            ok, user_data, _ = await api_fetch_user(a["init_data"], a["tg_id"], a["username"])
            if ok:
                await safe_edit(build_info_text(a, user_data), main_kb(uid))
                return
        await safe_edit("🏠 القائمة الرئيسية:", main_kb(uid))

# ==============================================================================
# 10. إقلاع المهام الخلفية المزدوجة عند بدء التطبيق
# ==============================================================================
async def on_startup(app):
    global bot_app
    bot_app = app
    
    # 1. إطلاق محرك GramBux التلقائي
    asyncio.create_task(bg_worker_grambux())
    
    # 2. إطلاق محرك ATF Airdrop المستقل بالكامل في الخلفية
    asyncio.create_task(bg_worker_atf())
    
    logger.info("⚡ تم إطلاق مهام الخلفية لـ GramBux و ATF بنجاح!")

# ==============================================================================
# 11. التشغيل الرئيسي وحلقة الحماية (Process Supervisor)
# ==============================================================================
def main():
    load_db()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start), CallbackQueryHandler(on_button)],
        states={
            INPUT_CREDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_input_creds)],
        },
        fallbacks=[CommandHandler("start", cmd_start), CallbackQueryHandler(on_button)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    logger.info("🚀 البوت الموحد يعمل الآن وجاهز لاستقبال الأوامر...")
    app.run_polling()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        main()
    else:
        while True:
            logger.info("🚀 بدء العملية الفرعية للبوت الموحد...")
            try:
                res = subprocess.run([sys.executable, __file__, "--child"])
                if res.returncode == 0:
                    logger.info("⏹️ تم إيقاف العملية بشكل طبيعي.")
                    break
                logger.warning(f"⚠️ توقفت العملية الفرعية (كود: {res.returncode}) — إعادة التشغيل خلال 10 ثوانٍ...")
            except KeyboardInterrupt:
                logger.info("⏹️ تم إيقاف البوت يدويًا.")
                break
            except Exception as e:
                logger.error(f"💥 خطأ في العملية الرئيسية: {e}")
            
            time.sleep(10)
