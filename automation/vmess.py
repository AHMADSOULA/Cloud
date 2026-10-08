"""
automation/vmess.py
- build_ssh_dark / build_vmess_dark / build_vless_dark
- بلا تشفير
"""
import base64
import json
from automation.sshs8 import PAYLOADS
from utils.logger import get_logger

log = get_logger("VMESS")


def _darktunnel_encode(data: dict) -> str:
    """يشفّر dict → darktunnel:// (base64 عادي)"""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "darktunnel://" + base64.b64encode(raw).decode("utf-8")


def build_ssh_dark(host: str, username: str, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف SSH dark — بلا تشفير"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

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
                    "payload": cfg["payload"],
                },
            },
        }

        return _darktunnel_encode(inner)

    except Exception as e:
        log.error(f"❌ build_ssh_dark: {e}", exc_info=True)
        return None


def build_vmess_dark(vmess_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف VMESS dark — بلا تشفير"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

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
                    "serverNameIndication": cfg["sni"],
                    "wsPath": vmess_data.get("path") or "/vmess/",
                    "wsHeaderHost": cfg["ws_header_host"],
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": cfg["payload"],
                },
            },
        }

        return _darktunnel_encode(inner)

    except Exception as e:
        log.error(f"❌ build_vmess_dark: {e}", exc_info=True)
        return None


def build_vless_dark(vless_data: dict, password: str, kind: str = "youtube", country: dict = None) -> str:
    """يبني ملف VLESS dark — بلا تشفير"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

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
                    "serverNameIndication": cfg["sni"],
                    "wsPath": vless_data.get("path") or "/vless/",
                    "wsHeaderHost": cfg["ws_header_host"],
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": cfg["payload"],
                },
            },
        }

        return _darktunnel_encode(inner)

    except Exception as e:
        log.error(f"❌ build_vless_dark: {e}", exc_info=True)
        return None
