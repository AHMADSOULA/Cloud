n()
import asyncio
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config import config
from bot import handlers
from database.db import init_db
from utils.logger import get_logger
from utils.helpers import extract_urls

log = get_logger("Main")

# ═══════════════════════════════════════════
# HTTP Server بسيط (باش Render يلقى Port)
# ═══════════════════════════════════════════

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        pass  # نسكتو اللوغات

def run_http_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info(f"✅ HTTP Server على port {port}")
    server.serve_forever()

# ═══════════════════════════════════════════
# Route Text
# ═══════════════════════════════════════════

async def route_text(update, context):
    from database import db
    user = update.effective_user
    text = update.message.text or ""

    if await handlers.handle_admin_input(update, context, text):
        return

    if extract_urls(text):
        await handlers.handle_url(update, context)
        return

    session = await db.get_session(user.id)
    if session and session.get("state") == "waiting_password":
        await handlers.handle_password(update, context)
        return

    await update.message.reply_text("ℹ️ أرسل /start للبدء.")

# ═══════════════════════════════════════════
# post_init (باش نخلقو الجداول قبل تشغيل البوت)
# ═══════════════════════════════════════════

async def post_init(app):
    log.info("🚀 جاري تهيئة قاعدة البيانات...")
    await init_db()
    log.info("✅ DB ready")
    
    from database import db
    await db.register_user(config.ADMIN_ID, "ADMIN")
    log.info("✅ ADMIN registered")

# ═══════════════════════════════════════════
# main
# ═══════════════════════════════════════════

def main():
    log.info("🚀 starting...")

    # ✅ 1. نشغلو HTTP Server فـ thread منفصل
    threading.Thread(target=run_http_server, daemon=True).start()

    # ✅ 2. نجهزو البوت مع post_init
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("status", handlers.status_cmd))
    app.add_handler(CommandHandler("cancel", handlers.cancel_cmd))
    app.add_handler(CommandHandler("request", handlers.request_cmd))
    app.add_handler(CallbackQueryHandler(handlers.button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_text))

    log.info("🚀 البوت شغال!")

    # ✅ 3. run_polling فـ الـ main thread (هو اللي كيتكلف بالـ event loop)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    mai
