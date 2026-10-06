import asyncio
import io
import os
import base64
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot import messages
from bot.keyboards import main_menu, admin_menu, countries_menu
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
# فحص نوع الرابط
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


# ═══════════════════════════════════════════
# handle_url (SSO)
# ═══════════════════════════════════════════

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
# SSH Handler — يعرض الدول
# ═══════════════════════════════════════════

async def handle_ssh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("🔐 SSH clicked")
    query = update.callback_query
    user = update.effective_user
    chat_id = query.message.chat_id if query else update.message.chat_id

    if await db.is_globally_stopped() and not is_admin(user.id):
        await context.bot.send_message(chat_id=chat_id, text="⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await context.bot.send_message(chat_id=chat_id, text="🔒 ما عندكش صلاحية.")
        return

    from automation.sshs8 import SSH_COUNTRIES
    kb = countries_menu("ssh", SSH_COUNTRIES)
    text = "🔐 *SSH WebSocket*\n\n🌍 *اختر الدولة:*"

    if query:
        try:
            await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ═══════════════════════════════════════════
# SSH Country — ينشئ الحساب و يبعت ملفين
# ═══════════════════════════════════════════

async def ssh_country_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = query.message.chat_id

    idx = int(query.data.split(":")[1])
    log.info(f"🔐 SSH country: idx={idx}")

    from automation.sshs8 import SSHS8, SSH_COUNTRIES
    from automation.vmess import build_ssh_dark

    if idx < 0 or idx >= len(SSH_COUNTRIES):
        await query.message.edit_text("❌ دولة غير موجودة.")
        return

    country = SSH_COUNTRIES[idx]

    if await db.is_globally_stopped() and not is_admin(user.id):
        await query.message.edit_text("⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await query.message.edit_text("🔒 ما عندكش صلاحية.")
        return

    await query.message.edit_text(f"⏳ SSH — {country['flag']} {country['name']}...")

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or user.first_name)
        ssh.set_chat(chat_id)
        ssh.bot = context.bot

        ok = await ssh.open_page(country["url"])
        if not ok:
            await query.message.edit_text("❌ ما قدرناش نفتحو الصفحة.")
            try:
                await browser.close()
            except Exception:
                pass
            return

        result = await ssh.create_ssh_account()

        if not result.get("success"):
            await query.message.edit_text(f"❌ فشل.\n\n{result.get('message', '')}")
            try:
                await ssh.close()
                await browser.close()
            except Exception:
                pass
            return

        host = result.get("host")
        username = result.get("username")
        password = result.get("password")

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *SSH Account*\n\n"
                f"🌍 الدولة: {country['flag']} {country['name']}\n"
                f"🖥️ Host: `{host}`\n"
                f"🔌 Port: `22`\n"
                f"👤 User: `{username}`\n"
                f"🔑 Pass: `{password}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        # ✅ ملفين فقط
        for kind, kind_name in [("youtube", "YOUTUBE"), ("snapchat", "SNAPCHAT")]:
            new_uri = build_ssh_dark(host, username, password, kind=kind)
            if not new_uri:
                continue
            filename_out = f"{kind_name}_4DAY{country['flag']}.dark"
            bio = io.BytesIO(new_uri.encode("utf-8"))
            bio.name = filename_out
            bio.seek(0)
            await context.bot.send_document(
                chat_id=chat_id,
                document=bio,
                filename=filename_out,
                caption=f"📁 {filename_out}",
            )
            await asyncio.sleep(0.5)

        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await ssh.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

    except Exception as e:
        log.exception("فشل SSH country")
        try:
            await query.message.edit_text(f"❌ {str(e)[:300]}")
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass


# ═══════════════════════════════════════════
# VMESS Handler
# ═══════════════════════════════════════════

async def handle_vmess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("🌐 VMESS clicked")
    query = update.callback_query
    user = update.effective_user
    chat_id = query.message.chat_id if query else update.message.chat_id

    if await db.is_globally_stopped() and not is_admin(user.id):
        await context.bot.send_message(chat_id=chat_id, text="⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await context.bot.send_message(chat_id=chat_id, text="🔒 ما عندكش صلاحية.")
        return

    from automation.sshs8 import VMESS_COUNTRIES
    kb = countries_menu("vmess", VMESS_COUNTRIES)
    text = "🌐 *VMESS*\n\n🌍 *اختر الدولة:*"

    if query:
        try:
            await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def vmess_country_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = query.message.chat_id

    idx = int(query.data.split(":")[1])
    log.info(f"🌐 VMESS country: idx={idx}")

    from automation.sshs8 import SSHS8, VMESS_COUNTRIES
    from automation.vmess import build_vmess_dark

    if idx < 0 or idx >= len(VMESS_COUNTRIES):
        await query.message.edit_text("❌ دولة غير موجودة.")
        return

    country = VMESS_COUNTRIES[idx]

    if await db.is_globally_stopped() and not is_admin(user.id):
        await query.message.edit_text("⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await query.message.edit_text("🔒 ما عندكش صلاحية.")
        return

    await query.message.edit_text(f"⏳ VMESS — {country['flag']} {country['name']}...")

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or user.first_name)
        ssh.set_chat(chat_id)
        ssh.bot = context.bot

        ok = await ssh.open_page(country["url"])
        if not ok:
            await query.message.edit_text("❌ ما قدرناش نفتحو الصفحة.")
            try:
                await browser.close()
            except Exception:
                pass
            return

        result = await ssh.create_vmess_account()

        if not result.get("success"):
            await query.message.edit_text(f"❌ فشل.\n\n{result.get('message', '')}")
            try:
                await ssh.close()
                await browser.close()
            except Exception:
                pass
            return

        vmess_config = result.get("vmess_config") or {}
        password = result.get("password") or "vmess_user"

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *VMESS Account*\n\n"
                f"🌍 الدولة: {country['flag']} {country['name']}\n"
                f"🌐 Host: `{vmess_config.get('add', '-')}`\n"
                f"🔌 Port: `{vmess_config.get('port', '-')}`\n"
                f"🆔 UUID: `{vmess_config.get('id', '-')}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        # ✅ ملفين فقط
        for kind, kind_name in [("youtube", "YOUTUBE"), ("snapchat", "SNAPCHAT")]:
            new_uri = build_vmess_dark(vmess_config, password, kind=kind)
            if not new_uri:
                continue
            filename_out = f"VMESS_{kind_name}_4DAY{country['flag']}.dark"
            bio = io.BytesIO(new_uri.encode("utf-8"))
            bio.name = filename_out
            bio.seek(0)
            await context.bot.send_document(
                chat_id=chat_id,
                document=bio,
                filename=filename_out,
                caption=f"📁 {filename_out}",
            )
            await asyncio.sleep(0.5)

        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await ssh.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

    except Exception as e:
        log.exception("فشل VMESS country")
        try:
            await query.message.edit_text(f"❌ {str(e)[:300]}")
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass


# ═══════════════════════════════════════════
# VLESS Handler
# ═══════════════════════════════════════════

async def handle_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log.info("⚡ VLESS clicked")
    query = update.callback_query
    user = update.effective_user
    chat_id = query.message.chat_id if query else update.message.chat_id

    if await db.is_globally_stopped() and not is_admin(user.id):
        await context.bot.send_message(chat_id=chat_id, text="⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await context.bot.send_message(chat_id=chat_id, text="🔒 ما عندكش صلاحية.")
        return

    from automation.sshs8 import VLESS_COUNTRIES
    kb = countries_menu("vless", VLESS_COUNTRIES)
    text = "⚡ *VLESS*\n\n🌍 *اختر الدولة:*"

    if query:
        try:
            await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def vless_country_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    chat_id = query.message.chat_id

    idx = int(query.data.split(":")[1])
    log.info(f"⚡ VLESS country: idx={idx}")

    from automation.sshs8 import SSHS8, VLESS_COUNTRIES
    from automation.vmess import build_vless_dark

    if idx < 0 or idx >= len(VLESS_COUNTRIES):
        await query.message.edit_text("❌ دولة غير موجودة.")
        return

    country = VLESS_COUNTRIES[idx]

    if await db.is_globally_stopped() and not is_admin(user.id):
        await query.message.edit_text("⛔ *البوت متوقف*", parse_mode=ParseMode.MARKDOWN)
        return

    if not await db.has_access(user.id):
        await query.message.edit_text("🔒 ما عندكش صلاحية.")
        return

    await query.message.edit_text(f"⏳ VLESS — {country['flag']} {country['name']}...")

    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, sender=None, user_tag=user.username or user.first_name)
        ssh.set_chat(chat_id)
        ssh.bot = context.bot

        ok = await ssh.open_page(country["url"])
        if not ok:
            await query.message.edit_text("❌ ما قدرناش نفتحو الصفحة.")
            try:
                await browser.close()
            except Exception:
                pass
            return

        result = await ssh.create_vmess_account()

        if not result.get("success"):
            await query.message.edit_text(f"❌ فشل.\n\n{result.get('message', '')}")
            try:
                await ssh.close()
                await browser.close()
            except Exception:
                pass
            return

        vless_config = result.get("vmess_config") or {}
        password = result.get("password") or "vless_user"

        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *VLESS Account*\n\n"
                f"🌍 الدولة: {country['flag']} {country['name']}\n"
                f"🌐 Host: `{vless_config.get('add', '-')}`\n"
                f"🔌 Port: `{vless_config.get('port', '-')}`\n"
                f"🆔 UUID: `{vless_config.get('id', '-')}`"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

        # ✅ ملفين فقط
        for kind, kind_name in [("youtube", "YOUTUBE"), ("snapchat", "SNAPCHAT")]:
            new_uri = build_vless_dark(vless_config, password, kind=kind)
            if not new_uri:
                continue
            filename_out = f"VLESS_{kind_name}_4DAY{country['flag']}.dark"
            bio = io.BytesIO(new_uri.encode("utf-8"))
            bio.name = filename_out
            bio.seek(0)
            await context.bot.send_document(
                chat_id=chat_id,
                document=bio,
                filename=filename_out,
                caption=f"📁 {filename_out}",
            )
            await asyncio.sleep(0.5)

        try:
            await query.message.delete()
        except Exception:
            pass
        try:
            await ssh.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass

    except Exception as e:
        log.exception("فشل VLESS country")
        try:
            await query.message.edit_text(f"❌ {str(e)[:300]}")
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass


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

    # SSH
    if data == "ssh_ws":
        try:
            await handle_ssh(update, context)
        except Exception as e:
            log.exception("فشل SSH")
        return

    if data.startswith("ssh_country:"):
        try:
            await ssh_country_handler(update, context)
        except Exception as e:
            log.exception("فشل SSH country")
        return

    # VMESS
    if data == "vmess":
        try:
            await handle_vmess(update, context)
        except Exception as e:
            log.exception("فشل VMESS")
        return

    if data.startswith("vmess_country:"):
        try:
            await vmess_country_handler(update, context)
        except Exception as e:
            log.exception("فشل VMESS country")
        return

    # VLESS
    if data == "vless":
        try:
            await handle_vless(update, context)
        except Exception as e:
            log.exception("فشل VLESS")
        return

    if data.startswith("vless_country:"):
        try:
            await vless_country_handler(update, context)
        except Exception as e:
            log.exception("فشل VLESS country")
        return

    # عام
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
