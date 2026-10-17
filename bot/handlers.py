import asyncio
import io
import random
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.keyboards import main_menu, continents_menu, countries_menu, admin_menu
from database import db
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sshs8 import SSHS8
from automation.vmess import build_ssh_dark, build_vmess_dark, build_vless_dark, build_trojan_dark

log = get_logger("Handlers")

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.register_user(user.id, user.username or user.first_name)
    if is_admin(user.id):
        await update.message.reply_text("👋 مرحباً ADMIN\n\nالبوت جاهز.", reply_markup=main_menu(is_admin=True))
        return
    if await db.has_access(user.id):
        await update.message.reply_text("👋 مرحباً", reply_markup=main_menu(is_admin=False))
        return
    await update.message.reply_text("🔒 أرسل /request باش تطلب صلاحية.")

async def handle_proto_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    proto_name = query.data.split(":", 1)[1]
    chat_id = query.message.chat_id

    await query.message.edit_text(f"⏳ جاري الدخول لـ {proto_name}...")
    browser = StealthBrowser()
    try:
        ctx = await browser.start()
        ssh = SSHS8(ctx, bot=context.bot, chat_id=chat_id)
        ok = await ssh.open_home()
        if not ok: 
            await query.message.edit_text("❌ فشل فتح الموقع.")
            await browser.close()
            return

        continents = await ssh.open_protocol(proto_name)
        if not continents: 
            await query.message.edit_text("❌ ما لقيناش القارات.")
            await browser.close()
            return

        context.user_data["ssh_browser"] = browser
        context.user_data["ssh_obj"] = ssh
        context.user_data["continents"] = continents
        context.user_data["proto_name"] = proto_name

        await query.message.edit_text(f"🔌 *{proto_name}*\n\n🌍 اختر القارة:", parse_mode=ParseMode.MARKDOWN, reply_markup=continents_menu(continents))
    except Exception as e:
        await query.message.edit_text(f"❌ {e}")
        await browser.close()

async def handle_continent_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    continents = context.user_data.get("continents", [])
    ssh = context.user_data.get("ssh_obj")
    
    if not ssh or idx >= len(continents): return
    
    continent = continents[idx]
    await query.message.edit_text(f"⏳ جاري فتح {continent['name']}...")
    
    countries = await ssh.open_continent(continent['name'])
    context.user_data["countries"] = countries
    await query.message.edit_text(f"🌍 *{continent['name']}*\n\nاختر الدولة:", parse_mode=ParseMode.MARKDOWN, reply_markup=countries_menu(countries))

async def handle_country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split(":")[1])
    countries = context.user_data.get("countries", [])
    ssh = context.user_data.get("ssh_obj")
    browser = context.user_data.get("ssh_browser")
    proto_name = context.user_data.get("proto_name", "")
    chat_id = query.message.chat_id

    if not ssh or idx >= len(countries): return

    country = countries[idx]
    await query.message.edit_text(f"⏳ جاري فتح {country['name']}...")
    
    servers = await ssh.open_country(country['name'])
    if not servers:
        await query.message.edit_text("❌ ما لقيناش خوادم.")
        return

    server = random.choice(servers)
    await query.message.edit_text(f"🎲 *اختيار عشوائي*\n\n🖥️ {server['id']}\n\n⏳ جاري إنشاء الحساب...")

    result = await ssh.create_account(server['href'])
    
    if result.get("success"):
        await context.bot.send_message(chat_id, f"✅ *تم إنشاء الحساب!*\n🌐 Host: `{result.get('ip')}`\n👤 User: `{result.get('user')}`\n🔑 Pass: `{result.get('password')}`", parse_mode=ParseMode.MARKDOWN)
        
        # بناء الملفات
        for kind in ["youtube", "snapchat"]:
            if "SSH" in proto_name:
                uri = build_ssh_dark(result.get("ip"), result.get("user"), result.get("password"), kind)
            elif "VMESS" in proto_name:
                uri = build_vmess_dark({"add": result.get("ip"), "id": result.get("link")}, result.get("password"), kind)
            elif "VLESS" in proto_name:
                uri = build_vless_dark({"add": result.get("ip"), "id": result.get("link")}, result.get("password"), kind)
            else:
                uri = build_trojan_dark({"add": result.get("ip")}, result.get("password"), kind)

            if uri:
                filename = f"{proto_name.replace(' ', '_')}_{kind.upper()}_{server['id']}.dark"
                bio = io.BytesIO(uri.encode())
                bio.name = filename
                await context.bot.send_document(chat_id=chat_id, document=bio, filename=filename)
                await asyncio.sleep(0.5)
    else:
        await query.message.edit_text(f"❌ فشل: {result.get('message')}")

    await ssh.close()
    await browser.close()
    for key in ["ssh_browser", "ssh_obj", "continents", "countries"]:
        context.user_data.pop(key, None)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("proto:"):
        await handle_proto_selected(update, context)
    elif data.startswith("cont:"):
        await handle_continent_selected(update, context)
    elif data.startswith("country:"):
        await handle_country_selected(update, context)
    elif data == "cloud_run":
        await query.message.edit_text("☁️ أرسل رابط SSO ديال Cloud Run.")
