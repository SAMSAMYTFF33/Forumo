# ==============================================================================
# ⚙️ مفاتيح التحكم بحسابات ATF (1 = يعمل | 0 = متوقف)
# ==============================================================================
ATF_ACCOUNT_1   = 1     # ATF - gz
ATF_ACCOUNT_2   = 1     # ATF - الحساب الثاني
ATF_ACCOUNT_3   = 1     # ATF - SKATE 
ATF_ACCOUNT_4   = 0     # ATF - الحساب الرابع
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
        "account_name": "الحساب الأول (gz)",
        "do_boost": True,
        "api_id": 31568734,
        "api_hash": "7286e8c92ccc4dc698d771664bf71700",
        "session_string": "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU=",
        "device_prefix": "dev-B",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-A155F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    },
    {
        "enabled": ATF_ACCOUNT_2 == 1,
        "account_name": "الحساب الثاني",
        "do_boost": True,
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu2AYJJY6BirfGnzglAB8ppxWTbWSqjEvsAjT01QZCU-_LkiLVzmOJcpiD4NsR2UeXCb6Ujl9wuvUl7diZMgaNoV3L-RnfwKIkJFUzQ2F6txstq0gxgyjfPwQnoYhFLJGWV-8RI4bCDikGqmAzSYtwaJ7YYBP0UWPBEAAUT6cby6QAZfYAO6IXTLktrR7E48X9j5dXApa1wh8T_WPZKP5IRE8njO53kiN9_NfrBqLEz_7vogPGcDxDo9XU3S4wQ-DZTB4iEmXzzZ3dxcYrWUqpmtGLho0Uc_uS3amDa7hlg3tzo6ngvXiygMVkf8xjkxI6lAcC63gt527D43ePyRvLxY=",
        "device_prefix": "dev-D",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; 23124RA7EO) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not=A?Brand";v="24"',
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
        "account_name": "الحساب الثالث (SKATE)",
        "do_boost": True,
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu3uWEMwOhx78ucgVfqr0pS4dqY-ZoadziQ2tr6oMiXKg7fJJZ1HFL2VJBIe8Krw0LJZCbFO9dczyhhdwZ1OL0sX8zwTwuSxoxWzM12cF9okgymz3b7RPMBqthYhMxZQ-ivjAiqSW3yEyUG6-roO6OpdG2ydmiFXqd8-vJxKBYpVXu1VQtqRrNEaZl9wRSWJ0U-hBypmPsvjXzo1JPfX0sqkTPB-E86AHZOqCBHzq9xFkoTyPiS60cFFpOHN8kP7Q33qnmU49Khq9YTVo-kKgxlXXys8mL_H5H-Hke_wO4skgG8j5qDmrpRKZo5guTczEOOAsxXNL7XOo8X7a_eyNAgM=",
        "device_prefix": "dev-Oppo",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; CPH2565) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-MA,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    },
    {
        "enabled": ATF_ACCOUNT_4 == 1,
        "account_name": "الحساب الرابع",
        "do_boost": False,
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu4j9pNRXRJyJM8cFNQA4qSBm7h1yYxoSdldMF9cPYV3_bLr0d_ksxdqoxhqZydscC6lPpb6tup3RnrXm17QoueAx3NZq7_wux4vWMFSj3WoyrHDkSmLlC4XyayKncCXbdMHJYGwL4I5wZwGUUrRzk13rVsXHWaXjtJPhNunpSEHGKKe_m_FuBwCno5dxpi5yWOb7Js1lPuHmE3Vbep7PnQrsIExZ_SkcLiJX2adVp84AZOi8_14ok1nJ6Ezitlng6ONN8pK7GkxU25q36lLiQ7mP8QWwcPHiWoLA48FFfbYVnrK3uS8XWnLSCAtEVwrMqd9igyRNKDqObz_3S3VzyEs=",
        "device_prefix": "dev-E",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; 2310FPCA4G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="123", "Google Chrome";v="123"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-DZ,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        }
    },
    {
        "enabled": ATF_ACCOUNT_5 == 1,
        "account_name": "الحساب الخامس (ZAMASO)",
        "do_boost": False,
        "api_id": 31514497,
        "api_hash": "98d779341dd063307994de23cfd9796d",
        "session_string": "1BJWap1wBu4nVoNbxlJjeimChDuFtJFf-DIOl0cQE-sdurr6DuG3MLi23QOlaAmdHcU4k6lvqYt0Cn9Edehg8jApjS7Hhus2LNpBPotjpyNNWSWISgWMmBA-_GV0aPcXCcL8NTNjwAvaQCPptkQ02560D2UM5iunpN7kEIkwWNa-mMRFfMmwldrK81tc7CQf2QqkGLBijcNJsw-1-7h-UZ1A1Y75gk3BaLXrM-upajdg89y9Ka-vVsiUw4CZL8gMWU2CcxkPSjoxWBA-7bzG-HPnWduIyY6G__IDUsVua9ZTCFYywMkNccpNfwdXLAPEAjtFQ-bawSyWEM9uzM2pVlfE1Nxg2Nww=",
        "device_prefix": "dev-F",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; RMX3710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
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

TASKS_ATF = [
    {"id": "website_visit", "wait": 3, "name": "Website"},
    {"id": "youtube_like_comment", "wait": 33, "name": "YouTube"},
    {"id": "twitter_retweet", "wait": 33, "name": "Twitter"},
    {"id": "telegram_react_latest", "wait": 23, "name": "React"}
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
                headers["X-ATF-TMA-Session"] = data.get("tma_session_token")
                return data, headers
    return None, None


async def execute_task_atf(session, headers, tg_id, init_data, device_prefix, task, is_started, acc_name):
    now = int(time.time())
    
    # 1. إذا لم تكن المهمة قد بدأت -> إرسال زر GO (start_task)
    if not is_started:
        print(f"👉 [{acc_name}] [GO] بدء مهمة: {task['name']}")
        start_payload = {
            "tg_id": tg_id, "task_id": task["id"], "client_started_at": now,
            "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{now}",
            "request_id": f"rq-{now}-{tg_id}"
        }
        try:
            async with session.post(START_TASK_ENDPOINT, json=start_payload, headers=headers) as resp:
                s_data = await resp.json()
                if s_data.get("status") != "success":
                    print(f"❌ [{acc_name}] فشل البدء للمهمة {task['name']}: {s_data.get('message')}")
                    return False
        except Exception as e:
            print(f"❌ [{acc_name}] خطأ في بدء المهمة {task['name']}: {e}")
            return False
        
        await asyncio.sleep(task['wait'])

    # 2. إرسال طلب المطالبة (CLAIM)
    print(f"🟩 [{acc_name}] [CLAIM] المطالبة بمكافأة: {task['name']}")
    claim_payload = {
        "tg_id": tg_id, "task_id": task["id"], "client_started_at": now,
        "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{now}",
        "request_id": f"rq-{now}-{tg_id}"
    }
    try:
        async with session.post(CLAIM_TASK_ENDPOINT, json=claim_payload, headers=headers) as resp:
            c_data = await resp.json()
            if c_data.get("status") == "success":
                print(f"✅ [{acc_name}] تم جمع مهمة {task['name']} بنجاح! المكافأة: +{c_data.get('reward', 3)} ATF")
                return True
            else:
                print(f"⚠️ [{acc_name}] فشلت المطالبة للمهمة {task['name']}: {c_data.get('message')}")
                return False
    except Exception as e:
        print(f"❌ [{acc_name}] خطأ في مطالبة {task['name']}: {e}")
        return False


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
                async with session.post(ACTIVATE_BOOST_ENDPOINT, json=payload, headers=headers):
                    pass
        except Exception:
            pass
        await asyncio.sleep(round(random.uniform(9, 11), 2))


async def smart_tasks_worker(client, bot, acc_config, lock):
    acc_name = acc_config["account_name"]
    device_prefix = acc_config["device_prefix"]
    
    while True:
        async with lock:
            print("\n" + "="*50)
            print(f"🔍 [{acc_name}] فحص الوضع الحالي للمهام...")
            
            init_data = await get_init_data_atf(client, bot, acc_name)
            if not init_data:
                print(f"🛑 [{acc_name}] فشل جلب initData، محاولة بعد 15 ثانية...")
                await asyncio.sleep(15)
                continue

            async with aiohttp.ClientSession() as session:
                me = await client.get_me()
                login_data, headers = await login_atf(session, init_data, me.id, me.username, acc_config)
                
                if not login_data:
                    print(f"🛑 [{acc_name}] فشل تسجيل الدخول، محاولة بعد 15 ثانية...")
                    await asyncio.sleep(15)
                    continue

                cooldowns = login_data.get("task_cooldowns", {})
                task_starts = login_data.get("task_starts", {})
                current_time = int(time.time())
                
                sleep_times = []

                for task in TASKS_ATF:
                    task_id = task["id"]
                    cd_time = cooldowns.get(task_id, 0)
                    is_started = task_id in task_starts

                    # الوضع 1: المهمة قيد العد التنازلي
                    if cd_time > current_time:
                        remaining = cd_time - current_time
                        sleep_times.append(remaining)
                        mins, secs = divmod(remaining, 60)
                        hrs, mins = divmod(mins, 60)
                        print(f"⏳ [{acc_name}] [{task['name']}]: قيد الانتظار باقي له ({hrs}h {mins}m {secs}s)")
                    
                    # الوضع 2: المهمة جاهزة للتنفيذ (زر GO أو زر CLAIM)
                    else:
                        if is_started:
                            print(f"💡 [{acc_name}] [{task['name']}]: يتطلب الضغط على [CLAIM]")
                        else:
                            print(f"💡 [{acc_name}] [{task['name']}]: يتطلب الضغط على [GO]")

                        await execute_task_atf(session, headers, me.id, init_data, device_prefix, task, is_started, acc_name)

        # حساب وقت النوم المطلوب بناءً على أقرب مهمة ستنتهي
        if sleep_times:
            shortest_wait = min(sleep_times)
            next_wait = shortest_wait + 8  # إضافة 8 ثوانٍ كأمان للسيرفر
            mins, secs = divmod(next_wait, 60)
            hrs, mins = divmod(mins, 60)
            print(f"😴 [{acc_name}] سينام لمدة: ({hrs} ساعة و {mins} دقيقة و {secs} ثانية) حتى تجهز أقرب مهمة...\n")
            await asyncio.sleep(next_wait)
        else:
            print(f"🎉 [{acc_name}] جميع المهام مكتملة! نوم لمدة ساعتين (7205 ثوانٍ)...\n")
            await asyncio.sleep(7205)


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

    try:
        me = await client.get_me()
        bot = await client.get_input_entity(TARGET_BOT_USERNAME_ATF)
        lock = asyncio.Lock()

        workers_to_run = [
            smart_tasks_worker(client, bot, acc_config, lock)
        ]

        if acc_config.get("do_boost", True):
            # إنشاء جلسة HTTP مخصصة للـ Boost المستمر
            async with aiohttp.ClientSession() as http_session:
                init_data = await get_init_data_atf(client, bot, acc_name)
                if init_data:
                    login_data, headers = await login_atf(http_session, init_data, me.id, me.username, acc_config)
                    if headers:
                        workers_to_run.append(atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"]))

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

    print(f"🚀 ATF: تشغيل {len(active_accounts)} حسابات بنظام التحقق والدقة الذكية...")
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
            print("🚀 تشغيل العملية (ATF فقط - حسابات متعددة بالتوقيت الذكي)...")
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
