# ==============================================================================
# ⚙️ مفاتيح التحكم بحسابات ATF (1 = يعمل | 0 = متوقف)
# ==============================================================================
ATF_ACCOUNT_1   = 1     # ATF - gz
ATF_ACCOUNT_2   = 1     # ATF - الحساب الثاني
ATF_ACCOUNT_3   = 1     # ATF - SKATE 
ATF_ACCOUNT_4   = 1     # ATF - الحساب الرابع
ATF_ACCOUNT_5   = 1     # ATF - ZAMASO 
# ==============================================================================

import time
import asyncio
import urllib.parse
import aiohttp
import random
import sys
import subprocess
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

# ==============================================================================
# 🟩 إعدادات حسابات ATF Bot
# ==============================================================================

ACCOUNTS_CONFIG = [
    {
        "enabled": ATF_ACCOUNT_1 == 1,
        "account_name": "الحساب الأول (الثاني سابقاً)",
        "do_boost": True,  # تفعيل تسريع التعدين
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
        "enabled": ATF_ACCOUNT_2 == 1,
        "account_name": "الحساب الثاني (الرابع سابقاً)",
        "do_boost": True,  # تفعيل تسريع التعدين
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu2AYJJY6BirfGnzglAB8ppxWTbWSqjEvsAjT01QZCU-_LkiLVzmOJcpiD4NsR2UeXCb6Ujl9wuvUl7diZMgaNoV3L-RnfwKIkJFUzQ2F6txstq0gxgyjfPwQnoYhFLJGWV-8RI4bCDikGqmAzSYtwaJ7YYBP0UWPBEAAUT6cby6QAZfYAO6IXTLktrR7E48X9j5dXApa1wh8T_WPZKP5IRE8njO53kiN9_NfrBqLEz_7vogPGcDxDo9XU3S4wQ-DZTB4iEmXzzZ3dxcYrWUqpmtGLho0Uc_uS3amDa7hlg3tzo6ngvXiygMVkf8xjkxI6lAcC63gt527D43ePyRvLxY=",
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
    },
    {
        "enabled": ATF_ACCOUNT_3 == 1,
        "account_name": "الحساب الثالث",
        "do_boost": True,  # تفعيل تسريع التعدين
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu3uWEMwOhx78ucgVfqr0pS4dqY-ZoadziQ2tr6oMiXKg7fJJZ1HFL2VJBIe8Krw0LJZCbFO9dczyhhdwZ1OL0sX8zwTwuSxoxWzM12cF9okgymz3b7RPMBqthYhMxZQ-ivjAiqSW3yEyUG6-roO6OpdG2ydmiFXqd8-vJxKBYpVXu1VQtqRrNEaZl9wRSWJ0U-hBypmPsvjXzo1JPfX0sqkTPB-E86AHZOqCBHzq9xFkoTyPiS60cFFpOHN8kP7Q33qnmU49Khq9YTVo-kKgxlXXys8mL_H5H-Hke_wO4skgG8j5qDmrpRKZo5guTczEOOAsxXNL7XOo8X7a_eyNAgM=",
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
        "enabled": ATF_ACCOUNT_4 == 1,
        "account_name": "الحساب الرابع",
        "do_boost": False, # تعطيل تسريع التعدين (فقط مهام)
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu4j9pNRXRJyJM8cFNQA4qSBm7h1yYxoSdldMF9cPYV3_bLr0d_ksxdqoxhqZydscC6lPpb6tup3RnrXm17QoueAx3NZq7_wux4vWMFSj3WoyrHDkSmLlC4XyayKncCXbdMHJYGwL4I5wZwGUUrRzk13rVsXHWaXjtJPhNunpSEHGKKe_m_FuBwCno5dxpi5yWOb7Js1lPuHmE3Vbep7PnQrsIExZ_SkcLiJX2adVp84AZOi8_14ok1nJ6Ezitlng6ONN8pK7GkxU25q36lLiQ7mP8QWwcPHiWoLA48FFfbYVnrK3uS8XWnLSCAtEVwrMqd9igyRNKDqObz_3S3VzyEs=",
        "device_prefix": "dev-E",
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
    },
    {
        "enabled": ATF_ACCOUNT_5 == 1,
        "account_name": "الحساب الخامس (ZAMASO)",
        "do_boost": False, # تعطيل تسريع التعدين (فقط مهام)
        "api_id": 31514497,
        "api_hash": "98d779341dd063307994de23cfd9796d",
        "session_string": "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww=",
        "device_prefix": "dev-F",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
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
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "Twitter"},
    {"id": "website_visit", "min_seconds": 0, "name": "Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React"}
]

# ==============================================================================
# 🟩 دوال ATF Bot الأساسية
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
    except Exception:
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


async def do_boost_atf(session, headers, payload):
    try:
        async with session.post(ACTIVATE_BOOST_ENDPOINT, json=payload, headers=headers) as resp:
            return await resp.json()
    except Exception:
        return None


async def attempt_claim_atf(session, headers, claim_payload):
    try:
        async with session.post(CLAIM_TASK_ENDPOINT, json=claim_payload, headers=headers) as resp:
            data = await resp.json()
            return data.get("status") == "success", data
    except Exception as e:
        return False, {"status": "error", "message": str(e)}


