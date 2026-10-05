"""
utils/dark_encrypt_test.py
- اختبار كل طرق التشفير
- يبعث كل طريقة كملف للمستخدم
"""
import io
import asyncio
import base64
import json
from utils.logger import get_logger

log = get_logger("DarkEncryptTest")


# ═══════════════════════════════════════════
# بنية SSH الأساسية
# ═══════════════════════════════════════════

def _build_ssh_config(host: str, username: str, password: str) -> dict:
    return {
        "type": "SSH",
        "name": "SSH",
        "sshTunnelConfig": {
            "sshConfig": {
                "host": host or "",
                "port": 22,
                "username": username or "",
                "password": password or "",
            },
            "injectConfig": {
                "mode": "PROXY",
                "proxyHost": "34.43.46.91",
                "proxyPort": 443,
                "payload": "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]",
            },
        },
    }


# ═══════════════════════════════════════════
# 10 طرق تشفير
# ═══════════════════════════════════════════

def method_1_base64_standard(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8")
    return "darktunnel://" + b64


def method_2_base64_rstrip(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8").rstrip("=")
    return "darktunnel://" + b64


def method_3_base64_urlsafe(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("utf-8")
    return "darktunnel://" + b64


def method_4_base64_urlsafe_rstrip(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return "darktunnel://" + b64


def method_5_base64_double(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64_1 = base64.b64encode(raw)
    b64_2 = base64.b64encode(b64_1).decode("utf-8")
    return "darktunnel://" + b64_2


def method_6_base64_hex(host: str, username: str, password: str) -> str:
    config = _build_ssh_config(host, username, password)
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    hex_str = raw.hex()
    b64 = base64.b64encode(hex_str.encode("utf-8")).decode("utf-8")
    return "darktunnel://" + b64


def method_7_locked_sshConfig(host: str, username: str, password: str) -> str:
    config = {
        "type": "SSH",
        "name": "SSH_4DAY🇫🇷",
        "sshTunnelConfig": {
            "injectConfig": {
                "enabled": True,
                "mode": "PROXY",
            }
        },
        "encryptedLockedConfig": {
            "LockedAppConfig": {
                "VersionCode": 32,
                "VersionName": "1.0.26",
                "Message": "APP_/DARK TUNEEL📱",
                "ConnectedMessage": "بصحتك🤍",
                "ExpiredAtTimestamp": 0,
                "HardwareIdList": [],
                "TunnelType": "SSH",
                "IsSshLocked": True,
            },
            "EncryptedLockedConfig": {
                "InjectConfig": {
                    "IsEncrypted": True,
                    "EncryptedMode": "PROXY",
                    "EncryptedProxyHost": "34.43.46.91",
                    "EncryptedProxyPort": "443",
                    "EncryptedServerNameIndication": [],
                    "EncryptedPayload": "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]",
                    "EncryptedDnsttDnsHost": "1.1.1.1",
                    "EncryptedDnsttDnsPort": "53",
                    "EncryptedDnsttServerName": [],
                    "EncryptedDnsttPubkey": [],
                },
                "SshConfig": {
                    "IsEncrypted": True,
                    "IsLocked": True,
                    "EncryptedHost": host or "",
                    "EncryptedPort": "22",
                    "EncryptedUsername": username or "",
                    "EncryptedPassword": password or "",
                },
                "V2RayConfig": {
                    "IsEncrypted": True,
                    "IsInjectModeEnabled": False,
                    "EncryptedConfig": [],
                },
            },
        },
    }
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8")
    return "darktunnel://" + b64


def method_8_locked_rstrip(host: str, username: str, password: str) -> str:
    config = {
        "type": "SSH",
        "name": "SSH_4DAY🇫🇷",
        "sshTunnelConfig": {
            "injectConfig": {
                "enabled": True,
                "mode": "PROXY",
            }
        },
        "encryptedLockedConfig": {
            "LockedAppConfig": {
                "VersionCode": 32,
                "VersionName": "1.0.26",
                "Message": "APP_/DARK TUNEEL📱",
                "ConnectedMessage": "بصحتك🤍",
                "ExpiredAtTimestamp": 0,
                "HardwareIdList": [],
                "TunnelType": "SSH",
                "IsSshLocked": True,
            },
            "EncryptedLockedConfig": {
                "InjectConfig": {
                    "IsEncrypted": True,
                    "EncryptedMode": "PROXY",
                    "EncryptedProxyHost": "34.43.46.91",
                    "EncryptedProxyPort": "443",
                    "EncryptedServerNameIndication": [],
                    "EncryptedPayload": "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]",
                    "EncryptedDnsttDnsHost": "1.1.1.1",
                    "EncryptedDnsttDnsPort": "53",
                    "EncryptedDnsttServerName": [],
                    "EncryptedDnsttPubkey": [],
                },
                "SshConfig": {
                    "IsEncrypted": True,
                    "IsLocked": True,
                    "EncryptedHost": host or "",
                    "EncryptedPort": "22",
                    "EncryptedUsername": username or "",
                    "EncryptedPassword": password or "",
                },
                "V2RayConfig": {
                    "IsEncrypted": True,
                    "IsInjectModeEnabled": False,
                    "EncryptedConfig": [],
                },
            },
        },
    }
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8").rstrip("=")
    return "darktunnel://" + b64


def method_9_sshConfig_with_encryptedLocked(host: str, username: str, password: str) -> str:
    config = {
        "type": "SSH",
        "name": "SSH_4DAY🇫🇷",
        "sshTunnelConfig": {
            "sshConfig": {
                "host": host or "",
                "port": 22,
                "username": username or "",
                "password": password or "",
            },
            "injectConfig": {
                "enabled": True,
                "mode": "PROXY",
                "proxyHost": "34.43.46.91",
                "proxyPort": 443,
                "payload": "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]",
            },
        },
        "encryptedLockedConfig": {
            "LockedAppConfig": {
                "IsSshLocked": True,
            }
        },
    }
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8")
    return "darktunnel://" + b64


def method_10_sshConfig_locked_name(host: str, username: str, password: str) -> str:
    config = {
        "type": "SSH",
        "name": "🔒 LOCKED - SSH_4DAY🇫🇷",
        "sshTunnelConfig": {
            "sshConfig": {
                "host": host or "",
                "port": 22,
                "username": username or "",
                "password": password or "",
            },
            "injectConfig": {
                "enabled": True,
                "mode": "PROXY",
                "proxyHost": "34.43.46.91",
                "proxyPort": 443,
                "payload": "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]",
            },
            "IsLocked": True,
            "IsSshLocked": True,
        },
    }
    raw = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64 = base64.b64encode(raw).decode("utf-8")
    return "darktunnel://" + b64


METHODS = {
    "1_base64_standard": method_1_base64_standard,
    "2_base64_rstrip": method_2_base64_rstrip,
    "3_base64_urlsafe": method_3_base64_urlsafe,
    "4_base64_urlsafe_rstrip": method_4_base64_urlsafe_rstrip,
    "5_base64_double": method_5_base64_double,
    "6_base64_hex": method_6_base64_hex,
    "7_locked_sshConfig": method_7_locked_sshConfig,
    "8_locked_rstrip": method_8_locked_rstrip,
    "9_sshConfig_with_encryptedLocked": method_9_sshConfig_with_encryptedLocked,
    "10_sshConfig_locked_name": method_10_sshConfig_locked_name,
}


# ═══════════════════════════════════════════
# دالة الاختبار الرئيسية
# ═══════════════════════════════════════════

async def test_all_methods_and_notify(bot, chat_id: int, host: str, username: str, password: str):
    """
    ✅ يجرّب كل الطرق ويبعث كل طريقة كملف
    """
    log.info(f"🧪 Testing {len(METHODS)} methods for {host}")

    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🧪 *اختبار {len(METHODS)} طريقة تشفير*\n\n"
            f"🖥️ Host: `{host}`\n"
            f"👤 User: `{username}`\n"
            f"🔑 Pass: `{password}`\n\n"
            f"⏳ جاري الإرسال..."
        ),
        parse_mode="Markdown",
    )

    results = []

    for idx, (name, func) in enumerate(METHODS.items(), 1):
        try:
            uri = func(host, username, password)
            if not uri:
                log.warning(f"⚠️ {name}: فشل البناء")
                results.append((name, "❌ فشل"))
                continue

            filename = f"TEST_{idx}_{name}.dark"
            bio = io.BytesIO(uri.encode("utf-8"))
            bio.name = filename
            bio.seek(0)

            await bot.send_document(
                chat_id=chat_id,
                document=bio,
                filename=filename,
                caption=(
                    f"🧪 *طريقة {idx}/{len(METHODS)}*\n\n"
                    f"📛 الاسم: `{name}`\n"
                    f"📁 الملف: `{filename}`\n\n"
                    f"جرّبها فـ التطبيق وقوللي واش خدمت ✅"
                ),
                parse_mode="Markdown",
            )

            results.append((name, "✅ مرسل"))
            log.info(f"✅ {name} → sent")

            await asyncio.sleep(0.8)

        except Exception as e:
            log.error(f"❌ {name}: {e}", exc_info=True)
            results.append((name, f"❌ {str(e)[:50]}"))

    summary = "\n".join([f"{i+1}. `{n}` — {s}" for i, (n, s) in enumerate(results)])
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ *تم إرسال {len(results)} طريقة*\n\n"
            f"{summary}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *جرب كل طريقة فـ التطبيق*\n"
            f"✅ اللي تخدم → قوللي اسمها"
        ),
        parse_mode="Markdown",
    )
