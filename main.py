# ============================ ======== ==========================================
# ⚙️ مفاتيح التحكم بكل حساب على حدة (1 = يعمل | 0 = متوقف)
# ==================================== ==========================================
MINER_ACCOUNT_1 = 1     # Cloud Miner - Xituc
MINER_ACCOUNT_2 = 1     # Cloud Miner - gz_73

ATF_ACCOUNT_1   = 0     # ATF - الثاني سابقاً
ATF_ACCOUNT_2   = 1     # ATF - حمز 1 
ATF_ACCOUNT_3   = 1     # ATF - الحساب الثالث
ATF_ACCOUNT_4   = 1     # ATF  حمز 2 
# ==============================================================================


import threading
import requests
import re
import time
from urllib.parse import unquote

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
# 🟦 الجزء الأول: Cloud Miner (Threading + requests)
# ==============================================================================

def run_miner(account_name, link):
    sess = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10)',
        'X-Requested-With': 'XMLHttpRequest'
    }
    match = re.search(r'tgWebAppData=([^&]+)', link)
    data = unquote(match.group(1)) if match else link

    print(f"🚀 [{account_name}] Miner: تشغيل")

    while True:
        try:
            res = sess.post(
                "https://cloud-miner.cloud/auth_miner.php?php=1&rp=m",
                data={'action': 'auth', 'data': data},
                headers=headers
            ).json()

            if res.get('success') != 'true':
                print(f"❌ [{account_name}] Miner: فشل المصادقة، حدّث الرابط")
                break

            auth_link = res['auth_link'].replace('\\/', '/')
            html = sess.get(auth_link, headers=headers).text
            finish_match = re.search(r'mining_finish\s*=\s*([\d.]+)', html)
            finish_time = float(finish_match.group(1)) if finish_match else 0

            if finish_time <= time.time():
                sess.get(
                    "https://cloud-miner.cloud/AJAX/mining_control.php",
                    params={'action': 'start_mining'},
                    headers=headers
                )
                html = sess.get(auth_link, headers=headers).text
                finish_match = re.search(r'mining_finish\s*=\s*([\d.]+)', html)
                finish_time = float(finish_match.group(1)) if finish_match else time.time() + (4 * 3600)

            wait = max(0, finish_time - time.time())
            h, rem = divmod(wait, 3600)
            m, _ = divmod(rem, 60)
            print(f"✅ [{account_name}] Miner: نشط - نوم {int(h)}س {int(m)}د")
            time.sleep(wait + 10)

        except Exception as e:
            print(f"⚠️ [{account_name}] Miner: {type(e).__name__} - إعادة محاولة بعد دقيقة")
            time.sleep(60)


MINER_ACCOUNTS = [
    {
        "enabled": MINER_ACCOUNT_1 == 1,
        "name": "الحساب الأول (Xituc)",
        "link": """https://cloud-miner.cloud/auth_miner.php?rp=m#tgWebAppData=query_id%3DAAFypmh7AgAAAHKmaHvlpB-o%26user%3D%257B%2522id%2522%253A6365423218%252C%2522first_name%2522%253A%2522%25E3%2583%25A1%25E2%2581%25A0%2520SKATE%25E3%2583%25A1%25F0%259F%2592%259A%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522Xituc%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252F-w-OBX620cikWaU1XrLeP_B35IAiph9Gd60Lt_Oe1iPojNspdmw1nL1IML3IvL1e.svg%2522%257D%26auth_date%3D1787080735%26signature%3Dos4AwF4mgjP3hZYvKVcLwNGUPi6kPQHjdZQcBN5koT_fnEbHAVCrOk9SWyHEuAn8TIIFM0bshoqLTLEQ78tBBA%26hash%3D78f34ab9dfc8e9f65dc27d02335ec536e1172cc9cbcf73471bb9afc753c1e278&tgWebAppVersion=9.6&tgWebAppPlatform=android"""
    },
    {
        "enabled": MINER_ACCOUNT_2 == 1,
        "name": "الحساب الثاني (gz_73)",
        "link": """https://cloud-miner.cloud/auth_miner.php?rp=m#tgWebAppData=query_id%3DAAF9jkdHAwAAAH2OR0c2vai2%26user%3D%257B%2522id%2522%253A7638322813%252C%2522first_name%2522%253A%2522gz%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522gz_73%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252FvyjrX4xmHCzrkZOZNqs6Wi5yJLTYuj9yn3OK9kDQID00rFDeZVpiDqZ9DKEIKQ_y.svg%2522%257D%26auth_date%3D1787089461%26signature%3Dvmh4YpArdubdsQ9abZlRZ-2W6lu7xe24KIHI-Md32TBwc8JqSN8tqK9ur1ou9sb8o1OVPZsWSWWJkMoYhusrDg%26hash%3D33faff30b8ced319f14280a7339f4f356537fa020dae0fb2361ac959333326a9&tgWebAppVersion=9.6&tgWebAppPlatform=android"""
    }
]


