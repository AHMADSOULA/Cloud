from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ═══════════════════════════════════════════
# القائمة الرئيسية
# ═══════════════════════════════════════════

def main_menu(is_admin: bool = False):
    rows = [
        [InlineKeyboardButton("📊 حالتي", callback_data="status")],
        [InlineKeyboardButton("🚀 بروتوكولات", callback_data="protocols")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🔴 تسجيل (REC)", callback_data="rec_start")])
        rows.append([InlineKeyboardButton("⏹️ إيقاف التسجيل", callback_data="rec_stop")])
        rows.append([InlineKeyboardButton("⚙️ ADMIN", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════
# قائمة الأدمن
# ═══════════════════════════════════════════

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


# ═══════════════════════════════════════════
# قائمة عامة (للدول والبروتوكولات)
# ═══════════════════════════════════════════

def list_menu(items: list, prefix: str):
    rows = []
    for idx, item in enumerate(items):
        name = item.get('name') if isinstance(item, dict) else item
        rows.append([InlineKeyboardButton(name[:60], callback_data=f"{prefix}:{idx}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


# ═══════════════════════════════════════════
# قوائم مخصصة
# ═══════════════════════════════════════════

def protocols_menu(protocols: list):
    """قائمة البروتوكولات (SSH, VMESS, VLESS...)"""
    return list_menu(protocols, "proto")


def continents_menu(continents: list):
    """قائمة القارات (Europe, Asia...)"""
    return list_menu(continents, "cont")


def countries_menu(countries: list):
    """قائمة الدول (France, Germany...)"""
    return list_menu(countries, "country")


def servers_menu(servers: list):
    """قائمة الخوادم (E105, E97...)"""
    return list_menu(servers, "server")


# ═══════════════════════════════════════════
# قائمة نوع SSH (YOUTUBE / SNAPCHAT) — اختياري
# ═══════════════════════════════════════════

def ssh_types_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 YOUTUBE 4DAY", callback_data="ssh_create:youtube")],
        [InlineKeyboardButton("👻 SNAPCHAT 4DAY", callback_data="ssh_create:snapchat")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ])
