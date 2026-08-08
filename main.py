import asyncio, time, random, urllib.parse, aiohttp
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters

BOT_TOKEN = "8976290159:AAH10zmWMqZ2QbSx5bBxf9ckoUAwuU0Rhic"
ALLOWED_USER_IDS = {7638322813, 97755684}
BOT_PASSWORD = "SAMSAM@@2026"

BOT_U = "monsterland_bot"
APP_URL = "https://lets.playmonsterland.com"
API_USER = f"{APP_URL}/api/user?include=monsters"
API_VITALS = f"{APP_URL}/api/vitals"
API_ADS = f"{APP_URL}/api/ads/create-task"
API_RES = f"{APP_URL}/api/ads/task-result"
API_DONE = f"{APP_URL}/api/ads/complete"

ITEMS = {"food": "magic_apple", "hygiene": "magic_towel", "energy": "wizard_coffee"}
PASS, CREDS, THRESH, DELAY = range(4)

db, ok_users = {}, set()


def allowed(uid): return uid in ALLOWED_USER_IDS
def udb(uid): return db.setdefault(uid, {"idx": 0, "accs": []})
def acc(uid):
    d = udb(uid)
    if not d["accs"]: return None
    d["idx"] = min(d["idx"], len(d["accs"]) - 1)
    return d["accs"][d["idx"]]

def headers(tok):
    return {"authority": "lets.playmonsterland.com", "accept": "*/*", "authorization": tok,
            "content-type": "application/json", "origin": APP_URL, "referer": APP_URL + "/",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"}


def parse_creds(text):
    """
    يتعرف على API_ID / API_HASH / SESSION بغض النظر عن الترتيب أو الصيغة.
    يدعم: كل قيمة بسطر، أو الكل بسطر واحد، مع أو بدون "key = value".
    """
    # نقسّم بالأسطر أولًا، وكل سطر نشيل منه "شيء=" إذا وُجدت (أول = فقط، حتى لا نقطع الـ session)
    raw_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    cleaned = []
    for l in raw_lines:
        if "=" in l:
            key, val = l.split("=", 1)
            cleaned.append(val.strip().strip('"\''))
        else:
            cleaned.append(l.strip().strip('"\''))

    # لو كل شي جا بسطر واحد (مفصول بمسافات)، نفكّه كمان كخيار احتياطي
    if len(cleaned) == 1 and " " in cleaned[0]:
        cleaned = cleaned[0].split()
        cleaned = [c.strip('"\',:=') for c in cleaned]

    aid = hsh = sess = None
    for t in cleaned:
        t = t.strip()
        if not t:
            continue
        if t.isdigit() and 5 <= len(t) <= 15 and not aid:
            aid = t
        elif len(t) == 32 and all(c in '0123456789abcdefABCDEF' for c in t) and not hsh:
            hsh = t
        elif len(t) > 50 and not sess:
            sess = t

    return aid, hsh, sess


# ============== أزرار (بدون أي تغيير) ==============

def main_kb(uid):
    a = acc(uid)
    if not a: return InlineKeyboardMarkup([[InlineKeyboardButton("➕ إضافة حساب", callback_data="add")]])
    ads = "الخدمة ADS قيد تشغيل 🟢" if a["ads"] else "الخدمة ADS متوقفة 🔴"
    noads = "تنفيد بدون ADS مشغل 🟢" if a["noads"] else "تنفيد بدون ADS متوقف 🔴"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 {a['name']} 🔄", callback_data="accs")],
        [InlineKeyboardButton(ads, callback_data="t_ads")],
        [InlineKeyboardButton(noads, callback_data="t_noads")],
        [InlineKeyboardButton("📊 معلومات الوحش الحالية", callback_data="info")],
        [InlineKeyboardButton("Setting ⚙️", callback_data="settings")],
        [InlineKeyboardButton("🎯 تنفيذ مباشر", callback_data="direct")],
    ])

