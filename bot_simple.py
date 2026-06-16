import time
import requests
import re
import threading
from bs4 import BeautifulSoup
from telebot import types
import telebot

# ==========================================
# الإعدادات — غيّر هنا فقط
# ==========================================
TELEGRAM_TOKEN = "8650391038:AAHlGK6jM2rlR8IdJ_DCLmuEGrVe12nre7M"

BASE_URL      = "https://forumok.com"
LOGIN_URL     = "https://forumok.com/login"
TARGET_URL    = "https://forumok.com/orders-search/socio"
CONFIRMED_URL = "https://forumok.com/publisher-requests/socio/confirmed"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": BASE_URL
}

# ==========================================
# الحساب محفوظ في الذاكرة فقط (يُمسح عند إعادة التشغيل)
# ==========================================
saved_account = {"email": None, "password": None}

bot = telebot.TeleBot(TELEGRAM_TOKEN)

user_session   = {}   # chat_id -> requests.Session
user_steps     = {}   # chat_id -> "email" | "password"
user_temp      = {}   # chat_id -> بيانات مؤقتة أثناء التسجيل
auto_hunt_flag = {}   # chat_id -> bool

# ==========================================
# تسجيل الدخول
# ==========================================
def do_login(email, password):
    sess = requests.Session()
    try:
        sess.get(BASE_URL, headers=HEADERS, timeout=10)
        r = sess.post(LOGIN_URL, data={
            "signin[username]": email,
            "signin[password]": password,
            "signin[remember]": "1",
            "signin[refer_url]": "@office_initial"
        }, headers=HEADERS, timeout=10)
        if r.status_code == 200 and "Выход" in r.text:
            return sess
    except Exception:
        pass
    return None

def get_session(chat_id):
    sess = user_session.get(chat_id)
    if sess:
        try:
            r = sess.get(BASE_URL, headers=HEADERS, timeout=8)
            if "Выход" in r.text:
                return sess
        except Exception:
            pass
    email    = saved_account["email"]
    password = saved_account["password"]
    if not email:
        return None
    sess = do_login(email, password)
    if sess:
        user_session[chat_id] = sess
    return sess

# ==========================================
# جلب المهام
# ==========================================
def fetch_tasks(session):
    try:
        r = session.get(TARGET_URL, headers=HEADERS, timeout=12)
        if "Выход" not in r.text:
            return None
        soup  = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        tasks = []
        if table:
            for row in table.find_all("tr")[1:]:
                if any(c in row.get("class", []) for c in ["taken-list", "gray-list"]):
                    continue
                cells = row.find_all("td")
                if len(cells) >= 3:
                    links = cells[-1].find_all("a", href=True)
                    if links:
                        url = links[0]["href"]
                        if not url.startswith("http"):
                            url = BASE_URL + url
                        if "?ok=1" not in url:
                            url += "?ok=1" if "?" not in url else "&ok=1"
                        tasks.append(url)
        return tasks
    except Exception:
        return None

