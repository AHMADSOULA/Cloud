import asyncio
import io
import base64
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot import messages
from bot.keyboards import main_menu, admin_menu, ssh_countries_menu
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow
from automation.sshs8 import SSHS8

log = get_logger("Handlers")

# ═══════════════════════════════════════════
# ملفات Cloud Run
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
        return None

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID

# ═══════════════════════════════════════════
# الأوامر الأساسية
# ═══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)
    if is_admin(user.id):
        await update.message.reply_text(
            messages.WELCOME_ADMIN,
            parse_mode="Markdown",
            reply_markup=main_menu(is_admin=True),
            disable_web_page_preview=True,
        )
    else:
        await update.message.reply_text("🔒 أرسل /request باش تطلب صلاحية.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ /start - /admin - /cancel")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 البوت شغال.")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 تم الإلغاء.")

async def request_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ تم إرسال طلبك.")

# ═══════════════════════════════════════════
# Cloud Run
# ═══════════════════════════════════════════

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id): return
    
    text = update.message.text or ""
    urls = extract_urls(text)
    if not urls: return
        
    sso_url = urls[0]
    msg = await update.message.reply_text("⏳ جاري التنفيذ... [0/6]")
    browser = StealthBrowser()
    
    try:
        ctx = await browser.start()
        result = await run_sso_flow(ctx, sso_url, image=config.DEFAULT_IMAGE, sender=msg, user_tag=user.username)
        
        if not result.get("success"):
            shot = result.get("screenshot")
            if shot and os.path.exists(shot):
                with open(shot, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="❌ الحساب محذوف أو تم إغلاقه.")
                try: os.remove(shot)
                except: pass
                await msg.delete()
            else:
                await msg.edit_text(f"❌ فشل: {result.get('message')}")
            return

        domain = result.get("domain")
        final_url = result.get("final_url")
        flag = result.get("flag", "🇺🇸")
        
        for dark in DARK_FILES:
            uri = build_darktunnel_uri_with_host(dark["uri"], domain)
            if uri:
                filename = f"{dark['name']}_{flag}.dark"
                bio = io.BytesIO(uri.encode())
                bio.name = filename
                await context.bot.send_document(chat_id=update.effective_chat.id, document=bio, filename=filename)
        
        try: await msg.delete()
        except: pass
        
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        await browser.close()

# ═══════════════════════════════════════════
# SSH WebSocket
# ═══════════════════════════════════════════

async def handle_ssh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("🔐 SSH WebSocket clicked")
    query = update.callback_query
    user = update.effective_user
    
    if not await db.has_access(user.id):
        await query.message.reply_text("🔒 ما عندكش صلاحية.")
        return

    msg = await context.bot.send_message(chat_id=query.message.chat_id, text="⏳ انتظر...")
    
    try:
        from automation.sshs8 import SSHS8, KNOWN_COUNTRIES
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
        return

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or user.first_name)

        countries = await ssh.open_ssh_websocket()
        if not countries:
            countries = KNOWN_COUNTRIES

        context.user_data["ssh_countries"] = countries
        context.user_data["ssh_obj"] = ssh
        context.user_data["ssh_browser"] = browser

        kb = ssh_countries_menu(countries)
        try:
            await msg.edit_text("🌍 *اختر الدولة:*", parse_mode="Markdown", reply_markup=kb)
        except Exception:
            pass
    except Exception as e:
        await msg.edit_text(f"❌ فشل: {str(e)[:300]}")
        try: await browser.close()
        except: pass