def accs_kb(uid):
    d = udb(uid)
    kb = [[InlineKeyboardButton(("✅" if i == d["idx"] else "🔘") + " " + a["name"], callback_data=f"sw_{i}")]
          for i, a in enumerate(d["accs"])]
    kb += [[InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add")]]
    if d["accs"]: kb += [[InlineKeyboardButton("🗑️ حذف حساب", callback_data="deltmenu")]]
    kb += [[InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
    return InlineKeyboardMarkup(kb)

def del_kb(uid):
    kb = [[InlineKeyboardButton(f"❌ حذف {a['name']}", callback_data=f"del_{i}")] for i, a in enumerate(udb(uid)["accs"])]
    kb += [[InlineKeyboardButton("🔙 إلغاء ورجوع", callback_data="accs")]]
    return InlineKeyboardMarkup(kb)

def info_text(m, p, a):
    v = m.get("vitals", {}) if m else {}
    t = (f"📊 **معلومات الحساب:**\n\n🍎 **نسبة magic food:** `{v.get('food',0):.2f}%`\n"
         f"🧻 **نسبة wash:** `{v.get('hygiene',0):.2f}%`\n☕️ **نسبة energy:** `{v.get('energy',0):.2f}%`\n"
         f"💰 **عدد Lumis:** `{p.get('lumis',0) if p else 0}`\n")
    if a and a.get("sched", 0) > 0:
        rem = int(a["sched"] - time.time())
        t += f"\n⏳ **سيتم شراء {a.get('sv','عنصر')} تلقائياً بعد:** `{rem}` **ثانية**" if rem > 0 else "\n⏳ **جاري تنفيذ عملية شراء الآن...**"
    return t


# ============== منطق اللعبة ==============

async def get_monster(aid, ahash, sess, tok=None):
    if tok:
        async with aiohttp.ClientSession() as s:
            async with s.get(API_USER, headers=headers(tok), timeout=10) as r:
                if r.status == 200:
                    d = await r.json()
                    ms = d.get("monsters", [])
                    if ms: return True, ms[0], d.get("profile", {}), tok, None
    try:
        async with TelegramClient(StringSession(sess), int(aid), ahash) as c:
            bot = await c.get_input_entity(BOT_U)
            wv = await c(RequestWebViewRequest(peer=bot, bot=bot, platform="android", from_bot_menu=False, url=APP_URL))
            init = wv.url.split("tgWebAppData=")[1].split("&tgWebAppVersion")[0]
            ntok = f"tma {urllib.parse.unquote(init)}"
            async with aiohttp.ClientSession() as s:
                async with s.get(API_USER, headers=headers(ntok), timeout=10) as r:
                    if r.status != 200: return False, None, None, None, f"خطأ سيرفر ({r.status})"
                    d = await r.json()
                    ms = d.get("monsters", [])
                    if not ms: return False, None, None, None, "لا يوجد وحش."
                    return True, ms[0], d.get("profile", {}), ntok, None
    except Exception as e:
        return False, None, None, None, f"فشل الاتصال: {e}"

async def buy_direct(tok, mid, item):
    async with aiohttp.ClientSession() as s:
        async with s.post(API_VITALS, headers=headers(tok), json={"monsterId": mid, "itemId": item, "action": "purchase"}, timeout=15) as r:
            return r.status

async def buy_with_ad(tok, mid, item):
    async with aiohttp.ClientSession() as s:
        async with s.post(API_ADS, headers=headers(tok), json={"action": "vitals", "metadata": {"monsterId": mid, "itemId": item}}, timeout=15) as r:
            if r.status != 200: return r.status
            tx = (await r.json()).get("adTxId")
        if not tx: return None
        await asyncio.sleep(random.randint(8, 12))
        async with s.get(f"{API_RES}?txId={tx}", headers=headers(tok), timeout=15): pass
        async with s.post(API_DONE, headers=headers(tok), json={"adTxId": tx, "provider": "gigapub"}, timeout=15) as r:
            return r.status

async def bg_worker():
    while True:
        try:
            for uid, d in list(db.items()):
                if not allowed(uid): continue
                for a in d["accs"]:
                    if not a["ads"] and not a["noads"]:
                        a["sched"] = 0
                        continue
                    ok, m, p, tok, _ = await get_monster(a["aid"], a["ahash"], a["sess"], a.get("tok"))
                    if not ok: continue
                    a["tok"] = tok
                    mid, v, th, now = m.get("_id"), m.get("vitals", {}), a["th"], time.time()
                    target = next(((vt, it) for vt, it in ITEMS.items() if v.get(vt, 100) < th), None)
                    if target:
                        vt, it = target
                        if a.get("sched", 0) == 0:
                            lo, hi = a.get("delay", (8, 16))
                            a["sched"] = now + random.randint(lo, hi)
                            a["sv"] = vt
                        elif now >= a["sched"]:
                            if a["noads"]: await buy_direct(a["tok"], mid, it)
                            elif a["ads"]: await buy_with_ad(a["tok"], mid, it)
                            a["sched"] = 0
                    else:
                        a["sched"] = 0
            await asyncio.sleep(10)
        except Exception:
            await asyncio.sleep(10)


# ============== الواجهة ==============

async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not allowed(uid):
        await u.message.reply_text("⛔ غير مصرح لك.")
        return ConversationHandler.END
    if uid not in ok_users:
        await u.message.reply_text("🔐 أدخل كلمة السر:")
        return PASS
    a = acc(uid)
    if not a:
        await u.message.reply_text("أرسل بيانات الحساب (بأي ترتيب):\nAPI_ID\nAPI_HASH\nSESSION", parse_mode="Markdown")
        return CREDS
    ok, m, p, tok, _ = await get_monster(a["aid"], a["ahash"], a["sess"], a.get("tok"))
    if ok: a["tok"] = tok
    txt = info_text(m, p, a) if ok else "🏠 القائمة الرئيسية:"
    await u.message.reply_text(txt, reply_markup=main_kb(uid), parse_mode="Markdown")
    return ConversationHandler.END

async def on_pass(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not allowed(uid): return ConversationHandler.END
    if u.message.text.strip() == BOT_PASSWORD:
        ok_users.add(uid)
        if not acc(uid):
            await u.message.reply_text("✅ تم!\nأرسل بيانات الحساب (بأي ترتيب):\nAPI_ID\nAPI_HASH\nSESSION", parse_mode="Markdown")
            return CREDS
        await u.message.reply_text("✅ تم!\n\n🏠 القائمة الرئيسية:", reply_markup=main_kb(uid))
        return ConversationHandler.END
    await u.message.reply_text("❌ كلمة السر غلط. أعد المحاولة:")
    return PASS

async def on_creds(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not allowed(uid) or uid not in ok_users: return ConversationHandler.END
    aid, ah, sess = parse_creds(u.message.text.strip())
    if not (aid and ah and sess):
        await u.message.reply_text("⚠️ البيانات غير مكتملة أو غير مفهومة. أرسلها من جديد (كل قيمة بسطر أفضل):")
        return CREDS
    msg = await u.message.reply_text("⏳ جاري التحقق...")
    ok, m, p, tok, err = await get_monster(aid, ah, sess)
    if not ok:
        await msg.edit_text(f"❌ {err}\n\nأعد الإرسال:")
        return CREDS
    d = udb(uid)
    a = {"aid": aid, "ahash": ah, "sess": sess, "tok": tok, "name": m.get("name", "وحش"),
         "mid": m.get("_id"), "ads": False, "noads": False, "th": 55, "delay": (8, 16), "sched": 0, "sv": None}
    d["accs"].append(a)
    d["idx"] = len(d["accs"]) - 1
    await msg.edit_text(f"✅ **تم إضافة الحساب!**\n\n{info_text(m, p, a)}", parse_mode="Markdown")
    await u.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=main_kb(uid))
    return ConversationHandler.END

async def on_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    uid = u.effective_user.id
    if not allowed(uid) or uid not in ok_users:
        await q.edit_message_text("⛔ غير مصرح لك.")
        return ConversationHandler.END
    data, d, a = q.data, udb(uid), acc(uid)

    if data == "direct":
        if not a: return
        kb = [[InlineKeyboardButton("🍎 Magic Food", callback_data="b_food")],
              [InlineKeyboardButton("🧻 Wash", callback_data="b_hygiene")],
              [InlineKeyboardButton("☕️ Energy", callback_data="b_energy")],
              [InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        await q.edit_message_text("🎯 **اختر العنصر:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    if data.startswith("b_"):
        if not a: return
        vt = data[2:]
        await q.edit_message_text(f"⚡ جاري شراء **{vt}**...", parse_mode="Markdown")
        st = await buy_direct(a["tok"], a["mid"], ITEMS[vt])
        txt = f"✅ تم شراء **{vt}** بنجاح!" if st == 200 else f"⚠️ فشل. كود: {st}"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_kb(uid))
        return

    if data == "settings":
        if not a: return
        lo, hi = a.get("delay", (8, 16))
        kb = [[InlineKeyboardButton("📊 تعديل النسبة", callback_data="set_th")],
              [InlineKeyboardButton("⏱️ تعديل المهلة", callback_data="set_delay")],
              [InlineKeyboardButton("🔙 رجوع", callback_data="back")]]
        await q.edit_message_text(f"⚙️ **إعدادات ({a['name']})**\n\n🔹 النسبة: `{a['th']}%`\n🔹 المهلة: `{lo}`-`{hi}` ث",
                                   parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data == "set_th":
        await q.edit_message_text("📊 أدخل نسبة جديدة (مثال: 55):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء ❌", callback_data="cancel")]]))
        return THRESH

    if data == "set_delay":
        await q.edit_message_text("⏱️ أدخل المهلة بصيغة `min-max` (مثال: 8-16، أقل رقم 3):", parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("إلغاء ❌", callback_data="cancel")]]))
        return DELAY

    if data == "cancel":
        await q.edit_message_text("تم الإلغاء.", reply_markup=main_kb(uid))
        return ConversationHandler.END

    if data == "accs":
        await q.edit_message_text("🔄 **إدارة الحسابات**", reply_markup=accs_kb(uid), parse_mode="Markdown")
    elif data.startswith("sw_"):
        i = int(data[3:])
        if 0 <= i < len(d["accs"]):
            d["idx"] = i
            await q.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=main_kb(uid))
    elif data == "add":
        await q.edit_message_text("📥 أرسل بيانات الحساب (بأي ترتيب):\nAPI_ID\nAPI_HASH\nSESSION", parse_mode="Markdown")
        return CREDS
    elif data == "deltmenu":
        await q.edit_message_text("🗑️ **اختر للحذف:**", reply_markup=del_kb(uid))
    elif data.startswith("del_"):
        i = int(data[4:])
        if 0 <= i < len(d["accs"]):
            d["accs"].pop(i)
            d["idx"] = 0
            await q.message.reply_text("🏠 القائمة الرئيسية:", reply_markup=main_kb(uid))
    elif data in ("back", "info"):
        if a:
            ok, m, p, tok, _ = await get_monster(a["aid"], a["ahash"], a["sess"], a.get("tok"))
            if ok:
                a["tok"] = tok
                await q.edit_message_text(info_text(m, p, a), reply_markup=main_kb(uid), parse_mode="Markdown")
                return
        await q.edit_message_text("🏠 القائمة الرئيسية:", reply_markup=main_kb(uid))
    elif data == "t_ads":
        if a:
            a["ads"] = not a["ads"]
            if a["ads"]: a["noads"] = False
            await q.edit_message_reply_markup(reply_markup=main_kb(uid))
    elif data == "t_noads":
        if a:
            a["noads"] = not a["noads"]
            if a["noads"]: a["ads"] = False
            await q.edit_message_reply_markup(reply_markup=main_kb(uid))

