"""
automation/sshs8.py
- كيدير SSH بنفس طريقة ضغطات المستخدم
"""
import asyncio
import random
import string
import re
import os
import base64
import json
from utils.logger import get_logger
from utils.recorder import BrowserRecorder

log = get_logger("SSHS8")


BASE_URL = "https://sshs8.com"


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
        self.recorder = BrowserRecorder(context)

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    def set_bot(self, bot):
        self.bot = bot
        if self.chat_id:
            self.recorder.set_bot(bot, self.chat_id)

    # ═══════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════

    async def _shot(self, name: str):
        """screenshot عند أي خطوة"""
        if not self.page:
            return
        try:
            path = f"/tmp/step_{name}_{int(asyncio.get_event_loop().time()*1000)}.png"
            await self.page.screenshot(path=path, full_page=False, timeout=10000)
            log.info(f"📸 {name}")
        except Exception:
            pass

    async def _close_ads(self):
        """يغلق الإعلانات"""
        try:
            await self.page.evaluate("""
                () => {
                    document.querySelectorAll('iframe').forEach(f => {
                        if(f.src && (f.src.includes('ads') || f.src.includes('google') || f.src.includes('doubleclick') || f.src.includes('fluid'))) f.remove();
                    });
                    document.querySelectorAll('[class*="popup"], [class*="modal"], [class*="overlay"]').forEach(el => {
                        try {
                            const s = window.getComputedStyle(el);
                            if (s.zIndex > 100 || s.position === 'fixed') el.remove();
                        } catch(e) {}
                    });
                }
            """)
            await self.page.wait_for_timeout(500)
        except Exception:
            pass

    async def _click(self, selector: str, desc: str = ""):
        """click + force"""
        try:
            el = self.page.locator(selector).first
            if await el.count() > 0:
                await el.click(timeout=5000, force=True)
                await self.page.wait_for_timeout(2000)
                log.info(f"✅ click: {desc or selector[:30]}")
                return True
            return False
        except Exception as e:
            log.warning(f"⚠️ click: {e}")
            return False

    # ═══════════════════════════════════════
    # Workflow
    # ═══════════════════════════════════════

    async def open_home(self) -> bool:
        log.info(f"🌐 فتح: {BASE_URL}")
        self.page = await self.context.new_page()
        try:
            await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(4000)

            # Cloudflare
            title = await self.page.title()
            if "just a moment" in title.lower() or "cloudflare" in title.lower():
                for i in range(30):
                    await self.page.wait_for_timeout(2000)
                    title = await self.page.title()
                    if "just a moment" not in title.lower():
                        break

            await self._close_ads()
            await self._shot("home")
            return True
        except Exception as e:
            log.error(f"❌ open_home: {e}")
            return False

    async def click_ssh_protocol(self) -> list:
        """يضغط على SSH Websocket من الشريط"""
        await self._close_ads()
        await self._click('a:has-text("SSH Websocket")', "SSH Websocket")
        await self.page.wait_for_timeout(4000)
        await self._shot("ssh_page")

        continents = await self.page.evaluate(r"""
            () => {
                const out = [];
                const keywords = ["أوروبا", "آسيا", "أمريكا الشمالية", "أمريكا الجنوبية", "أفريقيا", "Europe", "Asia", "North America", "South America", "Africa"];
                document.querySelectorAll('a').forEach(a => {
                    const t = (a.innerText || '').trim();
                    for (const kw of keywords) {
                        if (t.includes(kw) && !out.find(x => x.name === kw)) {
                            out.push({ name: kw, href: a.href || '' });
                            break;
                        }
                    }
                });
                return out;
            }
        """)
        log.info(f"🌍 Continents: {len(continents)}")
        return continents

    async def click_continent(self, continent_name: str) -> list:
        """يضغط على القارة → الدول"""
        await self._close_ads()
        await self._click(f'a:has-text("{continent_name}")', continent_name)
        await self.page.wait_for_timeout(4000)
        await self._shot(f"continent_{continent_name.replace(' ','_')}")

        countries = await self.page.evaluate(r"""
            () => {
                const out = [];
                const exclude = ["Menu", "Home", "About", "Close", "Open", "SSH Websocket", "SSH Dropbear", "SSH STunnel", "SSH Tunnel", "OpenVPN", "V2Ray VLESS", "V2Ray VMESS", "WireGuard"];
                document.querySelectorAll('h2, h3, h4, strong').forEach(h => {
                    const t = (h.innerText || '').trim();
                    if (!t || t.length > 60) return;
                    if (exclude.includes(t)) return;
                    if (!out.find(x => x.name === t)) out.push({ name: t, href: '' });
                });
                return out;
            }
        """)
        log.info(f"🌍 Countries: {len(countries)}")
        return countries

    async def click_country(self, country_name: str) -> list:
        """يضغط على الدولة → الخوادم"""
        await self._close_ads()
        await self._click(f'text="{country_name}"', country_name)
        await self.page.wait_for_timeout(4000)
        await self._shot(f"country_{country_name.replace(' ','_')}")

        # ✅ نضغطو "قائمة الخوادم"
        await self._click('text="قائمة الخوادم"', "قائمة الخوادم")
        await self.page.wait_for_timeout(3000)

        servers = await self.page.evaluate(r"""
            () => {
                const out = [];
                document.querySelectorAll('[class*="card"], article').forEach(card => {
                    const txt = (card.innerText || '');
                    const match = txt.match(/E\d{2,3}/);
                    if (!match) return;
                    const btns = Array.from(card.querySelectorAll('a, button'));
                    const createBtn = btns.find(b => (b.innerText || '').includes('إنشاء') || (b.innerText || '').toLowerCase().includes('create'));
                    if (!createBtn) return;
                    out.push({ id: match[0], href: createBtn.href || '' });
                });
                return out;
            }
        """)
        log.info(f"🖥️ Servers: {len(servers)}")
        return servers

    async def create_account(self, server_href: str) -> dict:
        """ينشئ الحساب فـ الخادم"""
        password = generate_password()

        try:
            await self.page.goto(server_href, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(4000)
            await self._close_ads()
            await self._shot("server_page")

            # ✅ username
            for sel in ['input[name*="user" i]', 'input[type="text"]', 'input[name="username"]']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        val = await el.input_value()
                        if not val:
                            await el.fill(f"u{random.randint(100000000, 999999999)}")
                        break
                except Exception:
                    continue

            # ✅ password
            for sel in ['input[type="password"]', 'input[name*="pass" i]']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.fill(password)
                        break
                except Exception:
                    continue

            # ✅ Create
            await self.page.wait_for_timeout(500)
            url_before = self.page.url

            for sel in ['button:has-text("إنشاء حساب")', 'button:has-text("Create account")', 'button:has-text("Create")', 'input[type="submit"]']:
                if await self._click(sel, "Create"):
                    break

            # ✅ نستناو
            for i in range(20):
                await self.page.wait_for_timeout(1000)
                if self.page.url != url_before:
                    break

            await self.page.wait_for_timeout(3000)
            await self._close_ads()
            await self._shot("after_create")

            # ✅ نستخرجو
            return await self._extract(page, password)

        except Exception as e:
            log.error(f"❌ create: {e}")
            return {"success": False, "message": str(e)[:200]}

    async def _extract(self, page, fallback_pass: str) -> dict:
        result = {
            "success": False,
            "host": None,
            "username": None,
            "password": fallback_pass,
            "message": None,
        }

        for attempt in range(30):
            data = await page.evaluate(r"""
                () => {
                    const out = { values: [], host: null, user: null };
                    document.querySelectorAll('input, textarea').forEach(inp => {
                        const v = (inp.value || inp.textContent || '').trim();
                        if (!v || v.toLowerCase() === 'copy') return;
                        out.values.push(v);
                    });
                    // IPv4
                    for (const v of out.values) {
                        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v)) {
                            const parts = v.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) && !v.startsWith('192.168.') && !v.startsWith('10.')) {
                                out.host = v; break;
                            }
                        }
                    }
                    // Username
                    for (const v of out.values) {
                        if (v === out.host) continue;
                        if (/^[a-z0-9_\-]{4,30}$/i.test(v) && !/^\d+$/.test(v)) {
                            out.user = v; break;
                        }
                    }
                    return out;
                }
            """)

            if data.get("host") and not result["host"]:
                result["host"] = data["host"]
            if data.get("user") and not result["username"]:
                result["username"] = data["user"]

            if result["host"] and result["username"]:
                result["success"] = True
                break

            await page.wait_for_timeout(1500)

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
