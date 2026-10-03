import asyncio
import io
import base64
import json
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot import messages
from bot.keyboards import main_menu
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow

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

    async def add(self, user_id, chat_id, sso_url, user_tag):
        async with self.lock:
            self.counter += 1
            num = self.counter
            self.queue.append({
                "num": num,
                "user_id": user_id,
                "chat_id": chat_id,
                "sso_url": sso_url,
                "user_tag": user_tag,
            })
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


queue = JobQueue()


# ═══════════════════════════════════════════
# 3 ملفات Dark
# ═══════════════════════════════════════════

DARK_FILES = [
    {
        "name": "YOUTUBE_4H_🇺🇸",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiQEFNMl9EMyBZT1VUVUJFIiwidmxlc3NUdW5uZWxDb25maWciOnsidjJyYXlDb25maWciOnsiaG9zdCI6Imdvb2dsZS5jb20iLCJwb3J0Ijo0NDMsInV1aWQiOiJhYWFhMTExMS1iYmJiLTRjY2MtOGRkZC1lZWVlZmZmZjAwMDAiLCJzZXJ2ZXJOYW1lSW5kaWNhdGlvbiI6Imdvb2dsZXZpZGVvLmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQ0NTg4MjYxNDUzNi51cy1jZW50cmFsMS5ydW4uYXBwIn19fQ==",
    },
    {
        "name": "SNAPCHAT_4H_🇺🇸",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiU05BUENIQVRfNEhf8J-HuvCfh7giLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiZ29vZ2xlLmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYXBpLnNuYXBjaGF0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTEwMjc5NzcwNDc4OC51cy1jZW50cmFsMS5ydW4uYXBwIn0sImluamVjdENvbmZpZyI6eyJtb2RlIjoiUFJPWFkiLCJwcm94eUhvc3QiOiIxNTcuMjQwLjkuMzkiLCJwYXlsb2FkIjoiQ09OTkVDVCBbaG9zdF06W3BvcnRdIEhUVFAvMS4xW2NybGZdeC1jb25uZWN0ZWQtdG86IDM0LjE0My43Mi4yW2NybGZdcHJveHktY29ubmVjdGlvbjoga2VlcC1hbGl2ZVtjcmxmXWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl11c2VyLWFnZW50OiBGQkFWLzAuMCBbY3JsZl14LWlvcmctYnNpZDogQEFNMl9EM1tjcmxmXVtjcmxmXSJ9fX0=",
    },
    {
        "name": "FREE_4H_🇺🇸",
        "uri": "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoiRlJFRV80SF_wn4e68J-HuCIsInZsZXNzVHVubmVsQ29uZmlnIjp7InYycmF5Q29uZmlnIjp7Imhvc3QiOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwicG9ydCI6NDQzLCJ1dWlkIjoiYWFhYTExMTEtYmJiYi00Y2NjLThkZGQtZWVlZWZmZmYwMDAwIiwic2VydmVyTmFtZUluZGljYXRpb24iOiJhbHQxMy55dDMuZ2dwaHQuY29tIiwid3NQYXRoIjoiL1RlbGVncmFtL0BBTTJfRDMvQEFITUFEMzIxNCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl1jb25uZWN0aW9uOiBrZWVwLWFsaXZlW2NybGZddXNlci1hZ2VudDogRkJBVi8wLjAgW2NybGZdeC1pb3JnLWJzaWQ6IEBBTTJfRDNbY3JsZl1bY3JsZl0ifX19",
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


# ═══════════════════════════════════════════
# الأوامر
# ═══════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)
    await update.message.reply_text(
        messages.WELCOME, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu()
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(messages.WELCOME, parse_mode=ParseMode.MARKDOWN)


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
# handle_url
# ═══════════════════════════════════════════

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    urls = extract_urls(text)
    if not urls:
        return
    sso_url = urls[0]
    user = update.effective_user

    if "skills.google" not in sso_url and "qwiklabs" not in sso_url and "accounts.google.com" not in sso_url:
        await update.message.reply_text("⚠️ الرابط لا يبدو من Google Skills.")
        return

    user_tag = f"@{user.username}" if user.username else f"@{user.first_name}"
    log.info(f"🔗 URL: {sso_url[:150]}")

    if is_full_sso_url(sso_url):
        num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag)
        await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.")
        asyncio.create_task(process_queue(update.effective_chat.id, user.id, context))
        return

    if is_direct_addsession_url(sso_url):
        from automation.sso_flow import extract_email_from_url
        email = extract_email_from_url(sso_url)
        if email:
            await db.set_session(user_id=user.id, sso_url=sso_url, state="waiting_password")
            await update.message.reply_text(
                f"📧 لقينا الإيميل:\n`{email}`\n\n🔑 *أرسل كلمة السر باش نكملو:*",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag)
    await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.")
    asyncio.create_task(process_queue(update.effective_chat.id, user.id, context))


# ═══════════════════════════════════════════
# handle_password
# ═══════════════════════════════════════════

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
    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag)
    await update.message.reply_text(f"📥 تم استلام الرابط رقم {num}.")
    asyncio.create_task(process_queue(update.effective_chat.id, user.id, context))


# ═══════════════════════════════════════════
# process_queue
# ═══════════════════════════════════════════

async def process_queue(chat_id, user_id, context):
    async with asyncio.Lock():
        item = await queue.get_next()
        if not item:
            return

        job = item
        try:
            # ✅ رسالة وحدة تتغير
            msg = await context.bot.send_message(chat_id=chat_id, text="🚀 جاري التنفيذ... [0/8]")

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

                # ❌ فشل
                if not result.get("success"):
                    message = result.get("message", "فشل")
                    try:
                        await msg.edit_text(f"❌ توقفنا\n\n📋 {message}")
                    except Exception:
                        pass
                    return

                # ✅ نجح
                domain = result["domain"]
                final_url = result["final_url"]
                flag = result.get("flag", "🇺🇸")

                # ✅ رسالة وحدة: رابط run.app
                try:
                    await msg.edit_text(
                        f"✅ *تم النشر!*\n\n"
                        f"🌐 *رابط run.app:*\n`{final_url}`\n\n"
                        f"🌍 *Region:* {flag}",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass

                # ✅ 3 ملفات dark
                for idx, dark in enumerate(DARK_FILES, 1):
                    try:
                        new_uri = build_darktunnel_uri_with_host(dark["uri"], domain)
                        if not new_uri:
                            continue
                        safe_domain = "".join(c for c in domain.lower() if c.isalnum() or c in ".-_")[:40]
                        filename = f"{dark['name']} - {safe_domain}.dark"
                        bio = io.BytesIO(new_uri.encode("utf-8"))
                        bio.name = filename
                        bio.seek(0)
                        await context.bot.send_document(
                            chat_id=chat_id, document=bio, filename=filename,
                            caption=f"✅ {dark['name']}",
                        )
                        log.info(f"✅ [{idx}/3] {dark['name']}")
                    except Exception as e:
                        log.error(f"❌ dark {dark['name']}: {e}", exc_info=True)

            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

        except Exception as e:
            log.exception("فشل تنفيذ المهمة")
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"❌ فشل\n\n{str(e)[:400]}")
            except Exception:
                pass

        finally:
            await queue.finish()
            if queue.queue_size() > 0:
                asyncio.create_task(process_queue(chat_id, user_id, context))


# ═══════════════════════════════════════════

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "status":
        await status_cmd(update, context)
    elif query.data == "help":
        await query.message.reply_text(messages.WELCOME, parse_mode=ParseMode.MARKDOWN)
