import asyncio
import urllib.parse
import aiohttp
import json
import time
import random
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from cryptography.fernet import Fernet

# ===================== البيانات المشفرة =====================
KEY = b'oiL4Z8RZJ-znrlkJg0fKD0xuDqWQNxfK4pbPyJWONVw='

ENC_SESSION = b'gAAAAABqcinpJArdkQQQs5PP4opqhCwLb-aOCBIMYWaCOIIi64YBC55xED_QhbANbqD-_VXg7DbABO2fSOhUXGC3gBS6_NFEfNJD-NdnVLjwqEAyLIA6E_LOlLpHTT-oLLywXTFTprBcmBPhwqJooV-TrUkJa7kVVO24Uu8l_TgT3AnozPtFBh45DRm4Yk8KSTeYN5O-7XYGJrVeozK1wNxUbWa9w_3cS0MZ6FA1JyyiVcBbXfRwYpNn1cM1EuRUFveZ7-uw87BFySXS_Frq9-Ozp0wFwzgjeOK1G3Yo1Fh6xEaDUnFFuJPqMTWcXAEvTrOW7vwJwkZq12mF4tVI0L3ErOI-LzpQ-XVCSEJXC4VjBkiSR5JDU_VtumU1v6pkAe6pGM57H4mPQrGw-4-TVzgGsgxf7hu_Tt9dLIhPW-TcwB4R6ZUmJQHiZ5pSrKtQG-vyag15V_AOEQJHyfQKpaNL3AnN65TZw7pZwOnx7kjIcCamwZFdIodZO0ltlBzARUaYpi-2Behdk7PpvH8UkOecEs9m9NlEjZ7cejJzZy10ymgxJnrp64Y='

ENC_API_ID = b'gAAAAABqcinp5y377NK8ct-rOloxUyl_ZvHsworgDh-D4qZorDcoRwHe48_L9zVy8jwXTKFmw47o9uy_ejZDKH15PyRS-FBs6Q=='

ENC_API_HASH = b'gAAAAABqcinptbEUy6dF8_N2jmKxdSYoHJ7NQ1BuDJlHT3WRidEUrYxRKTl8fAB624dbnifGAtJSLkcVCycLtL0cQr8NBWuxGu09P1O15-Kd_6xGO8d7yjdbRRwe0L_potYhmQesrWW2'

# ===================== فك التشفير =====================
def decrypt_data(encrypted: bytes) -> str:
    cipher = Fernet(KEY)
    return cipher.decrypt(encrypted).decode()

SESSION_STRING = decrypt_data(ENC_SESSION)
API_ID = int(decrypt_data(ENC_API_ID))
API_HASH = decrypt_data(ENC_API_HASH)

# ===================== باقي الكود كما هو =====================
TARGET_BOT_USERNAME = "ATF_AIRDROP_bot"
WEB_APP_URL = "https://atfminers.asloni.online/miner/index.html"
BASE_URL = "https://atfminers.asloni.online"

LOGIN_ENDPOINT = f"{BASE_URL}/miner/index.php?action=login"
START_MINE_ENDPOINT = f"{BASE_URL}/miner/index.php?action=start_mine"
ACTIVATE_BOOST_ENDPOINT = f"{BASE_URL}/miner/index.php?action=activate_boost"
START_TASK_ENDPOINT = f"{BASE_URL}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT = f"{BASE_URL}/miner/index.php?action=claim_task"

CYCLE_INTERVAL = 7500
RETRY_CLAIM_DELAY = 30
MAX_CLAIM_RETRY_TIME = 600

TASKS = [
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube Like & Comment"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "X (Twitter) Retweet"},
    {"id": "website_visit", "min_seconds": 0, "name": "Visit Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React to latest post"}
]

# ===================== دوال مساعدة =====================

