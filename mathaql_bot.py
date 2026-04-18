#!/usr/bin/env python3
"""
MathAql Premium Bot — @MATHAQL_UZ_BOT
Spanel (Linux hosting) da ishlaydi.
 
O'rnatish:
  pip3 install python-telegram-bot==20.7 --break-system-packages
 
Ishga tushirish:
  python3 mathaql_bot.py
 
Spanel uchun:
  screen -S mathaql_bot python3 mathaql_bot.py
  yoki systemd service qiling (quyida ko'rsatilgan)
"""
 
import logging
import json
import os
import re
import random
import string
import hmac
import hashlib
import threading
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
 
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
 
# ══════════════════════════════════════════════════
# SOZLAMALAR — BU YERNI O'ZGARTIRING
# ══════════════════════════════════════════════════
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8770443554:AAEaNldDsRGWc7bLi2i-sq2t73X8WV-lXGI")
ADMIN_IDS   = [7549818189]
 
# To'lov rekvizitlari
PAYME_CARD  = "5614 6838 6188 2512"   # Humo/UzCard
CLICK_CARD  = "4916 9903 1051 3137"   # Visa/MasterCard
CARD_OWNER  = "ARZIYEVA MARIFAT"
 
# Kriptografik imzo kaliti (sayt bilan bir xil bo'lishi shart!)
SECRET_KEY  = "MATHAQL_SECRET_2024_UZ"
 
# Ma'lumotlar fayli
DATA_FILE   = Path("mathaql_data.json")
 
# ══════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("mathaql_bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)
 
# ══════════════════════════════════════════════════
# MA'LUMOTLAR BAZASI (JSON fayl)
# ══════════════════════════════════════════════════
def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"users": {}, "payments": {}, "codes": {}, "stats": {}}
 
def save_data(data: dict):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
 
