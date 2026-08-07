import asyncio
import urllib.parse
import aiohttp
import json
import time 
import random
from cryptography.fernet import Fernet
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

# ===================== إعدادات الجلسات (Sessions منفصلة تماماً) =====================
# 1. جلسة خاصة بـ ATF
SESSION_STRING_ATF = "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU="

# 2. جلسة خاصة بـ Monsterland (ضع سيشن حسابك هنا)
SESSION_STRING_MONSTER = "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww="

# ===================== البيانات المشفرة (ATF) =====================
KEY = b'oiL4Z8RZJ-znrlkJg0fKD0xuDqWQNxfK4pbPyJWONVw='
ENC_API_ID = b'gAAAAABqcinp5y377NK8ct-rOloxUyl_ZvHsworgDh-D4qZorDcoRwHe48_L9zVy8jwXTKFmw47o9uy_ejZDKH15PyRS-FBs6Q=='
ENC_API_HASH = b'gAAAAABqcinptbEUy6dF8_N2jmKxdSYoHJ7NQ1BuDJlHT3WRidEUrYxRKTl8fAB624dbnifGAtJSLkcVCycLtL0cQr8NBWuxGu09P1O15-Kd_6xGO8d7yjdbRRwe0L_potYhmQesrWW2'

def decrypt_data(encrypted: bytes) -> str:
    cipher = Fernet(KEY)
    return cipher.decrypt(encrypted).decode()

API_ID = int(decrypt_data(ENC_API_ID))
API_HASH = decrypt_data(ENC_API_HASH)


# ===================== إعدادات ATF =====================
TARGET_BOT_USERNAME_ATF = "ATF_AIRDROP_bot"
WEB_APP_URL_ATF = "https://atfminers.asloni.online/miner/index.html"
BASE_URL_ATF = "https://atfminers.asloni.online"

LOGIN_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=login"
START_MINE_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=start_mine"
ACTIVATE_BOOST_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=activate_boost"
START_TASK_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=claim_task"

CYCLE_INTERVAL_ATF = 7500  # ساعتان و 5 دقائق
RETRY_CLAIM_DELAY_ATF = 30
MAX_CLAIM_RETRY_TIME_ATF = 600

TASKS_ATF = [
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube Like & Comment"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "X (Twitter) Retweet"},
    {"id": "website_visit", "min_seconds": 0, "name": "Visit Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React to latest post"}
]


# ===================== إعدادات Monsterland =====================
TARGET_BOT_USERNAME_MONSTER = "monsterland_bot"
WEB_APP_URL_MONSTER = "https://lets.playmonsterland.com"

API_CREATE_AD = "https://lets.playmonsterland.com/api/ads/create-task"
API_TASK_RESULT = "https://lets.playmonsterland.com/api/ads/task-result"
API_COMPLETE_AD = "https://lets.playmonsterland.com/api/ads/complete"

MONSTER_ID = "6a734e0d9289c0b99d65707a"

ITEMS_LIST_MONSTER = [
    ("magic_apple", "Magic Apple"),
    ("wizard_coffee", "Wizard Coffee"),
    ("magic_towel", "Magic Towel"),
]


# ====================================================================
#                          دوال ATF الأساسية
# ====================================================================

async def get_init_data_atf(client, bot):
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
        print(f"⚠️ [ATF] خطأ في استخراج initData: {e}")
        return None

async def login_atf(session, init_data, tg_id, username):
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL_ATF,
        "Referer": f"{BASE_URL_ATF}/miner/index.html",
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

async def do_boost_atf(session, headers, payload):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                print("⚡ [ATF] Boost activated successfully!")
            else:
                msg = data.get("message", "Unknown")
                if "already" in msg.lower() or "wait" in msg.lower():
                    print(f"ℹ️ [ATF] Boost: {msg}")
                else:
                    print(f"⚠️ [ATF] Boost failed: {msg}")
            return data
    except Exception as e:
        print(f"💥 [ATF] Boost error: {e}")
        return None

