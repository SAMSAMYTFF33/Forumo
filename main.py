import asyncio
import urllib.parse
import aiohttp
import json
import time 
import random
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from cryptography.fernet import Fernet

# ================================================================
#                    القسم الأول: بيانات الكود الأول (ATF)
# ================================================================

# ==== بيانات ATF المشفرة ====
KEY_ATF = b'oiL4Z8RZJ-znrlkJg0fKD0xuDqWQNxfK4pbPyJWONVw='

SESSION_STRING_ATF = "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU="

ENC_SESSION_ATF = b'...' 
ENC_API_ID_ATF = b'gAAAAABqcinp5y377NK8ct-rOloxUyl_ZvHsworgDh-D4qZorDcoRwHe48_L9zVy8jwXTKFmw47o9uy_ejZDKH15PyRS-FBs6Q=='
ENC_API_HASH_ATF = b'gAAAAABqcinptbEUy6dF8_N2jmKxdSYoHJ7NQ1BuDJlHT3WRidEUrYxRKTl8fAB624dbnifGAtJSLkcVCycLtL0cQr8NBWuxGu09P1O15-Kd_6xGO8d7yjdbRRwe0L_potYhmQesrWW2'

# ==== دوال فك تشفير ATF ====
def decrypt_data_atf(encrypted: bytes) -> str:
    cipher = Fernet(KEY_ATF)
    return cipher.decrypt(encrypted).decode()

API_ID_ATF = int(decrypt_data_atf(ENC_API_ID_ATF))
API_HASH_ATF = decrypt_data_atf(ENC_API_HASH_ATF)

# ==== إعدادات ATF ====
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

# ================================================================
#                    القسم الثاني: بيانات الكود الثاني (Monsterland)
# ================================================================

API_ID_MONSTER = 31514497
API_HASH_MONSTER = "98d779341dd063307994de23cfd9796d"
SESSION_STRING_MONSTER = "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww="

TARGET_BOT_USERNAME_MONSTER = "monsterland_bot"
WEB_APP_URL_MONSTER = "https://lets.playmonsterland.com"

API_CREATE_AD_MONSTER = "https://lets.playmonsterland.com/api/ads/create-task"
API_TASK_RESULT_MONSTER = "https://lets.playmonsterland.com/api/ads/task-result"
API_COMPLETE_AD_MONSTER = "https://lets.playmonsterland.com/api/ads/complete"

MONSTER_ID = "6a734e0d9289c0b99d65707a"

ITEMS_LIST_MONSTER = [
    ("magic_apple", "Magic Apple"),
    ("wizard_coffee", "Wizard Coffee"),
    ("magic_towel", "Magic Towel"),
]

# ================================================================
#                    القسم الثالث: دوال ATF (الكود الأول)
# ================================================================

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
    async with session.post(LOGIN_ENDPOINT_ATF, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("tma_session_token"), data.get("react_post"), headers
    return None, None, None

async def do_boost_atf(session, headers, payload):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT_ATF, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                print("[ATF] ⚡ Boost activated successfully!")
            else:
                msg = data.get("message", "Unknown")
                if "already" in msg.lower() or "wait" in msg.lower():
                    print(f"[ATF] ℹ️ Boost: {msg}")
                else:
                    print(f"[ATF] ⚠️ Boost failed: {msg}")
            return data
    except Exception as e:
        print(f"[ATF] 💥 Boost error: {e}")
        return None

async def attempt_claim_atf(session, headers, claim_payload, task_name):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT_ATF, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                reward = data.get("reward", 0)
                print(f"[ATF] ✅ {task_name} تمت المطالبة بنجاح! +{reward} ATF")
                return True, data
            else:
                return False, data
    except Exception as e:
        print(f"[ATF] ❌ خطأ في claim_task لـ {task_name}: {e}")
        return False, {"status": "error", "message": str(e)}

async def do_task_atf(session, headers, task, tg_id, init_data, react_post_link=None):
    task_id = task["id"]
    min_sec = task["min_seconds"]
    task_name = task["name"]

    if task_id == "telegram_react_latest" and not react_post_link:
        print(f"[ATF] ⚠️ {task_name}: لا يوجد رابط للتحديث الأخير، تخطي")
        return

    print(f"[ATF] 🔄 بدء المهمة: {task_name}")
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
        async with session.post(START_TASK_ENDPOINT_ATF, json=start_payload, headers=headers) as resp:
            start_data = await resp.json()
            if start_data.get("status") != "success":
                print(f"[ATF] ❌ فشل start_task لـ {task_name}: {start_data.get('message')}")
                return
            server_started_at = start_data.get("started_at")
            started_at = int(server_started_at) if server_started_at else now
            print(f"[ATF] ✅ start_task لـ {task_name} تم، started_at={started_at}")
    except Exception as e:
        print(f"[ATF] ❌ خطأ في start_task لـ {task_name}: {e}")
        return

    wait_time = min_sec + 3
    if wait_time > 0:
        print(f"[ATF] ⏳ انتظار {wait_time} ثانية قبل المطالبة لـ {task_name}...")
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
        print(f"[ATF] ❌ فشل claim_task لـ {task_name}: {claim_data.get('message')}")
        return

    print(f"[ATF] ⏳ {task_name}: سيتم إعادة محاولة claim كل {RETRY_CLAIM_DELAY_ATF} ثانية...")
    start_time = time.time()
    while True:
        if time.time() - start_time > MAX_CLAIM_RETRY_TIME_ATF:
            print(f"[ATF] ❌ {task_name}: انتهى وقت إعادة المحاولة.")
            break
        await asyncio.sleep(RETRY_CLAIM_DELAY_ATF)
        success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name)
        if success:
            return

