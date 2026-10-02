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
# قوالب JSON + VLESS
# ═══════════════════════════════════════════

VLESS_TEMPLATE = (
    "vless://aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000@google.com:443"
    "?path=%2FTelegram%2F%40AM2_D3%2F%40AHMAD3214&security=tls&encryption=none"
    "&host={domain}&type=ws&sni={domain}#%40AHMAD3214"
)

JSON_TEMPLATE = r'''{
  "dns": {
    "fallbackStrategy": "disabledIfAnyMatch",
    "hosts": {},
    "servers": [
      {
        "address": "tcp://8.8.8.8",
        "fakedns": [
          {"ipPool": "198.18.0.0/15", "poolSize": 65535}
        ],
        "queryStrategy": "UseIPv4"
      }
    ]
  },
  "inbounds": [
    {"listen": "0.0.0.0", "port": "1080", "protocol": "dokodemo-door",
     "settings": {"network": "tcp,udp", "followRedirect": true}, "tag": "tun-inbound"},
    {"listen": "127.0.0.1", "port": "10808", "protocol": "socks",
     "settings": {"auth": "noauth", "udp": true}, "tag": "socks-inbound"}
  ],
  "log": {"loglevel": "warning"},
  "outbounds": [
    {
      "mux": {"enabled": false},
      "protocol": "vless",
      "proxySettings": {"tag": "AhMed", "transportLayer": true},
      "settings": {
        "vnext": [{
          "address": "yt3.ggpht.com", "port": 443,
          "users": [{"encryption": "none", "flow": "", "id": "aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000", "level": 8}]
        }]
      },
      "streamSettings": {
        "network": "ws", "security": "tls",
        "tlsSettings": {"allowInsecure": true, "serverName": "yt3.ggpht.com"},
        "wsSettings": {"headers": {"Host": "__DOMAIN__"}, "path": "/Telegram/@AM2_D3/@AHMAD3214"}
      },
      "tag": "VLESS"
    },
    {
      "domainStrategy": "AsIs",
      "protocol": "http",
      "settings": {
        "servers": [{"address": "57.144.120.4", "port": 8080}],
        "headers": {"Host": "yt3.ggpht.com:443", "Proxy-Connection": "keep-alive",
                    "User-Agent": "FBAV/0.0", "X-iorg-bsid": "@AM2_D3"}
      },
      "tag": "@AM2_D3"
    },
    {"protocol": "freedom", "tag": "direct"},
    {"protocol": "blackhole", "tag": "block"}
  ],
  "policy": {"levels": {"8": {"connIdle": 300, "downlinkOnly": 1, "handshake": 4, "uplinkOnly": 1}}},
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      {"outboundTag": "direct", "protocol": ["dns"], "type": "field"},
      {"inboundTag": ["tun-inbound", "socks-inbound"], "outboundTag": "VLESS", "type": "field"}
    ]
  }
}'''


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
            browser = StealthBrowser()
            ctx = await browser.start()

            try:
                result = await run_sso_flow(
                    ctx,
                    job["sso_url"],
                    image=config.DEFAULT_IMAGE,
                    sender=None,
                    user_tag=job["user_tag"],
                )

                domain = result["domain"]
                final_url = result["final_url"]

                # ✅ رسالة النتيجة
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ **𝙃𝙚𝙧𝙚 𝙮𝙤𝙪 𝙜𝙤 𝙗𝙧𝙤**\n\n"
                        f"🌐 **Domain:**\n`{domain}`\n\n"
                        f"🔗 **URL:**\n`{final_url}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )

                # ✅ VLESS
                try:
                    vless_result = VLESS_TEMPLATE.format(domain=domain)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔗 <b>VLESS:</b>\n<pre><code class=\"language-java\">{vless_result}</code></pre>",
                        parse_mode='html',
                    )
                    log.info("✅ VLESS sent")
                except Exception as e:
                    log.error(f"❌ VLESS: {e}", exc_info=True)

                # ✅ JSON
                try:
                    json_result = JSON_TEMPLATE.replace("__DOMAIN__", domain)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"📄 <b>JSON:</b>\n<pre><code class=\"language-json\">{json_result}</code></pre>",
                        parse_mode='html',
                    )
                    log.info("✅ JSON sent")
                except Exception as e:
                    log.error(f"❌ JSON: {e}", exc_info=True)

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