async def attempt_claim_atf(session, headers, claim_payload, task_name):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                reward = data.get("reward", 0)
                print(f"✅ [ATF] {task_name} تمت المطالبة بنجاح! +{reward} ATF")
                return True, data
            else:
                return False, data
    except Exception as e:
        print(f"❌ [ATF] خطأ في claim_task لـ {task_name}: {e}")
        return False, {"status": "error", "message": str(e)}

async def do_task_atf(session, headers, task, tg_id, init_data, react_post_link=None):
    task_id = task["id"]
    min_sec = task["min_seconds"]
    task_name = task["name"]

    if task_id == "telegram_react_latest" and not react_post_link:
        print(f"⚠️ [ATF] {task_name}: لا يوجد رابط للتحديث الأخير، تخطي")
        return

    print(f"🔄 [ATF] بدء المهمة: {task_name}")
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
                print(f"❌ [ATF] فشل start_task لـ {task_name}: {start_data.get('message')}")
                return
            server_started_at = start_data.get("started_at")
            started_at = int(server_started_at) if server_started_at else now
            print(f"✅ [ATF] start_task لـ {task_name} تم، started_at={started_at}")
    except Exception as e:
        print(f"❌ [ATF] خطأ في start_task لـ {task_name}: {e}")
        return

    wait_time = min_sec + 3
    if wait_time > 0:
        print(f"⏳ [ATF] انتظار {wait_time} ثانية قبل المطالبة لـ {task_name}...")
        await asyncio.sleep(wait_time)

    claim_payload = {
        "tg_id": tg_id,
        "task_id": task_id,
        "client_started_at": started_at,
        "initData": init_data,
        "device_id": f"dev-{tg_id}-{started_at}",
        "request_id": f"rq-{started_at}-{tg_id}"
    }

    success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name)
    if success:
        return

    msg = claim_data.get("message", "").lower()
    keywords = ["wait", "try again", "not ready", "please wait", "seconds", "cooldown", "retry"]
    if not any(k in msg for k in keywords):
        print(f"❌ [ATF] فشل claim_task لـ {task_name}: {claim_data.get('message')}")
        return

    print(f"⏳ [ATF] {task_name}: سيتم إعادة محاولة claim كل {RETRY_CLAIM_DELAY_ATF} ثانية...")
    start_time = time.time()
    while True:
        if time.time() - start_time > MAX_CLAIM_RETRY_TIME_ATF:
            print(f"❌ [ATF] {task_name}: انتهى وقت إعادة المحاولة.")
            break
        await asyncio.sleep(RETRY_CLAIM_DELAY_ATF)
        success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name)
        if success:
            return


# ====================================================================
#                          دوال Monsterland الأساسية
# ====================================================================

def build_headers_monster(token: str) -> dict:
    return {
        "authority": "lets.playmonsterland.com",
        "accept": "*/*",
        "accept-encoding": "identity",
        "accept-language": "ar,en-US;q=0.9,en;q=0.8,ru;q=0.7,fr;q=0.6",
        "authorization": token,
        "content-type": "application/json",
        "origin": "https://lets.playmonsterland.com",
        "referer": "https://lets.playmonsterland.com/",
        "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
    }

async def fetch_fresh_token_monster(client: TelegramClient) -> str:
    try:
        bot = await client.get_input_entity(TARGET_BOT_USERNAME_MONSTER)
        web_view = await client(
            RequestWebViewRequest(
                peer=bot, bot=bot, platform="android", from_bot_menu=False, url=WEB_APP_URL_MONSTER
            )
        )
        raw_url = web_view.url
        if "tgWebAppData=" not in raw_url:
            print(f"❌ [Monster] تعذر استخراج initData من: {raw_url}")
            return None

        init_data = raw_url.split("tgWebAppData=")[1].split("&tgWebAppVersion")[0]
        decoded = urllib.parse.unquote(init_data)
        token = f"tma {decoded}"
        print("🔑 [Monster] تم توليد توكن جديد.")
        return token
    except Exception as e:
        print(f"⚠️ [Monster] فشل توليد توكن جديد: {e}")
        return None