async def get_init_data(client, bot):
    try:
        web_view = await client(RequestWebViewRequest(
            peer=bot, bot=bot, platform="android", from_bot_menu=True, url=WEB_APP_URL
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
        print(f"⚠️ خطأ في استخراج initData: {e}")
        return None

async def login(session, init_data, tg_id, username):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/miner/index.html",
        "X-Requested-With": "XMLHttpRequest",
        "X-Telegram-Init-Data": init_data,
    }
    payload = {
        "initData": init_data,
        "tg_id": tg_id,
        "username": username or "",
        "request_id": f"rq-{int(time.time()*1000)}-{tg_id}",
        "device_id": f"dev-{tg_id}-{int(time.time())}"
    }
    async with session.post(LOGIN_ENDPOINT, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("tma_session_token"), data.get("react_post"), headers
    return None, None, None

async def do_boost(session, headers, payload):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                print("⚡ Boost activated!")
            else:
                msg = data.get("message", "Unknown")
                if "already" in msg.lower() or "wait" in msg.lower():
                    print(f"ℹ️ Boost: {msg}")
                else:
                    print(f"⚠️ Boost failed: {msg}")
            return data
    except Exception as e:
        print(f"💥 Boost error: {e}")
        return None

async def attempt_claim(session, headers, claim_payload, task_name):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                reward = data.get("reward", 0)
                print(f"✅ {task_name} تمت المطالبة بنجاح! +{reward} ATF")
                return True, data
            else:
                return False, data
    except Exception as e:
        print(f"❌ خطأ في claim_task لـ {task_name}: {e}")
        return False, {"status": "error", "message": str(e)}

async def do_task(session, headers, task, tg_id, init_data, react_post_link=None):
    task_id = task["id"]
    min_sec = task["min_seconds"]
    task_name = task["name"]

    if task_id == "telegram_react_latest" and not react_post_link:
        print(f"⚠️ {task_name}: لا يوجد رابط للتحديث الأخير، تخطي")
        return

    print(f"🔄 بدء المهمة: {task_name}")
    now = int(time.time())

    start_payload = {
        "tg_id": tg_id,
        "task_id": task_id,
        "client_started_at": now,
        "initData": init_data,
        "device_id": f"dev-{tg_id}-{now}",
        "request_id": f"rq-{now}-{tg_id}"
    }
    try:
        async with session.post(START_TASK_ENDPOINT, json=start_payload, headers=headers) as resp:
            start_data = await resp.json()
            if start_data.get("status") != "success":
                print(f"❌ فشل start_task لـ {task_name}: {start_data.get('message')}")
                return
            server_started_at = start_data.get("started_at")
            started_at = int(server_started_at) if server_started_at else now
            print(f"✅ start_task لـ {task_name} تم، started_at={started_at}")
    except Exception as e:
        print(f"❌ خطأ في start_task لـ {task_name}: {e}")
        return

    wait_time = min_sec + 3
    if wait_time > 0:
        print(f"⏳ انتظار {wait_time} ثانية قبل المطالبة لـ {task_name}...")
        await asyncio.sleep(wait_time)

    claim_payload = {
        "tg_id": tg_id,
        "task_id": task_id,
        "client_started_at": started_at,
        "initData": init_data,
        "device_id": f"dev-{tg_id}-{started_at}",
        "request_id": f"rq-{started_at}-{tg_id}"
    }

    success, claim_data = await attempt_claim(session, headers, claim_payload, task_name)
    if success:
        return

    msg = claim_data.get("message", "").lower()
    keywords = ["wait", "try again", "not ready", "please wait", "seconds", "cooldown", "retry"]
    if not any(k in msg for k in keywords):
        print(f"❌ فشل claim_task لـ {task_name}: {claim_data.get('message')} (لن يتم إعادة المحاولة)")
        return

    print(f"⏳ {task_name}: سيتم إعادة محاولة claim كل {RETRY_CLAIM_DELAY} ثانية لمدة تصل إلى 10 دقائق...")
    start_time = time.time()
    attempt = 1
    while True:
        if time.time() - start_time > MAX_CLAIM_RETRY_TIME:
            print(f"❌ {task_name}: انتهى وقت إعادة المحاولة (10 دقائق) دون نجاح.")
            break
        await asyncio.sleep(RETRY_CLAIM_DELAY)
        attempt += 1
        print(f"🔄 محاولة claim رقم {attempt} لـ {task_name}...")
        success, claim_data = await attempt_claim(session, headers, claim_payload, task_name)
        if success:
            return
        new_msg = claim_data.get("message", "").lower()
        if not any(k in new_msg for k in keywords):
            print(f"❌ {task_name}: فشل نهائي: {claim_data.get('message')}")
            return

# ===================== المهام المتوازية =====================

async def boost_worker(client, bot, me):
    async with aiohttp.ClientSession() as session:
        while True:
            delay = round(random.uniform(9, 12), 2)
            try:
                init_data = await get_init_data(client, bot)
                if not init_data:
                    await asyncio.sleep(delay)
                    continue

                token, _, _ = await login(session, init_data, me.id, me.username)
                if not token:
                    await asyncio.sleep(delay)
                    continue

                headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/miner/index.html",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Telegram-Init-Data": init_data,
                    "X-ATF-TMA-Session": token,
                }
                payload = {
                    "initData": init_data,
                    "tg_id": me.id,
                    "username": me.username or "",
                    "request_id": f"rq-{int(time.time()*1000)}-{me.id}",
                    "device_id": f"dev-{me.id}-{int(time.time())}",
                    "display_preview": "0.0000"
                }

                async with session.post(START_MINE_ENDPOINT, json=payload, headers=headers) as resp:
                    pass

                await do_boost(session, headers, payload)

            except Exception as e:
                print(f"💥 خطأ في حلقة التسريع: {e}")

            print(f"⏳ انتظار عشوائي: {delay} ثانية...")
            await asyncio.sleep(delay)

async def tasks_worker(client, bot, me):
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(CYCLE_INTERVAL)

            print("\n" + "="*50)
            print("📝 بدء تنفيذ المهام الأربع...")
            print("="*50)

            try:
                init_data = await get_init_data(client, bot)
                if not init_data:
                    print("❌ تعذر استخراج initData للمهام")
                    continue

                token, react_post, _ = await login(session, init_data, me.id, me.username)
                if not token:
                    print("❌ فشل تسجيل الدخول للمهام")
                    continue

                headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": BASE_URL,
                    "Referer": f"{BASE_URL}/miner/index.html",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Telegram-Init-Data": init_data,
                    "X-ATF-TMA-Session": token,
                }

                react_post_link = react_post.get("link") if react_post else None

                for task in TASKS:
                    await do_task(session, headers, task, me.id, init_data, react_post_link)

                print("✅ تم الانتهاء من جميع المهام.")

            except Exception as e:
                print(f"💥 خطأ في حلقة المهام: {e}")

# ===================== التشغيل الرئيسي =====================

async def main():
    print("🔄 جاري الاتصال بحساب التلغرام...")
    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"✅ تم تسجيل الدخول: {me.first_name} (@{me.username or me.id})")
        bot = await client.get_input_entity(TARGET_BOT_USERNAME)

        await asyncio.gather(
            boost_worker(client, bot, me),
            tasks_worker(client, bot, me)
        )

if __name__ == "__main__":
    asyncio.run(main())