async def boost_worker_atf(session, headers, me, init_data, lock):
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

                async with session.post(START_MINE_ENDPOINT_ATF, json=payload, headers=headers) as resp:
                    pass

                await do_boost_atf(session, headers, payload)

        except Exception as e:
            print(f"[ATF] 💥 خطأ في حلقة التسريع: {e}")

        await asyncio.sleep(delay)

async def tasks_worker_atf(session, headers, me, init_data, react_post, lock):
    while True:
        async with lock:
            print("\n" + "="*50)
            print("[ATF] 📝 بدء تنفيذ المهام الدورية...")
            print("="*50)

            try:
                react_post_link = react_post.get("link") if isinstance(react_post, dict) else None

                for task in TASKS_ATF:
                    await do_task_atf(session, headers, task, me.id, init_data, react_post_link)

                print("[ATF] ✅ تم الانتهاء من جميع المهام بنجاح.")

            except Exception as e:
                print(f"[ATF] 💥 خطأ في حلقة المهام: {e}")

        print(f"\n[ATF] ⏳ المهام في وضع الانتظار لمدة {CYCLE_INTERVAL_ATF} ثانية...\n")
        await asyncio.sleep(CYCLE_INTERVAL_ATF)

# ================================================================
#                    القسم الرابع: دوال Monsterland (الكود الثاني)
# ================================================================

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
                peer=bot,
                bot=bot,
                platform="android",
                from_bot_menu=False,
                url=WEB_APP_URL_MONSTER,
            )
        )
        raw_url = web_view.url
        if "tgWebAppData=" not in raw_url:
            print(f"[Monster] ❌ تعذر استخراج initData من: {raw_url}")
            return None

        init_data = raw_url.split("tgWebAppData=")[1].split(
            "&tgWebAppVersion"
        )[0]
        decoded = urllib.parse.unquote(init_data)
        token = f"tma {decoded}"

        with open("latest_token_monster.txt", "w", encoding="utf-8") as f:
            f.write(token)
        print("[Monster] 🔑 تم توليد توكن جديد وحفظه.")
        return token
    except Exception as e:
        print(f"[Monster] ⚠️ فشل توليد توكن جديد: {e}")
        return None

async def execute_instant_ad_monster(token: str, item_id: str, label: str):
    headers = build_headers_monster(token)
    payload = {
        "action": "vitals",
        "metadata": {"monsterId": MONSTER_ID, "itemId": item_id},
    }
    try:
        res_create = requests.post(
            API_CREATE_AD_MONSTER, headers=headers, json=payload, timeout=15
        )
        if res_create.status_code == 401:
            return 401

        if res_create.status_code != 200:
            print(
                f"[Monster] ❌ فشل إنشاء ({label}): {res_create.status_code} - {res_create.text}"
            )
            return res_create.status_code

        tx_id = res_create.json().get("adTxId")
        if not tx_id:
            print(f"[Monster] ⚠️ لم يتم العثور على adTxId لـ ({label}).")
            return None

        print(f"[Monster] ⚡ تم إنشاء ({label}) -> ID: {tx_id}")

        await asyncio.sleep(2)

        requests.get(
            f"{API_TASK_RESULT_MONSTER}?txId={tx_id}", headers=headers, timeout=15
        )

        payload_complete = {"adTxId": tx_id, "provider": "gigapub"}
        res_complete = requests.post(
            API_COMPLETE_AD_MONSTER, headers=headers, json=payload_complete, timeout=15
        )
        print(f"[Monster] 🚀 تأكيد إكمال ({label}): Status {res_complete.status_code}")
        print(f"[Monster] Response: {res_complete.text}")
        return res_complete.status_code

    except Exception as e:
        print(f"[Monster] ⚠️ خطأ شبكة أثناء تنفيذ ({label}): {e}")
        return None

