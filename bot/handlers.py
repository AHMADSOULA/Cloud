import asyncio
import io
import base64
import json
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot import messages
from bot.keyboards import main_menu
from database import db
from utils.helpers import extract_urls
from utils.logger import get_logger
from config import config
from automation.browser import StealthBrowser
from automation.sso_flow import run_sso_flow

log = get_logger("Handlers")

# ═══════════════════════════════════════════
# طابور (Queue)
# ═══════════════════════════════════════════

class JobQueue:
    def __init__(self):
        self.queue = []
        self.counter = 0
        self.current = None
        self.lock = asyncio.Lock()

    async def add(self, user_id, chat_id, sso_url, user_tag):
        async with self.lock:
            self.counter += 1
            num = self.counter
            self.queue.append({
                "num": num,
                "user_id": user_id,
                "chat_id": chat_id,
                "sso_url": sso_url,
                "user_tag": user_tag,
            })
            return num

    def position(self, user_id):
        for i, item in enumerate(self.queue):
            if item["user_id"] == user_id:
                return i + 1
        return 0

    async def get_next(self):
        async with self.lock:
            if self.current is not None:
                return None
            if not self.queue:
                return None
            self.current = self.queue.pop(0)
            return self.current

    async def finish(self):
        async with self.lock:
            self.current = None

    def queue_size(self):
        return len(self.queue)


queue = JobQueue()


# ═══════════════════════════════════════════
# قوالب
# ═══════════════════════════════════════════

VLESS_TEMPLATE = (
    "vless://aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000@google.com:443"
    "?path=%2FTelegram%2F%40AM2_D3%2F%40AHMAD3214&security=tls&encryption=none"
    "&host={domain}&type=ws&sni={domain}#%40AHMAD3214"
)

JSON_TEMPLATE = r'''{
  "dns": {
    "fallbackStrategy": "disabledIfAnyMatch",
    "hosts": {},
    "servers": [
      {
        "address": "tcp://8.8.8.8",
        "fakedns": [
          {"ipPool": "198.18.0.0/15", "poolSize": 65535}
        ],
        "queryStrategy": "UseIPv4"
      }
    ]
  },
  "inbounds": [
    {"listen": "0.0.0.0", "port": "1080", "protocol": "dokodemo-door",
     "settings": {"network": "tcp,udp", "followRedirect": true}, "tag": "tun-inbound"},
    {"listen": "127.0.0.1", "port": "10808", "protocol": "socks",
     "settings": {"auth": "noauth", "udp": true}, "tag": "socks-inbound"}
  ],
  "log": {"loglevel": "warning"},
  "outbounds": [
    {
      "mux": {"enabled": false},
      "protocol": "vless",
      "proxySettings": {"tag": "AhMed", "transportLayer": true},
      "settings": {
        "vnext": [{
          "address": "yt3.ggpht.com", "port": 443,
          "users": [{"encryption": "none", "flow": "", "id": "aaaa1111-bbbb-4ccc-8ddd-eeeeffff0000", "level": 8}]
        }]
      },
      "streamSettings": {
        "network": "ws", "security": "tls",
        "tlsSettings": {"allowInsecure": true, "serverName": "yt3.ggpht.com"},
        "wsSettings": {"headers": {"Host": "__DOMAIN__"}, "path": "/Telegram/@AM2_D3/@AHMAD3214"}
      },
      "tag": "VLESS"
    },
    {
      "domainStrategy": "AsIs",
      "protocol": "http",
      "settings": {
        "servers": [{"address": "57.144.120.4", "port": 8080}],
        "headers": {"Host": "yt3.ggpht.com:443", "Proxy-Connection": "keep-alive",
                    "User-Agent": "FBAV/0.0", "X-iorg-bsid": "@AM2_D3"}
      },
      "tag": "@AM2_D3"
    },
    {"protocol": "freedom", "tag": "direct"},
    {"protocol": "blackhole", "tag": "block"}
  ],
  "policy": {"levels": {"8": {"connIdle": 300, "downlinkOnly": 1, "handshake": 4, "uplinkOnly": 1}}},
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      {"outboundTag": "direct", "protocol": ["dns"], "type": "field"},
      {"inboundTag": ["tun-inbound", "socks-inbound"], "outboundTag": "VLESS", "type": "field"}
    ]
  }
}'''

DARKTUNNEL_BASE_URI = "darktunnel://eyJ0eXBlIjoiVkxFU1MiLCJuYW1lIjoi2YXYrNin2YbZiiDYp9iz2YrYpyDZiCDYp9ir2YrYsSAiLCJ2bGVzc1R1bm5lbENvbmZpZyI6eyJ2MnJheUNvbmZpZyI6eyJob3N0IjoiYWx0MTMueXQzLmdncGh0LmNvbSIsInBvcnQiOjQ0MywidXVpZCI6ImFhYWExMTExLWJiYmItNGNjYy04ZGRkLWVlZWVmZmZmMDAwMCIsInNlcnZlck5hbWVJbmRpY2F0aW9uIjoiYWx0MTMueXQzLmdncGh0LmNvbSIsIndzUGF0aCI6Ii9UZWxlZ3JhbS9AQU0yX0QzL0BBSE1BRDMyMTQiLCJ3c0hlYWRlckhvc3QiOiJhaG1lZC12aXAxLTQxNDAwODYxMjEyMy5ldXJvcGUtd2VzdDEucnVuLmFwcCJ9LCJpbmplY3RDb25maWciOnsiZW5hYmxlZCI6dHJ1ZSwibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMTU3LjI0MC45LjM5IiwicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RdOltwb3J0XSBIVFRQLzEuMVtjcmxmXXgtY29ubmVjdGVkLXRvOiAzNC4xNDMuNzIuMltjcmxmXXByb3h5LWNv