def get_user(data: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {"id": user_id, "step": "start", "plan": None, "created": now_str()}
    return data["users"][uid]
 
def now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")
 
# ══════════════════════════════════════════════════
# KOD GENERATOR — MAQ-DDMM-YYYY + random
# ══════════════════════════════════════════════════
def generate_code(plan: str) -> str:
    """Har foydalanuvchiga unikal, 1 martalik kod"""
    d = datetime.now()
    dd   = d.strftime("%d")
    mm   = d.strftime("%m")
    yyyy = d.strftime("%Y")
    plan_tag = "YIL" if plan == "yearly" else "MKT" if plan == "school" else "OYL"
    unique = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"MAQ-{dd}{mm}-{yyyy}-{plan_tag}-{unique}"
 
# ══════════════════════════════════════════════════
# REJALARI
# ══════════════════════════════════════════════════
PLANS = {
    "monthly": {
        "label": "💡 Oylik Premium",
        "price": "49,000 so'm",
        "price_int": 49000,
        "days": 30,
        "desc": "1-11 sinf, DTM, AI yechuvchi, streak bonus"
    },
    "yearly": {
        "label": "🌟 Yillik Premium",
        "price": "299,000 so'm",
        "price_int": 299000,
        "days": 365,
        "desc": "Oylikdan 49% arzonroq! + MS, Boss Battle, Sertifikat"
    },
    "school": {
        "label": "🏫 Maktab Premium",
        "price": "500,000 so'm",
        "price_int": 500000,
        "days": 30,
        "desc": "30 ta o'quvchi, o'qituvchi paneli, haftalik hisobot"
    }
}
 
# ══════════════════════════════════════════════════
# /start — ASOSIY MENYU
# ══════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    u = get_user(data, user.id)
    u["name"]     = user.full_name
    u["username"] = user.username or ""
    u["step"]     = "main"
    save_data(data)
 
    text = (
        f"👋 Assalomu alaykum, *{user.first_name}*!\n\n"
        "🎓 *MathAql* — O'zbekiston №1 matematika platformasi\n"
        "mathaql.uz'da darslar ishlang, streak saqlang, DTM ga tayyorlaning!\n\n"
        "💳 *Premium sotib olish uchun quyidan tanlang:*"
    )
 
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Oylik — 49,000 so'm",  callback_data="plan_monthly")],
        [InlineKeyboardButton("🌟 Yillik — 299,000 so'm", callback_data="plan_yearly")],
        [InlineKeyboardButton("🏫 Maktab — 500,000 so'm", callback_data="plan_school")],
        [InlineKeyboardButton("❓ Savol berish",           callback_data="support")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
 
    # Admin uchun bildiruv
    if user.id not in ADMIN_IDS:
        await notify_admins(
            ctx, f"👤 Yangi foydalanuvchi:\n"
                 f"Ism: {user.full_name}\n"
                 f"@{user.username or '—'}\n"
                 f"ID: {user.id}\n"
                 f"Vaqt: {now_str()}"
        )
 
# ══════════════════════════════════════════════════
# REJA TANLASH
# ══════════════════════════════════════════════════
async def cb_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    await q.answer()
    plan = q.data.replace("plan_", "")
    p    = PLANS.get(plan)
    if not p:
        return
 
    data = load_data()
    u    = get_user(data, q.from_user.id)
    u["plan"] = plan
    u["step"] = "card_select"
    save_data(data)
 
    text = (
        f"{p['label']}\n\n"
        f"💰 Narx: *{p['price']}*\n"
        f"📅 Muddat: *{p['days']} kun*\n"
        f"✅ {p['desc']}\n\n"
        f"💳 *Qaysi karta bilan to'laysiz?*"
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟣 Humo",   callback_data=f"card_humo_{plan}"),
            InlineKeyboardButton("🔵 UzCard", callback_data=f"card_uzcard_{plan}"),
        ],
        [
            InlineKeyboardButton("💳 Visa/MC", callback_data=f"card_visa_{plan}"),
            InlineKeyboardButton("💵 Naqd",    callback_data=f"card_naqd_{plan}"),
        ],
        [InlineKeyboardButton("← Orqaga", callback_data="back_main")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
 
# ══════════════════════════════════════════════════
# KARTA TANLASH → TO'LOV MA'LUMOTLARI
# ══════════════════════════════════════════════════
async def cb_card(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q      = update.callback_query
    await q.answer()
    _, card_type, plan = q.data.split("_", 2)
    p      = PLANS.get(plan)
    if not p:
        return
 
    data = load_data()
    u    = get_user(data, q.from_user.id)
    u["card_type"] = card_type
    u["step"]      = "awaiting_payment"
 
    # To'lov ID yaratish
    pay_id = f"pay_{q.from_user.id}_{int(datetime.now().timestamp())}"
    u["current_pay_id"] = pay_id
    data["payments"][pay_id] = {
        "user_id":   q.from_user.id,
        "user_name": q.from_user.full_name,
        "username":  q.from_user.username or "",
        "plan":      plan,
        "amount":    p["price_int"],
        "card_type": card_type,
        "status":    "pending",
        "created":   now_str()
    }
    save_data(data)
 
    # Karta rekvizitlari
    if card_type in ("humo", "uzcard", "naqd"):
        card_num  = PAYME_CARD
        card_note = "Humo / UzCard"
    else:
        card_num  = CLICK_CARD
        card_note = "Visa / MasterCard"
 
    text = (
        f"✅ *To'lov ma'lumotlari:*\n\n"
        f"📦 Tarif: *{p['label']}*\n"
        f"💰 Summa: *{p['price']}*\n\n"
        f"💳 *Karta raqami:*\n"
        f"`{card_num}`\n"
        f"👤 Egasi: `{CARD_OWNER}`\n"
        f"🏦 Tur: {card_note}\n\n"
        f"📋 *Ko'chirma izohi:*\n"
        f"`MathAql {pay_id[-8:]}`\n\n"
        f"⚠️ To'lov qilgandan keyin *chek rasmini* yuboring!\n"
        f"Admin tekshirib, sizga *aktivatsiya kodi* yuboradi.\n\n"
        f"🆔 To'lov ID: `{pay_id[-12:]}`"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Chek yubordim — tasdiqlash kutaman", callback_data=f"sent_receipt_{pay_id}")],
        [InlineKeyboardButton("← Orqaga", callback_data=f"plan_{plan}")],
    ])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
 
    # Adminga xabar
    admin_text = (
        f"💳 *Yangi to'lov so'rovi!*\n\n"
        f"👤 {q.from_user.full_name} (@{q.from_user.username or '—'})\n"
        f"🆔 User ID: `{q.from_user.id}`\n"
        f"📦 Tarif: {p['label']}\n"
        f"💰 Narx: {p['price']}\n"
        f"💳 Karta: {card_type}\n"
        f"🆔 Pay ID: `{pay_id}`\n"
        f"⏰ {now_str()}"
    )
    admin_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tasdiqlash",  callback_data=f"admin_approve_{pay_id}_{plan}_{q.from_user.id}"),
        InlineKeyboardButton("❌ Rad etish",   callback_data=f"admin_reject_{pay_id}_{q.from_user.id}"),
    ]])
    await notify_admins(ctx, admin_text, reply_markup=admin_kb)
 