# ==========================================
# اصطحاب مهمة
# ==========================================
def take_task(session, task_url):
    try:
        r = session.get(task_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return False
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find("form", action=re.compile(r"batch|order_request"))
        if not form:
            return False

        post_url = f"{BASE_URL}/order_request_socio/batch"
        if form.get("action"):
            act = form["action"]
            post_url = act if act.startswith("http") else BASE_URL + act

        post_data = {"batch_action": "batchConfirm"}
        for inp in form.find_all("input", type="hidden"):
            if inp.get("name"):
                post_data[inp["name"]] = inp.get("value", "")

        ids = [cb.get("value") for cb in form.find_all("input", class_="batch_checkbox") if cb.get("value")]
        if not ids:
            f = form.find("input", name="ids[]")
            if f:
                ids = [f.get("value", "")]
        if not ids:
            return False

        post_data["ids[]"] = ids
        res = session.post(post_url, data=post_data, headers=HEADERS, timeout=10)
        return res.status_code == 200
    except Exception:
        return False

# ==========================================
# حلقة الاصطحاب التلقائي
# ==========================================
def hunt_loop(chat_id):
    taken = 0
    while auto_hunt_flag.get(chat_id, False):
        try:
            sess = get_session(chat_id)
            if not sess:
                time.sleep(30)
                continue
            tasks = fetch_tasks(sess)
            if tasks is None:
                time.sleep(30)
                continue
            for url in tasks:
                if not auto_hunt_flag.get(chat_id, False):
                    break
                if take_task(sess, url):
                    taken += 1
                    try:
                        bot.send_message(chat_id, f"✅ تم اصطحاب مهمة! المجموع: {taken}")
                    except Exception:
                        pass
                time.sleep(3)
            time.sleep(20)
        except Exception as e:
            print(f"[HUNT] {e}")
            time.sleep(30)

# ==========================================
# القائمة الرئيسية
# ==========================================
def main_menu(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not saved_account["email"]:
        markup.add(types.InlineKeyboardButton("🔑 تسجيل الدخول", callback_data="login"))
    else:
        hunting = auto_hunt_flag.get(chat_id, False)
        lbl = "🟢 الاصطحاب التلقائي: يعمل — اضغط لإيقافه" if hunting else "🔴 الاصطحاب التلقائي: متوقف — اضغط لتشغيله"
        markup.add(types.InlineKeyboardButton(lbl, callback_data="toggle_hunt"))
        markup.add(types.InlineKeyboardButton(f"👤 {saved_account['email']}", callback_data="noop"))
        markup.add(types.InlineKeyboardButton("🚪 تسجيل خروج", callback_data="logout"))
    return markup

# ==========================================
# أوامر البوت
# ==========================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    text = f"👋 أهلاً!\nالحساب: `{saved_account['email']}`" if saved_account["email"] else "👋 أهلاً! لا يوجد حساب مُسجَّل."
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_menu(chat_id))

@bot.message_handler(func=lambda m: m.chat.id in user_steps)
def handle_steps(message):
    chat_id = message.chat.id
    step = user_steps.get(chat_id)

    if step == "email":
        user_temp[chat_id] = {"email": message.text.strip()}
        user_steps[chat_id] = "password"
        bot.send_message(chat_id, "🔐 أدخل كلمة المرور:")

    elif step == "password":
        email    = user_temp.get(chat_id, {}).get("email", "")
        password = message.text.strip()
        msg = bot.send_message(chat_id, "⏳ جارٍ تسجيل الدخول...")
        sess = do_login(email, password)
        user_steps.pop(chat_id, None)
        user_temp.pop(chat_id, None)
        try:
            bot.delete_message(chat_id, msg.message_id)
        except Exception:
            pass
        if sess:
            saved_account["email"]    = email
            saved_account["password"] = password
            user_session[chat_id]     = sess
            bot.send_message(chat_id, "✅ تم تسجيل الدخول!", reply_markup=main_menu(chat_id))
        else:
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تحقق من البيانات.", reply_markup=main_menu(chat_id))

# ==========================================
# الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id    = call.message.chat.id
    message_id = call.message.message_id
    data       = call.data
    bot.answer_callback_query(call.id)

    if data == "login":
        user_steps[chat_id] = "email"
        try:
            bot.edit_message_text("📧 أدخل البريد الإلكتروني:", chat_id, message_id)
        except Exception:
            bot.send_message(chat_id, "📧 أدخل البريد الإلكتروني:")

    elif data == "toggle_hunt":
        if not saved_account["email"]:
            bot.send_message(chat_id, "⚠️ سجّل الدخول أولاً.")
            return
        hunting = auto_hunt_flag.get(chat_id, False)
        if hunting:
            auto_hunt_flag[chat_id] = False
            txt = "🔴 تم إيقاف الاصطحاب التلقائي."
        else:
            auto_hunt_flag[chat_id] = True
            threading.Thread(target=hunt_loop, args=(chat_id,), daemon=True).start()
            txt = "🟢 تم تشغيل الاصطحاب التلقائي!\nسيُخبرك البوت عند اصطحاب أي مهمة."
        try:
            bot.edit_message_text(txt, chat_id, message_id, reply_markup=main_menu(chat_id))
        except Exception:
            bot.send_message(chat_id, txt, reply_markup=main_menu(chat_id))

    elif data == "logout":
        auto_hunt_flag[chat_id] = False
        user_session.pop(chat_id, None)
        saved_account["email"]    = None
        saved_account["password"] = None
        try:
            bot.edit_message_text("🚪 تم تسجيل الخروج.", chat_id, message_id, reply_markup=main_menu(chat_id))
        except Exception:
            bot.send_message(chat_id, "🚪 تم تسجيل الخروج.", reply_markup=main_menu(chat_id))

    elif data == "noop":
        pass

# ==========================================
# تشغيل
# ==========================================
if __name__ == "__main__":
    print("✅ البوت يعمل...")
    bot.infinity_polling(timeout=30, long_polling_timeout=30) 
