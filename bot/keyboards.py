from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu(is_admin=False):
    rows = [
        [InlineKeyboardButton("📊 حالتي", callback_data="status")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ ADMIN", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 تحويل SSH", callback_data="convert:ssh")],
        [InlineKeyboardButton("🌐 تحويل VMESS", callback_data="convert:vmess")],
        [InlineKeyboardButton("⚡ تحويل VLESS", callback_data="convert:vless")],
        [InlineKeyboardButton("🛡️ تحويل Trojan", callback_data="convert:trojan")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_main")],
    ])
