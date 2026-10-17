"""
automation/vmess.py
- يبني ملفات SSH (YOUTUBE + SNAPCHAT)
"""
import base64
import json
from utils.logger import get_logger

log = get_logger("VMESS")

# ✅ Payload موحد (SSH فقط)
SSH_PAYLOAD = "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]"


def _encode(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "darktunnel://" + base64.b64encode(raw).decode("utf-8")


def build_ssh_dark(host: str, username: str, password: str, kind: str = "youtube") -> str:
    """يبني ملف SSH dark (YOUTUBE ولا SNAPCHAT)"""
    try:
        name = "SNAPCHAT 4day" if kind == "snapchat" else "YOUTUBE 4day"

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
        log.error(f"❌ build_ssh_dark: {e}")
        return None