async def ssh_country_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    idx = int(query.data.split(":")[1])

    countries = context.user_data.get("ssh_countries", [])
    ssh = context.user_data.get("ssh_obj")
    browser = context.user_data.get("ssh_browser")

    if not ssh or idx >= len(countries):
        await query.message.reply_text("❌ انتهت الجلسة.")
        return

    country = countries[idx]
    await query.message.edit_text(f"⏳ جاري إنشاء حساب {country}...")

    try:
        result = await ssh.create_account(country)
        if not result.get("success"):
            await query.message.edit_text("❌ فشل إنشاء الحساب.")
            return

        host = result.get("host")
        username = result.get("username")
        password = result.get("password")

        from automation.vmess import build_ssh_dark
        new_uri = build_ssh_dark(host, username, password, kind="youtube")

        if not new_uri:
            await query.message.edit_text("❌ فشل بناء ملف dark.")
            return

        bio = io.BytesIO(new_uri.encode("utf-8"))
        bio.name = f"SSH_{country}.dark"
        bio.seek(0)

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=bio,
            filename=bio.name,
            caption=f"✅ SSH Account\n🌍 {country}\n🖥️ Host: {host or '-'}\n🔌 Port: 22\n👤 User: {username}\n🔑 Pass: {password}"
        )

        context.user_data.pop("ssh_countries", None)
        context.user_data.pop("ssh_obj", None)
        context.user_data.pop("ssh_browser", None)

        try: await ssh.close()
        except: pass
        try: await browser.close()
        except: pass

        await query.message.delete()
    except Exception as e:
        await query.message.reply_text(f"❌ فشل: {str(e)[:300]}")

# ═══════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data

    if data == "ssh_ws":
        await handle_ssh(update, context)
    elif data.startswith("ssh_country:"):
        await ssh_country_handler(update, context)
    elif data == "back_main":
        if is_admin(user.id):
            await query.message.edit_text(messages.WELCOME_ADMIN, parse_mode="Markdown", reply_markup=main_menu(True))
    elif data.startswith("admin") and not is_admin(user.id):
        await query.message.reply_text("🚫 ماشي ADMIN")
    elif data == "admin":
        await query.message.edit_text("⚙️ ADMIN PANEL", reply_markup=admin_menu())
    elif data == "admin_stats":
        await query.message.edit_text("📊 الإحصائيات مازال ما تبرمجتش.")
    elif data == "admin_users":
        await query.message.edit_text("👥 المستخدمين مازال ما تبرمجوش.")
    elif data == "admin_banned":
        await query.message.edit_text("🚫 المحظورين مازال ما تبرمجوش.")
    elif data == "admin_requests":
        await query.message.edit_text("📋 الطلبات مازال ما تبرمجوش.")
    elif data == "admin_priority":
        context.user_data["await"] = "priority"
        await query.message.edit_text("⚡ أرسل ID:")
    elif data == "admin_ban":
        context.user_data["await"] = "ban"
        await query.message.edit_text("🔨 أرسل ID:")
    elif data == "admin_grant":
        context.user_data["await"] = "grant"
        await query.message.edit_text("✅ أرسل ID:")
    elif data == "admin_pause":
        context.user_data["await"] = "pause"
        await query.message.edit_text("⏸️ أرسل ID:")
    elif data == "admin_broadcast":
        context.user_data["await"] = "broadcast"
        await query.message.edit_text("📢 أرسل الرسالة:")
    elif data == "admin_stop_all":
        await db.set_global_stop(True)
        await query.message.edit_text("⛔ إيقاف للجميع", reply_markup=admin_menu())
    elif data == "admin_start_all":
        await db.set_global_stop(False)
        await query.message.edit_text("▶️ تشغيل للجميع", reply_markup=admin_menu())

async def handle_admin_input(update, context, text):
    mode = context.user_data.get("await")
    if not mode: return False
    if not is_admin(update.effective_user.id): return False
    context.user_data.pop("await", None)
    try:
        if mode == "grant":
            await db.set_access(int(text), 1)
            await update.message.reply_text(f"✅ تم تفعيل {text}")
        elif mode == "ban":
            await db.set_ban(int(text), 1)
            await update.message.reply_text(f"🚫 تم حظر {text}")
        elif mode == "priority":
            await db.set_priority(int(text), 100)
            await update.message.reply_text(f"⚡ تم زيادة {text}")
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
