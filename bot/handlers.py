import asyncio
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
# قوالب VLESS (3 مختلفة)
# ═══════════════════════════════════════════

VLESS_FREE = (
    "vless://aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000@google.com:443"
    "?path=%2FTelegram%2F%40AM2_D3%2F%40AHMAD3214&security=tls&encryption=none"
    "&host={domain}&type=ws&sni=alt13.yt3.ggpht.com#%40AM2_D3%20FREE"
)

VLESS_YOUTUBE = (
    "vless://aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000@google.com:443"
    "?path=%2FTelegram%2F%40AM2_D3%2F%40AHMAD3214&security=tls&encryption=none"
    "&host={domain}&type=ws&sni=googlevideo.com#%40AM2_D3%20YOUTUBE"
)

VLESS_SNAPCHAT = (
    "vless://aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000@google.com:443"
    "?path=%2FTelegram%2F%40AM2_D3%2F%40AHMAD3214&security=tls&encryption=none"
    "&host={domain}&type=ws&sni=api.snapchat.com#%40AM2_D3%20SNAPCHAT"
)


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
# استقبال SSO
# ═══════════════════════════════════════════

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    urls = extract_urls(text)
    if not urls:
        await update.message.reply_text(messages.NO_URL)
        return
    sso_url = urls[0]
    user = update.effective_user

    if "skills.google" not in sso_url and "qwiklabs" not in sso_url:
        await update.message.reply_text("⚠️ الرابط لا يبدو من Google Skills.")
        return

    user_tag = f"@{user.username}" if user.username else f"@{user.first_name}"

    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag)

    await update.message.reply_text(
        f"📥 تم استلام الرابط رقم {num} وسيبدأ الآن.\n"
        f"يمكنك إرسال رابط آخر وسيضاف إلى الطابور تلقائياً."
    )

    asyncio.create_task(process_queue(update.effective_chat.id, user.id, context))


# ═══════════════════════════════════════════
# معالجة الطابور
# ═══════════════════════════════════════════

async def process_queue(chat_id, user_id, context):
    async with asyncio.Lock():
        item = await queue.get_next()
        if not item:
            return

        job = item
        try:
            # ✅ نبعثو رسالة باش نستعملوها كـ sender للتصوير
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text="⏳ بدء العملية...",
            )

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

                domain = result["domain"]
                final_url = result["final_url"]

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ **𝙃𝙚𝙧𝙚 𝙮𝙤𝙪 𝙜𝙤 𝙗𝙧𝙤**\n\n"
                        f"🌐 **Domain:**\n`{domain}`\n\n"
                        f"🔗 **URL:**\n`{final_url}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )

                # ✅ VLESS FREE
                try:
                    vless = VLESS_FREE.format(domain=domain)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔗 **VLESS FREE:**\n<pre><code class=\"language-java\">{vless}</code></pre>",
                        parse_mode='html',
                    )
                except Exception as e:
                    log.error(f"❌ VLESS FREE: {e}", exc_info=True)

                # ✅ VLESS YOUTUBE
                try:
                    vless = VLESS_YOUTUBE.format(domain=domain)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔗 **VLESS YOUTUBE:**\n<pre><code class=\"language-java\">{vless}</code></pre>",
                        parse_mode='html',
                    )
                except Exception as e:
                    log.error(f"❌ VLESS YOUTUBE: {e}", exc_info=True)

                # ✅ VLESS SNAPCHAT
                try:
                    vless = VLESS_SNAPCHAT.format(domain=domain)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔗 **VLESS SNAPCHAT:**\n<pre><code class=\"language-java\">{vless}</code></pre>",
                        parse_mode='html',
                    )
                except Exception as e:
                    log.error(f"❌ VLESS SNAPCHAT: {e}", exc_info=True)

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
