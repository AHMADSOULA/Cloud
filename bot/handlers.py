import asyncio
import io
import base64
import json
import re
import os
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
from automation.vmess import build_ssh_dark

log = get_logger("Handlers")

# ═══════════════════════════════════════════
# Cloud Run
# ═══════════════════════════════════════════
DARK_FILES = [
    {"name": "YOUTUBE_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiQEFNMl9EMyBZT1VUVUJFIiwidmxlc3NUdW5uZWxDb25maWciOnsidjJyYXlDb25maWciOnsiaG9zdCI6Imdvb2dsZS5jb20iLCJwb3J0Ijo0NDMsInV1aWQiOiJhYWFhMTExMS1iYmJiLTRjY2MtOGRkZC1lZWVlZmZmZjAwMDAiLCJzZXJ2ZXJOYW1lSW5kaWNhdGlvbiI6Imdvb2dsZXZpZGVvLmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQ0NTg4MjYxNDUzNi51cy1jZW50cmFsMS5ydW4uYXBwIn19fQ=="},
    {"name": "SNAPCHAT_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiU05BUENIQVRfNEhf8J-HuvCfh7giLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiZ29vZ2xlLmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYXBpLnNuYXBjaGF0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTEwMjc5NzcwNDc4OC51cy1jZW50cmFsMS5ydW4uYXBwIn0sImluamVjdENvbmZpZyI6eyJtb2RlIjoiUFJPWFkiLCJwcm94eUhvc3QiOiIxNTcuMjQwLjkuMzkiLCJwYXlsb2FkIjoiQ09OTkVDVCBbaG9zdF06W3BvcnRdIEhUVFAvMS4xW2NybGZdeC1jb25uZWN0ZWQtdG86IDM0LjE0My43Mi4yW2NybGZdcHJveHktY29ubmVjdGlvbjoga2VlcC1hbGl2ZVtjcmxmXWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl11c2VyLWFnZW50OiBGQkFWLzAuMCBbY3JsZl14LWlvcmctYnNpZDogQEFNMl9EM1tjcmxmXVtjcmxmXSJ9fX0="},
    {"name": "FREE_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiRlJFRV80SF_wn4e68J-HuCIsInZsZXNzVHVubmVsQ29uZmlnIjp7InYycmF5Q29uZmlnIjp7Imhvc3QiOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwicG9ydCI6NDQzLCJ1dWlkIjoiYWFhYTExMTEtYmJiYi00Y2NjLThkZGQtZWVlZWZmZmYwMDAwIiwic2VydmVyTmFtZUluZGljYXRpb24iOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwid3NQYXRoIjoiL1RlbGVncmFtL0BBTTJfRDMvQEFITUFEMzIxNCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl1jb25uZWN0aW9uOiBrZWVwLWFsaXZlW2Nyb2ZdeC1pb3JnLWJzaWQ6IEBBTTJfRDNbY3JsZl1bY3JsZl0ifX19"},
]

def _b64_pad(s: str) -> str:
    s = s.strip()
    return s + ("=" * ((4 - (len(s) % 4)) % 4)) if s else s

def build_darktunnel_uri_with_host(base_uri: str, new_host: str) -> str:
    try:
        raw_b64 = base_uri.split("darktunnel://", 1)[1].strip()
        raw_b64 = _b64_pad(raw_b64)
        decoded = base64.b64decode(raw_b64.encode("utf-8")).decode("utf-8")
        data = json.loads(decoded)
        v2ray = data.get("vlessTunnelConfig", {}).get("v2rayConfig")
        if v2ray and "wsHeaderHost" not in v2ray:
            v2ray["wsHeaderHost"] = new_host
        else:
            stack = [data]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    if "wsHeaderHost" in cur: cur["wsHeaderHost"] = new_host
                    stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
                elif isinstance(cur, list):
                    stack.extend(v for v in cur if isinstance(v, (dict, list)))
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return "darktunnel://" + base64.b64encode(raw).decode("utf-8")
    except Exception as e:
        log.error(f"❌ build_darktunnel: {e}")
        return None

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# ═══════════════════════════════════════════
# الأوامر
# ═══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)

    if is_admin(user.id):
        await update.message.reply_text(
            messages.WELCOME_ADMIN,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu(is_admin=True),
            disable_web_page_preview=True,
        )
        return

    await update.message.reply_text("🔒 أرسل /request باش تطلب صلاحية.")

async def request_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم إرسال طلبك.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ /start - /admin - /cancel")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 البوت شغال.")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 تم الإلغاء.")


