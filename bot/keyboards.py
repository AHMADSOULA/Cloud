from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton("📊 حالتي", callback_data="status")],
        [InlineKeyboardButton("🔐 SSH WebSocket", callback_data="ssh_start")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⏹️ إيقاف التسجيل", callback_data="rec_stop")])
        rows.append([InlineKeyboardButton("⚙️ ADMIN", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("🚫 محظورين", callback_data="admin_banned")],
        [InlineKeyboardButton("📋 طلبات", callback_data="admin_requests")],
        [InlineKeyboardButton("⚡ سرعة", callback_data="admin_priority")],
        [InlineKeyboardButton("🔨 حظر", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ صلاحية", callback_data="admin_grant")],
        [InlineKeyboardButton("⏸️ توقيف/تشغيل", callback_data="admin_pause")],
        [InlineKeyboardButton("📢 رسالة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⛔ إيقاف للجميع", callback_data="admin_stop_all")],
        [InlineKeyboardButton("▶️ تشغيل للجميع", callback_data="admin_start_all")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ])


def list_menu(items: list, prefix: str):
    rows = []
    for idx, item in enumerate(items):
        name = item.get('name') if isinstance(item, dict) else item
        rows.append([InlineKeyboardButton(name[:60], callback_data=f"{prefix}:{idx}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def continents_menu(continents: list):
    return list_menu(continents, "cont")


def countries_menu(countries: list):
    return list_menu(countries, "country")
