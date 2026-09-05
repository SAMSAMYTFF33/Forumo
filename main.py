import time
import asyncio
import urllib.parse
import aiohttp
import random
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonSimpleWebView

# =============================================================================
# ⚙️ مفاتيح التحكم بحسابات ATF (1 = يعمل | 0 = متوقف)
# ==============================================================================
ATF_ACCOUNT_1   = 1     # ATF - gz (الحساب الأول)
ATF_ACCOUNT_2   = 1     # ATF - الحساب ousama 
ATF_ACCOUNT_3   = 1     # ATF - SKATE (الحساب الثالث)
ATF_ACCOUNT_4   = 1     # ATF - الحساب الرابع
ATF_ACCOUNT_5   = 1     # ATF - ZAMASO (الحساب الخامس)

# ==============================================================================
# ⚙️ مفاتيح التحكم بحسابات BODA (1 = يعمل | 0 = متوقف)
# ==============================================================================
BODA_ACCOUNT_1  = 1     # BODA - gz (الحساب الأول)
BODA_ACCOUNT_2  = 1     # BODA - الحساب الثاني (متوقف)
BODA_ACCOUNT_3  = 0     # BODA - SKATE (الحساب الثالث)
BODA_ACCOUNT_4  = 0     # BODA - الحساب الرابع (متوقف)
BODA_ACCOUNT_5  = 0     # BODA - ZAMASO (الحساب الخامس)
# ==============================================================================