# ═══════════════════════════════════════════
# Cloud Run (SSO)
# ═══════════════════════════════════════════

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return await update.message.reply_text("🔒 ماشي مسموح.")
        
    text = update.message.text or ""
    urls = extract_urls(text)
    if not urls:
        return await update.message.reply_text("❌ أرسل رابط SSO صحيح.")
        
    sso_url = urls[0]
    if "skills.google" not in sso_url and "qwiklabs" not in sso_url:
        return await update.message.reply_text("⚠️ الرابط ماشي من Google Skills.")

    # ✅ رسالة وحدة كتبدل
    msg = await update.message.reply_text("⏳ انتظر 2 دقائق لكمال العملية...")
    browser = StealthBrowser()
    
    try:
        ctx = await browser.start()
        result = await run_sso_flow(ctx, sso_url, image=config.DEFAULT_IMAGE, sender=msg, user_tag=user.username or "admin")
        
        # ✅ كشف الحساب المحذوف أو المشكل
        if not result.get("success"):
            error_msg = result.get("message", "")
            error_code = result.get("error", "")
            
            # ✅ إلا كان الحساب محذوف أو مغلق
            if error_code == "account_deleted" or "محذوف" in error_msg or "مغلق" in error_msg:
                try:
                    page = None
                    if ctx.pages:
                        page = ctx.pages[0]
                    if page:
                        path = "/tmp/account_deleted.png"
                        await page.screenshot(path=path)
                        with open(path, "rb") as f:
                            await update.message.reply_photo(
                                photo=f,
                                caption="❌ الحساب محذوف أو تم إغلاقه."
                            )
                        os.remove(path)
                except Exception:
                    await update.message.reply_text("❌ الحساب محذوف أو تم إغلاقه.")
                return
            
            await msg.edit_text(f"❌ فشل: {error_msg}")
            return

        domain = result.get("domain")
        final_url = result.get("final_url")
        flag = result.get("flag", "🇺🇸")
        
        # ✅ نبعثو الملفات
        for dark in DARK_FILES:
            uri = build_darktunnel_uri_with_host(dark["uri"], domain)
            if not uri: continue
            filename = f"{dark['name']}_{flag}.dark"
            bio = io.BytesIO(uri.encode())
            bio.name = filename
            await context.bot.send_document(chat_id=update.effective_chat.id, document=bio, filename=filename)
        
        # ✅ نمسحو رسالة الانتظار
        try:
            await msg.delete()
        except Exception:
            pass
        
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        await browser.close()


# ═══════════════════════════════════════════
# ADMIN - تحويل SSH
# ═══════════════════════════════════════════

async def admin_panel(query, context):
    await query.message.edit_text(
        "⚙️ *ADMIN PANEL*\n\nاختر:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_menu(),
    )

async def ask_for_ssh_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["await_convert_ssh"] = True
    
    # ✅ بلا parse_mode باش ما يوقعش خطأ
    await query.message.edit_text(
        "🔐 تحويل SSH\n\n"
        "أرسل المعلومات بالشكل التالي:\n"
        "IP:Port@User:Pass\n\n"
        "مثال:\n"
        "152.228.162.19:22@u1595199941:U6CqrexXyK"
    )

async def handle_ssh_conversion_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("await_convert_ssh"):
        return False
        
    text = update.message.text.strip()
    context.user_data.pop("await_convert_ssh", None)
    
    try:
        parts = text.split("@")
        if len(parts) != 2:
            raise ValueError("تأكد من الشكل IP:Port@User:Pass")
        
        host_port = parts[0].strip()
        user_pass = parts[1].strip().split(":")
        
        if len(user_pass) != 2:
            raise ValueError("تأكد من الشكل IP:Port@User:Pass")
        
        host_port_split = host_port.split(":")
        if len(host_port_split) != 2:
            raise ValueError("تأكد من الشكل IP:Port@User:Pass")
        
        host = host_port_split[0]
        port = host_port_split[1]
        user = user_pass[0]
        password = user_pass[1]
        
        uri = build_ssh_dark(host, user, password, kind="youtube")
        
        if not uri:
            raise ValueError("فشل بناء الملف")
        
        filename = f"SSH_{host}.dark"
        bio = io.BytesIO(uri.encode())
        bio.name = filename
        
        # ✅ بلا parse_mode
        await update.message.reply_document(
            document=bio,
            filename=filename,
            caption=(
                f"✅ تم التحويل!\n\n"
                f"🖥️ Host: {host}\n"
                f"🔌 Port: {port}\n"
                f"👤 User: {user}\n"
                f"🔑 Pass: {password}\n\n"
                f"📁 {filename}"
            )
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ خطأ: {e}\n\n"
            f"تأكد من الشكل: IP:Port@User:Pass"
        )
        
    return True


# ═══════════════════════════════════════════
# ADMIN - الأدوات القديمة
# ═══════════════════════════════════════════

