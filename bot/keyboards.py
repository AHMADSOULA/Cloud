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
    rows = []
    for idx, item in enumerate(items):
        name = item.get('name') if isinstance(item, dict) else item
        # نزيدو الإيموجي ديال القارة/الدولة
        emoji = "🌍" if prefix == "cont" else "🏳️"
        rows.append([InlineKeyboardButton(f"{emoji} {name}", callback_data=f"{prefix}:{idx}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(rows)


def continents_menu(continents):
    return list_menu(continents, "cont")


def countries_menu(countries):
    return list_menu(countries, "country")


def admin_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]])
