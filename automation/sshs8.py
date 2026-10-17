"""
automation/sshs8.py
- يستكشف الموقع: Menu → Protocol → Continent → Country → Random Server
- Screenshot عند أي مشكل
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


BASE_URL = "https://sshs8.com"

# ✅ Payload موحد
SSH_PAYLOAD = "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]"

# ✅ SNI/WSHost موحد للـ VMESS/VLESS/Trojan
V2RAY_SNI = "youtube.com"
V2RAY_WS_HOST = "youtube.com"

PAYLOADS = {
    "youtube": {
        "sni": V2RAY_SNI,
        "ws_header_host": V2RAY_WS_HOST,
        "payload": SSH_PAYLOAD,
    },
    "snapchat": {
        "sni": V2RAY_SNI,
        "ws_header_host": V2RAY_WS_HOST,
        "payload": SSH_PAYLOAD,
    },
}


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
        self.screenshot_counter = 0

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    # ═══════════════════════════════════════
    # Screenshot helper
    # ═══════════════════════════════════════

    async def _screenshot(self, caption: str = "❌ خطأ"):
        """يصوّر الصفحة ويبعثها"""
        if not self.page or not self.bot or not self.chat_id:
            return
        try:
            self.screenshot_counter += 1
            path = f"/tmp/sshs8_error_{self.screenshot_counter}_{int(asyncio.get_event_loop().time()*1000)}.png"
            await self.page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                try:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=f,
                        caption=caption[:1000],
                    )
                except Exception as e:
                    log.warning(f"⚠️ send_photo: {e}")
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ screenshot: {e}")

    async def _fail(self, message: str) -> dict:
        """يصوّر ويوقف"""
        log.warning(f"❌ {message}")
        await self._screenshot(f"❌ {message}")
        return {"success": False, "message": message}

    # ═══════════════════════════════════════
    # 1. فتح الموقع
    # ═══════════════════════════════════════

    async def open_home(self) -> bool:
        log.info(f"🌐 فتح: {BASE_URL}")
        self.page = await self.context.new_page()

        try:
            await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(4000)

            # ✅ نتحققو من Cloudflare
            title = await self.page.title()
            if "just a moment" in title.lower() or "cloudflare" in title.lower():
                log.warning("⚠️ Cloudflare detected")
                # ✅ نستناو شوية
                for i in range(30):
                    await self.page.wait_for_timeout(2000)
                    title = await self.page.title()
                    if "just a moment" not in title.lower() and "cloudflare" not in title.lower():
                        log.info(f"✅ Cloudflare passed after {(i+1)*2}s")
                        break
                else:
                    await self._screenshot("❌ Cloudflare ما تجاوزناش")
                    return False

            return True
        except Exception as e:
            log.error(f"❌ open_home: {e}", exc_info=True)
            await self._screenshot(f"❌ open_home: {str(e)[:200]}")
            return False

    # ═══════════════════════════════════════
    # 2. البروتوكولات
    # ═══════════════════════════════════════

    async def get_protocols(self) -> list:
        page = self.page
        try:
            # ✅ نضغطو Menu
            menu_clicked = False
            for sel in [
                'button:has-text("Menu")',
                'text="Menu"',
                'a:has-text("Menu")',
                '[class*="menu-toggle"]',
                '[class*="hamburger"]',
                'button[aria-label*="menu" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=3000)
                        await page.wait_for_timeout(2000)
                        menu_clicked = True
                        log.info(f"✅ Menu clicked via {sel}")
                        break
                except Exception:
                    continue

            if not menu_clicked:
                # نصورو ونوقفو
                await self._screenshot("⚠️ ما لقيناش زر Menu")
                # نجربو نكملو

            # ✅ نستخرجو البروتوكولات
            protocols = await page.evaluate(r"""
                () => {
                    const out = [];
                    const known = [
                        "SSH Websocket", "SSH Dropbear", "SSH STunnel", "SSH Tunnel",
                        "OpenVPN", "V2Ray VLESS", "V2Ray VMESS", "WireGuard",
                        "Trojan Go VPN", "TROJAN", "ShadowSocksR", "ShadowSocks"
                    ];

                    const links = document.querySelectorAll('a');
                    for (const a of links) {
                        const t = (a.innerText || a.textContent || '').trim();
                        if (!t || t.length > 60) continue;

                        for (const proto of known) {
                            if (t.toLowerCase().includes(proto.toLowerCase()) && !out.find(x => x.name === proto)) {
                                out.push({ name: proto, href: a.href || '' });
                                break;
                            }
                        }
                    }

                    return out;
                }
            """)

            if not protocols:
                await self._screenshot("⚠️ ما لقيناش بروتوكولات")

            log.info(f"📋 Protocols: {len(protocols)}")
            return protocols

        except Exception as e:
            log.error(f"❌ get_protocols: {e}", exc_info=True)
            await self._screenshot(f"❌ get_protocols: {str(e)[:200]}")
            return []

    # ═══════════════════════════════════════
    # 3. فتح بروتوكول → القارات
    # ═══════════════════════════════════════

    async def open_protocol(self, protocol_name: str) -> list:
        page = self.page
        try:
            # ✅ نضغطو
            clicked = False
            for sel in [
                f'a:has-text("{protocol_name}")',
                f'text="{protocol_name}"',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        clicked = True
                        log.info(f"✅ Protocol clicked: {protocol_name}")
                        break
                except Exception:
                    continue

            if not clicked:
                await self._screenshot(f"❌ ما لقيناش {protocol_name}")
                return []

            # ✅ نستخرجو القارات
            continents = await page.evaluate(r"""
                () => {
                    const out = [];
                    const keywords = [
                        "أوروبا", "آسيا", "أمريكا الشمالية", "أمريكا الجنوبية", "أفريقيا",
                        "Europe", "Asia", "North America", "South America", "Africa"
                    ];
                    const links = document.querySelectorAll('a');
                    for (const a of links) {
                        const t = (a.innerText || a.textContent || '').trim();
                        if (!t || t.length > 60) continue;
                        for (const kw of keywords) {
                            if (t.includes(kw) && !out.find(x => x.name === kw)) {
                                out.push({ name: kw, href: a.href || '' });
                                break;
                            }
                        }
                    }
                    return out;
                }
            """)

            if not continents:
                await self._screenshot(f"⚠️ ما لقيناش قارات لـ {protocol_name}")

            log.info(f"🌍 Continents: {len(continents)}")
            return continents

        except Exception as e:
            log.error(f"❌ open_protocol: {e}", exc_info=True)
            await self._screenshot(f"❌ open_protocol: {str(e)[:200]}")
            return []

    # ═══════════════════════════════════════
    # 4. قارة → الدول
    # ═══════════════════════════════════════

    async def open_continent(self, continent_name: str) -> list:
        page = self.page
        try:
            clicked = False
            for sel in [
                f'a:has-text("{continent_name}")',
                f'text="{continent_name}"',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        clicked = True
                        log.info(f"✅ Continent clicked: {continent_name}")
                        break
                except Exception:
                    continue

            if not clicked:
                await self._screenshot(f"❌ ما لقيناش {continent_name}")
                return []

            countries = await page.evaluate(r"""
                () => {
                    const out = [];
                    const cards = document.querySelectorAll('[class*="card"], article, [class*="country"]');
                    for (const card of cards) {
                        const h = card.querySelector('h2, h3, h4, strong');
                        if (!h) continue;
                        const name = (h.innerText || '').trim();
                        if (!name || name.length > 60) continue;
                        const link = card.querySelector('a');
                        const href = link ? link.href : '';
                        if (!out.find(x => x.name === name)) {
                            out.push({ name: name, href: href });
                        }
                    }
                    return out;
                }
            """)

            if not countries:
                await self._screenshot(f"⚠️ ما لقيناش دول فـ {continent_name}")

            log.info(f"🌍 Countries: {len(countries)}")
            return countries

        except Exception as e:
            log.error(f"❌ open_continent: {e}", exc_info=True)
            await self._screenshot(f"❌ open_continent: {str(e)[:200]}")
            return []

    # ═══════════════════════════════════════
    # 5. دولة → الخوادم
    # ═══════════════════════════════════════

    async def open_country(self, country_name: str) -> list:
        page = self.page
        try:
            clicked = False
            for sel in [
                f'text="{country_name}"',
                f'a:has-text("{country_name}")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=5000)
                        await page.wait_for_timeout(3000)
                        clicked = True
                        log.info(f"✅ Country clicked: {country_name}")
                        break
                except Exception:
                    continue

            if not clicked:
                await self._screenshot(f"❌ ما لقيناش {country_name}")
                return []

            # ✅ نضغطو "قائمة الخوادم" إلا كان
            for sel in [
                'text="قائمة الخوادم"',
                'a:has-text("قائمة الخوادم")',
                'button:has-text("قائمة الخوادم")',
                'text="Server List"',
                'a:has-text("Server List")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await page.wait_for_timeout(3000)
                        log.info(f"✅ Server list opened")
                        break
                except Exception:
                    continue

            # ✅ نستخرجو الخوادم
            servers = await page.evaluate(r"""
                () => {
                    const out = [];
                    const cards = document.querySelectorAll('[class*="card"], article, [class*="server"]');
                    for (const card of cards) {
                        const text = (card.innerText || '');
                        const match = text.match(/E\d{2,3}/);
                        if (!match) continue;

                        const btn = card.querySelector('a, button');
                        if (!btn) continue;

                        // نلقاو رابط إنشاء حساب
                        const createBtn = Array.from(card.querySelectorAll('a, button')).find(b =>
                            (b.innerText || '').includes('إنشاء') || (b.innerText || '').toLowerCase().includes('create')
                        );

                        out.push({
                            id: match[0],
                            href: (createBtn ? createBtn.href : btn.href) || '',
                            text: text.trim().substring(0, 100),
                        });
                    }
                    return out;
                }
            """)

            if not servers:
                await self._screenshot(f"⚠️ ما لقيناش خوادم فـ {country_name}")

            log.info(f"🖥️ Servers: {len(servers)}")
            return servers

        except Exception as e:
            log.error(f"❌ open_country: {e}", exc_info=True)
            await self._screenshot(f"❌ open_country: {str(e)[:200]}")
            return []

    # ═══════════════════════════════════════
    # 6. إنشاء الحساب
    # ═══════════════════════════════════════

    async def create_account_from_server(self, server_href: str) -> dict:
        page = self.page
        if not server_href:
            return await self._fail("❌ لا يوجد رابط خادم")

        password_value = generate_password()

        try:
            await page.goto(server_href, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            # ✅ نعبيو username
            for sel in ['input[name*="user" i]', 'input[type="text"]', 'input[name="username"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        val = await el.input_value()
                        if not val:
                            await el.fill(f"u{random.randint(100000000, 999999999)}")
                        break
                except Exception:
                    continue

            # ✅ نعبيو password
            for sel in ['input[type="password"]', 'input[name*="pass" i]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        await page.wait_for_timeout(200)
                        await el.fill("")
                        await el.fill(password_value)
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(500)
            url_before = page.url

            # ✅ نضغطو Create
            for sel in [
                'button:has-text("إنشاء حساب")',
                'button:has-text("Create account")',
                'button:has-text("Create")',
                'input[type="submit"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(timeout=5000)
                        log.info(f"✅ Create clicked")
                        break
                except Exception:
                    continue

            # ✅ نستناو
            for i in range(30):
                await page.wait_for_timeout(1000)
                if page.url != url_before:
                    break

            await page.wait_for_timeout(3000)

            # ✅ نستخرجو
            return await self._extract_credentials(page, password_value)

        except Exception as e:
            log.error(f"❌ create_account_from_server: {e}", exc_info=True)
            return await self._fail(f"❌ create: {str(e)[:200]}")

    # ═══════════════════════════════════════
    # 7. استخراج المعلومات
    # ═══════════════════════════════════════

    async def _extract_credentials(self, page, fallback_password: str) -> dict:
        result = {
            "success": False,
            "host": None,
            "domain": None,
            "username": None,
            "password": fallback_password,
            "vmess_config": None,
            "link_tls": None,
            "message": None,
        }

        for attempt in range(40):
            data = await page.evaluate(r"""
                () => {
                    const out = { values: [], ipv4: null, domain: null, user: null, pass: null, link: null };
                    const inputs = document.querySelectorAll('input, textarea');
                    for (const inp of inputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (!val) continue;
                        if (val.toLowerCase() === 'copy') continue;
                        out.values.push(val);
                        if (val.startsWith('vmess://') || val.startsWith('vless://') || val.startsWith('trojan://')) {
                            out.link = val;
                        }
                    }
                    for (const v of out.values) {
                        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v)) {
                            const parts = v.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) && !v.startsWith('192.168.') && !v.startsWith('10.') && !v.startsWith('127.')) {
                                out.ipv4 = v;
                                break;
                            }
                        }
                    }
                    for (const v of out.values) {
                        if (v === out.ipv4) continue;
                        if (/^[a-z0-9\-\.]+\.[a-z]{2,}$/i.test(v) && v.length < 60) {
                            out.domain = v;
                            break;
                        }
                    }
                    for (const v of out.values) {
                        if (v === out.ipv4 || v === out.domain) continue;
                        if (/^[a-z0-9_\-]{4,30}$/i.test(v) && !/^\d+$/.test(v)) {
                            out.user = v;
                            break;
                        }
                    }
                    return out;
                }
            """)

            if data.get("ipv4") and not result["host"]:
                result["host"] = data["ipv4"]
            if data.get("domain") and not result["domain"]:
                result["domain"] = data["domain"]
            if data.get("user") and not result["username"]:
                result["username"] = data["user"]
            if data.get("link") and not result["link_tls"]:
                result["link_tls"] = data["link"]

            if result["link_tls"]:
                vmess = self._decode_link(result["link_tls"])
                if vmess:
                    result["vmess_config"] = vmess
                    result["success"] = True
                    break
            elif result["host"] and result["username"]:
                result["success"] = True
                break

            await page.wait_for_timeout(1500)

        if not result["success"]:
            return await self._fail("❌ ما لقيناش المعلومات.")

        return result

    def _decode_link(self, link: str) -> dict:
        try:
            if link.startswith("vless://"):
                from urllib.parse import urlparse, parse_qs, unquote
                u = link.replace("vless://", "")
                parsed = urlparse("vless://" + u)
                uuid = parsed.username or parsed.netloc.split("@")[0] if "@" in parsed.netloc else ""
                host = parsed.hostname or ""
                port = parsed.port or 443
                params = parse_qs(parsed.query)
                return {
                    "id": uuid, "add": host, "port": port,
                    "path": unquote(params.get("path", ["/vless/"])[0]),
                    "host": params.get("host", ["youtube.com"])[0],
                    "sni": params.get("sni", "youtube.com")[0] if params.get("sni") else "youtube.com",
                }
            elif link.startswith("vmess://"):
                b64 = link.replace("vmess://", "").strip()
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                try:
                    decoded = base64.b64decode(b64).decode("utf-8")
                except Exception:
                    decoded = base64.urlsafe_b64decode(b64).decode("utf-8")
                return json.loads(decoded)
            elif link.startswith("trojan://"):
                from urllib.parse import urlparse, parse_qs
                u = link.replace("trojan://", "")
                parsed = urlparse("trojan://" + u)
                password = parsed.username or ""
                host = parsed.hostname or ""
                port = parsed.port or 443
                params = parse_qs(parsed.query)
                return {
                    "id": password, "add": host, "port": port,
                    "path": params.get("path", ["/trojan/"])[0],
                    "host": params.get("host", ["youtube.com"])[0],
                    "sni": "youtube.com",
                }
        except Exception as e:
            log.error(f"❌ _decode_link: {e}")
        return None

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