async def admin_stats(query):
    users = await db.get_all_users()
    active = await db.get_active_users()
    text = f"📊 إحصائيات\n\n👥 {len(users)}\n✅ {len(active)}\n"
    await query.message.edit_text(text, reply_markup=admin_menu())

async def admin_users(query):
    users = await db.get_all_users()
    lines = ["👥 المستخدمين:\n"]
    for u in users[:30]:
        emoji = "🚫" if u.get("banned") else ("✅" if u.get("access") else "⏳")
        lines.append(f"{emoji} {u['user_id']} — {u.get('username') or '-'}")
    await query.message.edit_text("\n".join(lines), reply_markup=admin_menu())

async def admin_banned(query):
    banned = await db.get_banned_users()
    text = "🚫 لا محظورين" if not banned else "\n".join([f"{u['user_id']}" for u in banned])
    await query.message.edit_text(text, reply_markup=admin_menu())

async def admin_requests(query):
    await query.message.edit_text("📋 طلبات", reply_markup=admin_menu())

async def admin_priority(query, context):
    context.user_data["await"] = "priority"
    await query.message.edit_text("⚡ أرسل ID:")

async def admin_ban(query, context):
    context.user_data["await"] = "ban"
    await query.message.edit_text("🔨 أرسل ID:")

async def admin_grant(query, context):
    context.user_data["await"] = "grant"
    await query.message.edit_text("✅ أرسل ID:")

async def admin_pause(query, context):
    context.user_data["await"] = "pause"
    await query.message.edit_text("⏸️ أرسل ID:")

async def admin_broadcast(query, context):
    context.user_data["await"] = "broadcast"
    await query.message.edit_text("📢 أرسل الرسالة:")

async def admin_stop_all(query):
    await db.set_global_stop(True)
    await query.message.edit_text("⛔ إيقاف للجميع", reply_markup=admin_menu())

async def admin_start_all(query):
    await db.set_global_stop(False)
    await query.message.edit_text("▶️ تشغيل للجميع", reply_markup=admin_menu())


# ═══════════════════════════════════════════
# handle_admin_input
# ═══════════════════════════════════════════

async def handle_admin_input(update, context, text):
    mode = context.user_data.get("await")
    if not mode:
        return False

    user = update.effective_user
    if not is_admin(user.id):
        context.user_data.pop("await", None)
        return False

    context.user_data.pop("await", None)
    try:
        if mode == "grant":
            uid = int(text)
            await db.set_access(uid, 1)
            await update.message.reply_text(f"✅ تم تفعيل {uid}")
        elif mode == "ban":
            uid = int(text)
            await db.set_ban(uid, 1)
            await update.message.reply_text(f"🚫 تم حظر {uid}")
        elif mode == "priority":
            uid = int(text)
            await db.set_priority(uid, 100)
            await update.message.reply_text(f"⚡ تم زيادة {uid}")
        elif mode == "pause":
            uid = int(text)
            u = await db.get_user(uid)
            if u:
                new_val = 0 if u.get("access") else 1
                await db.set_access(uid, new_val)
                await update.message.reply_text(f"⏸️ تم تبديل {uid}")
        elif mode == "broadcast":
            users = await db.get_all_users()
            sent = 0
            for u in users:
                try:
                    await context.bot.send_message(chat_id=u["user_id"], text=text)
                    sent += 1
                except Exception:
                    pass
            await update.message.reply_text(f"📢 تم الإرسال لـ {sent}")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
    return True


# ═══════════════════════════════════════════
# button_handler
# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data

    if data == "status":
        await status_cmd(update, context)
    elif data == "back_main":
        if is_admin(user.id):
            await query.message.edit_text(messages.WELCOME_ADMIN, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu(True))
    elif data.startswith("admin") and not is_admin(user.id):
        await query.message.reply_text("🚫 ماشي ADMIN")
    elif data == "admin":
        await admin_panel(query, context)
    elif data == "admin_convert_ssh":
        await ask_for_ssh_conversion(update, context)
    elif data == "admin_stats":
        await admin_stats(query)
    elif data == "admin_users":
        await admin_users(query)
    elif data == "admin_banned":
        await admin_banned(query)
    elif data == "admin_requests":
        await admin_requests(query)
    elif data == "admin_priority":
        await admin_priority(query, context)
    elif data == "admin_ban":
        await admin_ban(query, context)
    elif data == "admin_grant":
        await admin_grant(query, context)
    elif data == "admin_pause":
        await admin_pause(query, context)
    elif data == "admin_broadcast":
        await admin_broadcast(query, context)
    elif data == "admin_stop_all":
        await admin_stop_all(query)
    elif data == "admin_start_all":
        await admin_start_all(query)
