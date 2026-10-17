from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(is_admin=False):
    rows = [
        [InlineKeyboardButton("☁️ Cloud Run (SSO)", callback_data="cloud_run")],
        [InlineKeyboardButton("🔐 SSH", callback_data="proto:SSH Websocket")],
        [InlineKeyboardButton("🌐 VMESS", callback_data="proto:V2Ray VMESS")],
        [InlineKeyboardButton("⚡ VLESS", callback_data="proto:V2Ray VLESS")],
        [InlineKeyboardButton("🛡️ TROJAN", callback_data="proto:TROJAN")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ ADMIN", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def list_menu(items, prefix):
    """يبني الأزرار مع الإيموجي (إذا كان موجود)"""
    rows = []
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            name = item.get('name', '')
            emoji = item.get('emoji', '')
            display = f"{emoji} {name}" if emoji else f"🌍 {name}"
        else:
            display = str(item)
        
        # ✅ تقصير الاسم باش يبان مزيان فـ الزر
        if len(display) > 60:
            display = display[:57] + "..."
            
        rows.append([InlineKeyboardButton(display, callback_data=f"{prefix}:{idx}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def continents_menu(continents):
    return list_menu(continents, "cont")


def countries_menu(countries):
    return list_menu(countries, "country")


def admin_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]])