# ==============================================================================
# 🟩 إعدادات الحسابات المشتركة لـ ATF و BODA
# ==============================================================================
ACCOUNTS_CONFIG = [
    {
        "atf_enabled": ATF_ACCOUNT_1 == 1,
        "boda_enabled": BODA_ACCOUNT_1 == 1,
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
        "atf_enabled": ATF_ACCOUNT_2 == 1,
        "boda_enabled": BODA_ACCOUNT_2 == 1,
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
        "atf_enabled": ATF_ACCOUNT_3 == 1,
        "boda_enabled": BODA_ACCOUNT_3 == 1,
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
        "atf_enabled": ATF_ACCOUNT_4 == 1,
        "boda_enabled": BODA_ACCOUNT_4 == 1,
        "account_name": "الحساب الرابع",
        "do_boost": True,
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu3E3ixVfR8ae3yJnPtwfAjXfmbV9o_ud-zFiEbSr1ir2RUOjO2qf0jaP6P5Dpzh7sz607dhyDJX26eEo3dm-YZW0DzXKGkiOI6E7VHnMplSf1S15aKcekSHXoZ6U614I_Irx0AeoSkU12iPqy6PY5slRUUrz3D1k5MIROVwrm0Sn61yWRPJPQ-T8PAMyRjxsZHM5fuGFTz2sZRjSIpTKaleHybBFwuWRbCg3ADiYaPYsxEozXuyGmIT_dggv6gDQ6agIVkrDHUHDdzyOctKWs7UyAgSOxtrSunbtks2yEX_hvRjh5EIA9gejGO9G3sg72sbBDBCYSXXwyo2f8A4vEj8=",
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
        "atf_enabled": ATF_ACCOUNT_5 == 1,
        "boda_enabled": BODA_ACCOUNT_5 == 1,
        "account_name": "الحساب الخامس (ZAMASO)",
        "do_boost": True,
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

# ==============================================================================
# 🟨 ثوابت وإعدادات ATF Bot
# ==============================================================================
TARGET_BOT_USERNAME_ATF = "ATF_AIRDROP_bot"
WEB_APP_URL_ATF = "https://atfminers.asloni.online/miner/index.html"
BASE_URL_ATF = "https://atfminers.asloni.online"

LOGIN_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=login"
START_MINE_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=start_mine"
ACTIVATE_BOOST_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=activate_boost"
START_TASK_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=start_task"
CLAIM_TASK_ENDPOINT_ATF = f"{BASE_URL_ATF}/miner/index.php?action=claim_task"

TASKS_ATF = [
    {"id": "website_visit", "wait": 3, "name": "Website"},
    {"id": "youtube_like_comment", "wait": 33, "name": "YouTube"},
    {"id": "twitter_retweet", "wait": 33, "name": "Twitter"},
    {"id": "telegram_react_latest", "wait": 23, "name": "React"}
]

# ==============================================================================
# 🟦 ثوابت وإعدادات BODA Bot
# ==============================================================================
TARGET_BOT_BODA = "YodaAirdropBot"
BASE_URL_BODA = "https://baby-yoda.arsidfani.workers.dev"

MOROCCO_OFFSET = timedelta(hours=1)  # GMT+1 (بتوقيت المغرب)
TARGET_HOUR_BODA = 3  # 3 صباحاً
TARGET_MINUTE_BODA = 0


# ==============================================================================
# 🛠️ دالة النوم الاستجابي
# ==============================================================================
async def pauseable_sleep(seconds, event=None):
    """انتظار ذكي يستجيب لأمر التوقف والعمل دون أن يعطل الحلقة."""
    end_time = time.time() + seconds
    while time.time() < end_time:
        if event is not None and not event.is_set():
            await event.wait()
        rem = end_time - time.time()
        if rem > 0:
            await asyncio.sleep(min(rem, 2))


# ==============================================================================
# 🟩 دوال وتدفق بوت ATF
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
    async with session.post(LOGIN_ENDPOINT_ATF, json=payload, headers=headers) as resp:
        if resp.status == 200:
            data = await resp.json()
            if data.get("status") == "success":
                headers["X-ATF-TMA-Session"] = data.get("tma_session_token")
                return data, headers
    return None, None


async def execute_task_atf(session, headers, tg_id, init_data, device_prefix, task, is_started, acc_name, atf_run_event):
    now = int(time.time())

    if not is_started:
        print(f"👉 [{acc_name}] [GO] بدء مهمة: {task['name']}")
        start_payload = {
            "tg_id": tg_id, "task_id": task["id"], "client_started_at": now,
            "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{now}",
            "request_id": f"rq-{now}-{tg_id}"
        }
        try:
            async with session.post(START_TASK_ENDPOINT_ATF, json=start_payload, headers=headers) as resp:
                s_data = await resp.json()
                if s_data.get("status") != "success":
                    print(f"❌ [{acc_name}] فشل البدء للمهمة {task['name']}: {s_data.get('message')}")
                    return False
        except Exception as e:
            print(f"❌ [{acc_name}] خطأ في بدء المهمة {task['name']}: {e}")
            return False

        wait_sec = task.get('wait', 5) + 3
        print(f"⏳ [{acc_name}] انتظار {wait_sec} ثانية لإنهاء المهمة...")
        await pauseable_sleep(wait_sec, atf_run_event)

    now_claim = int(time.time())
    print(f"🟩 [{acc_name}] [CLAIM] المطالبة بمكافأة: {task['name']}")
    claim_payload = {
        "tg_id": tg_id, "task_id": task["id"], "client_started_at": now_claim,
        "initData": init_data, "device_id": f"{device_prefix}-{tg_id}-{now_claim}",
        "request_id": f"rq-{now_claim}-{tg_id}"
    }
    try:
        async with session.post(CLAIM_TASK_ENDPOINT_ATF, json=claim_payload, headers=headers) as resp:
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


async def atf_boost_worker(session, headers, me, init_data, lock, device_prefix, atf_run_event):
    await asyncio.sleep(2)
    while True:
        try:
            await atf_run_event.wait()
            async with lock:
                payload = {
                    "initData": init_data, 
                    "tg_id": me.id, 
                    "username": me.username or "",
                    "request_id": f"rq-{int(time.time()*1000)}-{me.id}",
                    "device_id": f"{device_prefix}-{me.id}-{int(time.time())}",
                    "display_preview": "0.0000"
                }
                async with session.post(START_MINE_ENDPOINT_ATF, json=payload, headers=headers):
                    pass
                async with session.post(ACTIVATE_BOOST_ENDPOINT_ATF, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        if res.get("status") == "success":
                            print(f"🚀 [{me.id}] تم إرسال تسريع التعدين (BOOST) بنجاح!")
        except Exception:
            pass
        await pauseable_sleep(round(random.uniform(9, 11), 2), atf_run_event)


async def smart_tasks_worker(client, bot, acc_config, session, lock, atf_run_event):
    acc_name = acc_config["account_name"]
    device_prefix = acc_config["device_prefix"]

    while True:
        await atf_run_event.wait()

        async with lock:
            print("\n" + "="*50)
            print(f"🔍 [{acc_name}] فحص الوضع الحالي للمهام...")

            init_data = await get_init_data_atf(client, bot, acc_name)
            if not init_data:
                print(f"🛑 [{acc_name}] فشل جلب initData، محاولة بعد 15 ثانية...")
                await pauseable_sleep(15, atf_run_event)
                continue

            me = await client.get_me()
            login_data, headers = await login_atf(session, init_data, me.id, me.username, acc_config)

            if not login_data:
                print(f"🛑 [{acc_name}] فشل تسجيل الدخول، محاولة بعد 15 ثانية...")
                await pauseable_sleep(15, atf_run_event)
                continue

            cooldowns = login_data.get("task_cooldowns", {})
            task_starts = login_data.get("task_starts", {})
            current_time = int(time.time())

            action_executed = False
            sleep_times = []

            for task in TASKS_ATF:
                await atf_run_event.wait()
                task_id = task["id"]
                cd_time = cooldowns.get(task_id, 0)
                is_started = task_id in task_starts

                if cd_time > current_time and not is_started:
                    remaining = cd_time - current_time
                    sleep_times.append(remaining)
                    mins, secs = divmod(remaining, 60)
                    hrs, mins = divmod(mins, 60)
                    print(f"⏳ [{acc_name}] [{task['name']}]: قيد الانتظار باقي له ({hrs}h {mins}m {secs}s)")
                else:
                    if is_started:
                        print(f"💡 [{acc_name}] [{task['name']}]: يتطلب الضغط المباشر على [CLAIM]")
                    else:
                        print(f"💡 [{acc_name}] [{task['name']}]: يتطلب البدء والجمع [GO -> CLAIM]")

                    await execute_task_atf(session, headers, me.id, init_data, device_prefix, task, is_started, acc_name, atf_run_event)
                    action_executed = True

        if action_executed:
            print(f"🔄 [{acc_name}] تم تنفيذ مهمة، جاري التحديث المباشر من السيرفر...")
            await pauseable_sleep(3, atf_run_event)
            continue

        if sleep_times:
            shortest_wait = min(sleep_times)
            next_wait = max(shortest_wait + 5, 10)
            mins, secs = divmod(next_wait, 60)
            hrs, mins = divmod(mins, 60)
            print(f"😴 [{acc_name}] جميع المهام قيد الانتظار. نوم حتى جاهزية أقرب مهمة: ({hrs}h {mins}m {secs}s)...\n")
            await pauseable_sleep(next_wait, atf_run_event)
        else:
            print(f"🎉 [{acc_name}] جميع المهام مكتملة! إعاده الفحص بعد 15 دقيقة...\n")
            await pauseable_sleep(900, atf_run_event)


async def account_worker_atf(acc_config, atf_run_event):
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

        async with aiohttp.ClientSession() as http_session:
            init_data = await get_init_data_atf(client, bot, acc_name)
            if not init_data:
                print(f"🛑 [{acc_name}] فشل جلب initData الأولي")
                await client.disconnect()
                return

            login_data, headers = await login_atf(http_session, init_data, me.id, me.username, acc_config)
            if not headers:
                print(f"🛑 [{acc_name}] فشل تسجيل الدخول الأولي")
                await client.disconnect()
                return

            workers_to_run = [
                smart_tasks_worker(client, bot, acc_config, http_session, lock, atf_run_event)
            ]

            if acc_config.get("do_boost", True):
                workers_to_run.append(atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"], atf_run_event))

            await asyncio.gather(*workers_to_run)

    except Exception as e:
        print(f"🛑 [{acc_name}] توقف: {type(e).__name__}")
    finally:
        await client.disconnect()


async def main_atf_app(atf_run_event):
    active_accounts = [acc for acc in ACCOUNTS_CONFIG if acc.get("atf_enabled", True)]
    if not active_accounts:
        print("⚠️ ATF: كل الحسابات متوقفة")
        return

    print(f"🚀 ATF: تشغيل {len(active_accounts)} حسابات بنظام التحقق والدقة الذكية...")
    results = await asyncio.gather(
        *(account_worker_atf(acc, atf_run_event) for acc in active_accounts),
        return_exceptions=True
    )
    for acc, result in zip(active_accounts, results):
        if isinstance(result, Exception):
            print(f"🛑 [{acc['account_name']}] خطأ غير متوقع في ATF: {type(result).__name__}")


# ==============================================================================
# 🟦 دوال وتدفق بوت BODA (تم دعم البصمة ودقة الوقت والـ Sessions)
# ==============================================================================
def get_morocco_time():
    """الحصول على الوقت الحالي بتوقيت المغرب (GMT+1)."""
    return datetime.now(timezone.utc) + MOROCCO_OFFSET


def get_target_time_boda():
    """الحصول على وقت الهدف (3:00 صباحاً بتوقيت المغرب)."""
    now = get_morocco_time()
    target = now.replace(hour=TARGET_HOUR_BODA, minute=TARGET_MINUTE_BODA, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


async def wait_until_target_time_boda():
    """تنتظر حتى الساعة 3:00 صباحاً بتوقيت المغرب مع تفادي الانحراف الزمني."""
    target = get_target_time_boda()
    now = get_morocco_time()
    wait_seconds = (target - now).total_seconds()

    wait_hours = int(wait_seconds // 3600)
    wait_minutes = int((wait_seconds % 3600) // 60)
    wait_seconds_remain = int(wait_seconds % 60)

    print(f"\n⏰ الوقت الحالي (المغرب): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 المنطقة الزمنية: GMT+1 (المغرب)")
    print(f"⏳ الانتظار حتى الساعة {TARGET_HOUR_BODA:02d}:{TARGET_MINUTE_BODA:02d} صباحاً (بتوقيت المغرب)")
    print(f"📅 التاريخ المستهدف: {target.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱️ المتبقي: {wait_hours} ساعة و {wait_minutes} دقيقة و {wait_seconds_remain} ثانية")

    last_log_time = 0
    while True:
        now = get_morocco_time()
        rem_seconds = (target - now).total_seconds()
        if rem_seconds <= 0:
            break

        if rem_seconds > 60:
            await asyncio.sleep(30)
            if time.time() - last_log_time >= 600:
                hours = int(rem_seconds // 3600)
                minutes = int((rem_seconds % 3600) // 60)
                print(f"⏳ BODA - متبقي حتى الساعة 3:00 صباحاً: {hours} ساعة و {minutes} دقيقة")
                last_log_time = time.time()
        else:
            await asyncio.sleep(rem_seconds)
            break


async def get_init_data_boda(acc_config):
    """استخراج initData من بوت YodaAirdropBot لحساب محدد."""
    session_str = acc_config["session_string"]
    api_id = acc_config["api_id"]
    api_hash = acc_config["api_hash"]
    acc_name = acc_config["account_name"]

    try:
        async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
            me = await client.get_me()
            print(f"✅ BODA [{acc_name}] تم تسجيل الدخول: {me.first_name} (ID: {me.id})")

            await client.send_message(TARGET_BOT_BODA, "/start")
            await asyncio.sleep(2)

            target_url = None
            bot_entity = await client.get_input_entity(TARGET_BOT_BODA)

            async for message in client.iter_messages(TARGET_BOT_BODA, limit=10):
                if message.reply_markup and hasattr(message.reply_markup, 'rows'):
                    for row in message.reply_markup.rows:
                        for button in row.buttons:
                            if isinstance(button, (KeyboardButtonWebView, KeyboardButtonSimpleWebView)):
                                target_url = button.url
                                break
                        if target_url:
                            break
                if target_url:
                    break

            if not target_url:
                print(f"❌ BODA [{acc_name}] لم يتم العثور على زر WebApp.")
                return None, None

            web_view = await client(RequestWebViewRequest(
                peer=bot_entity,
                bot=bot_entity,
                platform="android",
                from_bot_menu=False,
                url=target_url
            ))

            full_url = web_view.url
            if "#tgWebAppData=" in full_url:
                raw_init_data = full_url.split("#tgWebAppData=")[1].split("&")[0]
            elif "tgWebAppData=" in full_url:
                raw_init_data = full_url.split("tgWebAppData=")[1].split("&")[0]
            else:
                raw_init_data = full_url

            return urllib.parse.unquote(raw_init_data), me.id
    except Exception as e:
        print(f"❌ BODA [{acc_name}] خطأ في جلب initData: {e}")
        return None, None


def build_headers_boda(init_data, user_id, acc_config):
    """بناء الهيدرز الخاصة بـ BODA ديناميكياً باستخدام البصمة المخصصة للحساب من ATF."""
    extra = acc_config.get("extra_headers", {})
    return {
        "accept": "*/*",
        "accept-language": extra.get("accept-language", "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"),
        "content-type": "application/json",
        "sec-ch-ua": extra.get("sec-ch-ua", '"Chromium";v="126", "Not/A)Brand";v="8"'),
        "sec-ch-ua-mobile": extra.get("sec-ch-ua-mobile", "?1"),
        "sec-ch-ua-platform": extra.get("sec-ch-ua-platform", '"Android"'),
        "sec-fetch-dest": extra.get("sec-fetch-dest", "empty"),
        "sec-fetch-mode": extra.get("sec-fetch-mode", "cors"),
        "sec-fetch-site": extra.get("sec-fetch-site", "same-origin"),
        "x-guest-id": f"guest_{user_id}_{int(time.time())}",
        "x-init-data": init_data,
        "x-start-param": "",
        "referer": BASE_URL_BODA + "/",
        "origin": BASE_URL_BODA,
        "user-agent": acc_config["user_agent"]
    }


async def req_boda(session, endpoint, method='GET', data=None, headers=None):
    url = BASE_URL_BODA + endpoint
    async with session.request(method, url, json=data, headers=headers, timeout=15) as resp:
        resp.raise_for_status()
        return await resp.json()


async def video_ads_boda(session, headers, limit=10, acc_name=""):
    st = await req_boda(session, '/api/state', headers=headers)
    ads = st.get('ads', {})
    done = ads.get('done', 0)
    remaining = min(limit, ads.get('limit', 10) - done)
    if remaining <= 0:
        return 0, "مكتمل"
    earned = 0
    for i in range(remaining):
        wait = random.randint(5, 10)
        print(f"🎬 BODA [{acc_name}] فيديو {i+1}/{remaining} ({wait}s)")
        await asyncio.sleep(wait)
        res = await req_boda(session, '/api/ads/watch', 'POST', {'network': 'monetag'}, headers)
        if res.get('ok'):
            reward = res['result']['reward']
            earned += reward
            print(f"   +{reward} YODA")
        else:
            break
        await asyncio.sleep(random.uniform(2, 4))
    return earned, f"{earned:.2f} YODA"


async def link_ads_boda(session, headers, acc_name=""):
    st = await req_boda(session, '/api/state', headers=headers)
    links = [l for l in st.get('adLinks', []) if l.get('remaining', 0) > 0]
    if not links:
        return 0, "مكتمل"
    earned = 0
    for l in links:
        wait = l.get('wait_seconds', 5)
        print(f"🔗 BODA [{acc_name}] {l['title']} ({wait}s)")
        await asyncio.sleep(wait)
        res = await req_boda(session, '/api/ads/link', 'POST', {'linkId': l['id']}, headers)
        if res.get('ok'):
            reward = res['result']['reward']
            earned += reward
            print(f"   +{reward} YODA")
        else:
            break
        await asyncio.sleep(1)
    return earned, f"{earned:.2f} YODA"


async def social_tasks_boda(session, headers, acc_name=""):
    data = await req_boda(session, '/api/social/list', headers=headers)
    tasks = [t for t in data.get('tasks', []) if not t.get('completed')]
    if not tasks:
        return 0, "مكتمل"
    earned = 0
    for t in tasks:
        print(f"👤 BODA [{acc_name}] {t['title']}")
        await asyncio.sleep(2)
        res = await req_boda(session, '/api/social/complete', 'POST', {'taskId': t['id']}, headers)
        if res.get('ok'):
            reward = res['result']['reward']
            earned += reward
            print(f"   +{reward} YODA")
        else:
            break
        await asyncio.sleep(1)
    return earned, f"{earned:.2f} YODA"


async def run_boda_tasks_for_account(acc_config):
    """تنفيذ جميع مهام Baby Yoda لحساب محدد باستعمال بصمته المخصصة."""
    acc_name = acc_config["account_name"]
    now = get_morocco_time()
    print(f"\n🚀 BODA [{acc_name}] بدء تنفيذ المهام (بتوقيت المغرب: {now.strftime('%H:%M:%S')})...")

    init_data, user_id = await get_init_data_boda(acc_config)
    if not init_data:
        print(f"❌ BODA [{acc_name}] فشل استخراج initData.")
        return

    # 🎯 استخدام بصمة الجهاز الفريدة للحساب في BODA
    headers = build_headers_boda(init_data, user_id, acc_config)
    print(f"✅ BODA [{acc_name}] تم استخراج initData وبناء البصمة الخاصة بالحساب بنجاح.\n")

    async with aiohttp.ClientSession() as session:
        total = 0

        # 1. فيديو
        earned, msg = await video_ads_boda(session, headers, 10, acc_name)
        total += earned
        print(f"✅ BODA [{acc_name}] فيديو: {msg}\n")

        # 2. روابط
        earned, msg = await link_ads_boda(session, headers, acc_name)
        total += earned
        print(f"✅ BODA [{acc_name}] روابط: {msg}\n")

        # 3. اجتماعي
        earned, msg = await social_tasks_boda(session, headers, acc_name)
        total += earned
        print(f"✅ BODA [{acc_name}] اجتماعي: {msg}\n")

        end_time = get_morocco_time()
        print(f"💰 BODA [{acc_name}] الإجمالي اليومي: {total:.2f} YODA")
        print(f"✅ BODA [{acc_name}] اكتملت المهام في: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (بتوقيت المغرب)")


async def run_all_boda_tasks(atf_run_event):
    """إيقاف ATF مؤقتاً ثم تشغيل BODA لجميع الحسابات المفعلة، واستئناف ATF بعد الانتهاء."""
    active_boda_accounts = [acc for acc in ACCOUNTS_CONFIG if acc.get("boda_enabled", False)]
    if not active_boda_accounts:
        print("⚠️ BODA: لا توجد حسابات مفعلة لـ BODA.")
        return

    print("\n" + "=" * 60)
    print("🛑 إيقاف بوت ATF مؤقتاً لبدء تشغيل بوت BODA...")
    print("=" * 60)

    # ⏸️ إيقاف ATF مؤقتاً لمنع تعارض الجلسات
    atf_run_event.clear()
    await asyncio.sleep(3)

    try:
        print(f"🚀 BODA: بدء تشغيل {len(active_boda_accounts)} حسابات...")
        for acc in active_boda_accounts:
            try:
                await run_boda_tasks_for_account(acc)
            except Exception as e:
                print(f"❌ BODA [{acc['account_name']}] خطأ أثناء التنفيذ: {e}")
            await asyncio.sleep(5)
    finally:
        print("\n" + "=" * 60)
        print("✅ اكتملت جميع مهام BODA! استئناف عمل بوت ATF...")
        print("=" * 60)
        # ▶️ استئناف ATF
        atf_run_event.set()


async def boda_scheduler_loop(atf_run_event):
    """حلقة جدولة BODA اليومية عند 3 صباحاً بتوقيت المغرب."""
    print("=" * 60)
    print("🚀 جدولة Baby Yoda (BODA) Bot")
    print(f"📍 المنطقة الزمنية: GMT+1 (المغرب)")
    print(f"⏰ سيبدأ العمل يومياً عند الساعة {TARGET_HOUR_BODA:02d}:{TARGET_MINUTE_BODA:02d} صباحاً (بتوقيت المغرب)")
    print("=" * 60)

    while True:
        try:
            await wait_until_target_time_boda()
            await run_all_boda_tasks(atf_run_event)

            print("\n⏳ BODA - انتظار 5 دقائق قبل إنهاء الدورة اليومية...")
            await pauseable_sleep(300, atf_run_event)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ خطأ غير متوقع في جدولة BODA: {type(e).__name__}: {e}")
            print("⏳ انتظار 60 ثانية ثم إعادة المحاولة...")
            await asyncio.sleep(60)


# ==============================================================================
# 🟨 المنسق الرئيسي والنظام الشامل
# ==============================================================================
async def main_system():
    # حدث التحكم بتشغيل/توقف بوت ATF
    atf_run_event = asyncio.Event()
    atf_run_event.set()  # يبدأ بالعمل افتراضياً

    # تشغيل مهام ATF وجدولة BODA بالتوازي
    atf_task = asyncio.create_task(main_atf_app(atf_run_event))
    boda_task = asyncio.create_task(boda_scheduler_loop(atf_run_event))

    await asyncio.gather(atf_task, boda_task)


def run_bot():
    while True:
        try:
            asyncio.run(main_system())
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            print(f"⚠️ خطأ عام في النظام الرئيسي: {type(e).__name__}")
            time.sleep(5)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        run_bot()
    else:
        while True:
            print("🚀 تشغيل النظام المتكامل (ATF طوال اليوم + BODA في 3:00 صباحاً)...")
            try:
                result = subprocess.run([sys.executable, __file__, "--child"])
                if result.returncode == 0:
                    break
                print(f"⚠️ إعادة تشغيل العملية بعد 10 ثوانٍ (كود: {result.returncode})")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ خطأ مراقب: {type(e).__name__}")
            time.sleep(10)