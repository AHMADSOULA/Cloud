"""
automation/sshs8.py
- يدعم SSH / VLESS / VMESS
- قائمة دول مع URLs
"""
import asyncio
import random
import string
import re
import os
import base64
import json
from utils.logger import get_logger

log = get_logger("SSHS8")


# ═══════════════════════════════════════════
# الدول - SSH
# ═══════════════════════════════════════════

SSH_COUNTRIES = [
    {
        "name": "France",
        "flag": "🇫🇷",
        "url": "https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113",
    },
    {
        "name": "Germany",
        "flag": "🇩🇪",
        "url": "https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/105",
    },
    {
        "name": "Netherlands",
        "flag": "🇳🇱",
        "url": "https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/236",
    },
    {
        "name": "USA",
        "flag": "🇺🇸",
        "url": "https://vpnnamerica.sshs8.com/accounts/SSH_WEBSOCKET/58",
    },
]


# ═══════════════════════════════════════════
# الدول - VMESS
# ═══════════════════════════════════════════

VMESS_COUNTRIES = [
    {
        "name": "France",
        "flag": "🇫🇷",
        "url": "https://vpneurope.sshs8.com/accounts/VMESS/115",
    },
    {
        "name": "USA",
        "flag": "🇺🇸",
        "url": "https://vpnnamerica.sshs8.com/accounts/VMESS/52",
    },
    {
        "name": "Mexico",
        "flag": "🇲🇽",
        "url": "https://vpnnamerica.sshs8.com/accounts/VMESS/3",
    },
    {
        "name": "Netherlands",
        "flag": "🇳🇱",
        "url": "https://vpneurope.sshs8.com/accounts/VMESS/247",
    },
    {
        "name": "Germany",
        "flag": "🇩🇪",
        "url": "https://vpneurope.sshs8.com/accounts/VMESS/107",
    },
    {
        "name": "Italy",
        "flag": "🇮🇹",
        "url": "https://vpneurope.sshs8.com/accounts/VMESS/214",
    },
]


# ═══════════════════════════════════════════
# الدول - VLESS
# ═══════════════════════════════════════════

VLESS_COUNTRIES = [
    {
        "name": "France",
        "flag": "🇫🇷",
        "url": "https://vpneurope.sshs8.com/accounts/VLESS/113",
    },
    {
        "name": "Germany",
        "flag": "🇩🇪",
        "url": "https://vpneurope.sshs8.com/accounts/VLESS/105",
    },
    {
        "name": "Netherlands",
        "flag": "🇳🇱",
        "url": "https://vpneurope.sshs8.com/accounts/VLESS/236",
    },
    {
        "name": "USA",
        "flag": "🇺🇸",
        "url": "https://vpnnamerica.sshs8.com/accounts/VLESS/58",
    },
]


# ═══════════════════════════════════════════
# قوالب SSH (قوالب ثابتة)
# ═══════════════════════════════════════════

SNAPCHAT_TEMPLATE_URI = "darktunnel://eyJ0eXBlIjoiU1NIIiwibmFtZSI6IlNTSCIsInNzaFR1bm5lbENvbmZpZyI6eyJzc2hDb25maWciOnsiaG9zdCI6IjE1Mi4yMjguMTYyLjE5IiwidXNlcm5hbWUiOiJ1MzY0NTQ4MjAzMCIsInBhc3N3b3JkIjoibUQxaHo3UHdrViJ9LCJpbmplY3RDb25maWciOnsibW9kZSI6IlBST1hZIiwicHJveHlIb3N0IjoiMzQuNDMuNDYuOTEiLCJwcm94eVBvcnQiOjQ0MywicGF5bG9hZCI6IkNPTk5FQ1QgW2hvc3RfcG9ydF0gW3Byb3RvY29sXVtjcmxmXUhvc3Q6IGFwaS5zbmFwY2hhdC5jb21bY3JsZl1bY3JsZl0ifX19"

