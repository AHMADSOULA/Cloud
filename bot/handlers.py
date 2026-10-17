import asyncio
import io
import os
import random
import base64
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot import messages
from bot.keyboards import main_menu, admin_menu
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow

log = get_logger("Handlers")


# ═══════════════════════════════════════════
# Auto-start Recording
# ═══════════════════════════════════════════

async def _start_recording_for_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    log.info("🎬 Auto-start recording for admin")

    try:
        from automation.browser import StealthBrowser
        from automation.sshs8 import SSHS8
    except Exception as e:
        await update.message.reply_text(f"❌ import: {e}")
        return

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or "admin")
        ssh.set_chat(update.effective_chat.id)
        ssh.set_bot(context.bot)

        ok = await ssh.start_recording()
        if not ok:
            await update.message.reply_text("❌ فشل بدء التسجيل")
            await browser.close()
            return

        ok = await ssh.open_url("https://sshs8.com")
        if not ok:
            await update.message.reply_text("❌ فشل فتح الموقع")
            await browser.close()
            return

        context.user_data["recording"] = True
        context.user_data["rec_browser"] = browser
        context.user_data["rec_ssh"] = ssh

        railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "xxx.up.railway.app")
        await update.message.reply_text(
            f"🎬 *التسجيل بدا!*\n\n"
            f"📱 *ادخل لـ VNC من المتصفح:*\n"
            f"`https://{railway_url}/vnc.html`\n\n"
            f"⏳ *خدم عادي فـ VNC*\n"
            f"✅ *بعد ما تكمل، اضغط ⏹️ إيقاف التسجيل*",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        log.exception("فشل auto-start recording")
        await update.message.reply_text(f"❌ {str(e)[:300]}")
        try:
            await browser.close()
        except Exception:
            pass


# ═══════════════════════════════════════════
# /start
# ═══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)

    if user.id == config.ADMIN_ID:
        await update.message.reply_text(
            messages.WELCOME_ADMIN,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu(is_admin=True),
            disable_web_page_preview=True,
        )

        if context.user_data.get("recording"):
            await update.message.reply_text("🎬 التسجيل شغال بالفعل. اضغط ⏹️ لإيقافو")
            return

        # ✅ إلا كان تسجيل قديم — نقفلو
        old_browser = context.user_data.pop("rec_browser", None)
        old_ssh = context.user_data.pop("rec_ssh", None)
        if old_browser:
            try:
                if old_ssh:
                    await old_ssh.close()
                await old_browser.close()
            except Exception:
                pass
        context.user_data.pop("recording", None)

        # ✅ نبدلو التسجيل مباشرة
        await _start_recording_for_admin(update, context, user)
        return

    if await db.is_globally_stopped():
        await update.message.reply_text("⛔ *البوت متوقف حالياً*", parse_mode=ParseMode.MARKDOWN)
        return
    if await db.is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور.")
        return
    if await db.has_access(user.id):
        await update.message.reply_text(messages.WELCOME_USER, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu(is_admin=False), disable_web_page_preview=True)
        return
    await update.message.reply_text(messages.WELCOME_PENDING, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    await update.message.reply_text("🔒 أرسل `/request` باش تطلب صلاحية.", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════
# /request
# ═══════════════════════════════════════════

async def request_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == config.ADMIN_ID:
        await update.message.reply_text("✅ نتا ADMIN.")
        return
    if await db.has_access(user.id):
        await update.message.reply_text("✅ عندك صلاحية.")
        return
    await db.add_request(user.id, user.username or user.first_name)
    await update.message.reply_text("✅ تم إرسال طلبك.")
    try:
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"📋 *طلب جديد*\n\n👤 {user.first_name}\n🔗 @{user.username or '-'}\n🆔 `{user.id}`", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == config.ADMIN_ID: await start(update, context)
    else: await update.message.reply_text(messages.WELCOME_PENDING, parse_mode=ParseMode.MARKDOWN)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    jobs = await db.get_user_jobs(user.id, limit=5)
    if not jobs:
        await update.message.reply_text("📭 لا مهام.")
        return
    lines = []
    for jid, status, created in jobs:
        emoji = {"pending": "⏳", "done": "✅", "failed": "❌", "running": "🔄"}.get(status, "❔")
        lines.append(f"• `#{jid}` — {emoji} {status} — {created}")
    await update.message.reply_text(f"📊 *آخر {len(jobs)}:*\n\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.clear_session(user.id)

    ssh = context.user_data.pop("rec_ssh", None)
    if ssh:
        try: await ssh.close()
        except Exception: pass
    b = context.user_data.pop("rec_browser", None)
    if b:
        try: await b.close()
        except Exception: pass
    context.user_data.pop("recording", None)

    await update.message.reply_text("🚫 تم الإلغاء.")


# ═══════════════════════════════════════════
# Recording — إيقاف فقط
# ═══════════════════════════════════════════

async def handle_rec_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = query.message.chat_id

    if user.id != config.ADMIN_ID:
        await query.message.edit_text("🚫 ADMIN فقط")
        return

    if not context.user_data.get("recording"):
        await query.message.edit_text("⚠️ ما كاينش تسجيل شغال")
        return

    await query.message.edit_text("⏹️ جاري إيقاف التسجيل...")

    ssh = context.user_data.get("rec_ssh")
    browser = context.user_data.get("rec_browser")

    try:
        if ssh:
            await ssh.stop_and_send()
        await query.message.edit_text("✅ تم إيقاف التسجيل + بعث الملفات")
    except Exception as e:
        log.exception("فشل rec_stop")
        await query.message.edit_text(f"❌ {str(e)[:300]}")
    finally:
        try:
            if ssh: await ssh.close()
        except Exception: pass
        try:
            if browser: await browser.close()
        except Exception: pass
        context.user_data.pop("recording", None)
        context.user_data.pop("rec_browser", None)
        context.user_data.pop("rec_ssh", None)


# ═══════════════════════════════════════════
# ADMIN — كامل
# ═══════════════════════════════════════════

async def admin_panel(query, context):
    await query.message.edit_text("⚙️ *ADMIN PANEL*\n\nاختر:", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())


async def admin_stats(query):
    total = await db.count_jobs()
    users = await db.get_all_users()
    active = await db.get_active_users()
    banned = await db.get_banned_users()
    reqs = await db.get_requests()
    stopped = await db.is_globally_stopped()
    status = "⛔ موقف" if stopped else "✅ شغال"
    text = (f"📊 *إحصائيات*\n\n🟢 {status}\n👥 {len(users)}\n✅ {len(active)}\n🚫 {len(banned)}\n📋 {len(reqs)}\n🔧 {total}\n")
    try: await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def admin_users(query):
    users = await db.get_all_users()
    lines = ["👥 *المستخدمين:*\n"]
    for u in users[:30]:
        emoji = "🚫" if u.get("banned") else ("✅" if u.get("access") else "⏳")
        lines.append(f"{emoji} `{u['user_id']}` — {u.get('username') or '-'}")
    try: await query.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def admin_banned(query):
    banned = await db.get_banned_users()
    if not banned: text = "🚫 لا محظورين"
    else:
        lines = ["🚫 *محظورين:*\n"]
        for u in banned[:30]: lines.append(f"`{u['user_id']}` — {u.get('username') or '-'}")
        text = "\n".join(lines)
    try: await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def admin_requests(query):
    reqs = await db.get_requests("pending")
    if not reqs:
        try: await query.message.edit_text("📋 لا طلبات", reply_markup=admin_menu())
        except Exception: pass
        return
    lines = ["📋 *طلبات:*\n"]
    for r in reqs[:20]: lines.append(f"• `{r['user_id']}` — {r.get('username') or '-'}")
    try: await query.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def admin_priority(query, context):
    context.user_data["await"] = "priority"
    try: await query.message.edit_text("⚡ *زيادة سرعة*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass


async def admin_ban(query, context):
    context.user_data["await"] = "ban"
    try: await query.message.edit_text("🔨 *حظر*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass


async def admin_grant(query, context):
    context.user_data["await"] = "grant"
    try: await query.message.edit_text("✅ *صلاحية*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass


async def admin_pause(query, context):
    context.user_data["await"] = "pause"
    try: await query.message.edit_text("⏸️ *توقيف/تشغيل*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass


async def admin_broadcast(query, context):
    context.user_data["await"] = "broadcast"
    try: await query.message.edit_text("📢 *رسالة*\n\nأرسل النص:", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass


async def admin_stop_all(query):
    await db.set_global_stop(True)
    try: await query.message.edit_text("⛔ *إيقاف للجميع*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def admin_start_all(query):
    await db.set_global_stop(False)
    try: await query.message.edit_text("▶️ *تشغيل للجميع*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception: pass


async def handle_admin_input(update, context, text):
    mode = context.user_data.get("await")
    if not mode: return False
    user = update.effective_user
    if user.id != config.ADMIN_ID:
        context.user_data.pop("await", None)
        return False
    context.user_data.pop("await", None)
    try:
        if mode == "grant": uid = int(text); await db.set_access(uid, 1); await update.message.reply_text(f"✅ `{uid}`")
        elif mode == "ban": uid = int(text); await db.set_ban(uid, 1); await update.message.reply_text(f"🚫 `{uid}`")
        elif mode == "priority": uid = int(text); await db.set_priority(uid, 100); await update.message.reply_text(f"⚡ `{uid}`")
        elif mode == "pause":
            uid = int(text); u = await db.get_user(uid)
            if u:
                new_val = 0 if u.get("access") else 1
                await db.set_access(uid, new_val)
                await update.message.reply_text(f"⏸️ `{uid}`")
        elif mode == "broadcast":
            users = await db.get_all_users(); sent = 0
            for u in users:
                try: await context.bot.send_message(chat_id=u["user_id"], text=text); sent += 1
                except Exception: pass
            await update.message.reply_text(f"📢 {sent}")
    except Exception as e: await update.message.reply_text(f"❌ {e}")
    return True


# ═══════════════════════════════════════════
# button_handler
# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data
    log.info(f"🔘 {data}")

    if data == "rec_stop":
        await handle_rec_stop(update, context)
        return

    if data == "status":
        await status_cmd(update, context)
        return

    if data == "back_main":
        if user.id == config.ADMIN_ID:
            try: await query.message.edit_text(messages.WELCOME_ADMIN, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu(True), disable_web_page_preview=True)
            except Exception: pass
        return

    if data.startswith("admin") and user.id != config.ADMIN_ID:
        await query.message.reply_text("🚫 ماشي ADMIN")
        return
    if data == "admin": await admin_panel(query, context)
    elif data == "admin_stats": await admin_stats(query)
    elif data == "admin_users": await admin_users(query)
    elif data == "admin_banned": await admin_banned(query)
    elif data == "admin_requests": await admin_requests(query)
    elif data == "admin_priority": await admin_priority(query, context)
    elif data == "admin_ban": await admin_ban(query, context)
    elif data == "admin_grant": await admin_grant(query, context)
    elif data == "admin_pause": await admin_pause(query, context)
    elif data == "admin_broadcast": await admin_broadcast(query, context)
    elif data == "admin_stop_all": await admin_stop_all(query)
    elif data == "admin_start_all": await admin_start_all(query)
