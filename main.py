import asyncio
import urllib.parse
import aiohttp
import json
import time 
import random
import sys
import subprocess
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest 

# ===================== إعدادات الحسابات والهواتف ===================== 
ACCOUNTS_CONFIG = [
    {
        "account_name": "الحساب الأول",
        "api_id": 31514497,
        "api_hash": "98d779341dd063307994de23cfd9796d",
        "session_string": "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww=",
        "device_prefix": "dev-A",
        # هاتف: Samsung Galaxy S23 Ultra (Android 14 - Chrome 124)
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
        "account_name": "الحساب الثاني",
        "api_id": 31568734,
        "api_hash": "7286e8c92ccc4dc698d771664bf71700",
        "session_string": "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU=",
        "device_prefix": "dev-B",
        # هاتف: Google Pixel 8 Pro (Android 14 - Chrome 125)
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
        "account_name": "الحساب الثالث",
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu6E163KHvlWxvFMB8CJa3BozQdoNy-SaM35r6cIDE4AEnw84J5EufYhMXmliVmRPg0vYpQbKBEKGhKgugLK6V-JZL09a7g-T77PHK9UA9ERCfpG4cxLK26IRI-nMw81WcH-q83TUT3XvTCOrqSJBd4WnIGo2MH8d52F_5jbj1tgvwcFvkCjIYkr0qhSx5oPbWz9gMvpIX0Rwp8vUd1yVX6pvy5-u3AIqqabkgn7JgC5-7I_B7uMTnY2vQb0_rnvkn2SoZQYXFt1yWZyWaUwJvCqlAKSYihCGc5l3yQCzMRsm4xhkC-SGsjxyncEePn5KO8_ZVM22zA_rfEqs1PqSz14=",
        "device_prefix": "dev-C",
        # هاتف: Xiaomi 13 Pro (Android 14 - Chrome 123)
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
        "account_name": "الحساب الرابع",
        "api_id": 39861404,
        "api_hash": "4cb96e0a355d9eabec3f5f2cd4b67a5c",
        "session_string": "1BJWap1wBuzfstmypFIqgw7jQtfpa7HRe-BufbZHXtBIocVy1Up-bx-axaUN18sqwIdOXNwVAlvZkZARoGBYi5vlPjuv0AizjyC7pn6Gc_x28WJkAWnMAkvzFgG1X1h27LvPGBicBavSRDjkKBT28oKLAQmK1OhTqO6Y0oCmpQnroeriqeJ2IcLxyzFe1TPQix8TKy3kZvWHTrqqwpIzAeL_4vf8_ts6JcMgivg5-wr413f_5b0eS8UaP3QOGLH1_TgJgSOnj9WDvHIfNpBXbA7pPa7zzPEaEkkqVcYa1KO2gpcYDqMCPd_c1uFDZ-G-4D4-nc1GOqfW1qAGpsftEyfqn_UPqJ6s=",
        "device_prefix": "dev-D",
        # هاتف: OnePlus 12 (Android 14 - Chrome 126)
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

# ===================== إعدادات ATF العامة =====================
TARGET_BOT_USERNAME_ATF = "ATF_AIRDROP_bot"
WEB_APP_URL_ATF = "https://atfminers.asloni.online/miner/index.html"
BASE_URL_ATF = "https://atfminers.asloni.online"

LOGIN_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=login"
START_MINE_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=start_mine"
ACTIVATE_BOOST_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=activate_boost"
START_TASK_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT = f"{BASE_URL_ATF}/miner/index.php?action=claim_task"

CYCLE_INTERVAL_ATF = 7500
RETRY_CLAIM_DELAY_ATF = 30
MAX_CLAIM_RETRY_TIME_ATF = 600

TASKS_ATF = [
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube Like & Comment"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "X (Twitter) Retweet"},
    {"id": "website_visit", "min_seconds": 0, "name": "Visit Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React to latest post"}
]

# ===================== دوال ATF الأساسية =====================

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
        print(f"⚠️ [{acc_name}] خطأ في استخراج initData: {e}")
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
    async with session.post(LOGIN_ENDPOINT, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("tma_session_token"), data.get("react_post"), headers
    return None, None, None

async def do_boost_atf(session, headers, payload, acc_name):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT, json=payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                print(f"⚡ [{acc_name}] تم تفعيل التسريع بنجاح (Boost)!")
            else:
                msg = data.get("message", "Unknown")
                if "already" in msg.lower() or "wait" in msg.lower():
                    print(f"ℹ️ [{acc_name}] Boost: {msg}")
                else:
                    print(f"⚠️ [{acc_name}] Boost failed: {msg}")
            return data
    except Exception as e:
        print(f"💥 [{acc_name}] Boost error: {e}")
        return None

async def attempt_claim_atf(session, headers, claim_payload, task_name, acc_name):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                reward = data.get("reward", 0)
                print(f"✅ [{acc_name}] {task_name} تمت المطالبة بنجاح! +{reward} ATF")
                return True, data
            else:
                return False, data
    except Exception as e:
        print(f"❌ [{acc_name}] خطأ في claim_task لـ {task_name}: {e}")
        return False, {"status": "error", "message": str(e)}

async def do_task_atf(session, headers, task, tg_id, init_data, device_prefix, acc_name, react_post_link=None):
    task_id = task["id"]
    min_sec = task["min_seconds"]
    task_name = task["name"]

    if task_id == "telegram_react_latest" and not react_post_link:
        print(f"⚠️ [{acc_name}] {task_name}: لا يوجد رابط للتحديث الأخير، تخطي")
        return

    print(f"🔄 [{acc_name}] بدء المهمة: {task_name}")
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
        async with session.post(START_TASK_ENDPOINT, json=start_payload, headers=headers) as resp:
            start_data = await resp.json()
            if start_data.get("status") != "success":
                print(f"❌ [{acc_name}] فشل start_task لـ {task_name}: {start_data.get('message')}")
                return
            server_started_at = start_data.get("started_at")
            started_at = int(server_started_at) if server_started_at else now
            print(f"✅ [{acc_name}] start_task لـ {task_name} تم، started_at={started_at}")
    except Exception as e:
        print(f"❌ [{acc_name}] خطأ في start_task لـ {task_name}: {e}")
        return

    wait_time = min_sec + 3
    if wait_time > 0:
        print(f"⏳ [{acc_name}] انتظار {wait_time} ثانية قبل المطالبة لـ {task_name}...")
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
        print(f"❌ [{acc_name}] فشل claim_task لـ {task_name}: {claim_data.get('message')}")
        return

    print(f"⏳ [{acc_name}] {task_name}: سيتم إعادة محاولة claim كل {RETRY_CLAIM_DELAY_ATF} ثانية...")
    start_time = time.time()
    while True:
        if time.time() - start_time > MAX_CLAIM_RETRY_TIME_ATF:
            print(f"❌ [{acc_name}] {task_name}: انتهى وقت إعادة المحاولة.")
            break
        await asyncio.sleep(RETRY_CLAIM_DELAY_ATF)
        success, claim_data = await attempt_claim_atf(session, headers, claim_payload, task_name, acc_name)
        if success:
            return

# ===================== مهام الخلفية ATF Workers لكل حساب =====================

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
                async with session.post(START_MINE_ENDPOINT, json=payload, headers=headers) as resp:
                    pass
                await do_boost_atf(session, headers, payload, acc_name)
        except Exception as e:
            print(f"💥 [{acc_name}] خطأ في حلقة التسريع: {e}")
        await asyncio.sleep(delay)

async def atf_tasks_worker(session, headers, me, init_data, react_post, lock, device_prefix, acc_name):
    while True:
        async with lock:
            print("\n" + "="*50)
            print(f"📝 [{acc_name}] بدء تنفيذ المهام الدورية...")
            print("="*50)
            try:
                react_post_link = react_post.get("link") if isinstance(react_post, dict) else None
                for task in TASKS_ATF:
                    await do_task_atf(session, headers, task, me.id, init_data, device_prefix, acc_name, react_post_link)
                print(f"✅ [{acc_name}] تم الانتهاء من جميع المهام بنجاح.")
            except Exception as e:
                print(f"💥 [{acc_name}] خطأ في حلقة المهام: {e}")

        print(f"\n⏳ [{acc_name}] المهام في وضع الانتظار لمدة {CYCLE_INTERVAL_ATF} ثانية...\n")
        await asyncio.sleep(CYCLE_INTERVAL_ATF)

# ===================== معالج الحساب الموحد =====================

async def account_worker(acc_config):
    acc_name = acc_config["account_name"]
    print(f"🔄 [{acc_name}] جاري الاتصال بجلسة تيليجرام...")
    
    async with aiohttp.ClientSession() as http_session:
        async with TelegramClient(StringSession(acc_config["session_string"]), acc_config["api_id"], acc_config["api_hash"]) as client:
            me = await client.get_me()
            print(f"✅ [{acc_name}] تم تسجيل الدخول: {me.first_name} (@{me.username or me.id})")

            bot = await client.get_input_entity(TARGET_BOT_USERNAME_ATF)
            init_data = await get_init_data_atf(client, bot, acc_name)

            if not init_data:
                print(f"❌ [{acc_name}] فشل استخراج initData.")
                return

            token, react_post, _ = await login_atf(
                http_session, 
                init_data, 
                me.id, 
                me.username, 
                acc_config
            )

            if not token:
                print(f"❌ [{acc_name}] فشل تسجيل الدخول في اللعبة.")
                return

            print(f"✅ [{acc_name}] تم المصادقة بنجاح وجاهز للعمل!")
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

            # تشغيل حلقة التسريع والمهام للحساب معاً
            await asyncio.gather(
                atf_tasks_worker(http_session, headers, me, init_data, react_post, lock, acc_config["device_prefix"], acc_name),
                atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"], acc_name)
            )

# ===================== التشغيل الرئيسي لجميع الحسابات =====================

async def main():
    print("🚀 بدء تشغيل كافة الحسابات بالتوازي...")
    # إطلاق كافة الحسابات معاً بنفس الوقت
    await asyncio.gather(*(account_worker(acc) for acc in ACCOUNTS_CONFIG))

def run_bot():
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n⏹️ تم إيقاف السكربت يدوياً.")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️ خطأ عام في بيئة asyncio: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        run_bot()
    else:
        while True:
            print("🚀 تشغيل عملية فرعية جديدة للبوت...")
            try:
                result = subprocess.run([sys.executable, __file__, "--child"])
                if result.returncode == 0:
                    print("\n⏹️ تم إيقاف العملية بشكل طبيعي.")
                    break
                print(f"\n⚠️ توقفت العملية الفرعية (كود الخروج: {result.returncode}) — إعادة التشغيل الفوري خلال 10 ثوانٍ...\n")
            except KeyboardInterrupt:
                print("\n⏹️ تم إيقاف السكربت الرئيسي يدوياً.")
                break
            except Exception as e:
                print(f"\n⚠️ خطأ في عملية المراقب الرئيسي: {e}")
            
            time.sleep(10)