YOUTUBE_TEMPLATE_URI = "darktunnel://eyJ0eXBlIjoiU1NIIiwibmFtZSI6IlNTSCIsInNzaFR1bm5lbENvbmZpZyI6eyJzc2hDb25maWciOnsiaG9zdCI6IjE2MC4xMTkuMjUxLjE1IiwidXNlcm5hbWUiOiJ1NTU2NjI3MTg5OCIsInBhc3N3b3JkIjoiQWhtZWQyMDI1In0sImluamVjdENvbmZpZyI6eyJtb2RlIjoiUFJPWFkiLCJwcm94eUhvc3QiOiIzNC40My40Ni45MSIsInByb3h5UG9ydCI6NDQzLCJwYXlsb2FkIjoiQ09OTkVDVCBbaG9zdF9wb3J0XSBbcHJvdG9jb2xdW2NybGZdSG9zdDogeW91dHViZS5jb21bY3JsZl1bY3JsZl0ifX19"


def _b64_pad(s: str) -> str:
    s = s.strip()
    return s + ("=" * ((4 - (len(s) % 4)) % 4)) if s else s


def generate_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=10))


# ═══════════════════════════════════════════
# الكلاس الرئيسي
# ═══════════════════════════════════════════

class SSHS8:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None
        self.chat_id = None
        self.bot = None

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    # ═══════════════════════════════════════
    # فتح صفحة
    # ═══════════════════════════════════════

    async def open_page(self, url: str) -> bool:
        log.info(f"🌐 فتح: {url}")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            return True
        except Exception as e:
            log.error(f"❌ open_page: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # إنشاء حساب SSH
    # ═══════════════════════════════════════

    async def create_ssh_account(self) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password_input_value = generate_password()

        result = {
            "success": False,
            "username": None,
            "password": password_input_value,
            "host": None,
            "domain": None,
            "message": None,
        }

        try:
            # تعبئة Password
            filled = False
            for sel in [
                'input[type="password"]',
                'input[name*="pass" i]',
                'input[id*="pass" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        await page.wait_for_timeout(100)
                        await el.fill("")
                        await page.wait_for_timeout(100)
                        await el.fill(password_input_value)
                        filled = True
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(500)
            url_before = page.url

            # ضغط Create
            clicked = False
            for sel in [
                'button:has-text("Create an account")',
                'button:has-text("Create account")',
                'input[value="Create an account"]',
                'input[type="submit"]',
                'button:has-text("Create")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(150)
                        await el.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                js_clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, input[type="submit"], a, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                            if (t.includes('create')) {
                                try { el.click(); return t; } catch(e) {}
                            }
                        }
                        return null;
                    }
                """)
                if js_clicked:
                    clicked = True

            if not clicked:
                result["message"] = "❌ ما لقيناش زر Create"
                return result

            # نستناو URL يتبدل
            for i in range(20):
                await page.wait_for_timeout(500)
                if page.url != url_before:
                    break

            await page.wait_for_timeout(2000)

            # استخراج
            creds = await self._extract_ssh_creds(page)
            result["host"] = creds.get("host")
            result["username"] = creds.get("username")
            result["password"] = creds.get("password") or password_input_value
            result["domain"] = creds.get("domain")

            if not result["host"]:
                result["message"] = "❌ ما لقيناش IPv4."
                return result
            if not result["username"]:
                result["message"] = "❌ ما لقيناش Username."
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_ssh_account: {e}", exc_info=True)

        return result

    # ═══════════════════════════════════════
    # إنشاء حساب VMESS / VLESS
    # ═══════════════════════════════════════

    async def create_vmess_account(self) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password_value = generate_password()

        result = {
            "success": False,
            "password": password_value,
            "link_tls": None,
            "vmess_config": None,
            "message": None,
        }

        try:
            # تعبئة Password
            for sel in [
                'input[type="password"]',
                'input[name*="pass" i]',
                'input[id*="pass" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        await page.wait_for_timeout(100)
                        await el.fill("")
                        await page.wait_for_timeout(100)
                        await el.fill(password_value)
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(500)
            url_before = page.url

            # ضغط Create
            clicked = False
            for sel in [
                'button:has-text("Create an account")',
                'button:has-text("Create account")',
                'input[value="Create an account"]',
                'input[type="submit"]',
                'button:has-text("Create")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(150)
                        await el.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                js_clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, input[type="submit"], a, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                            if (t.includes('create')) {
                                try { el.click(); return t; } catch(e) {}
                            }
                        }
                        return null;
                    }
                """)
                if js_clicked:
                    clicked = True

            if not clicked:
                result["message"] = "❌ ما لقيناش زر Create"
                return result

            # نستناو URL يتبدل
            for i in range(20):
                await page.wait_for_timeout(500)
                if page.url != url_before:
                    break

            await page.wait_for_timeout(3000)

            # Link TLS
            link_tls = await self._extract_link_tls(page)
            if not link_tls:
                result["message"] = "❌ ما لقيناش Link TLS."
                return result

            result["link_tls"] = link_tls

            # نفكو base64
            vmess_data = self._decode_vmess_link(link_tls)
            if not vmess_data:
                result["message"] = "❌ ما قدرناش نفكو Link TLS."
                return result

            result["vmess_config"] = vmess_data
            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_vmess_account: {e}", exc_info=True)

        return result

    # ═══════════════════════════════════════
    # استخراج معلومات SSH
    # ═══════════════════════════════════════

    async def _extract_ssh_creds(self, page) -> dict:
        result = {"host": None, "domain": None, "username": None, "password": None}

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        for attempt in range(40):
            data = await page.evaluate(r"""
                () => {
                    const out = { all_values: [], host: null, domain: null, username: null, password: null };

                    const allInputs = Array.from(document.querySelectorAll('input'));
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || '').trim();
                        if (!val) continue;
                        if (val.toLowerCase() === 'copy') continue;
                        if (val.length < 2) continue;
                        
                        out.all_values.push({ value: val });
                    }
                    
                    const vals = out.all_values.map(x => x.value);
                    
                    for (const v of vals) {
                        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v)) {
                            const parts = v.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) &&
                                !v.startsWith('192.168.') &&
                                !v.startsWith('10.') &&
                                !v.startsWith('172.16.') &&
                                !v.startsWith('127.')) {
                                out.host = v;
                                break;
                            }
                        }
                    }
                    
                    for (const v of vals) {
                        if (v === out.host) continue;
                        if (/^[a-z0-9\-\.]+\.[a-z]{2,}$/i.test(v) && 
                            !/^(\d{1,3}\.){3}\d{1,3}$/.test(v) &&
                            v.length < 60) {
                            out.domain = v;
                            break;
                        }
                    }
                    
                    for (const v of vals) {
                        if (v === out.host || v === out.domain) continue;
                        if (/^[a-z0-9_\-]{4,30}$/i.test(v) && 
                            !/^\d+$/.test(v) &&
                            v.length >= 4 && v.length <= 30) {
                            out.username = v;
                            break;
                        }
                    }
                    
                    for (const v of vals) {
                        if (v === out.host || v === out.domain || v === out.username) continue;
                        if (/^[a-zA-Z0-9!@#$%^&*_\-]{6,40}$/.test(v) &&
                            v.length >= 6 && v.length <= 40) {
                            out.password = v;
                            break;
                        }
                    }
                    
                    return out;
                }
            """)

            if data.get("host") and not result["host"]:
                result["host"] = data["host"]
            if data.get("domain") and not result["domain"]:
                result["domain"] = data["domain"]
            if data.get("username") and not result["username"]:
                result["username"] = data["username"]
            if data.get("password") and not result["password"]:
                result["password"] = data["password"]

            if result["host"] and result["username"] and result["password"]:
                break

            await page.wait_for_timeout(2000)

        return result

    # ═══════════════════════════════════════
    # استخراج Link TLS (VMESS / VLESS)
    # ═══════════════════════════════════════

    async def _extract_link_tls(self, page) -> str:
        for attempt in range(30):
            link = await page.evaluate(r"""
                () => {
                    const labels = document.querySelectorAll('*');
                    
                    for (const el of labels) {
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (txt === 'Link TLS' || txt === 'Link TLS:') {
                            let parent = el.parentElement;
                            for (let d = 0; d < 5 && parent; d++) {
                                const inp = parent.querySelector('input, textarea');
                                if (inp) {
                                    const val = (inp.value || inp.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                parent = parent.parentElement;
                            }
                            let next = el.nextElementSibling;
                            for (let i = 0; i < 5 && next; i++) {
                                const inp = next.querySelector ? next.querySelector('input, textarea') : null;
                                if (inp) {
                                    const val = (inp.value || inp.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                if (next.tagName === 'INPUT' || next.tagName === 'TEXTAREA') {
                                    const val = (next.value || next.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                next = next.nextElementSibling;
                            }
                        }
                    }
                    
                    const allInputs = document.querySelectorAll('input, textarea');
                    for (const inp of allInputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (val && (val.startsWith('vmess://') || val.startsWith('vless://') || val.startsWith('eyJ'))) {
                            const parent = inp.closest('div, tr, td');
                            if (parent) {
                                const ptxt = (parent.innerText || '').toLowerCase();
                                if (ptxt.includes('tls') && !ptxt.includes('no tls') && !ptxt.includes('notls')) {
                                    return val;
                                }
                            }
                        }
                    }
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (val && val.length > 30 && !val.toLowerCase().includes('copy')) {
                            if (/^[A-Za-z0-9+/=]+$/.test(val.substring(0, 50))) {
                                return val;
                            }
                        }
                    }
                    
                    return null;
                }
            """)

            if link:
                return link.strip()

            await page.wait_for_timeout(2000)

        return None

    # ═══════════════════════════════════════
    # فك base64
    # ═══════════════════════════════════════

    def _decode_vmess_link(self, link: str) -> dict:
        try:
            # vmess://
            if link.startswith("vmess://"):
                b64 = link.replace("vmess://", "").strip()
            elif link.startswith("vless://"):
                # VLESS كيبدا بـ vless:// — كنستخرجو الـ UUID من query
                return self._parse_vless_link(link)
            else:
                b64 = link.strip()

            b64 = b64 + ("=" * ((4 - (len(b64) % 4)) % 4))

            try:
                decoded = base64.b64decode(b64).decode("utf-8")
            except Exception:
                decoded = base64.urlsafe_b64decode(b64).decode("utf-8")

            try:
                data = json.loads(decoded)
                return data
            except Exception:
                return None

        except Exception as e:
            log.error(f"❌ _decode_vmess_link: {e}")
            return None

    def _parse_vless_link(self, link: str) -> dict:
        """يفك vless:// link"""
        try:
            from urllib.parse import urlparse, parse_qs, unquote

            # vless://uuid@host:port?params#name
            u = link.replace("vless://", "")
            parsed = urlparse("vless://" + u)

            uuid = parsed.username or parsed.netloc.split("@")[0] if "@" in parsed.netloc else ""
            host = parsed.hostname or ""
            port = parsed.port or 443
            params = parse_qs(parsed.query)

            return {
                "id": uuid,
                "add": host,
                "port": port,
                "net": params.get("type", ["ws"])[0],
                "path": unquote(params.get("path", ["/vless/"])[0]),
                "host": params.get("host", ["googlevideo.com"])[0],
                "sni": params.get("sni", params.get("host", ["youtube.com"]))[0],
                "tls": params.get("security", ["tls"])[0],
            }
        except Exception as e:
            log.error(f"❌ _parse_vless_link: {e}")
            return None

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
