import asyncio
import io
import base64
import json
import os
from telegram import Update
from telegram.ext import ContextTypes
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)
    if is_admin(user.id):
        await update.message.reply_text(messages.WELCOME_ADMIN, parse_mode="Markdown", reply_markup=main_menu(is_admin=True))

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
            # ✅ إلا كان الحساب محذوف أو مغلق، كيبعت الصورة والرسالة
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data

    if data == "back_main":
        await query.message.edit_text(messages.WELCOME_ADMIN, parse_mode="Markdown", reply_markup=main_menu(True))
    elif data == "admin":
        await query.message.edit_text("⚙️ ADMIN PANEL", reply_markup=admin_menu())
    elif data == "admin_convert_ssh":
        context.user_data["await_convert_ssh"] = True
        await query.message.edit_text("🔐 تحويل SSH\n\nأرسل: IP:Port@User:Pass\nمثال:\n152.228.162.19:22@u1595199941:U6CqrexXyK")

async def handle_ssh_conversion_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("await_convert_ssh"): return False
    text = update.message.text.strip()
    context.user_data.pop("await_convert_ssh", None)
    try:
        parts = text.split("@")
        host, port = parts[0].split(":")
        user, password = parts[1].split(":")
        
        uri = build_ssh_dark(host, user, password, kind="youtube")
        if not uri: raise ValueError("فشل بناء الملف")
        
        filename = f"SSH_{host}.dark"
        bio = io.BytesIO(uri.encode())
        bio.name = filename
        await update.message.reply_document(document=bio, filename=filename)
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}\nتأكد من الشكل: IP:Port@User:Pass")
    return True