async def execute_instant_ad_monster(session: aiohttp.ClientSession, token: str, item_id: str, label: str):
    headers = build_headers_monster(token)
    payload = {
        "action": "vitals",
        "metadata": {"monsterId": MONSTER_ID, "itemId": item_id},
    }
    try:
        async with session.post(API_CREATE_AD, headers=headers, json=payload, timeout=15) as res_create:
            if res_create.status == 401:
                return 401
            
            text_create = await res_create.text()
            if res_create.status != 200:
                print(f"❌ [Monster] فشل إنشاء ({label}): {res_create.status} - {text_create}")
                return res_create.status
                
            data_create = json.loads(text_create)
            tx_id = data_create.get("adTxId")

        if not tx_id:
            print(f"⚠️ [Monster] لم يتم العثور على adTxId لـ ({label}).")
            return None

        print(f"⚡ [Monster] تم إنشاء ({label}) -> ID: {tx_id}")

        await asyncio.sleep(8)

        async with session.get(f"{API_TASK_RESULT}?txId={tx_id}", headers=headers, timeout=15) as res_check:
            pass 

        payload_complete = {"adTxId": tx_id, "provider": "gigapub"}
        async with session.post(API_COMPLETE_AD, headers=headers, json=payload_complete, timeout=15) as res_complete:
            text_complete = await res_complete.text()
            print(f"🚀 [Monster] تأكيد إكمال ({label}): Status {res_complete.status}")
            print(f"[Monster] Response: {text_complete}")
            return res_complete.status

    except Exception as e:
        print(f"⚠️ [Monster] خطأ شبكة أثناء تنفيذ ({label}): {e}")
        return None


# ====================================================================
#                          مهام الخلفية Workers
# ====================================================================

async def atf_boost_worker(session, headers, me, init_data, lock):
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
                    "device_id": f"dev-{me.id}-{int(time.time())}",
                    "display_preview": "0.0000"
                }
                async with session.post(START_MINE_ENDPOINT, json=payload, headers=headers) as resp:
                    pass
                await do_boost_atf(session, headers, payload)
        except Exception as e:
            print(f"💥 [ATF] خطأ في حلقة التسريع: {e}")
        await asyncio.sleep(delay)


async def atf_tasks_worker(session, headers, me, init_data, react_post, lock):
    while True:
        async with lock:
            print("\n" + "="*50)
            print("📝 [ATF] بدء تنفيذ المهام الدورية...")
            print("="*50)
            try:
                react_post_link = react_post.get("link") if isinstance(react_post, dict) else None
                for task in TASKS_ATF:
                    await do_task_atf(session, headers, task, me.id, init_data, react_post_link)
                print("✅ [ATF] تم الانتهاء من جميع المهام بنجاح.")
            except Exception as e:
                print(f"💥 [ATF] خطأ في حلقة المهام: {e}")
        
        print(f"\n⏳ [ATF] المهام في وضع الانتظار لمدة {CYCLE_INTERVAL_ATF} ثانية...\n")
        await asyncio.sleep(CYCLE_INTERVAL_ATF)


