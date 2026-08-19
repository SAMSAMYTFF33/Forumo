import threading
import requests
import re
import time
from urllib.parse import unquote

def run_miner(account_name, link):
    sess = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10)',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    # استخراج البيانات من الرابط
    match = re.search(r'tgWebAppData=([^&]+)', link)
    data = unquote(match.group(1)) if match else link

    print(f"🚀 [{account_name}] بدء تشغيل البوت...")
    
    while True:
        try:
            # 1. المصادقة
            res = sess.post(
                "https://cloud-miner.cloud/auth_miner.php?php=1&rp=m", 
                data={'action': 'auth', 'data': data}, 
                headers=headers
            ).json()
            
            if res.get('success') != 'true':
                print(f"❌ [{account_name}] فشل المصادقة، يرجى تحديث الرابط.")
                break
                
            auth_link = res['auth_link'].replace('\\/', '/')

            # 2. فحص حالة التعدين
            html = sess.get(auth_link, headers=headers).text
            finish_match = re.search(r'mining_finish\s*=\s*([\d.]+)', html)
            finish_time = float(finish_match.group(1)) if finish_match else 0

            # 3. بدء التعدين إذا كان متوقفاً
            if finish_time <= time.time():
                print(f"🔄 [{account_name}] التعدين متوقف، جاري التفعيل...")
                sess.get(
                    "https://cloud-miner.cloud/AJAX/mining_control.php", 
                    params={'action': 'start_mining'}, 
                    headers=headers
                )
                
                # تحديث الوقت بعد التفعيل
                html = sess.get(auth_link, headers=headers).text
                finish_match = re.search(r'mining_finish\s*=\s*([\d.]+)', html)
                finish_time = float(finish_match.group(1)) if finish_match else time.time() + (4 * 3600)

            # 4. حساب وقت النوم
            wait = max(0, finish_time - time.time())
            hours, remainder = divmod(wait, 3600)
            minutes, _ = divmod(remainder, 60)
            
            print(f"✅ [{account_name}] التعدين نشط. سأنام لمدة {int(hours)} ساعة و {int(minutes)} دقيقة...")
            time.sleep(wait + 10) # إضافة 10 ثواني كضمان
            
        except Exception as e:
            print(f"⚠️ [{account_name}] حدث خطأ: {e}. سأحاول مجدداً بعد دقيقة...")
            time.sleep(60)

# قائمة الحسابات ورئوابطها
accounts = [
    {
        "name": "الحساب الأول (Xituc)",
        "link": """https://cloud-miner.cloud/auth_miner.php?rp=m#tgWebAppData=query_id%3DAAFypmh7AgAAAHKmaHvlpB-o%26user%3D%257B%2522id%2522%253A6365423218%252C%2522first_name%2522%253A%2522%25E3%2583%25A1%25E2%2581%25A0%2520SKATE%25E3%2583%25A1%25F0%259F%2592%259A%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522Xituc%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252F-w-OBX620cikWaU1XrLeP_B35IAiph9Gd60Lt_Oe1iPojNspdmw1nL1IML3IvL1e.svg%2522%257D%26auth_date%3D1787080735%26signature%3Dos4AwF4mgjP3hZYvKVcLwNGUPi6kPQHjdZQcBN5koT_fnEbHAVCrOk9SWyHEuAn8TIIFM0bshoqLTLEQ78tBBA%26hash%3D78f34ab9dfc8e9f65dc27d02335ec536e1172cc9cbcf73471bb9afc753c1e278&tgWebAppVersion=9.6&tgWebAppPlatform=android"""
    },
    {
        "name": "الحساب الثاني (gz_73)",
        "link": """https://cloud-miner.cloud/auth_miner.php?rp=m#tgWebAppData=query_id%3DAAF9jkdHAwAAAH2OR0c2vai2%26user%3D%257B%2522id%2522%253A7638322813%252C%2522first_name%2522%253A%2522gz%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522gz_73%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252FvyjrX4xmHCzrkZOZNqs6Wi5yJLTYuj9yn3OK9kDQID00rFDeZVpiDqZ9DKEIKQ_y.svg%2522%257D%26auth_date%3D1787089461%26signature%3Dvmh4YpArdubdsQ9abZlRZ-2W6lu7xe24KIHI-Md32TBwc8JqSN8tqK9ur1ou9sb8o1OVPZsWSWWJkMoYhusrDg%26hash%3D33faff30b8ced319f14280a7339f4f356537fa020dae0fb2361ac959333326a9&tgWebAppVersion=9.6&tgWebAppPlatform=android"""
    }
]

# تشغيل الحسابات بشكل متوازي
threads = []
for acc in accounts:
    t = threading.Thread(target=run_miner, args=(acc["name"], acc["link"]))
    t.start()
    threads.append(t)

# الانتظار لضمان استمرار عمل المسارات
for t in threads:
    t.join()