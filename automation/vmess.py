"""
automation/vmess.py
- build_ssh_dark / build_vmess_dark / build_vless_dark / build_trojan_dark
- Payload موحد للـ SSH
- SNI/WSHost = youtube.com للـ V2Ray
"""
import base64
import json
from automation.sshs8 import PAYLOADS, SSH_PAYLOAD, V2RAY_SNI, V2RAY_WS_HOST
from utils.logger import get_logger

log = get_logger("VMESS")


def _encode(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "darktunnel://" + base64.b64encode(raw).decode("utf-8")


# ═══════════════════════════════════════════
# SSH
# ═══════════════════════════════════════════

def build_ssh_dark(host: str, username: str, password: str, kind: str = "youtube", country: dict = None) -> str:
    try:
        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        inner = {
            "type": "SSH",
            "name": name,
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
                    "payload": SSH_PAYLOAD,
                },
            },
        }
        return _encode(inner)
    except Exception as e:
        log.error(f"❌ build_ssh_dark: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════
# VMESS
# ═══════════════════════════════════════════

def build_vmess_dark(vmess_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    try:
        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        inner = {
            "type": "VMESS",
            "name": name,
            "vmessTunnelConfig": {
                "v2rayConfig": {
                    "host": vmess_data.get("add") or vmess_data.get("host") or "",
                    "port": int(vmess_data.get("port") or 443),
                    "uuid": vmess_data.get("id") or "",
                    "serverNameIndication": V2RAY_SNI,
                    "wsPath": vmess_data.get("path") or "/vmess/",
                    "wsHeaderHost": V2RAY_WS_HOST,
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": SSH_PAYLOAD,
                },
            },
        }
        return _encode(inner)
    except Exception as e:
        log.error(f"❌ build_vmess_dark: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════
# VLESS
# ═══════════════════════════════════════════

def build_vless_dark(vless_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    try:
        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        inner = {
            "type": "VLESS",
            "name": name,
            "vlessTunnelConfig": {
                "v2rayConfig": {
                    "host": vless_data.get("add") or vless_data.get("host") or "",
                    "port": int(vless_data.get("port") or 443),
                    "uuid": vless_data.get("id") or "",
                    "serverNameIndication": V2RAY_SNI,
                    "wsPath": vless_data.get("path") or "/vless/",
                    "wsHeaderHost": V2RAY_WS_HOST,
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": SSH_PAYLOAD,
                },
            },
        }
        return _encode(inner)
    except Exception as e:
        log.error(f"❌ build_vless_dark: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════
# TROJAN
# ═══════════════════════════════════════════

def build_trojan_dark(trojan_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    try:
        kind_name = "SNAPCHAT" if kind == "snapchat" else "YOUTUBE"
        name = f"{kind_name} 4day"

        inner = {
            "type": "TROJAN",
            "name": name,
            "trojanTunnelConfig": {
                "v2rayConfig": {
                    "host": trojan_data.get("add") or trojan_data.get("host") or "",
                    "port": int(trojan_data.get("port") or 443),
                    "password": trojan_data.get("id") or trojan_data.get("password") or "",
                    "serverNameIndication": V2RAY_SNI,
                    "wsPath": trojan_data.get("path") or "/trojan/",
                    "wsHeaderHost": V2RAY_WS_HOST,
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": SSH_PAYLOAD,
                },
            },
        }
        return _encode(inner)
    except Exception as e:
        log.error(f"❌ build_trojan_dark: {e}", exc_info=True)
        return None