# ══════════════════════════════════════════════════
# CHEK YUBORILDI XABARI
# ══════════════════════════════════════════════════
async def cb_sent_receipt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("✅ Tasdiqlash kutilmoqda...")
    await q.edit_message_text(
        "⏳ *Chekingiz ko'rib chiqilmoqda...*\n\n"
        "Admin 5-15 daqiqa ichida aktivatsiya kodini yuboradi.\n\n"
        "❓ Savol bo'lsa: @mathaql_support",
        parse_mode="Markdown"
    )
 
# ══════════════════════════════════════════════════
# RASM / HUJJAT — CHEK QABUL QILISH
# ══════════════════════════════════════════════════
async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    u    = get_user(data, user.id)
 
    if u.get("step") == "awaiting_payment":
        # Foydalanuvchiga tasdiqlash xabari
        await update.message.reply_text(
            "✅ *Chekingiz qabul qilindi!*\n\n"
            "Admin tekshirib, tez orada aktivatsiya kodini yuboradi.\n"
            "Odatda 5-15 daqiqa ichida.\n\n"
            "🙏 Sabr qiling!",
            parse_mode="Markdown"
        )
 
        # Adminga chekni yuborish
        pay_id = u.get("current_pay_id", "—")
        plan   = u.get("plan", "monthly")
        p      = PLANS.get(plan, PLANS["monthly"])
        caption = (
            f"📸 *Chek keldi!*\n\n"
            f"👤 {user.full_name} (@{user.username or '—'})\n"
            f"🆔 User ID: `{user.id}`\n"
            f"📦 {p['label']} — {p['price']}\n"
            f"🆔 Pay ID: `{pay_id}`\n"
            f"⏰ {now_str()}"
        )
        admin_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash → Kod yubor",
                callback_data=f"admin_approve_{pay_id}_{plan}_{user.id}"),
            InlineKeyboardButton("❌ Rad etish",
                callback_data=f"admin_reject_{pay_id}_{user.id}"),
        ]])
        for admin_id in ADMIN_IDS:
            try:
                if update.message.photo:
                    await ctx.bot.send_photo(
                        chat_id=admin_id,
                        photo=update.message.photo[-1].file_id,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=admin_kb
                    )
                elif update.message.document:
                    await ctx.bot.send_document(
                        chat_id=admin_id,
                        document=update.message.document.file_id,
                        caption=caption,
                        parse_mode="Markdown",
                        reply_markup=admin_kb
                    )
            except Exception as e:
                log.error(f"Admin xabari xatosi: {e}")
    else:
        await update.message.reply_text(
            "📸 Rasm qabul qilindi!\n"
            "Premium sotib olish uchun /start bosing."
        )
 
