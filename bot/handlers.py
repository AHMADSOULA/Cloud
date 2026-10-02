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
# طابور (Queue)
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

    def position(self, user_id):
        for i, item in enumerate(self.queue):
            if item["user_id"] == user_id:
                return i + 1
        return 0

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
# قوالب
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

DARKTUNNEL_BASE_URI = "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoi2YXYrNin2YbZiiDYp9iz2YrYpyDZiCDYp9ir2YrYsSAiLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiYWx0MTMueXQzLmdncGh0LmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYWx0MTMueXQzLmdncGh0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQxNDAwODYxMjEyMy5ldXJvcGUtd2VzdDEucnVuLmFwcCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNvbm5lY3Rpb246IGtlZXAtYWxpdmVbY3JsZl1jb25uZWN0aW9uOiBrZWVwLWFsaXZlW2NybGZddXNlci1hZ2VudDogRkJBVi8wLjAgW2NybGZdeC1pb3JnLWJzaWQ6IEBBTTJfRDNbY3JsZl1bY3JsZl0ifX19"


def _b64_pad(s: str) -> str:
    return s + ("=" * ((4 - (len(s) % 4)) % 4)) if s else s


def build_darktunnel_uri_with_host(new_host: str) -> str:
    b64 = _b64_pad(DARKTUNNEL_BASE_URI.split("darktunnel://", 1)[1].strip())
    data = json.loads(base64.b64decode(b64.encode("utf-8")).decode("utf-8"))
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

    # ✅ نضيف للطابور
    num = await queue.add(user.id, update.effective_chat.id, sso_url, user_tag)

    # ✅ نبعث رسالة التأكيد
    await update.message.reply_text(
        f"📥 تم استلام الرابط رقم {num} وسيبدأ الآن.\n"
        f"يمكنك إرسال رابط آخر وسيضاف إلى الطابور تلقائياً."
    )

    # ✅ نبعث رسالة البدء
    await update.message.reply_text("☁️ GC.Run\n✅ تم استلام الرابط. جاري التنفيذ الآن...")

    # ✅ نشغلو في الخلفية
    asyncio.create_task(process_queue(update.effective_chat.id, user.id, context))


# ═══════════════════════════════════════════
# معالجة الطابور
# ═══════════════════════════════════════════

async def process_queue(chat_id, user_id, context):
    async with asyncio.Lock():  # lock بسيط
        item = await queue.get_next()
        if not item:
            return

        job = item
        msg = None
        try:
            # نلقاو آخر رسالة في الشات
            # نبعتو رسالة باش نستعملوها كـ sender
            msg = await context.bot.send_message(chat_id=chat_id, text="⏳ بدء العملية...")

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

                # ✅ النتيجة
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"✅ **𝙃𝙚𝙧𝙚 𝙮𝙤𝙪 𝙜𝙤 𝙗𝙧𝙤**\n\n"
                        f"🌐 **Domain:**\n`{domain}`\n\n"
                        f"🔗 **URL:**\n`{final_url}`"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )

                # VLESS
                vless_result = VLESS_TEMPLATE.format(domain=domain)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔗 <b>VLESS:</b>\n<pre><code class=\"language-java\">{vless_result}</code></pre>",
                    parse_mode='html',
                )

                # JSON
                json_result = JSON_TEMPLATE.replace("__DOMAIN__", domain)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"📄 <b>JSON:</b>\n<pre><code class=\"language-json\">{json_result}</code></pre>",
                    parse_mode='html',
                )

                # Dark
                new_uri = build_darktunnel_uri_with_host(domain)
                safe_domain = "".join(c for c in domain.lower() if c.isalnum() or c in ".-_")[:40]
                bio = io.BytesIO(new_uri.encode("utf-8"))
                bio.name = f"زين و اسيا مجاني - {safe_domain}.dark"
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=bio,
                    filename=bio.name,
                    caption=f"✅ ملف DarkTunnel جاهز:\n`{domain}`",
                )

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

            # ✅ إذا كاين شي مهمة أخرى، نشغلوها
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
