import asyncio
import io
import base64
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.keyboards import main_menu, admin_menu
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow
from automation.vmess import build_ssh_dark, build_vmess_dark, build_vless_dark, build_trojan_dark

log = get_logger("Handlers")

# ═══════════════════════════════════════════
# إعدادات
# ═══════════════════════════════════════════
DARK_FILES = [
    {"name": "YOUTUBE_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiQEFNMl9EMyBZT1VUVUJFIiwidmxlc3NUdW5uZWxDb25maWciOnsidjJyYXlDb25maWciOnsiaG9zdCI6Imdvb2dsZS5jb20iLCJwb3J0Ijo0NDMsInV1aWQiOiJhYWFhMTExMS1iYmJiLTRjY2MtOGRkZC1lZWVlZmZmZjAwMDAiLCJzZXJ2ZXJOYW1lSW5kaWNhdGlvbiI6Imdvb2dsZXZpZGVvLmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQ0NTg4MjYxNDUzNi51cy1jZW50cmFsMS5ydW4uYXBwIn19fQ=="},
    {"name": "SNAPCHAT_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiU05BUENIQVRfNEhf8J-HuvCfh7giLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiZ29vZ2xlLmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYXBpLnNuYXBjaGF0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTEwMjc5NzcwNDc4OC51cy1jZW50cmFsMS5ydW4uYXBwIn0sImluamVjdENvbmZpZyI6eyJtb2RlIjoiUFJPWFkiLCJwcm94eUhvc3QiOiIxNTcuMjQwLjkuMzkiLCJwYXlsb2FkIjoiQ09OTkVDVCBbaG9zdF06W3BvcnRdIEhUVFAvMS4xW2NybGZdeC1jb25uZWN0ZWQtdG86IDM0LjE0My43Mi4yW2NybGZdcHJveHktY29ubmVjdGlvbjoga2VlcC1hbGl2ZVtjcmxmXWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl11c2VyLWFnZW50OiBGQkFWLzAuMCBbY3JsZl14LWlvcmctYnNpZDogQEFNMl9EM1tjcmxmXVtjcmxmXSJ9fX0="},
    {"name": "FREE_4H", "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiRlJFRV80SF_wn4e68J-HuCIsInZsZXNzVHVubmVsQ29uZmlnIjp7InYycmF5Q29uZmlnIjp7Imhvc3QiOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwicG9ydCI6NDQzLCJ1dWlkIjoiYWFhYTExMTEtYmJiYi00Y2NjLThkZGQtZWVlZWZmZmYwMDAwIiwic2VydmVyTmFtZUluZGljYXRpb24iOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwid3NQYXRoIjoiL1RlbGVncmFtL0BBTTJfRDMvQEFITUFEMzIxNCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl1jb25uZWN0aW9uOiBrZWVwLWFsaXZlW2Nyb2ZdeC1pb3JnLWJzaWQ6IEBBTTJfRDNbY3JsZl1bY3JsZl0ifX19"},
]

PAYLOAD = "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]"
PROXY_HOST = "34.43.46.91"
PROXY_PORT = 443
SNI = "youtube.com"

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID

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
                    if "wsHeaderHost" in cur:
                        cur["wsHeaderHost"] = new_host
                    stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
                elif isinstance(cur, list):
                    stack.extend(v for v in cur if isinstance(v, (dict, list)))
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return "darktunnel://" + base64.b64encode(raw).decode("utf-8")
    except Exception as e:
        log.error(f"❌ build_darktunnel: {e}")
        return None