# ══════════════════════════════════════════════════
# ADMIN: TASDIQLASH → KOD YUBORISH
# ══════════════════════════════════════════════════
async def cb_admin_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await q.answer("✅ Tasdiqlandi!")
 
    # callback_data: admin_approve_{pay_id}_{plan}_{user_id}
    parts   = q.data.split("_")
    # admin_approve_pay_USERID_TIMESTAMP_plan_uid
    # safe parsing:
    data_str = q.data[len("admin_approve_"):]
    # find last two underscored tokens = plan, user_id
    tokens   = data_str.rsplit("_", 2)
    pay_id   = tokens[0]
    plan     = tokens[1]
    user_id  = int(tokens[2])
 
    data   = load_data()
    code   = generate_code(plan)
    p      = PLANS.get(plan, PLANS["monthly"])
 
    # Kodni saqlash
    data["codes"][code] = {
        "plan":    plan,
        "user_id": user_id,
        "pay_id":  pay_id,
        "created": now_str(),
        "used":    False
    }
    if pay_id in data["payments"]:
        data["payments"][pay_id]["status"] = "approved"
        data["payments"][pay_id]["code"]   = code
    save_data(data)
 
    # Foydalanuvchiga kod yuborish
    user_text = (
        f"🎉 *To'lovingiz tasdiqlandi!*\n\n"
        f"📦 Tarif: *{p['label']}*\n"
        f"📅 Muddat: *{p['days']} kun*\n\n"
        f"🔑 *Aktivatsiya kodingiz:*\n"
        f"`{code}`\n\n"
        f"*Kodni qanday ishlatish:*\n"
        f"1️⃣ mathaql.uz saytiga kiring\n"
        f"2\u20e3 To'lov → 'Kodni kiritish' → Kodni yozing\n"
        f"3️⃣ ✅ Premium aktivlandi!\n\n"
        f"❓ Muammo bo'lsa: @mathaql_support\n"
        f"🙏 MathAql'dan foydalanganingiz uchun rahmat!"
    )
    try:
        await ctx.bot.send_message(
            chat_id=user_id,
            text=user_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"Foydalanuvchiga xabar yuborishda xato: {e}")
 
    # Admin xabari yangilash
    await q.edit_message_text(
        q.message.text + f"\n\n✅ *TASDIQLANDI* — Kod: `{code}`",
        parse_mode="Markdown"
    )
    log.info(f"Approved: {pay_id} → {code} → user {user_id}")
 
# ══════════════════════════════════════════════════
# ADMIN: RAD ETISH
# ══════════════════════════════════════════════════
async def cb_admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    await q.answer("❌ Rad etildi")
 
    parts   = q.data.split("_")
    data_str = q.data[len("admin_reject_"):]
    tokens   = data_str.rsplit("_", 1)
    pay_id   = tokens[0]
    user_id  = int(tokens[1])
 
    data = load_data()
    if pay_id in data["payments"]:
        data["payments"][pay_id]["status"] = "rejected"
    save_data(data)
 
    try:
        await ctx.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ *To'lovingiz tasdiqlanmadi.*\n\n"
                "Sabab: To'lov summasi noto'g'ri yoki chek aniq emas.\n\n"
                "Qayta to'lov qilish uchun /start bosing.\n"
                "❓ Muammo: @mathaql_support"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"Reject xabari xatosi: {e}")
 
    await q.edit_message_text(
        q.message.text + "\n\n❌ *RAD ETILDI*",
        parse_mode="Markdown"
    )
 
