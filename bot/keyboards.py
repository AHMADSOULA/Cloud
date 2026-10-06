from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton("📊 حالتي", callback_data="status")],
        [InlineKeyboardButton("🔐 SSH WebSocket", callback_data="ssh_ws")],
        [InlineKeyboardButton("🌐 VMESS", callback_data="vmess")],
        [InlineKeyboardButton("⚡ VLESS", callback_data="vless")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ ADMIN", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات بوت", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 مستخدمين حالياً", callback_data="admin_users")],
        [InlineKeyboardButton("🚫 محظورين من بوت", callback_data="admin_banned")],
        [InlineKeyboardButton("📋 قائمة طلبات استخدام", callback_data="admin_requests")],
        [InlineKeyboardButton("⚡ زيادة سرعة مستخدم", callback_data="admin_priority")],
        [InlineKeyboardButton("🔨 حضر مستخدم عبر ID", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ إعطاء صلاحية عبر ID", callback_data="admin_grant")],
        [InlineKeyboardButton("⏸️ توقيف/تشغيل مستخدم", callback_data="admin_pause")],
        [InlineKeyboardButton("📢 إرسال رسالة إلى مستخدمين", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⛔ إيقاف البوت عن الجميع", callback_data="admin_stop_all")],
        [InlineKeyboardButton("▶️ تشغيل البوت للجميع", callback_data="admin_start_all")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ])


def ssh_types_menu():
    """أزرار أنواع SSH"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 YOUTUBE 4DAY", callback_data="ssh_create:youtube")],
        [InlineKeyboardButton("👻 SNAPCHAT 4DAY", callback_data="ssh_create:snapchat")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ])


def countries_menu(kind: str, countries: list):
    """أزرار الدول - kind يحدد نوع"""
    rows = []
    for idx, c in enumerate(countries):
        rows.append([
            InlineKeyboardButton(
                f"{c['flag']} {c['name']}",
                callback_data=f"{kind}_country:{idx}"
            )
        ])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def ssh_countries_menu(countries: list):
    """متوافق مع القديم"""
    return countries_menu("ssh", countries)
