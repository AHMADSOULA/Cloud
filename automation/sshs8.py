"""
automation/sshs8.py
- يستكشف الموقع + يسجل كل خطوة
"""
import asyncio
import random
import string
import os
import base64
import json
from utils.logger import get_logger
from utils.recorder import BrowserRecorder

log = get_logger("SSHS8")


BASE_URL = "https://sshs8.com"

SSH_PAYLOAD = "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]"

V2RAY_SNI = "youtube.com"
V2RAY_WS_HOST = "youtube.com"

PAYLOADS = {
    "youtube": {"sni": V2RAY_SNI, "ws_header_host": V2RAY_WS_HOST, "payload": SSH_PAYLOAD},
    "snapchat": {"sni": V2RAY_SNI, "ws_header_host": V2RAY_WS_HOST, "payload": SSH_PAYLOAD},
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
        self.recorder = BrowserRecorder(context)

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    def set_bot(self, bot):
        self.bot = bot
        if self.chat_id:
            self.recorder.set_bot(bot, self.chat_id)

    # ═══════════════════════════════════════
    # Screenshot
    # ═══════════════════════════════════════

    async def _shot(self, name: str, send: bool = False):
        """screenshot + تسجيل"""
        if not self.page:
            return
        try:
            path = f"/tmp/rec_{name}_{int(asyncio.get_event_loop().time()*1000)}.png"
            await self.page.screenshot(path=path, full_page=False, timeout=10000)
            await self.recorder.add_step(f"screenshot_{name}", extra={"path": path})

            if send and self.bot and self.chat_id:
                try:
                    with open(path, "rb") as f:
                        await self.bot.send_photo(chat_id=self.chat_id, photo=f, caption=f"📸 {name}")
                except Exception as e:
                    log.warning(f"⚠️ send_photo: {e}")

            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    # ═══════════════════════════════════════
    # Close ads
    # ═══════════════════════════════════════

    async def _close_ads(self):
        if not self.page:
            return
        try:
            await self.page.evaluate("""
                () => {
                    const iframes = document.querySelectorAll('iframe');
                    for (const f of iframes) {
                        if (f.src && (f.src.includes('ads') || f.src.includes('google') || f.src.includes('doubleclick') || f.src.includes('fluid'))) {
                            f.remove();
                        }
                    }
                    const overlays = document.querySelectorAll('[class*="popup"], [class*="modal"], [class*="overlay"]');
                    for (const o of overlays) {
                        try {
                            const s = window.getComputedStyle(o);
                            if (s.zIndex > 100 || s.position === 'fixed') o.remove();
                        } catch(e) {}
                    }
                }
            """)
            await self.recorder.add_step("close_ads")
        except Exception:
            pass

    # ═══════════════════════════════════════
    # Click / Type
    # ═══════════════════════════════════════

    async def _click(self, selector: str, description: str = ""):
        if not self.page:
            return False
        try:
            el = self.page.locator(selector).first
            if await el.count() == 0:
                await self.recorder.add_step("click_not_found", selector=selector, value=description)
                return False
            if not await el.is_visible():
                await self.recorder.add_step("click_not_visible", selector=selector, value=description)
                return False
            await el.click(timeout=5000)
            await self.recorder.add_step("click", selector=selector, value=description)
            return True
        except Exception as e:
            await self.recorder.add_step("click_error", selector=selector, extra={"error": str(e)[:200]})
            return False

    # ═══════════════════════════════════════
    # Home
    # ═══════════════════════════════════════

    async def open_home(self) -> bool:
        log.info(f"🌐 فتح: {BASE_URL}")
        await self.recorder.start_recording()

        self.page = await self.context.new_page()

        try:
            await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await self.recorder.add_step("goto", value=BASE_URL)
            await self.page.wait_for_timeout(4000)

            title = await self.page.title()
            await self.recorder.add_step("page_loaded", extra={"title": title})

            if "just a moment" in title.lower() or "cloudflare" in title.lower():
                for i in range(30):
                    await self.page.wait_for_timeout(2000)
                    title = await self.page.title()
                    if "just a moment" not in title.lower() and "cloudflare" not in title.lower():
                        await self.recorder.add_step("cloudflare_passed", extra={"time": f"{(i+1)*2}s"})
                        break
                else:
                    await self._shot("cloudflare_blocked", send=True)
                    return False

            await self._close_ads()
            await self._shot("home_loaded", send=True)
            return True
        except Exception as e:
            log.error(f"❌ open_home: {e}", exc_info=True)
            await self.recorder.add_step("goto_failed", extra={"error": str(e)[:200]})
            return False

    # ═══════════════════════════════════════
    # Protocols
    # ═══════════════════════════════════════

    async def get_protocols(self) -> list:
        page = self.page
        try:
            await self._close_ads()

            protocols = await page.evaluate(r"""
                () => {
                    const out = [];
                    const known = ["SSH Websocket", "SSH Dropbear", "SSH STunnel", "SSH Tunnel", "OpenVPN", "V2Ray VLESS", "V2Ray VMESS", "WireGuard", "Trojan Go VPN", "TROJAN", "ShadowSocksR", "ShadowSocks"];
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

            await self.recorder.add_step("found_protocols", extra={"count": len(protocols), "names": [p['name'] for p in protocols]})
            await self._shot("protocols", send=True)
            return protocols
        except Exception as e:
            await self.recorder.add_step("get_protocols_error", extra={"error": str(e)[:200]})
            return []

    async def open_protocol(self, protocol_name: str) -> list:
        page = self.page
        try:
            await self._close_ads()
            await self._click(f'a:has-text("{protocol_name}")', protocol_name)
            await page.wait_for_timeout(4000)
            await self._shot(f"protocol_{protocol_name.replace(' ', '_')}", send=True)

            continents = await page.evaluate(r"""
                () => {
                    const out = [];
                    const keywords = ["أوروبا", "آسيا", "أمريكا الشمالية", "أمريكا الجنوبية", "أفريقيا", "Europe", "Asia", "North America", "South America", "Africa"];
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

            await self.recorder.add_step("found_continents", extra={"count": len(continents), "names": [c['name'] for c in continents]})
            return continents
        except Exception as e:
            await self.recorder.add_step("open_protocol_error", extra={"error": str(e)[:200]})
            return []

    async def open_continent(self, continent_name: str) -> list:
        page = self.page
        try:
            await self._close_ads()
            await self._click(f'a:has-text("{continent_name}")', continent_name)
            await page.wait_for_timeout(4000)
            await self._shot(f"continent_{continent_name.replace(' ', '_')}", send=True)

            countries = await page.evaluate(r"""
                () => {
                    const out = [];
                    const exclude = ["Menu", "Home", "About", "Close", "Open", "SSH Websocket", "SSH Dropbear", "SSH STunnel", "SSH Tunnel", "OpenVPN", "V2Ray VLESS", "V2Ray VMESS", "WireGuard", "Trojan Go VPN", "TROJAN", "ShadowSocksR", "ShadowSocks"];
                    const headers = document.querySelectorAll('h2, h3, h4, strong');
                    for (const h of headers) {
                        const name = (h.innerText || '').trim();
                        if (!name || name.length > 60) continue;
                        if (exclude.includes(name)) continue;
                        if (!out.find(x => x.name === name)) out.push({ name: name, href: '' });
                    }
                    const links = document.querySelectorAll('a[href*="SSH"], a[href*="vless"], a[href*="vmess"], a[href*="trojan"]');
                    for (const a of links) {
                        const t = (a.innerText || '').trim();
                        if (!t || t.length > 60 || t.length < 3) continue;
                        if (exclude.includes(t)) continue;
                        if (!out.find(x => x.name === t)) out.push({ name: t, href: a.href || '' });
                    }
                    return out;
                }
            """)

            await self.recorder.add_step("found_countries", extra={"count": len(countries), "names": [c['name'] for c in countries]})
            return countries
        except Exception as e:
            await self.recorder.add_step("open_continent_error", extra={"error": str(e)[:200]})
            return []

    async def open_country(self, country_name: str) -> list:
        page = self.page
        try:
            await self._close_ads()
            await self._click(f'text="{country_name}"', country_name)
            await page.wait_for_timeout(4000)
            await self._shot(f"country_{country_name.replace(' ', '_')}", send=True)

            for sel in ['text="قائمة الخوادم"', 'a:has-text("قائمة الخوادم")', 'text="Server List"']:
                if await self._click(sel, "server_list"):
                    await page.wait_for_timeout(3000)
                    break

            servers = await page.evaluate(r"""
                () => {
                    const out = [];
                    const cards = document.querySelectorAll('[class*="card"], article, [class*="server"]');
                    for (const card of cards) {
                        const text = (card.innerText || '');
                        const match = text.match(/E\d{2,3}/);
                        if (!match) continue;
                        const btns = Array.from(card.querySelectorAll('a, button'));
                        const createBtn = btns.find(b => (b.innerText || '').includes('إنشاء') || (b.innerText || '').toLowerCase().includes('create'));
                        if (!createBtn) continue;
                        out.push({ id: match[0], href: createBtn.href || '' });
                    }
                    return out;
                }
            """)

            await self.recorder.add_step("found_servers", extra={"count": len(servers), "servers": [s['id'] for s in servers]})
            return servers
        except Exception as e:
            await self.recorder.add_step("open_country_error", extra={"error": str(e)[:200]})
            return []

    async def create_account_from_server(self, server_href: str) -> dict:
        page = self.page
        if not server_href:
            return {"success": False, "message": "❌ لا يوجد رابط"}

        password_value = generate_password()

        try:
            await page.goto(server_href, wait_until="domcontentloaded", timeout=60000)
            await self.recorder.add_step("goto_server", value=server_href)
            await page.wait_for_timeout(4000)
            await self._close_ads()
            await self._shot("server_page", send=True)

            for sel in ['input[name*="user" i]', 'input[type="text"]', 'input[name="username"]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        val = await el.input_value()
                        if not val:
                            await el.fill(f"u{random.randint(100000000, 999999999)}")
                            await self.recorder.add_step("fill_username", selector=sel)
                        break
                except Exception:
                    continue

            for sel in ['input[type="password"]', 'input[name*="pass" i]']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.fill(password_value)
                        await self.recorder.add_step("fill_password", selector=sel, value=password_value[:5] + "...")
                        break
                except Exception:
                    continue

            for sel in ['button:has-text("إنشاء حساب")', 'button:has-text("Create account")', 'button:has-text("Create")', 'input[type="submit"]']:
                if await self._click(sel, "create_button"):
                    break

            await page.wait_for_timeout(5000)
            await self._shot("after_create", send=True)

            result = await self._extract_credentials(page, password_value)
            await self.recorder.add_step("extracted", extra=result)
            return result
        except Exception as e:
            await self.recorder.add_step("create_error", extra={"error": str(e)[:200]})
            return {"success": False, "message": str(e)[:200]}

    async def _extract_credentials(self, page, fallback_password: str) -> dict:
        result = {"success": False, "host": None, "domain": None, "username": None, "password": fallback_password, "vmess_config": None, "link_tls": None, "message": None}

        for attempt in range(40):
            data = await page.evaluate(r"""
                () => {
                    const out = { values: [], ipv4: null, domain: null, user: null, link: null };
                    const inputs = document.querySelectorAll('input, textarea');
                    for (const inp of inputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (!val || val.toLowerCase() === 'copy') continue;
                        out.values.push(val);
                        if (val.startsWith('vmess://') || val.startsWith('vless://') || val.startsWith('trojan://')) out.link = val;
                    }
                    for (const v of out.values) {
                        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v)) {
                            const parts = v.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) && !v.startsWith('192.168.') && !v.startsWith('10.') && !v.startsWith('127.')) { out.ipv4 = v; break; }
                        }
                    }
                    for (const v of out.values) {
                        if (v === out.ipv4) continue;
                        if (/^[a-z0-9\-\.]+\.[a-z]{2,}$/i.test(v) && v.length < 60) { out.domain = v; break; }
                    }
                    for (const v of out.values) {
                        if (v === out.ipv4 || v === out.domain) continue;
                        if (/^[a-z0-9_\-]{4,30}$/i.test(v) && !/^\d+$/.test(v)) { out.user = v; break; }
                    }
                    return out;
                }
            """)

            if data.get("ipv4") and not result["host"]: result["host"] = data["ipv4"]
            if data.get("domain") and not result["domain"]: result["domain"] = data["domain"]
            if data.get("user") and not result["username"]: result["username"] = data["user"]
            if data.get("link") and not result["link_tls"]: result["link_tls"] = data["link"]

            if result["link_tls"]:
                result["vmess_config"] = self._decode_link(result["link_tls"])
                result["success"] = True
                break
            elif result["host"] and result["username"]:
                result["success"] = True
                break

            await page.wait_for_timeout(1500)

        return result

    def _decode_link(self, link: str) -> dict:
        try:
            if link.startswith("vless://"):
                from urllib.parse import urlparse, parse_qs, unquote
                u = link.replace("vless://", "")
                parsed = urlparse("vless://" + u)
                uuid = parsed.username or parsed.netloc.split("@")[0] if "@" in parsed.netloc else ""
                return {"id": uuid, "add": parsed.hostname or "", "port": parsed.port or 443, "path": unquote(parse_qs(parsed.query).get("path", ["/vless/"])[0])}
            elif link.startswith("vmess://"):
                b64 = link.replace("vmess://", "").strip()
                b64 += "=" * ((4 - len(b64) % 4) % 4)
                try:
                    decoded = base64.b64decode(b64).decode("utf-8")
                except Exception:
                    decoded = base64.urlsafe_b64decode(b64).decode("utf-8")
                return json.loads(decoded)
        except Exception:
            return None

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