async def monsterland_worker(client: TelegramClient, session: aiohttp.ClientSession):
    current_token = await fetch_fresh_token_monster(client)
    cycle_count = 1
    
    while True:
        try:
            print(f"\n🔄 [Monster] --- الدورة التكرارية رقم #{cycle_count} ---")
            if current_token is None:
                current_token = await fetch_fresh_token_monster(client)

            for idx, (item_id, label) in enumerate(ITEMS_LIST_MONSTER):
                status = await execute_instant_ad_monster(session, current_token, item_id, label)

                if status == 401:
                    print("🔄 [Monster] التوكن منتهي — جاري تجديد التوكن وإعادة المحاولة...")
                    current_token = await fetch_fresh_token_monster(client)
                    if current_token:
                        await execute_instant_ad_monster(session, current_token, item_id, label)

                if idx < len(ITEMS_LIST_MONSTER) - 1:
                    delay = random.randint(30, 60)
                    print(f"⏳ [Monster] انتظار عشوائي {delay} ثانية قبل الإعلان التالي...")
                    await asyncio.sleep(delay)

            cycle_delay = random.randint(400, 600)
            print(f"\n⏳ [Monster] اكتملت الدورة #{cycle_count}. انتظار عشوائي {cycle_delay} ثانية قبل الدورة التالية...")
            cycle_count += 1
            await asyncio.sleep(cycle_delay)

        except Exception as loop_err:
            print(f"⚠️ [Monster] خطأ داخل حلقة التشغيل الرئيسية: {loop_err}")
            await asyncio.sleep(10)


# ====================================================================
#                          التشغيل الرئيسي المتزامن لكلتا الجلستين
# ====================================================================

async def run_atf_bot(http_session):
    print("🔄 [ATF] جاري الاتصال بجلسة تيليجرام الخاصة بـ ATF...")
    async with TelegramClient(StringSession(SESSION_STRING_ATF), API_ID, API_HASH) as client_atf:
        me_atf = await client_atf.get_me()
        print(f"✅ [ATF] تم تسجيل الدخول بالحساب: {me_atf.first_name} (@{me_atf.username or me_atf.id})")
        
        bot_atf = await client_atf.get_input_entity(TARGET_BOT_USERNAME_ATF)
        init_data_atf = await get_init_data_atf(client_atf, bot_atf)
        
        if not init_data_atf:
            print("❌ [ATF] فشل استخراج initData.")
            return

        token_atf, react_post_atf, _ = await login_atf(http_session, init_data_atf, me_atf.id, me_atf.username)
        if not token_atf:
            print("❌ [ATF] فشل تسجيل الدخول في اللعبة.")
            return
        
        print("✅ [ATF] تم المصادقة بنجاح وجاهز للعمل المستمر!")
        headers_atf = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE_URL_ATF,
            "Referer": f"{BASE_URL_ATF}/miner/index.html",
            "X-Requested-With": "XMLHttpRequest",
            "X-Telegram-Init-Data": init_data_atf,
            "X-ATF-TMA-Session": token_atf,
        }
        atf_lock = asyncio.Lock()

        # تشغيل مهام وتسريع ATF معاً
        await asyncio.gather(
            atf_tasks_worker(http_session, headers_atf, me_atf, init_data_atf, react_post_atf, atf_lock),
            atf_boost_worker(http_session, headers_atf, me_atf, init_data_atf, atf_lock)
        )


async def run_monster_bot(http_session):
    print("🔄 [Monster] جاري الاتصال بجلسة تيليجرام الخاصة بـ Monsterland...")
    async with TelegramClient(StringSession(SESSION_STRING_MONSTER), API_ID, API_HASH) as client_monster:
        me_monster = await client_monster.get_me()
        print(f"✅ [Monster] تم تسجيل الدخول بالحساب: {me_monster.first_name} (@{me_monster.username or me_monster.id})")
        
        # تشغيل حلقة إعلانات Monsterland
        await monsterland_worker(client_monster, http_session)


async def main():
    # فتح جلسة http موحدة وغير توقيفية للطلبات
    async with aiohttp.ClientSession() as http_session:
        print("\n🚀 بدء تشغيل البوتين معاً بجلستين مستقلتين تماماً...\n")
        
        # تشغيل البوتين بالتوازي التام دون أن يؤثر أحدهما على الآخر
        await asyncio.gather(
            run_atf_bot(http_session),
            run_monster_bot(http_session)
        )


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n⏹️ تم إيقاف السكربت يدوياً.")
            break
        except Exception as e:
            print(f"⚠️ خطأ عام، إعادة التشغيل الفوري بعد 10 ثوانٍ: {e}")
            time.sleep(10)
            