import asyncio
import urllib.parse
import aiohttp
import json
import time 
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from cryptography.fernet import Fernet

# ===================== البيانات المشفرة =====================
KEY = b'oiL4Z8RZJ-znrlkJg0fKD0xuDqWQNxfK4pbPyJWONVw='

SESSION_STRING = "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU="

ENC_API_ID = b'gAAAAABqcinp5y377NK8ct-rOloxUyl_ZvHsworgDh-D4qZorDcoRwHe48_L9zVy8jwXTKFmw47o9uy_ejZDKH15PyRS-FBs6Q=='

ENC_API_HASH = b'gAAAAABqcinptbEUy6dF8_N2jmKxdSYoHJ7NQ1BuDJlHT3WRidEUrYxRKTl8fAB624dbnifGAtJSLkcVCycLtL0cQr8NBWuxGu09P1O15-Kd_6xGO8d7yjdbRRwe0L_potYhmQesrWW2'

# ===================== فك التشفير =====================
def decrypt_data(encrypted: bytes) -> str:
    cipher = Fernet(KEY)
    return cipher.decrypt(encrypted).decode()

API_ID = int(decrypt_data(ENC_API_ID))
API_HASH = decrypt_data(ENC_API_HASH)

# ===================== إعدادات البوت والمهام =====================
TARGET_BOT_USERNAME = "ATF_AIRDROP_bot"
WEB_APP_URL = "https://atfminers.asloni.online/miner/index.html"
BASE_URL = "https://atfminers.asloni.online"

LOGIN_ENDPOINT = f"{BASE_URL}/miner/index.php?action=login"
START_TASK_ENDPOINT = f"{BASE_URL}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT = f"{BASE_URL}/miner/index.php?action=claim_task"

CYCLE_INTERVAL = 7500  # ساعتان و 5 دقائق (7500 ثانية)
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

# ===================== التشغيل الرئيسي =====================

async def main():
    print("🔄 جاري الاتصال بحساب التلغرام...")
    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        me = await client.get_me()
        print(f"✅ تم تسجيل الدخول: {me.first_name} (@{me.username or me.id})")
        bot = await client.get_input_entity(TARGET_BOT_USERNAME)

        async with aiohttp.ClientSession() as session:
            while True:
                print("\n" + "="*50)
                print("📝 بدء تنفيذ المهام...")
                print("="*50)

                try:
                    init_data = await get_init_data(client, bot)
                    if not init_data:
                        print("❌ تعذر استخراج initData للمهام")
                    else:
                        token, react_post, _ = await login(session, init_data, me.id, me.username)
                        if not token:
                            print("❌ فشل تسجيل الدخول للمهام")
                        else:
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

                            react_post_link = react_post.get("link") if isinstance(react_post, dict) else None

                            for task in TASKS:
                                await do_task(session, headers, task, me.id, init_data, react_post_link)

                            print("✅ تم الانتهاء من جميع المهام بنجاح.")

                except Exception as e:
                    print(f"💥 حدث خطأ في تنفيذ المهام: {e}")

                print(f"\n⏳ المهام في وضع الانتظار لمدة {CYCLE_INTERVAL} ثانية (ساعتان و5 دقائق)...\n")
                await asyncio.sleep(CYCLE_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
