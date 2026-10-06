"""
automation/vmess.py
- يستورد من sshs8.py
"""
from automation.sshs8 import (
    SSHS8,
    SSH_COUNTRIES,
    VMESS_COUNTRIES,
    VLESS_COUNTRIES,
    SNAPCHAT_TEMPLATE_URI,
    YOUTUBE_TEMPLATE_URI,
    _b64_pad,
)
import base64
import json
from utils.logger import get_logger

log = get_logger("VMESS")


def modify_ssh_template(template_uri: str, new_host: str, new_username: str, new_password: str) -> str:
    """يعدل قالب SSH — يغير host/username/password"""
    try:
        raw_b64 = template_uri.split("darktunnel://", 1)[1].strip()
        raw_b64 = _b64_pad(raw_b64)
        decoded = base64.b64decode(raw_b64.encode("utf-8")).decode("utf-8")
        data = json.loads(decoded)

        ssh_config = data.get("sshTunnelConfig", {}).get("sshConfig", {})
        ssh_config["host"] = new_host or ""
        ssh_config["username"] = new_username or ""
        ssh_config["password"] = new_password or ""

        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ modify_ssh_template: {e}", exc_info=True)
        return None


def build_ssh_dark(host: str, username: str, password: str, payload: str = None, name: str = "SSH") -> str:
    """يبني ملف SSH dark"""
    try:
        if not payload:
            payload = "CONNECT [host_port] [protocol][crlf]Host: youtube.com[crlf][crlf]"

        outer = {
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
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": payload,
                },
            },
        }

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_ssh_dark: {e}", exc_info=True)
        return None


def build_vmess_dark(vmess_data: dict, password: str) -> str:
    """يبني ملف VMESS dark"""
    try:
        host = vmess_data.get("add") or vmess_data.get("host") or ""
        port = int(vmess_data.get("port") or 443)
        uuid = vmess_data.get("id") or ""
        sni = vmess_data.get("sni") or vmess_data.get("host") or "youtube.com"
        path = vmess_data.get("path") or "/vmess/"
        ws_header_host = vmess_data.get("host") or "googlevideo.com"

        NEW_PAYLOAD = (
            "CONNECT [host_port] HTTP/1.1[crlf]"
            "Host: youtubekids.com[crlf]"
            "X-Online-Host: youtubekids.com[crlf]"
            "Connection: Keep-Alive[crlf]"
            "User-Agent: Mozilla/5.0[crlf][crlf]"
        )

        outer = {
            "type": "VMESS",
            "name": password or "vmess_user",
            "vmessTunnelConfig": {
                "v2rayConfig": {
                    "host": host,
                    "port": port,
                    "uuid": uuid,
                    "serverNameIndication": sni,
                    "wsPath": path,
                    "wsHeaderHost": ws_header_host,
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": NEW_PAYLOAD,
                },
            },
        }

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_vmess_dark: {e}", exc_info=True)
        return None


def build_vless_dark(vless_data: dict, password: str) -> str:
    """يبني ملف VLESS dark"""
    try:
        host = vless_data.get("add") or vless_data.get("host") or ""
        port = int(vless_data.get("port") or 443)
        uuid = vless_data.get("id") or ""
        sni = vless_data.get("sni") or vless_data.get("host") or "youtube.com"
        path = vless_data.get("path") or "/vless/"
        ws_header_host = vless_data.get("host") or "googlevideo.com"

        NEW_PAYLOAD = (
            "CONNECT [host_port] HTTP/1.1[crlf]"
            "Host: youtubekids.com[crlf]"
            "X-Online-Host: youtubekids.com[crlf]"
            "Connection: Keep-Alive[crlf]"
            "User-Agent: Mozilla/5.0[crlf][crlf]"
        )

        outer = {
            "type": "VLESS",
            "name": password or "vless_user",
            "vlessTunnelConfig": {
                "v2rayConfig": {
                    "host": host,
                    "port": port,
                    "uuid": uuid,
                    "serverNameIndication": sni,
                    "wsPath": path,
                    "wsHeaderHost": ws_header_host,
                },
                "injectConfig": {
                    "enabled": True,
                    "mode": "PROXY",
                    "proxyHost": "34.43.46.91",
                    "proxyPort": 443,
                    "payload": NEW_PAYLOAD,
                },
            },
        }

        raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(raw).decode("utf-8")
        return "darktunnel://" + b64

    except Exception as e:
        log.error(f"❌ build_vless_dark: {e}", exc_info=True)
        return None
