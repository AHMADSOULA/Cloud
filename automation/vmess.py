"""
automation/vmess.py
- build_ssh_dark / build_vmess_dark / build_vless_dark
- مقفولة (locked)
"""
from automation.sshs8 import PAYLOADS
from utils.dark_crypto import build_locked_dark
from utils.logger import get_logger

log = get_logger("VMESS")


def build_ssh_dark(host: str, username: str, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف SSH dark مقفول"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])
        country = country or {"name": "France", "flag": "🇫🇷"}

        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        ssh_config = {
            "host": host or "",
            "port": 22,
            "username": username or "",
            "password": password or "",
        }

        return build_locked_dark(
            kind="SSH",
            name=name,
            payload=cfg["payload"],
            ssh_config=ssh_config,
        )
    except Exception as e:
        log.error(f"❌ build_ssh_dark: {e}", exc_info=True)
        return None


def build_vmess_dark(vmess_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف VMESS dark مقفول"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])
        country = country or {"name": "France", "flag": "🇫🇷"}

        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        v2ray_config = {
            "host": vmess_data.get("add") or vmess_data.get("host") or "",
            "port": int(vmess_data.get("port") or 443),
            "uuid": vmess_data.get("id") or "",
            "serverNameIndication": cfg["sni"],
            "wsPath": vmess_data.get("path") or "/vmess/",
            "wsHeaderHost": cfg["ws_header_host"],
        }

        return build_locked_dark(
            kind="VMESS",
            name=name,
            payload=cfg["payload"],
            v2ray_config=v2ray_config,
        )
    except Exception as e:
        log.error(f"❌ build_vmess_dark: {e}", exc_info=True)
        return None


def build_vless_dark(vless_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف VLESS dark مقفول"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])
        country = country or {"name": "France", "flag": "🇫🇷"}

        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        v2ray_config = {
            "host": vless_data.get("add") or vless_data.get("host") or "",
            "port": int(vless_data.get("port") or 443),
            "uuid": vless_data.get("id") or "",
            "serverNameIndication": cfg["sni"],
            "wsPath": vless_data.get("path") or "/vless/",
            "wsHeaderHost": cfg["ws_header_host"],
        }

        return build_locked_dark(
            kind="VLESS",
            name=name,
            payload=cfg["payload"],
            v2ray_config=v2ray_config,
        )
    except Exception as e:
        log.error(f"❌ build_vless_dark: {e}", exc_info=True)
        return None
