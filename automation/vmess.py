"""
automation/vmess.py
- build_ssh_dark / build_vmess_dark / build_vless_dark
- kind: youtube / snapchat فقط
"""
import base64
import json
from automation.sshs8 import PAYLOADS
from utils.logger import get_logger

log = get_logger("VMESS")


def build_ssh_dark(host: str, username: str, password: str, kind: str = "youtube") -> str:
    """يبني ملف SSH dark حسب النوع (youtube / snapchat)"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

        outer = {
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
                    "payload": cfg["payload"],
                },
            },
        }

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_ssh_dark: {e}", exc_info=True)
        return None


def build_vmess_dark(vmess_data: dict, password: str, kind: str = "youtube") -> str:
    """يبني ملف VMESS dark حسب النوع"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

        host = vmess_data.get("add") or vmess_data.get("host") or ""
        port = int(vmess_data.get("port") or 443)
        uuid = vmess_data.get("id") or ""
        path = vmess_data.get("path") or "/vmess/"

        outer = {
            "type": "VMESS",
            "name": password or "vmess_user",
            "vmessTunnelConfig": {
                "v2rayConfig": {
                    "host": host,
                    "port": port,
                    "uuid": uuid,
                    "serverNameIndication": cfg["sni"],
                    "wsPath": path,
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

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_vmess_dark: {e}", exc_info=True)
        return None


def build_vless_dark(vless_data: dict, password: str, kind: str = "youtube") -> str:
    """يبني ملف VLESS dark حسب النوع"""
    try:
        cfg = PAYLOADS.get(kind, PAYLOADS["youtube"])

        host = vless_data.get("add") or vless_data.get("host") or ""
        port = int(vless_data.get("port") or 443)
        uuid = vless_data.get("id") or ""
        path = vless_data.get("path") or "/vless/"

        outer = {
            "type": "VLESS",
            "name": password or "vless_user",
            "vlessTunnelConfig": {
                "v2rayConfig": {
                    "host": host,
                    "port": port,
                    "uuid": uuid,
                    "serverNameIndication": cfg["sni"],
                    "wsPath": path,
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

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_vless_dark: {e}", exc_info=True)
        return None