async def run_instant_ads_monster(client: TelegramClient, current_token):
    print(
        f"\n===== [Monster] [{time.strftime('%Y-%m-%d %H:%M:%S')}] بدء دورة تنفيذ الإعلانات الثلاثة ====="
    )

    for idx, (item_id, label) in enumerate(ITEMS_LIST_MONSTER):
        try:
            status = await execute_instant_ad_monster(current_token, item_id, label)

            if status == 401:
                print("[Monster] 🔄 التوكن منتهي — جاري تجديد التوكن وإعادة المحاولة...")
                current_token = await fetch_fresh_token_monster(client)
                if current_token:
                    await execute_instant_ad_monster(current_token, item_id, label)

            if idx < len(ITEMS_LIST_MONSTER) - 1:
                delay = random.randint(8, 35)
                print(f"[Monster] ⏳ انتظار عشوائي {delay} ثانية قبل الإعلان التالي...")
                await asyncio.sleep(delay)

        except Exception as e:
            print(f"[Monster] ⚠️ خطأ غير متوقع أثناء معالجة {label}: {e}")

    return current_token

async def main_loop_monster(client: TelegramClient):
    print(f"[Monster] ✅ تسجيل دخول بنجاح: {await client.get_me().first_name}")

    current_token = await fetch_fresh_token_monster(client)
    cycle_count = 1

    while True:
        try:
            print(f"\n[Monster] 🔄 --- الدورة التكرارية #{cycle_count} ---")
            if current_token is None:
                current_token = await fetch_fresh_token_monster(client)

            current_token = await run_instant_ads_monster(client, current_token)

            cycle_delay = random.randint(10, 45)
            print(
                f"\n[Monster] ⏳ اكتملت الدورة #{cycle_count}. انتظار عشوائي {cycle_delay} ثانية قبل بدء الدورة التالية..."
            )
            cycle_count += 1
            await asyncio.sleep(cycle_delay)

        except Exception as loop_err:
            print(f"[Monster] ⚠️ خطأ داخل حلقة التشغيل الرئيسية: {loop_err}")
            await asyncio.sleep(10)

# ================================================================
#                    القسم الخامس: التشغيل المتزامن
# ================================================================

async def run_atf_bot():
    """تشغيل بوت ATF"""
    print("[ATF] 🚀 جاري تشغيل بوت ATF...")
    try:
        async with TelegramClient(StringSession(SESSION_STRING_ATF), API_ID_ATF, API_HASH_ATF) as client:
            me = await client.get_me()
            print(f"[ATF] ✅ تم تسجيل الدخول: {me.first_name} (@{me.username or me.id})")
            bot = await client.get_input_entity(TARGET_BOT_USERNAME_ATF)

            async with aiohttp.ClientSession() as session:
                print("[ATF] 🔄 جاري استخراج initData وتسجيل الدخول الأولي...")
                init_data = await get_init_data_atf(client, bot)
                if not init_data:
                    print("[ATF] ❌ فشل استخراج initData، تأكد من صحة بيانات البوت والرابط.")
                    return

                token, react_post, _ = await login_atf(session, init_data, me.id, me.username)
                if not token:
                    print("[ATF] ❌ فشل تسجيل الدخول (Login) في اللعبة.")
                    return
                
                print("[ATF] ✅ تم المصادقة بنجاح وجاهز للبدء المستمر!")

                headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Origin": BASE_URL_ATF,
                    "Referer": f"{BASE_URL_ATF}/miner/index.html",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-Telegram-Init-Data": init_data,
                    "X-ATF-TMA-Session": token,
                }

                work_lock = asyncio.Lock()

                await asyncio.gather(
                    tasks_worker_atf(session, headers, me, init_data, react_post, work_lock),
                    boost_worker_atf(session, headers, me, init_data, work_lock)
                )
    except Exception as e:
        print(f"[ATF] 💥 خطأ فادح: {e}")

async def run_monster_bot():
    """تشغيل بوت Monsterland"""
    print("[Monster] 🚀 جاري تشغيل بوت Monsterland...")
    try:
        async with TelegramClient(StringSession(SESSION_STRING_MONSTER), API_ID_MONSTER, API_HASH_MONSTER) as client:
            me = await client.get_me()
            print(f"[Monster] ✅ تسجيل دخول بنجاح: {me.first_name} (@{me.username or me.id})")
            await main_loop_monster(client)
    except Exception as e:
        print(f"[Monster] 💥 خطأ فادح: {e}")

async def main():
    """تشغيل البوتين معاً"""
    print("="*60)
    print("🚀 تشغيل البوتين معاً في نفس الوقت...")
    print("="*60)
    
    # تشغيل المهمتين بشكل متوازي
    await asyncio.gather(
        run_atf_bot(),
        run_monster_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف جميع البوتات يدويًا.")
    except Exception as e:
        print(f"⚠️ خطأ عام: {e}")