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
from bot.keyboards import (
    main_menu, admin_menu, protocols_menu,
    continents_menu, countries_menu,
)
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow, extract_email_from_url, extract_password_from_url

log = get_logger("Handlers")


# ═══════════════════════════════════════════
# طابور
# ═══════════════════════════════════════════

class JobQueue:
    def __init__(self):
        self.queue = []
        self.counter = 0
        self.current = None
        self.lock = asyncio.Lock()

    async def add(self, user_id, chat_id, sso_url, user_tag, priority=0):
        async with self.lock:
            self.counter += 1
            num = self.counter
            self.queue.append({
                "num": num,
                "user_id": user_id,
                "chat_id": chat_id,
                "sso_url": sso_url,
                "user_tag": user_tag,
                "priority": priority,
            })
            self.queue.sort(key=lambda x: -x["priority"])
            return num

    async def get_next(self):
        async with self.lock:
            if self.current is not None:
                return None
            if not self.queue:
                return None
            self.current = self.queue.pop(0)
            return self.current

    async def finish(self):
        async with self.lock:
            self.current = None

    def queue_size(self):
        return len(self.queue)

    def position(self, user_id):
        for i, item in enumerate(self.queue):
            if item["user_id"] == user_id:
                return i + 1
        return 0


queue = JobQueue()


# ═══════════════════════════════════════════
# 3 ملفات DarkTunnel (Cloud Run)
# ═══════════════════════════════════════════