def start_miner_threads():
    """يشغّل حسابات Cloud Miner المفعّلة فقط، كخيوط خلفية (daemon)."""
    active = [a for a in MINER_ACCOUNTS if a["enabled"]]
    if not active:
        print("⚠️ Miner: كل الحسابات متوقفة")
        return []
    threads = []
    for acc in active:
        t = threading.Thread(target=run_miner, args=(acc["name"], acc["link"]), daemon=True)
        t.start()
        threads.append(t)
    return threads


# ==============================================================================
# 🟩 الجزء الثاني: ATF Bot (asyncio + Telethon)
# ==============================================================================

ACCOUNTS_CONFIG = [
    {
        "enabled": ATF_ACCOUNT_1 == 1,
        "account_name": "الحساب الأول (الثاني سابقاً)",
        "api_id": 31568734,
        "api_hash": "7286e8c92ccc4dc698d771664bf71700",
        "session_string": "1BJWap1sBuxjvSEbIQZYZ_pwBJo9M9XfWiyMQLlzTt48Ku7r1-_gW20dBsDHYtoKza6DvS1cZQsPc5e5wwJBz-SO-t4iEqHXU68xVGFVZN5gnTLUPY7Jztm21a2Snmy2SgsIGg0NK5KuxO39moAE8vnGPsdb-BDCxrvRIpxYWwEi_CYp0NZ_Z2gAfqK8ZZIM36Gyq4u0yVU_xSYdl8HmNaV0Imop8p9MnOQIHyXRswfgDSz4dMctk3_AMbsg0i7UCJ3yoHH97-UjYFqBHyi2j2LxcQrezwaJeVYvLKxmpxCf-jCwPK_a9vHaM2L7QV6wfcBsS1jgiwVVpik4XXj5aGQ18UdkCOTU=",
        "device_prefix": "dev-B",
        "boost_enabled": True,
        "task_interval": 7500,
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
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu2AYJJY6BirfGnzglAB8ppxWTbWSqjEvsAjT01QZCU-_LkiLVzmOJcpiD4NsR2UeXCb6Ujl9wuvUl7diZMgaNoV3L-RnfwKIkJFUzQ2F6txstq0gxgyjfPwQnoYhFLJGWV-8RI4bCDikGqmAzSYtwaJ7YYBP0UWPBEAAUT6cby6QAZfYAO6IXTLktrR7E48X9j5dXApa1wh8T_WPZKP5IRE8njO53kiN9_NfrBqLEz_7vogPGcDxDo9XU3S4wQ-DZTB4iEmXzzZ3dxcYrWUqpmtGLho0Uc_uS3amDa7hlg3tzo6ngvXiygMVkf8xjkxI6lAcC63gt527D43ePyRvLxY=",
        "device_prefix": "dev-D",
        "boost_enabled": True,
        "task_interval": 7500,
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
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1wBu7Oc6U4ZneKR0j1wHryzKHetYqBSdS8LkfdQfip8imnJ4bXGoRP1aptufqTcmio8XKpmGtKJXVxsJ5g_h5C42NpjWVQVZjotwR1vkz6abxa6NjON1knvuCw2tXyJCgEmjRfRVE4uxobS_fJat8a-rgSrMWIpe33NXmnu8mh4ZuauXvilX9XGDHmRynsTz7fJvT58SxtnUY6m3c5p3qS2zlmt7caVviwDTZBmlPejSvcDDx9zrRsEItxo7KGv6XGIqy6cRLrADeeLHh444BnjsYZEE6JdWUu6aWbHB7moshhEymotE8B7pOvRBl2JVszY0ZK3eK59KQH-Jly81GqXZqs=",
        "device_prefix": "dev-E",
        "boost_enabled": False,        # بدون تسريع تعدين
        "task_interval": 7500,         # تنفيذ المهام كل 2س و 5د (7500 ثانية)
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.103 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "en-US,en;q=0.9,ar-MA;q=0.8"
        }
    },
    {
        "enabled": ATF_ACCOUNT_4 == 1,
        "account_name": "الحساب الرابع الجديد",
        "api_id": 38197378,
        "api_hash": "1efeb1db162150616801ae759799ca97",
        "session_string": "1BJWap1sBu4j9pNRXRJyJM8cFNQA4qSBm7h1yYxoSdldMF9cPYV3_bLr0d_ksxdqoxhqZydscC6lPpb6tup3RnrXm17QoueAx3NZq7_wux4vWMFSj3WoyrHDkSmLlC4XyayKncCXbdMHJYGwL4I5wZwGUUrRzk13rVsXHWaXjtJPhNunpSEHGKKe_m_FuBwCno5dxpi5yWOb7Js1lPuHmE3Vbep7PnQrsIExZ_SkcLiJX2adVp84AZOi8_14ok1nJ6Ezitlng6ONN8pK7GkxU25q36lLiQ7mP8QWwcPHiWoLA48FFfbYVnrK3uS8XWnLSCAtEVwrMqd9igyRNKDqObz_3S3VzyEs=",
        "device_prefix": "dev-F",
        "boost_enabled": False,        # بدون تسريع تعدين
        "task_interval": 7500,         # تنفيذ المهام كل 2س و 5د (7500 ثانية)
        "user_agent": "Mozilla/5.0 (Linux; Android 13; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        "extra_headers": {
            "sec-ch-ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"
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

RETRY_CLAIM_DELAY_ATF = 30
MAX_CLAIM_RETRY_TIME_ATF = 600

TASKS_ATF = [
    {"id": "youtube_like_comment", "min_seconds": 30, "name": "YouTube"},
    {"id": "twitter_retweet", "min_seconds": 30, "name": "Twitter"},
    {"id": "website_visit", "min_seconds": 0, "name": "Website"},
    {"id": "telegram_react_latest", "min_seconds": 20, "name": "React"}
]


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
    """ينفّذ مهمة واحدة، يرجّع (نجاح: bool, رسالة: str)"""
    task_id = task["id"]
    task_name = task["name"]

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


async def atf_tasks_worker(session, headers, me, init_data, react_post, lock, device_prefix, acc_name, interval):
    while True:
        async with lock:
            react_post_link = react_post.get("link") if isinstance(react_post, dict) else None
            ok_count = 0
            for task in TASKS_ATF:
                success, _ = await do_task_atf(session, headers, task, me.id, init_data, device_prefix, react_post_link)
                if success:
                    ok_count += 1
            print(f"📝 [{acc_name}] مهام: {ok_count}/{len(TASKS_ATF)} ناجحة")

        await asyncio.sleep(interval)


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

            tasks_to_run = [
                atf_tasks_worker(
                    http_session, headers, me, init_data, react_post, lock, 
                    acc_config["device_prefix"], acc_name, acc_config.get("task_interval", 7500)
                )
            ]

            # تشغيل تسريع التعدين فقط للحسابات المسموح لها (الأول والثاني)
            if acc_config.get("boost_enabled", True):
                tasks_to_run.append(
                    atf_boost_worker(http_session, headers, me, init_data, lock, acc_config["device_prefix"])
                )

            await asyncio.gather(*tasks_to_run)
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
# 🟨 نقطة التشغيل الموحدة
# ==============================================================================

def run_bot():
    start_miner_threads()
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
            print("🚀 تشغيل العملية (Cloud Miner + ATF)...")
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