# ═══════════════════════════════════════════
# الأوامر
# ═══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)
    
    if is_admin(user.id):
        await update.message.reply_text(
            "👋 *مرحباً يا ADMIN*\n\n"
            "📌 *Labs المتوفرة:*\n"
            "🇧🇪 https://www.skills.google/focuses/19372?parent=catalog\n"
            "🇺🇸 https://www.skills.google/focuses/33353?parent=catalog\n\n"
            "✅ أرسل رابط SSO للبدء.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu(is_admin=True),
            disable_web_page_preview=True,
        )
        return
    
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

    msg = await update.message.reply_text("⏳ جاري أتمتة Cloud Run...")
    
    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        result = await run_sso_flow(ctx, sso_url, image=config.DEFAULT_IMAGE, sender=msg, user_tag=user.username or "admin")
        
        if not result.get("success"):
            await msg.edit_text(f"❌ فشل: {result.get('message')}")
            return

        domain = result.get("domain")
        final_url = result.get("final_url")
        flag = result.get("flag", "🇺🇸")
        
        await msg.edit_text(f"✅ *تم إنشاء الخدمة!*\n\n🌐 `{final_url}`\n🌍 {flag}", parse_mode=ParseMode.MARKDOWN)

        for dark in DARK_FILES:
            uri = build_darktunnel_uri_with_host(dark["uri"], domain)
            if not uri: continue
            filename = f"{dark['name']}_{flag}.dark"
            bio = io.BytesIO(uri.encode())
            bio.name = filename
            await context.bot.send_document(chat_id=update.effective_chat.id, document=bio, filename=filename)
            
    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {e}")
    finally:
        await browser.close()

# ═══════════════════════════════════════════
# ADMIN: تحويل الملفات
# ═══════════════════════════════════════════
async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "⚙️ *ADMIN PANEL*\n\nاختر الخدمة اللي بغيتي تحولها:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_menu()
    )

async def ask_for_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service = query.data.split(":")[1]
    context.user_data["convert_service"] = service
    
    if service in ["ssh", "trojan"]:
        format_text = "`host@user:pass`"
    else:
        format_text = "`vmess://...` أو `vless://...`"
        
    await query.message.edit_text(
        f"📝 *تحويل {service.upper()}*\n\n"
        f"أرسل المعلومات بالشكل التالي:\n"
        f"{format_text}\n\n"
        f"البوت غادي يزيد Proxy + Payload + SNI.",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_conversion_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = context.user_data.get("convert_service")
    if not service:
        return
        
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    try:
        if service in ["ssh", "trojan"]:
            # الشكل: host@user:pass
            parts = re.split(r'[@:]', text)
            if len(parts) < 3:
                raise ValueError("تأكد من الشكل host@user:pass")
            
            host, user, password = parts[0], parts[1], parts[2]
            
            if service == "ssh":
                uri = build_ssh_dark(host, user, password, kind="youtube")
            else:
                data = {"add": host, "id": password}
                uri = build_trojan_dark(data, password, kind="youtube")
            
        else: # vmess / vless
            if text.startswith("vmess://"):
                b64 = text.replace("vmess://", "")
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                data = json.loads(base64.b64decode(b64).decode())
            elif text.startswith("vless://"):
                data = {"add": text.split("@")[1].split(":")[0], "id": text.split("@")[0].split("vless://")[1]}
            else:
                raise ValueError("لينك غير صحيح")
            
            if service == "vmess":
                uri = build_vmess_dark(data, data.get("id", "pass"), kind="youtube")
            else:
                uri = build_vless_dark(data, data.get("id", "pass"), kind="youtube")
        
        if not uri:
            raise ValueError("فشل بناء الملف.")

        filename = f"{service.upper()}_CONVERTED.dark"
        bio = io.BytesIO(uri.encode())
        bio.name = filename
        
        await update.message.reply_document(
            document=bio,
            filename=filename,
            caption=f"✅ تم إضافة Proxy + Payload + SNI\n📁 {filename}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
    finally:
        context.user_data.pop("convert_service", None)

# ═══════════════════════════════════════════
# button_handler
# ═══════════════════════════════════════════
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "admin":
        await handle_admin_panel(update, context)
    elif data.startswith("convert:"):
        await ask_for_conversion(update, context)
    elif data == "back_main":
        await query.message.edit_text("👋 القائمة الرئيسية", reply_markup=main_menu(True))
