"""
automation/sshs8.py
- vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113
- يفتح الصفحة، يقرا الدول، يعبي Password، يضغط Create
- يستخرج Host/User/Pass
- سريع بلا صور
"""
import asyncio
import random
import string
import re
import os
from utils.logger import get_logger

log = get_logger("SSHS8")


FRANCE_CREATE_URL = "https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113"


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
    # 1. فتح الصفحة الرئيسية + قراءة الدول
    # ═══════════════════════════════════════

    async def open_ssh_websocket(self) -> list:
        log.info(f"🌐 فتح: {FRANCE_CREATE_URL}")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(FRANCE_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            countries = await page.evaluate(r"""
                () => {
                    const out = [];
                    
                    const selects = document.querySelectorAll('select');
                    for (const sel of selects) {
                        for (const opt of sel.options) {
                            const t = (opt.textContent || '').trim();
                            if (t && t.length > 1 && t.length < 50 && 
                                !t.toLowerCase().includes('select') &&
                                !t.toLowerCase().includes('choose')) {
                                out.push(t);
                            }
                        }
                    }
                    
                    if (out.length === 0) {
                        const flags = document.querySelectorAll('[class*="country"], [class*="flag"], [data-country]');
                        for (const el of flags) {
                            const t = (el.textContent || el.getAttribute('data-country') || '').trim();
                            if (t && t.length > 1 && t.length < 50) {
                                out.push(t);
                            }
                        }
                    }
                    
                    if (out.length === 0) {
                        const links = document.querySelectorAll('a[href*="country"], a[href*="region"], a[href*="server"]');
                        for (const a of links) {
                            const t = (a.textContent || '').trim();
                            if (t && t.length > 1 && t.length < 50) {
                                out.push(t);
                            }
                        }
                    }
                    
                    return [...new Set(out)];
                }
            """)

            log.info(f"🌍 Countries from page: {len(countries)}")
            return countries or []

        except Exception as e:
            log.error(f"❌ open_ssh_websocket: {e}", exc_info=True)
            return []

    # ═══════════════════════════════════════
    # 2. تعبئة Password + Create
    # ═══════════════════════════════════════

    async def create_account(self, country: str = "France") -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password_input_value = generate_password()

        result = {
            "success": False,
            "username": None,
            "password": password_input_value,
            "country": country,
            "host": None,
            "domain": None,
            "message": None,
        }

        try:
            if country and country not in ("France", ""):
                try:
                    select = page.locator("select").first
                    if await select.count() > 0:
                        await select.select_option(label=country, timeout=3000)
                        await page.wait_for_timeout(1000)
                        log.info(f"✅ Country selected: {country}")
                except Exception as e:
                    log.warning(f"⚠️ select country: {e}")

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

            for i in range(20):
                await page.wait_for_timeout(500)
                if page.url != url_before:
                    log.info(f"✅ URL تبدل بعد {(i+1)*0.5}s")
                    break

            await page.wait_for_timeout(2000)

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
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(1000)

        for attempt in range(20):
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

            log.info(f"🔍 attempt {attempt+1}: host={data.get('host')} domain={data.get('domain')} user={data.get('username')} pass={data.get('password')}")

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

            await page.wait_for_timeout(1500)

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
