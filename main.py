from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from config import config
from bot import handlers
from database.db import init_db
from utils.logger import get_logger

log = get_logger("Main")

async def post_init(app):
    await init_db()
    from database import db
    await db.register_user(config.ADMIN_ID, "ADMIN")

def main():
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("status", handlers.status_cmd))
    app.add_handler(CommandHandler("cancel", handlers.cancel_cmd))
    app.add_handler(CommandHandler("request", handlers.request_cmd))
    app.add_handler(CallbackQueryHandler(handlers.button_handler))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