DARK_FILES = [
    {
        "name": "YOUTUBE_4H",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiQEFNMl9EMyBZT1VUVUJFIiwidmxlc3NUdW5uZWxDb25maWciOnsidjJyYXlDb25maWciOnsiaG9zdCI6Imdvb2dsZS5jb20iLCJwb3J0Ijo0NDMsInV1aWQiOiJhYWFhMTExMS1iYmJiLTRjY2MtOGRkZC1lZWVlZmZmZjAwMDAiLCJzZXJ2ZXJOYW1lSW5kaWNhdGlvbiI6Imdvb2dsZXZpZGVvLmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQ0NTg4MjYxNDUzNi51cy1jZW50cmFsMS5ydW4uYXBwIn19fQ==",
    },
    {
        "name": "SNAPCHAT_4H",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiU05BUENIQVRfNEhf8J-HuvCfh7giLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiZ29vZ2xlLmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYXBpLnNuYXBjaGF0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTEwMjc5NzcwNDc4OC51cy1jZW50cmFsMS5ydW4uYXBwIn0sImluamVjdENvbmZpZyI6eyJtb2RlIjoiUFJPWFkiLCJwcm94eUhvc3QiOiIxNTcuMjQwLjkuMzkiLCJwYXlsb2FkIjoiQ09OTkVDVCBbaG9zdF06W3BvcnRdIEhUVFAvMS4xW2NybGZdeC1jb25uZWN0ZWQtdG86IDM0LjE0My43Mi4yW2NybGZdcHJveHktY29ubmVjdGlvbjoga2VlcC1hbGl2ZVtjcmxmXWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl11c2VyLWFnZW50OiBGQkFWLzAuMCBbY3JsZl14LWlvcmctYnNpZDogQEFNMl9EM1tjcmxmXVtjcmxmXSJ9fX0=",
    },
    {
        "name": "FREE_4H",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiRlJFRV80SF_wn4e68J-HuCIsInZsZXNzVHVubmVsQ29uZmlnIjp7InYycmF5Q29uZmlnIjp7Imhvc3QiOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwicG9ydCI6NDQzLCJ1dWlkIjoiYWFhYTExMTEtYmJiYi00Y2NjLThkZGQtZWVlZWZmZmYwMDAwIiwic2VydmVyTmFtZUluZGljYXRpb24iOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwid3NQYXRoIjoiL1RlbGVncmFtL0BBTTJfRDMvQEFITUFEMzIxNCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl1jb25uZWN0aW9uOiBrZWVwLWFsaXZlW2Nyb2ZdeC1pb3JnLWJzaWQ6IEBBTTJfRDNbY3JsZl1bY3JsZl0ifX19",
    },
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
                    if "wsHeaderHost" in cur:
                        cur["wsHeaderHost"] = new_host
                    stack.extend(v for v in cur.values() if isinstance(v, (dict, list)))
                elif isinstance(cur, list):
                    stack.extend(v for v in cur if isinstance(v, (dict, list)))
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        new_b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + new_b64
    except Exception as e:
        log.error(f"❌ build_darktunnel: {e}", exc_info=True)
        return None


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


# ═══════════════════════════════════════════
# /start
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

    if await db.is_globally_stopped():
        await update.message.reply_text(
            "⛔ *البوت متوقف حالياً*\n\nرايح يرجع يخدم قريباً. جرب من بعد.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if await db.is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور من البوت.")
        return

    if await db.has_access(user.id):
        await update.message.reply_text(
            messages.WELCOME_USER,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu(is_admin=False),
            disable_web_page_preview=True,
        )
        return

    await update.message.reply_text(
        messages.WELCOME_PENDING,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )
    await update.message.reply_text(
        "🔒 *للحصول على صلاحية:*\n\nأرسل `/request` باش نرسلو طلبك للـ ADMIN.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════
# /request
# ═══════════════════════════════════════════

async def request_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if is_admin(user.id):
        await update.message.reply_text("✅ نتا ADMIN — عندك صلاحية كاملة.")
        return

    if await db.has_access(user.id):
        await update.message.reply_text("✅ عندك صلاحية.")
        return

    await db.add_request(user.id, user.username or user.first_name)
    await update.message.reply_text("✅ تم إرسال طلبك للـ ADMIN. رايح نراجعوه قريباً.")

    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"📋 *طلب استخدام جديد*\n\n"
                f"👤 الاسم: {user.first_name}\n"
                f"🔗 اليوزر: @{user.username or '-'}\n"
                f"🆔 ID: `{user.id}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        log.warning(f"⚠️ ما قدرناش نبعثو للأدمن: {e}")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        await start(update, context)
    else:
        await update.message.reply_text(messages.WELCOME_PENDING, parse_mode=ParseMode.MARKDOWN)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    jobs = await db.get_user_jobs(user.id, limit=5)
    if not jobs:
        await update.message.reply_text("📭 لا توجد مهام سابقة.")
        return
    lines = []
    for jid, status, created in jobs:
        emoji = {"pending": "⏳", "done": "✅", "failed": "❌", "running": "🔄"}.get(status, "❔")
        lines.append(f"• `#{jid}` — {emoji} {status} — {created}")
    await update.message.reply_text(
        f"📊 *آخر {len(jobs)} مهام:*\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.clear_session(user.id)

    b = context.bot_data.pop(f"browser_{user.id}", None)
    if b:
        try:
            await b.close()
        except Exception:
            pass
    await update.message.reply_text("🚫 تم الإلغاء.")


# ═══════════════════════════════════════════
# SSO helpers
# ═══════════════════════════════════════════

def is_full_sso_url(url: str) -> bool:
    u = (url or "").lower()
    if "skills.google/google_sso" in u: return True
    if "token=" in u: return True
    if "password=" in u: return True
    return False


def is_direct_addsession_url(url: str) -> bool:
    u = (url or "").lower()
    if "accounts.google.com/addsession" in u and "skills.google" not in u: return True
    return False


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if await db.is_globally_stopped() and not is_admin(user.id):
        await update.message.reply_text("⛔ *البوت متوقف حالياً*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await update.message.reply_text("🔒 ما عندكش صلاحية.\nأرسل `/request`.", parse_mode=ParseMode.MARKDOWN)
        return

    text = update.message.text or ""
    urls = extract_urls(text)
    if not urls:
        await update.message.reply_text(messages.NO_URL)
        return
    sso_url = urls[0]

    if "skills.google" not in sso_url and "qwiklabs" not in sso_url and "accounts.google.com" not in sso_url:
        await update.message.reply_text("⚠️ الرابط لا يبدو من Google Skills.")
        return

    user_tag = f"@{user.username}" if user.username else f"@{user.first_name}"
    log.info(f"🔗 URL: {sso_url[:150]}")

    u = await db.get_user(user.id)
    priority = (u.get("priority") or 0) if u else 0

    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag, priority)
    pos = queue.position(user.id)
    if pos > 1:
        await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.\n📍 موقعك: {pos}")
    else:
        await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.")
    asyncio.create_task(process_queue(update.effective_chat.id, context))


async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = (update.message.text or "").strip()
    if not password:
        return

    session = await db.get_session(user.id)
    if not session or session.get("state") != "waiting_password":
        return

    try:
        await update.message.delete()
    except Exception:
        pass

    sso_url = session.get("sso_url")
    if not sso_url:
        await update.message.reply_text("❌ ما لقيناش الرابط.")
        return

    await db.clear_session(user.id)

    if "Password=" not in sso_url:
        sep = "&" if "?" in sso_url else "?"
        sso_url = f"{sso_url}{sep}Password={password}"

    user_tag = f"@{user.username}" if user.username else f"@{user.first_name}"
    u = await db.get_user(user.id)
    priority = (u.get("priority") or 0) if u else 0

    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag, priority)
    asyncio.create_task(process_queue(update.effective_chat.id, context))
    await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.")


async def process_queue(chat_id, context):
    async with asyncio.Lock():
        item = await queue.get_next()
        if not item:
            return

        job = item
        try:
            msg = await context.bot.send_message(chat_id=job["chat_id"], text="🚀 جاري التنفيذ... [0/8]")

            browser = StealthBrowser()
            ctx = await browser.start()

            try:
                result = await run_sso_flow(
                    ctx,
                    job["sso_url"],
                    image=config.DEFAULT_IMAGE,
                    sender=msg,
                    user_tag=job["user_tag"],
                )

                if not result.get("success"):
                    message = result.get("message", "فشل")
                    try:
                        await msg.edit_text(f"❌ توقفنا\n\n{message}")
                    except Exception:
                        pass
                    return

                domain = result.get("domain")
                final_url = result.get("final_url")
                flag = result.get("flag", "🇺🇸")

                if not domain:
                    try:
                        await msg.edit_text("❌ فشل: ما لقيناش domain")
                    except Exception:
                        pass
                    return

                for idx, dark in enumerate(DARK_FILES, 1):
                    try:
                        new_uri = build_darktunnel_uri_with_host(dark["uri"], domain)
                        if not new_uri:
                            continue
                        safe_domain = "".join(c for c in domain.lower() if c.isalnum() or c in ".-_")[:40]
                        display_name = f"{dark['name']}_{flag}"
                        filename = f"{display_name} - {safe_domain}.dark"
                        bio = io.BytesIO(new_uri.encode("utf-8"))
                        bio.name = filename
                        bio.seek(0)
                        await context.bot.send_document(
                            chat_id=job["chat_id"],
                            document=bio,
                            filename=filename,
                            caption=f"✅ {display_name}",
                        )
                    except Exception as e:
                        log.error(f"❌ dark: {e}")

                try:
                    await msg.edit_text(
                        f"✅ *تم النشر!*\n\n🌐 `{final_url}`\n🌍 {flag}",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

        except Exception as e:
            log.exception("فشل المهمة")
            try:
                await context.bot.send_message(chat_id=job["chat_id"], text=f"❌ {str(e)[:400]}")
            except Exception:
                pass
        finally:
            await queue.finish()
            if queue.queue_size() > 0:
                asyncio.create_task(process_queue(job["chat_id"], context))


# ═══════════════════════════════════════════
# Protocol Flow
# ═══════════════════════════════════════════

async def handle_protocols(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("🚀 Protocols clicked")
    query = update.callback_query
    user = update.effective_user
    chat_id = query.message.chat_id

    if not await db.has_access(user.id):
        await query.message.edit_text("🔒 ما عندكش صلاحية.")
        return

    await query.message.edit_text("⏳ جاري الدخول للموقع...")

    try:
        from automation.sshs8 import SSHS8
    except Exception as e:
        await query.message.edit_text(f"❌ خطأ: {e}")
        return

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or user.first_name)
        ssh.set_chat(chat_id)
        ssh.bot = context.bot

        ok = await ssh.open_home()
        if not ok:
            await query.message.edit_text("❌ ما قدرناش نفتحو الموقع.")
            try:
                await browser.close()
            except Exception:
                pass
            return

        protocols = await ssh.get_protocols()
        if not protocols:
            await query.message.edit_text("❌ ما لقيناش البروتوكولات.")
            try:
                await browser.close()
            except Exception:
                pass
            return

        context.user_data["ssh_browser"] = browser
        context.user_data["ssh_obj"] = ssh
        context.user_data["protocols"] = protocols

        kb = protocols_menu(protocols)
        await query.message.edit_text(
            "🔌 *اختر البروتوكول:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )

    except Exception as e:
        log.exception("فشل protocols")
        try:
            await query.message.edit_text(f"❌ {str(e)[:300]}")
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass


async def handle_proto_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = int(query.data.split(":")[1])
    protocols = context.user_data.get("protocols", [])
    ssh = context.user_data.get("ssh_obj")

    if not ssh or idx >= len(protocols):
        await query.message.edit_text("❌ انتهت الجلسة.")
        return

    proto = protocols[idx]
    await query.message.edit_text(f"⏳ جاري فتح {proto['name']}...")

    continents = await ssh.open_protocol(proto['name'])
    if not continents:
        await query.message.edit_text("❌ ما لقيناش القارات.")
        return

    context.user_data["continents"] = continents
    context.user_data["selected_proto"] = proto['name']

    kb = continents_menu(continents)
    await query.message.edit_text(
        f"🔌 *{proto['name']}*\n\n🌍 *اختر القارة:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


async def handle_continent_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = int(query.data.split(":")[1])
    continents = context.user_data.get("continents", [])
    ssh = context.user_data.get("ssh_obj")

    if not ssh or idx >= len(continents):
        await query.message.edit_text("❌ انتهت الجلسة.")
        return

    continent = continents[idx]
    await query.message.edit_text(f"⏳ جاري فتح {continent['name']}...")

    countries = await ssh.open_continent(continent['name'])
    if not countries:
        await query.message.edit_text("❌ ما لقيناش الدول.")
        return

    context.user_data["countries"] = countries
    context.user_data["selected_continent"] = continent['name']

    kb = countries_menu(countries)
    await query.message.edit_text(
        f"🌍 *{continent['name']}*\n\n🏳️ *اختر الدولة:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )


async def handle_country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = query.message.chat_id

    idx = int(query.data.split(":")[1])
    countries = context.user_data.get("countries", [])
    ssh = context.user_data.get("ssh_obj")
    browser = context.user_data.get("ssh_browser")

    if not ssh or idx >= len(countries):
        await query.message.edit_text("❌ انتهت الجلسة.")
        return

    country = countries[idx]
    await query.message.edit_text(f"⏳ جاري فتح {country['name']}...")

    servers = await ssh.open_country(country['name'])
    if not servers:
        await query.message.edit_text(f"❌ ما لقيناش خوادم لـ {country['name']}.")
        return

    server = random.choice(servers)
    log.info(f"🎲 Random server: {server['id']}")

    await query.message.edit_text(
        f"🎲 *اختيار عشوائي*\n\n"
        f"🏳️ الدولة: {country['name']}\n"
        f"🖥️ الخادم: {server['id']}\n\n"
        f"⏳ جاري إنشاء الحساب..."
    )

    result = await ssh.create_account_from_server(server['href'])
    if not result.get("success"):
        await query.message.edit_text(f"❌ فشل.\n\n{result.get('message', '')}")
        try:
            await browser.close()
        except Exception:
            pass
        return

    proto = context.user_data.get("selected_proto", "")
    country_info = {"name": country['name'], "flag": "🌍"}

    from automation.vmess import build_ssh_dark, build_vmess_dark, build_vless_dark, build_trojan_dark
    from automation.sshs8 import SSH_PAYLOAD, V2RAY_SNI, V2RAY_WS_HOST

    builder = None
    data = None
    if "VMESS" in proto.upper():
        builder = build_vmess_dark
        data = result["vmess_config"]
    elif "VLESS" in proto.upper():
        builder = build_vless_dark
        data = result["vmess_config"]
    elif "TROJAN" in proto.upper():
        builder = build_trojan_dark
        data = result["vmess_config"]
    else:
        builder = build_ssh_dark
        data = result

    host = result.get("host") or (data.get("add") if data else None)
    username = result.get("username") or (data.get("id") if data else None)
    password = result.get("password") or ""

    # ✅ نبعثو المعلومات مع proxy + payload
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ *Account*\n\n"
            f"🔌 {proto}\n"
            f"🌍 {country['name']}\n"
            f"🖥️ Server: {server['id']}\n"
            f"🌐 Host: `{host}`\n"
            f"👤 User: `{username}`\n"
            f"🔑 Pass: `{password}`\n\n"
            f"📡 Proxy: `34.43.46.91:443`\n"
            f"📡 Payload: `{SSH_PAYLOAD[:80]}...`\n\n"
            f"🔒 SNI: `{V2RAY_SNI}`\n"
            f"🌐 WS Host: `{V2RAY_WS_HOST}`"
        ),
        parse_mode=ParseMode.MARKDOWN,
    )

    for kind, kind_name in [("youtube", "YOUTUBE"), ("snapchat", "SNAPCHAT")]:
        try:
            if data:
                new_uri = builder(data, password, kind=kind, country=country_info)
            else:
                new_uri = builder(host, username, password, kind=kind, country=country_info)
            if not new_uri:
                continue
            filename = f"{kind_name}_4DAY.dark"
            bio = io.BytesIO(new_uri.encode("utf-8"))
            bio.name = filename
            bio.seek(0)
            await context.bot.send_document(
                chat_id=chat_id,
                document=bio,
                filename=filename,
                caption=f"📁 {filename}",
            )
            await asyncio.sleep(0.5)
        except Exception as e:
            log.error(f"❌ build: {e}")

    try:
        await ssh.close()
    except Exception:
        pass
    try:
        await browser.close()
    except Exception:
        pass

    for key in ["ssh_browser", "ssh_obj", "protocols", "continents", "countries", "selected_proto", "selected_continent"]:
        context.user_data.pop(key, None)


# ═══════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════

async def admin_panel(query, context):
    await query.message.edit_text(
        "⚙️ *ADMIN PANEL*\n\nاختر:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_menu(),
    )


async def admin_stats(query):
    total = await db.count_jobs()
    users = await db.get_all_users()
    active = await db.get_active_users()
    banned = await db.get_banned_users()
    reqs = await db.get_requests()
    stopped = await db.is_globally_stopped()

    status = "⛔ موقف للجميع" if stopped else "✅ شغال"

    text = (
        f"📊 *إحصائيات البوت*\n\n"
        f"🟢 الحالة: {status}\n"
        f"👥 مجموع: {len(users)}\n"
        f"✅ نشطين: {len(active)}\n"
        f"🚫 محظورين: {len(banned)}\n"
        f"📋 طلبات: {len(reqs)}\n"
        f"🔧 مهام: {total}\n"
        f"📦 طابور: {queue.queue_size()}\n"
    )
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


async def admin_users(query):
    users = await db.get_all_users()
    lines = ["👥 *المستخدمين:*\n"]
    for u in users[:30]:
        emoji = "🚫" if u.get("banned") else ("✅" if u.get("access") else "⏳")
        pri = f"⚡{u.get('priority',0)}" if u.get("priority") else ""
        name = u.get("username") or "-"
        lines.append(f"{emoji} `{u['user_id']}` — {name} {pri}")
    try:
        await query.message.edit_text("\n".join(lines) or "لا مستخدمين", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


async def admin_banned(query):
    banned = await db.get_banned_users()
    if not banned:
        text = "🚫 لا محظورين"
    else:
        lines = ["🚫 *المحظورين:*\n"]
        for u in banned[:30]:
            lines.append(f"`{u['user_id']}` — {u.get('username') or '-'}")
        text = "\n".join(lines)
    try:
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


async def admin_requests(query):
    reqs = await db.get_requests("pending")
    if not reqs:
        try:
            await query.message.edit_text("📋 لا طلبات", reply_markup=admin_menu())
        except Exception:
            pass
        return
    lines = ["📋 *طلبات:*\n"]
    for r in reqs[:20]:
        lines.append(f"• `{r['user_id']}` — {r.get('username') or '-'}")
    try:
        await query.message.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


async def admin_priority(query, context):
    context.user_data["await"] = "priority"
    try:
        await query.message.edit_text("⚡ *زيادة سرعة*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def admin_ban(query, context):
    context.user_data["await"] = "ban"
    try:
        await query.message.edit_text("🔨 *حظر*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def admin_grant(query, context):
    context.user_data["await"] = "grant"
    try:
        await query.message.edit_text("✅ *صلاحية*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def admin_pause(query, context):
    context.user_data["await"] = "pause"
    try:
        await query.message.edit_text("⏸️ *توقيف/تشغيل*\n\nأرسل ID:", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def admin_broadcast(query, context):
    context.user_data["await"] = "broadcast"
    try:
        await query.message.edit_text("📢 *رسالة*\n\nأرسل النص:", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass


async def admin_stop_all(query):
    await db.set_global_stop(True)
    try:
        await query.message.edit_text("⛔ *تم الإيقاف للجميع*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


async def admin_start_all(query):
    await db.set_global_stop(False)
    try:
        await query.message.edit_text("▶️ *تم التشغيل للجميع*", parse_mode=ParseMode.MARKDOWN, reply_markup=admin_menu())
    except Exception:
        pass


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
            await update.message.reply_text(f"✅ تم تفعيل `{uid}`", parse_mode=ParseMode.MARKDOWN)

        elif mode == "ban":
            uid = int(text)
            await db.set_ban(uid, 1)
            await update.message.reply_text(f"🚫 تم حظر `{uid}`", parse_mode=ParseMode.MARKDOWN)

        elif mode == "priority":
            uid = int(text)
            await db.set_priority(uid, 100)
            await update.message.reply_text(f"⚡ تم زيادة `{uid}`", parse_mode=ParseMode.MARKDOWN)

        elif mode == "pause":
            uid = int(text)
            u = await db.get_user(uid)
            if u:
                new_val = 0 if u.get("access") else 1
                await db.set_access(uid, new_val)
                await update.message.reply_text(f"⏸️ تم تبديل `{uid}`", parse_mode=ParseMode.MARKDOWN)

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
        await update.message.reply_text(f"❌ {e}")

    return True


# ═══════════════════════════════════════════
# button_handler
# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data
    log.info(f"🔘 callback: {data}")

    # ✅ Workflow الجديد
    if data == "protocols":
        await handle_protocols(update, context)
        return
    if data.startswith("proto:"):
        await handle_proto_selected(update, context)
        return
    if data.startswith("cont:"):
        await handle_continent_selected(update, context)
        return
    if data.startswith("country:"):
        await handle_country_selected(update, context)
        return

    # ✅ القديم
    if data == "status":
        await status_cmd(update, context)
        return

    if data == "back_main":
        if is_admin(user.id):
            try:
                await query.message.edit_text(
                    messages.WELCOME_ADMIN,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu(True),
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return

    if data.startswith("admin") and not is_admin(user.id):
        await query.message.reply_text("🚫 ماشي ADMIN")
        return

    if data == "admin":
        await admin_panel(query, context)
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
