"""
automation/sshs8.py
- يدعم URLs متعددة (دول مختلفة)
- سريع بلا صور
"""
import asyncio
import random
import string
import re
import os
from utils.logger import get_logger

log = get_logger("SSHS8")


# ═══════════════════════════════════════════
# قائمة الدول مع URLs
# ═══════════════════════════════════════════

COUNTRIES = [
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


def get_country_by_index(idx: int) -> dict:
    """يرجع الدولة حسب الـ index"""
    if 0 <= idx < len(COUNTRIES):
        return COUNTRIES[idx]
    return COUNTRIES[0]


def generate_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=10))


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
    # 1. فتح صفحة (URL مخصص)
    # ═══════════════════════════════════════

    async def open_page(self, url: str) -> bool:
        """يفتح صفحة مخصصة"""
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

    async def open_france_page(self) -> bool:
        """متوافق مع القديم — فرنسا"""
        return await self.open_page("https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113")

    # ═══════════════════════════════════════
    # 2. تعبئة Password + Create
    # ═══════════════════════════════════════

    async def create_account(self, country_url: str = None) -> dict:
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
            # ✅ 1. نعبيو Password
            filled = False
            for sel in [
                'input[type="password"]',
                'input[name*="pass" i]',
                'input[id*="pass" i]',
                'input[placeholder*="pass" i]',
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
                        log.info(f"✅ password filled: {password_input_value}")
                        filled = True
                        break
                except Exception:
                    continue

            if not filled:
                log.warning("⚠️ ما لقيناش حقل Password")

            await page.wait_for_timeout(500)
            url_before = page.url

            # ✅ 2. نضغطو Create
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
                        log.info(f"✅ Clicked via {sel}")
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
                    log.info(f"✅ JS Clicked: {js_clicked}")

            log.info(f"🎯 Create clicked: {clicked}")

            if not clicked:
                result["message"] = "❌ ما لقيناش زر Create"
                return result

            # ✅ 3. نستناو URL يتبدل
            for i in range(20):
                await page.wait_for_timeout(500)
                if page.url != url_before:
                    log.info(f"✅ URL تبدل بعد {(i+1)*0.5}s")
                    break

            await page.wait_for_timeout(2000)

            # ✅ 4. استخراج المعلومات
            creds = await self._extract_by_order(page)

            result["host"] = creds.get("host")
            result["username"] = creds.get("username")
            result["password"] = creds.get("password") or password_input_value
            result["domain"] = creds.get("domain")

            log.info(f"🔍 نهائي: host={result['host']} user={result['username']} pass={result['password']}")

            if not result["host"]:
                result["message"] = "❌ ما لقيناش IPv4."
                return result
            if not result["username"]:
                result["message"] = "❌ ما لقيناش Username."
                return result
            if not result["password"] or result["password"] == "Copy":
                result["message"] = "❌ ما لقيناش Password."
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)

        return result

    # ═══════════════════════════════════════
    # 3. استخراج المعلومات
    # ═══════════════════════════════════════

    async def _extract_by_order(self, page) -> dict:
        result = {"host": None, "domain": None, "username": None, "password": None}

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        for attempt in range(40):
            data = await page.evaluate(r"""
                () => {
                    const out = { all_values: [], host: null, domain: null, username: null, password: null, debug: [] };

                    const allInputs = Array.from(document.querySelectorAll('input'));
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || '').trim();
                        if (!val) continue;
                        if (val.toLowerCase() === 'copy') continue;
                        if (val.length < 2) continue;
                        
                        out.all_values.push({ value: val });
                        out.debug.push({
                            value: val.substring(0, 40),
                            type: inp.type || '',
                            name: inp.name || '',
                            id: inp.id || '',
                        });
                    }
                    
                    if (out.all_values.length === 0) {
                        const bodyText = document.body.innerText || '';
                        
                        const patterns = {
                            ipv4: /(?:IPv4|IP|Host)[\s:]*([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})/i,
                            domain: /(?:Domain|Hostname)[\s:]*([a-z0-9\-\.]+\.[a-z]{2,})/i,
                            username: /(?:Username|User)[\s:]*([a-zA-Z0-9_\-]{4,30})/i,
                            password: /(?:Password|Pass)[\s:]*([a-zA-Z0-9!@#$%^&*_\-]{6,40})/i,
                        };
                        
                        for (const [key, regex] of Object.entries(patterns)) {
                            const m = bodyText.match(regex);
                            if (m && m[1]) {
                                out.all_values.push({ value: m[1] });
                                out.debug.push({ value: m[1].substring(0, 40), source: 'text_' + key });
                            }
                        }
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
                    
                    if (!out.host) {
                        const bodyText = document.body.innerText || '';
                        const ips = bodyText.match(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g) || [];
                        for (const ip of ips) {
                            const parts = ip.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) &&
                                !ip.startsWith('192.168.') &&
                                !ip.startsWith('10.') &&
                                !ip.startsWith('172.16.') &&
                                !ip.startsWith('127.') &&
                                ip !== '0.0.0.0') {
                                out.host = ip;
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

            log.info(f"🔍 attempt {attempt+1}: host={data.get('host')} domain={data.get('domain')} user={data.get('username')} pass={data.get('password')}")
            if attempt == 0:
                log.info(f"🔍 debug: {data.get('debug', [])[:10]}")

            if data.get("host") and not result["host"]:
                result["host"] = data["host"]
            if data.get("domain") and not result["domain"]:
                result["domain"] = data["domain"]
            if data.get("username") and not result["username"]:
                result["username"] = data["username"]
            if data.get("password") and not result["password"]:
                result["password"] = data["password"]

            if result["host"] and result["username"] and result["password"]:
                log.info("✅ معلومات كاملة!")
                break

            await page.wait_for_timeout(2000)

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
