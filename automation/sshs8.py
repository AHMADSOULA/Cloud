"""
automation/sshs8.py
- sshs8.com → Menu → SSH Websocket → قارة → دولة → Create Account → استخراج بيانات
"""
import asyncio
import random
import string
import re
import os
from utils.logger import get_logger

log = get_logger("SSHS8")


def generate_username():
    return "u" + "".join(random.choices(string.digits, k=10))


def generate_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=8))


# ═══════════════════════════════════════════
# القارات المتوفرة فـ sshs8
# ═══════════════════════════════════════════

CONTINENTS = [
    "Europe and West Asia",
    "East Asia",
    "North America",
    "Africa",
]


class SSHS8:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None

    async def _shot(self, page, caption: str = ""):
        if not self.sender:
            return
        try:
            path = f"/tmp/sshs8_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=f"📸 {caption}"[:1000])
                except Exception:
                    pass
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    # ═══════════════════════════════════════
    # 1. فتح الموقع والدخول لـ SSH WebSocket
    # ═══════════════════════════════════════

    async def open_ssh_websocket(self) -> list:
        log.info("🌐 فتح sshs8.com")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
            await self._shot(page, "1️⃣ الصفحة الرئيسية")

            # ✅ نفتحو Menu
            try:
                menu_btn = page.locator('button:has-text("Menu"), a:has-text("Menu")').first
                if await menu_btn.count() > 0 and await menu_btn.is_visible():
                    await menu_btn.click()
                    await page.wait_for_timeout(1500)
                    await self._shot(page, "2️⃣ Menu مفتوح")
            except Exception as e:
                log.warning(f"⚠️ Menu: {e}")

            # ✅ نضغطو على SSH Websocket
            ssh_clicked = False
            for sel in [
                'a:has-text("SSH Websocket")',
                'li:has-text("SSH Websocket")',
                'span:has-text("SSH Websocket")',
                'button:has-text("SSH Websocket")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        ssh_clicked = True
                        log.info("✅ SSH Websocket clicked")
                        break
                except Exception:
                    continue

            if not ssh_clicked:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('a, li, span, button')) {
                            const t = (el.innerText || '').trim();
                            if (t === 'SSH Websocket') {
                                try { el.click(); return; } catch (e) {}
                            }
                        }
                    }
                """)

            await page.wait_for_timeout(4000)
            await self._shot(page, "3️⃣ SSH Websocket")

            # ✅ نستخرجو القارات
            continents = await self._get_continents(page)
            log.info(f"🌍 القارات: {continents}")

            if not continents:
                continents = CONTINENTS

            return continents

        except Exception as e:
            log.error(f"❌ open_ssh_websocket: {e}", exc_info=True)
            return CONTINENTS

    # ═══════════════════════════════════════
    # 2. استخراج القارات
    # ═══════════════════════════════════════

    async def _get_continents(self, page) -> list:
        try:
            continents = await page.evaluate("""
                () => {
                    const out = [];
                    const keywords = ['Europe', 'Asia', 'America', 'Africa'];
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, p, div, span')) {
                        const t = (el.innerText || '').trim();
                        if (t.length > 5 && t.length < 60 &&
                            keywords.some(k => t.includes(k))) {
                            out.push(t);
                        }
                    }
                    return [...new Set(out)];
                }
            """)
            return continents or []
        except Exception as e:
            log.error(f"❌ _get_continents: {e}")
            return []

    # ═══════════════════════════════════════
    # 3. استخراج الدول
    # ═══════════════════════════════════════

    async def _get_countries_from_page(self, page) -> list:
        try:
            countries = await page.evaluate("""
                () => {
                    const out = [];
                    for (const el of document.querySelectorAll('a, button, li, span')) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('server list') || t.includes('create account')) {
                            const parent = el.closest('div');
                            if (parent) {
                                const lines = (parent.innerText || '').split('\\n').map(l => l.trim()).filter(l => l);
                                for (const l of lines) {
                                    if (/^[A-Z][a-z]+(\\s+[A-Z][a-z]+)*$/.test(l) && l.length > 3 && l.length < 40) {
                                        out.push(l);
                                    }
                                }
                            }
                        }
                    }
                    return [...new Set(out)];
                }
            """)
            return countries or []
        except Exception as e:
            log.error(f"❌ _get_countries_from_page: {e}")
            return []

    # ═══════════════════════════════════════
    # 4. اختيار قارة
    # ═══════════════════════════════════════

    async def select_continent(self, continent: str) -> list:
        page = self.page
        log.info(f"🌍 اختيار القارة: {continent}")

        try:
            await page.evaluate(f"""
                () => {{
                    const target = {continent!r}.toLowerCase();
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, p, div, a, button, span')) {{
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === target) {{
                            try {{ el.click(); return; }} catch (e) {{}}
                        }}
                    }}
                }}
            """)

            await page.wait_for_timeout(4000)
            await self._shot(page, f"4️⃣ {continent}")

            countries = await self._get_countries_from_page(page)
            log.info(f"🌍 الدول: {countries}")
            return countries

        except Exception as e:
            log.error(f"❌ select_continent: {e}", exc_info=True)
            return []

    # ═══════════════════════════════════════
    # 5. اختيار دولة
    # ═══════════════════════════════════════

    async def select_country(self, country: str) -> bool:
        page = self.page
        log.info(f"🌍 اختيار الدولة: {country}")

        try:
            clicked = await page.evaluate(f"""
                () => {{
                    const target = {country!r}.toLowerCase();
                    for (const el of document.querySelectorAll('a, button, div, span')) {{
                        const t = (el.innerText || '').trim();
                        if (t.toLowerCase().includes('server list')) {{
                            const parent = el.closest('div');
                            if (parent && parent.innerText.toLowerCase().includes(target)) {{
                                try {{ el.click(); return 'server_list'; }} catch (e) {{}}
                            }}
                        }}
                    }}
                    return null;
                }}
            """)

            if not clicked:
                await page.evaluate(f"""
                    () => {{
                        const target = {country!r}.toLowerCase();
                        for (const el of document.querySelectorAll('a, button, div, span, h1, h2, h3')) {{
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === target) {{
                                try {{ el.click(); return; }} catch (e) {{}}
                            }}
                        }}
                    }}
                """)

            await page.wait_for_timeout(4000)
            await self._shot(page, f"5️⃣ {country}")
            return True

        except Exception as e:
            log.error(f"❌ select_country: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # 6. Create Account
    # ═══════════════════════════════════════

    async def create_account(self, country: str = "") -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        username = generate_username()
        password = generate_password()

        log.info(f"👤 User: {username}")
        log.info(f"🔑 Pass: {password}")

        result = {
            "success": False,
            "username": username,
            "password": password,
            "country": country,
            "host": None,
            "message": None,
        }

        try:
            # ✅ نضغطو على "Create Account"
            clicked = False
            for sel in [
                'button:has-text("Create Account")',
                'a:has-text("Create Account")',
                'button:has-text("Create")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        clicked = True
                        log.info("✅ Create Account clicked")
                        break
                except Exception:
                    continue

            if not clicked:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('create account') || t === 'create') {
                                try { el.click(); return; } catch (e) {}
                            }
                        }
                    }
                """)

            await page.wait_for_timeout(3000)
            await self._shot(page, "6️⃣ بعد Create Account")

            # ✅ نعبيو الحقول
            try:
                for sel in [
                    'input[name*="user" i]', 'input[id*="user" i]',
                    'input[placeholder*="user" i]',
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click()
                            await el.fill(username)
                            break
                    except Exception:
                        continue

                for sel in [
                    'input[name*="pass" i]', 'input[id*="pass" i]',
                    'input[placeholder*="pass" i]', 'input[type="password"]',
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click()
                            await el.fill(password)
                            break
                    except Exception:
                        continue
            except Exception as e:
                log.warning(f"⚠️ inputs: {e}")

            await page.wait_for_timeout(2000)
            await self._shot(page, "7️⃣ بعد تعبئة الحقول")

            # ✅ زر Generate/Submit
            for sel in [
                'button:has-text("Generate")',
                'button:has-text("Submit")',
                'button:has-text("Create")',
                'button:has-text("Get")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        log.info(f"✅ {sel} clicked")
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(6000)
            await self._shot(page, "8️⃣ بعد Submit")

            # ✅ استخراج المعلومات
            info = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    const out = { host: null, user: null, pass: null, all_text: '' };
                    out.all_text = body;

                    const ipv4 = body.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/g) || [];
                    for (const ip of ipv4) {
                        const parts = ip.split('.').map(Number);
                        if (parts.every(p => p >= 0 && p <= 255) &&
                            ip !== '0.0.0.0' && ip !== '127.0.0.1') {
                            out.host = ip;
                            break;
                        }
                    }

                    if (!out.host) {
                        const hostnames = body.match(/\\b([a-z][a-z0-9\\-]{2,63}\\.)+[a-z]{2,}\\b/gi) || [];
                        for (const h of hostnames) {
                            const hl = h.toLowerCase();
                            if (!hl.includes('sshs8') && !hl.includes('google') &&
                                !hl.includes('youtube') && !hl.includes('facebook') &&
                                !hl.includes('example') && !hl.includes('cloudflare')) {
                                out.host = h;
                                break;
                            }
                        }
                    }

                    const user = body.match(/\\bu[0-9]{6,12}\\b/);
                    if (user) out.user = user[0];

                    const pass = body.match(/(?:password|pass)\\s*[:\\-]\\s*([A-Za-z0-9]{6,16})/i);
                    if (pass) out.pass = pass[1];

                    return out;
                }
            """)

            log.info(f"🔍 info: {info.get('host')} | {info.get('user')} | {info.get('pass')}")
            log.info(f"📄 All text preview: {info.get('all_text', '')[:800]}")

            if info.get("host"):
                result["host"] = info["host"]
            if info.get("user"):
                result["username"] = info["user"]
            if info.get("pass"):
                result["password"] = info["pass"]

            if not result["host"]:
                log.warning("❌ مالقيناش host")
                result["success"] = False
                result["message"] = "ما لقيناش host — يمكن الموقع تبدل."
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            await self._shot(page, f"❌ خطأ: {str(e)[:100]}")

        return result

    async def close(self):
        try:
            await self.page.close()
        except Exception:
            pass
