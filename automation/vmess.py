"""
automation/vmess.py
- بناء ملفات Dark (SSH / VMESS / VLESS / TROJAN)
"""
import base64
import json
from utils.logger import get_logger

log = get_logger("VMESS")

SSH_PAYLOAD = "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]"
V2RAY_SNI = "youtube.com"
V2RAY_WS_HOST = "youtube.com"

def _encode(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "darktunnel://" + base64.b64encode(raw).decode("utf-8")

def build_ssh_dark(host, username, password, kind="youtube"):
    name = "SNAPCHAT 4day" if kind == "snapchat" else "YOUTUBE 4day"
    inner = {
        "type": "SSH", "name": name,
        "sshTunnelConfig": {
            "sshConfig": {"host": host or "", "port": 22, "username": username or "", "password": password or ""},
            "injectConfig": {"enabled": True, "mode": "PROXY", "proxyHost": "34.43.46.91", "proxyPort": 443, "payload": SSH_PAYLOAD}
        }
    }
    return _encode(inner)

def build_vmess_dark(data, password, kind="youtube"):
    name = "SNAPCHAT 4day" if kind == "snapchat" else "YOUTUBE 4day"
    inner = {
        "type": "VMESS", "name": name,
        "vmessTunnelConfig": {
            "v2rayConfig": {
                "host": data.get("add", ""), "port": int(data.get("port", 443)),
                "uuid": data.get("id", ""), "serverNameIndication": V2RAY_SNI,
                "wsPath": data.get("path", "/vmess/"), "wsHeaderHost": V2RAY_WS_HOST
            },
            "injectConfig": {"enabled": True, "mode": "PROXY", "proxyHost": "34.43.46.91", "proxyPort": 443, "payload": SSH_PAYLOAD}
        }
    }
    return _encode(inner)

def build_vless_dark(data, password, kind="youtube"):
    name = "SNAPCHAT 4day" if kind == "snapchat" else "YOUTUBE 4day"
    inner = {
        "type": "VLESS", "name": name,
        "vlessTunnelConfig": {
            "v2rayConfig": {
                "host": data.get("add", ""), "port": int(data.get("port", 443)),
                "uuid": data.get("id", ""), "serverNameIndication": V2RAY_SNI,
                "wsPath": data.get("path", "/vless/"), "wsHeaderHost": V2RAY_WS_HOST
            },
            "injectConfig": {"enabled": True, "mode": "PROXY", "proxyHost": "34.43.46.91", "proxyPort": 443, "payload": SSH_PAYLOAD}
        }
    }
    return _encode(inner)

def build_trojan_dark(data, password, kind="youtube"):
    name = "SNAPCHAT 4day" if kind == "snapchat" else "YOUTUBE 4day"
    inner = {
        "type": "TROJAN", "name": name,
        "trojanTunnelConfig": {
            "v2rayConfig": {
                "host": data.get("add", ""), "port": int(data.get("port", 443)),
                "password": data.get("id", "") or password, "serverNameIndication": V2RAY_SNI,
                "wsPath": data.get("path", "/trojan/"), "wsHeaderHost": V2RAY_WS_HOST
            },
            "injectConfig": {"enabled": True, "mode": "PROXY", "proxyHost": "34.43.46.91", "proxyPort": 443, "payload": SSH_PAYLOAD}
        }
    }
    return _encode(inner)