async def on_thresh(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not allowed(uid) or uid not in ok_users: return ConversationHandler.END
    t = u.message.text.strip()
    if t in ("إلغاء", "/cancel"):
        await u.message.reply_text("تم الإلغاء.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    if not t.isdigit() or int(t) > 70:
        await u.message.reply_text("⚠️ رقم صحيح فقط (حتى 70).")
        return THRESH
    a = acc(uid)
    if a: a["th"] = int(t)
    await u.message.reply_text("✅ تم التحديث.", reply_markup=main_kb(uid))
    return ConversationHandler.END

async def on_delay(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not allowed(uid) or uid not in ok_users: return ConversationHandler.END
    t = u.message.text.strip()
    if t in ("إلغاء", "/cancel"):
        await u.message.reply_text("تم الإلغاء.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    try:
        lo, hi = map(int, t.split("-"))
        if lo < 3:
            await u.message.reply_text("⚠️ أقل رقم مسموح 3. أعد الإدخال:")
            return DELAY
        if hi < lo:
            await u.message.reply_text("⚠️ الحد الأقصى يجب أن يكون ≥ الأدنى. أعد الإدخال:")
            return DELAY
        a = acc(uid)
        if a: a["delay"] = (lo, hi)
        await u.message.reply_text(f"✅ تم: {lo}-{hi} ث.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    except Exception:
        await u.message.reply_text("⚠️ صيغة غلط. مثال: `8-16`", parse_mode="Markdown")
        return DELAY

async def on_startup(app): asyncio.create_task(bg_worker())

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start), CallbackQueryHandler(on_button)],
        states={
            PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_pass)],
            CREDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, on_creds)],
            THRESH: [CallbackQueryHandler(on_button), MessageHandler(filters.TEXT & ~filters.COMMAND, on_thresh)],
            DELAY: [CallbackQueryHandler(on_button), MessageHandler(filters.TEXT & ~filters.COMMAND, on_delay)],
        },
        fallbacks=[CommandHandler("start", cmd_start), CallbackQueryHandler(on_button)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    print("🚀 البوت يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()