async def do_task_atf(session, headers, task, tg_id, init_data, device_prefix, react_post_link=None):
    task_id = task["id"]
    
    if task_id == "telegram_react_latest" and not react_post_link:
        return False, "لا يوجد رابط"

    now = int(time.time())
    start_payload = {
        "tg_id": tg_id, "task_id": task_id, "client_started_at": now,
        "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{now}",
        "request_id": f"rq-{now}-{tg_id}"
    }
    try:
        async with session.post(START_TASK_ENDPOINT, json=start_payload, headers=headers) as resp:
            start_data = await resp.json()
            if start_data.get("status") != "success":
                return False, start_data.get("message", "")
            started_at = int(start_data.get("started_at") or now)
    except Exception as e:
        return False, str(e)

    wait_time = task["min_seconds"] + 3
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    claim_payload = {
        "tg_id": tg_id, "task_id": task_id, "client_started_at": started_at,
        "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{started_at}",
        "request_id": f"rq-{started_at}-{tg_id}"
    }

    success, claim_data = await attempt_claim_atf(session, headers, claim_payload)
    if success:
        return True, claim_data.get("reward", 0)

    msg = claim_data.get("message", "")
    keywords = ["wait", "try again", "not ready", "please wait", "seconds", "cooldown", "retry"]
    if not any(k in msg.lower() for k in keywords):
        return False, msg

    start_time = time.time()
    while time.time() - start_time <= MAX_CLAIM_RETRY_TIME_ATF:
        await asyncio.sleep(RETRY_CLAIM_DELAY_ATF)
        success, claim_data = await attempt_claim_atf(session, headers, claim_payload)
        if success:
            return True, claim_data.get("reward", 0)
    return False, "انتهى وقت إعادة المحاولة"


async def atf_boost_worker(session, headers, me, init_data, lock, device_prefix):
    await asyncio.sleep(2)
    while True:
        try:
            async with lock:
                payload = {
                    "initData": init_data, "tg_id": me.id, "username": me.username or "",
                    "request_id": f"rq-{int(time.time()*1000)}-{me.id}",
                    "device_id": f"{device_prefix}-{me.id}-{int(time.time())}",
                    "display_preview": "0.0000"
                }
                async with session.post(START_MINE_ENDPOINT, json=payload, headers=headers):
                    pass
                await do_boost_atf(session, headers, payload)
        except Exception:
            pass
        await asyncio.sleep(round(random.uniform(9, 11), 2))


async def atf_tasks_worker(session, headers, me, init_data, react_post, lock, device_prefix, acc_name):
    while True:
        async with lock:
            react_post_link = react_post.get("link") if isinstance(react_post, dict) else None
            ok_count = 0
            for task in TASKS_ATF:
                success, _ = await do_task_atf(session, headers, task, me.id, init_data, device_prefix, react_post_link)
                if success:
                    ok_count += 1
            print(f"📝 [{acc_name}] مهام: {ok_count}/{len(TASKS_ATF)} ناجحة")

        await asyncio.sleep(CYCLE_INTERVAL_ATF)


async def account_worker(acc_config):
    acc_name = acc_config["account_name"]
    client = TelegramClient(StringSession(acc_config["session_string"]), acc_config["api_id"], acc_config["api_hash"])

    try:
        await client.connect()
    except Exception as e:
        print(f"🛑 [{acc_name}] فشل الاتصال: {type(e).__name__}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return

    if not await client.is_user_authorized():
        print(f"🛑 [{acc_name}] الجلسة غير مصرّحة - يلزم session جديد")
        await client.disconnect()
        return

    async with aiohttp.ClientSession() as http_session:
        try:
            me = await client.get_me()
            bot = await client.get_input_entity(TARGET_BOT_USERNAME_ATF)
            init_data = await get_init_data_atf(client, bot, acc_name)
            if not init_data:
                print(f"❌ [{acc_name}] فشل استخراج initData")
                return

            token, react_post, _ = await login_atf(http_session, init_data, me.id, me.username, acc_config)
            if not token:
                print(f"❌ [{acc_name}] فشل تسجيل الدخول")
                return

            print(f"✅ [{acc_name}] جاهز")
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
            
            # إعداد المهام التي سيقوم بها الحساب
            workers_to_run = [
                atf_tasks_worker(http_session, headers, me, init_data, react_post, lock, acc_config["device_prefix"], acc_name)
            ]
            
            # التحقق مما إذا كان الحساب مسموح له بتسريع التعدين
            if acc_config.get("do_boost", True):
                workers_to_run.append(atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"]))
            else:
                print(f"⚠️ [{acc_name}] سيكتفي بعمل المهام فقط ولن يضغط على تسريع التعدين (MAX SPEED).")

            await asyncio.gather(*workers_to_run)
        except Exception as e:
            print(f"🛑 [{acc_name}] توقف: {type(e).__name__}")
        finally:
            await client.disconnect()


async def main_atf():
    active_accounts = [acc for acc in ACCOUNTS_CONFIG if acc.get("enabled", True)]
    if not active_accounts:
        print("⚠️ ATF: كل الحسابات متوقفة")
        return

    print(f"🚀 ATF: تشغيل {len(active_accounts)} حساب")
    results = await asyncio.gather(
        *(account_worker(acc) for acc in active_accounts),
        return_exceptions=True
    )
    for acc, result in zip(active_accounts, results):
        if isinstance(result, Exception):
            print(f"🛑 [{acc['account_name']}] خطأ غير متوقع: {type(result).__name__}")


# ==============================================================================
# 🟨 نقطة التشغيل الرئيسية
# ==============================================================================

def run_bot():
    while True:
        try:
            asyncio.run(main_atf())
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"⚠️ خطأ عام: {type(e).__name__}")
            time.sleep(5)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        run_bot()
    else:
        while True:
            print("🚀 تشغيل العملية (ATF فقط - حسابات متعددة)...")
            try:
                result = subprocess.run([sys.executable, __file__, "--child"])
                if result.returncode == 0:
                    break
                print(f"⚠️ إعادة تشغيل بعد 10 ثوانٍ (كود: {result.returncode})")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ خطأ مراقب: {type(e).__name__}")
            time.sleep(10)