# ══════════════════════════════════════════════════
# ADMIN: /admin KOMANDASI
# ══════════════════════════════════════════════════
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    data = load_data()
    total_users    = len(data["users"])
    total_payments = len(data["payments"])
    approved       = sum(1 for p in data["payments"].values() if p.get("status") == "approved")
    pending        = sum(1 for p in data["payments"].values() if p.get("status") == "pending")
    total_codes    = len(data["codes"])
    total_sum      = sum(
        p.get("amount", 0)
        for p in data["payments"].values()
        if p.get("status") == "approved"
    )
 
    text = (
        f"📊 *MathAql Admin Panel*\n\n"
        f"👤 Foydalanuvchilar: *{total_users}*\n"
        f"💳 Jami to'lovlar: *{total_payments}*\n"
        f"✅ Tasdiqlangan: *{approved}*\n"
        f"⏳ Kutilmoqda: *{pending}*\n"
        f"🔑 Kodlar: *{total_codes}*\n"
        f"💰 Jami daromad: *{total_sum:,} so'm*\n\n"
        f"⏰ {now_str()}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Kutilayotgan to'lovlar", callback_data="admin_pending")],
        [InlineKeyboardButton("🔑 Kod yaratish", callback_data="admin_gencode")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
 
# ══════════════════════════════════════════════════
# ADMIN: KUTILAYOTGAN TO'LOVLAR
# ══════════════════════════════════════════════════
async def cb_admin_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!"); return
    await q.answer()
 
    data    = load_data()
    pending = {k: v for k, v in data["payments"].items() if v.get("status") == "pending"}
    if not pending:
        await q.edit_message_text("✅ Hech qanday kutilayotgan to'lov yo'q!")
        return
 
    text = f"⏳ *Kutilayotgan to'lovlar: {len(pending)} ta*\n\n"
    buttons = []
    for pay_id, pay in list(pending.items())[:10]:
        p = PLANS.get(pay["plan"], PLANS["monthly"])
        text += (
            f"👤 {pay['user_name']} | {p['price']} | {pay['card_type']}\n"
            f"🆔 `{pay_id[-12:]}` | ⏰ {pay['created']}\n\n"
        )
        buttons.append([
            InlineKeyboardButton(
                f"✅ {pay['user_name'][:15]}",
                callback_data=f"admin_approve_{pay_id}_{pay['plan']}_{pay['user_id']}"
            ),
            InlineKeyboardButton(
                "❌",
                callback_data=f"admin_reject_{pay_id}_{pay['user_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("← Orqaga", callback_data="back_admin")])
    await q.edit_message_text(text, parse_mode="Markdown",
                               reply_markup=InlineKeyboardMarkup(buttons))
 
# ══════════════════════════════════════════════════
# ADMIN: KOD YARATISH
# ══════════════════════════════════════════════════
async def cb_admin_gencode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!"); return
    await q.answer()
 
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Oylik", callback_data="gencode_monthly")],
        [InlineKeyboardButton("🌟 Yillik", callback_data="gencode_yearly")],
        [InlineKeyboardButton("🏫 Maktab", callback_data="gencode_school")],
    ])
    await q.edit_message_text("🔑 Qaysi tarif uchun kod yaratilsin?",
                               reply_markup=kb)
 
async def cb_gencode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!"); return
    await q.answer()
 
    plan = q.data.replace("gencode_", "")
    code = generate_code(plan)
    p    = PLANS.get(plan, PLANS["monthly"])
    data = load_data()
    data["codes"][code] = {
        "plan": plan, "created": now_str(),
        "used": False, "user_id": None
    }
    save_data(data)
 
    await q.edit_message_text(
        f"✅ *Yangi kod yaratildi!*\n\n"
        f"🔑 Kod: `{code}`\n"
        f"📦 Tarif: {p['label']}\n"
        f"📅 Muddat: {p['days']} kun\n\n"
        f"Bu kodni foydalanuvchiga yuboring.",
        parse_mode="Markdown"
    )
 
# ══════════════════════════════════════════════════
# ADMIN: BROADCAST
# ══════════════════════════════════════════════════
async def cb_admin_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        await q.answer("❌ Ruxsat yo'q!"); return
    await q.answer()
    data = load_data()
    data["users"][str(q.from_user.id)]["step"] = "broadcast"
    save_data(data)
    await q.edit_message_text(
        "📢 *Broadcast xabar*\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n\n"
        "_(Bekor qilish uchun /cancel)_",
        parse_mode="Markdown"
    )
 
# ══════════════════════════════════════════════════
# SUPPORT
# ══════════════════════════════════════════════════
async def cb_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "❓ *Yordam kerakmi?*\n\n"
        "📱 Support: @mathaql_support\n"
        "👨‍💻 Admin: @mathaql_admin\n"
        "🌐 Sayt: mathaql.uz\n\n"
        "Xabar yozing — 24 soat ichida javob beramiz!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("← Asosiy menyu", callback_data="back_main")
        ]])
    )
 
# ══════════════════════════════════════════════════
# BACK BUTTONS
# ══════════════════════════════════════════════════
async def cb_back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Oylik — 49,000 so'm",   callback_data="plan_monthly")],
        [InlineKeyboardButton("🌟 Yillik — 299,000 so'm",  callback_data="plan_yearly")],
        [InlineKeyboardButton("🏫 Maktab — 500,000 so'm",  callback_data="plan_school")],
        [InlineKeyboardButton("❓ Savol berish",            callback_data="support")],
    ])
    await q.edit_message_text(
        f"👋 *MathAql Premium*\n\n"
        "💳 Tarif tanlang:",
        parse_mode="Markdown",
        reply_markup=kb
    )
 
