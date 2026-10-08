"""
utils/dark_crypto.py
- تشفير/فك تشفير darktunnel
- XOR + base64 URL-safe (نفس بنية التطبيق)
"""
import base64
import json
from utils.logger import get_logger

log = get_logger("DarkCrypto")


# ═══════════════════════════════════════════
# المفتاح السري
# ═══════════════════════════════════════════

SECRET_KEY = b"SSH4DAY-VIP-FRANCE-2026-OK!!"


# ═══════════════════════════════════════════
# base64 helpers (نفس GC.py)
# ═══════════════════════════════════════════

def _b64_pad(s: str) -> str:
    s = s.strip()
    return s + ("=" * ((4 - (len(s) % 4)) % 4)) if s else s


def darktunnel_encode(data: dict) -> str:
    """✅ يشفّر dict → darktunnel:// (نفس GC.py — بلا rstrip)"""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "darktunnel://" + base64.b64encode(raw).decode("utf-8")


def darktunnel_decode(uri: str) -> dict:
    """يفك darktunnel:// → dict"""
    b64 = _b64_pad(uri.split("darktunnel://", 1)[1].strip())
    return json.loads(base64.b64decode(b64.encode("utf-8")).decode("utf-8"))


# ═══════════════════════════════════════════
# XOR
# ═══════════════════════════════════════════

def xor_bytes(data: bytes, key: bytes = SECRET_KEY) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


# ═══════════════════════════════════════════
# إنشاء ملف locked
# ═══════════════════════════════════════════

def build_locked_dark(
    kind: str,
    name: str,
    payload: str,
    v2ray_config: dict = None,
    ssh_config: dict = None,
) -> str:
    """
    ✅ يبني ملف dark مقفول (encryptedLockedConfig)
    - kind: VMESS / VLESS / SSH
    - name: CONFIG_VPS_🇫🇷_5DAY
    - payload: CONNECT ...
    - v2ray_config / ssh_config: المعلومات
    """
    try:
        # ✅ 1. المعلومات الداخلية
        if kind in ("VMESS", "VLESS"):
            inner = {
                "type": kind,
                "name": name,
                "v2rayConfig": v2ray_config or {},
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": payload,
                    "dnsHost": "1.1.1.1",
                    "dnsPort": 53,
                },
                "sshConfig": {
                    "port": 80,
                    "locked": True,
                },
            }
        else:  # SSH
            inner = {
                "type": "SSH",
                "name": name,
                "sshConfig": ssh_config or {},
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": payload,
                    "dnsHost": "1.1.1.1",
                    "dnsPort": 53,
                },
            }

        # ✅ 2. JSON
        raw_json = json.dumps(inner, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        # ✅ 3. XOR
        encrypted_bytes = xor_bytes(raw_json)

        # ✅ 4. base64 URL-safe
        encrypted_b64 = base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")

        # ✅ 5. البنية الخارجية
        outer = {
            "type": kind,
            "name": name,
            f"{kind.lower()}TunnelConfig": {
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                }
            },
            "encryptedLockedConfig": encrypted_b64,
        }

        # ✅ 6. darktunnel://
        return darktunnel_encode(outer)

    except Exception as e:
        log.error(f"❌ build_locked_dark: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════
# فك التشفير (للاختبار)
# ═══════════════════════════════════════════

def decrypt_locked_dark(encrypted_uri: str) -> dict:
    """يفك التشفير — يرجّع المعلومات"""
    try:
        outer = darktunnel_decode(encrypted_uri)

        enc = outer.get("encryptedLockedConfig")
        if not enc:
            return outer

        enc = _b64_pad(enc)
        encrypted_bytes = base64.urlsafe_b64decode(enc)
        raw_json = xor_bytes(encrypted_bytes)

        return json.loads(raw_json.decode("utf-8"))

    except Exception as e:
        log.error(f"❌ decrypt_locked_dark: {e}")
        return None


# ═══════════════════════════════════════════
# بناء ملف عادي (بلا قفل)
# ═══════════════════════════════════════════

def build_plain_dark(
    kind: str,
    name: str,
    payload: str,
    v2ray_config: dict = None,
    ssh_config: dict = None,
) -> str:
    """يبني ملف dark عادي (بلا تشفير) — نفس GC.py"""
    try:
        if kind in ("VMESS", "VLESS"):
            inner = {
                "type": kind,
                "name": name,
                f"{kind.lower()}TunnelConfig": {
                    "v2rayConfig": v2ray_config or {},
                    "injectConfig": {
                        "enabled": True,
                        "mode": "PROXY",
                        "proxyHost": "34.43.46.91",
                        "proxyPort": 443,
                        "payload": payload,
                    },
                },
            }
        else:  # SSH
            inner = {
                "type": "SSH",
                "name": name,
                "sshTunnelConfig": {
                    "sshConfig": ssh_config or {},
                    "injectConfig": {
                        "enabled": True,
                        "mode": "PROXY",
                        "proxyHost": "34.43.46.91",
                        "proxyPort": 443,
                        "payload": payload,
                    },
                },
            }

        return darktunnel_encode(inner)

    except Exception as e:
        log.error(f"❌ build_plain_dark: {e}", exc_info=True)
        return None