# ══════════════════════════════════════════════════
# MATN XABARLAR
# ══════════════════════════════════════════════════
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    data = load_data()
    u    = get_user(data, user.id)
 
    # Broadcast mode (admin)
    if user.id in ADMIN_IDS and u.get("step") == "broadcast":
        u["step"] = "main"
        save_data(data)
        sent = 0
        for uid_str, udata in data["users"].items():
            try:
                await ctx.bot.send_message(
                    chat_id=int(uid_str),
                    text=f"📢 *MathAql xabari:*\n\n{text}",
                    parse_mode="Markdown"
                )
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi!")
        return
 
    # /cancel
    if text.lower() in ("/cancel", "bekor"):
        u["step"] = "main"
        save_data(data)
        await update.message.reply_text("❌ Bekor qilindi. /start bosing.")
        return
 
    # Default
    await update.message.reply_text(
        "👋 Salom!\n\nPremium sotib olish uchun /start bosing.\n"
        "❓ Yordam: @mathaql_support",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Boshlash", callback_data="back_main")
        ]])
    )
 
# ══════════════════════════════════════════════════
# ADMIN NOTIFY HELPER
# ══════════════════════════════════════════════════
async def notify_admins(ctx, text: str, reply_markup=None):
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except Exception as e:
            log.error(f"Admin notify xatosi: {e}")
 
 
# ══════════════════════════════════════════════════
# HTTP SERVER — Sayt kod tekshirish uchun
# ══════════════════════════════════════════════════
class CodeVerifyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if parsed.path == "/verify":
            code = params.get("code", [""])[0].upper().strip()
            data = load_data()
            
            # Kodni tekshirish
            found = data["codes"].get(code)
            if not found:
                result = {"ok": False, "reason": "notfound"}
            elif found.get("used"):
                result = {"ok": False, "reason": "used"}
            else:
                plan = found.get("plan", "monthly")
                # Ishlatilgan deb belgilash
                data["codes"][code]["used"] = True
                data["codes"][code]["used_at"] = now_str()
                save_data(data)
                result = {"ok": True, "plan": plan}
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Log chiqarmaslik
 
def start_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), CodeVerifyHandler)
    log.info(f"✅ HTTP server: port {port}")
    server.serve_forever()
 
# ══════════════════════════════════════════════════
# ASOSIY — BOT ISHGA TUSHIRISH
# ══════════════════════════════════════════════════
def main():
    log.info("🚀 MathAql Bot ishga tushmoqda...")
    # HTTP server ni alohida threadda ishga tushirish
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()
 
    app = Application.builder().token(BOT_TOKEN).build()
 
    # Komandalar
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("admin",  cmd_admin))
    app.add_handler(CommandHandler("cancel", lambda u,c: handle_text(u,c)))
 
    # Callback query lar
    app.add_handler(CallbackQueryHandler(cb_plan,           pattern="^plan_"))
    app.add_handler(CallbackQueryHandler(cb_card,           pattern="^card_"))
    app.add_handler(CallbackQueryHandler(cb_sent_receipt,   pattern="^sent_receipt_"))
    app.add_handler(CallbackQueryHandler(cb_admin_approve,  pattern="^admin_approve_"))
    app.add_handler(CallbackQueryHandler(cb_admin_reject,   pattern="^admin_reject_"))
    app.add_handler(CallbackQueryHandler(cb_admin_pending,  pattern="^admin_pending"))
    app.add_handler(CallbackQueryHandler(cb_admin_gencode,  pattern="^admin_gencode"))
    app.add_handler(CallbackQueryHandler(cb_admin_broadcast,pattern="^admin_broadcast"))
    app.add_handler(CallbackQueryHandler(cb_gencode,        pattern="^gencode_"))
    app.add_handler(CallbackQueryHandler(cb_support,        pattern="^support"))
    app.add_handler(CallbackQueryHandler(cb_back_main,      pattern="^back_main"))
 
    # Rasm va hujjat (chek)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_photo))
 
    # Matn
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
 
    log.info("✅ Bot tayyor! Polling boshlandi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
 
if __name__ == "__main__":
    main()
