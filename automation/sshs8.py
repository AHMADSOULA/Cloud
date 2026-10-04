"""
automation/sshs8.py
- sshs8.com → SSH Websocket → قارة → دولة → Create Account → استخراج بيانات
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

            # ✅ نستخرجو القارات + الدول
            continents = await self._get_continents(page)
            log.info(f"🌍 القارات: {continents}")

            countries = await self._get_countries_from_page(page)
            log.info(f"🌍 الدول فالصفحة الحالية: {len(countries)}")

            if not continents:
                continents = CONTINENTS

            # نرجعو القارات باش المستخدم يختار
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
                    const keywords = ['Europe', 'Asia', 'America', 'Africa', 'West', 'East', 'North', 'South'];
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, p, div, span')) {
                        const t = (el.innerText || '').trim();
                        if (t.length > 5 && t.length < 60 &&
                            keywords.some(k => t.includes(k)) &&
                            !t.toLowerCase().includes('create') &&
                            !t.toLowerCase().includes('server list')) {
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
    # 3. استخراج الدول من الصفحة
    # ═══════════════════════════════════════

    async def _get_countries_from_page(self, page) -> list:
        try:
            countries = await page.evaluate("""
                () => {
                    const out = [];
                    for (const el of document.querySelectorAll('a, button, li, span')) {
                        const t = (el.innerText || '').trim();
                        if (t.toLowerCase().includes('server list') ||
                            t.toLowerCase().includes('create account')) {
                            // parent كيحتوي على اسم الدولة
                            const parent = el.closest('div');
                            if (parent) {
                                const lines = (parent.innerText || '').split('\\n').map(l => l.trim()).filter(l => l);
                                for (const l of lines) {
                                    if (l.match(/^[A-Z][a-z]+(\\s+[A-Z][a-z]+)*$/) && l.length > 3 && l.length < 40) {
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
    # 4. اختيار قارة → يفتح صفحة القارة
    # ═══════════════════════════════════════

    async def select_continent(self, continent: str) -> list:
        page = self.page
        log.info(f"🌍 اختيار القارة: {continent}")

        try:
            clicked = await page.evaluate(f"""
                () => {{
                    const target = {continent!r}.toLowerCase();
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, p, div, a, button, span')) {{
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === target) {{
                            try {{ el.click(); return t; }} catch (e) {{}}
                        }}
                    }}
                    return null;
                }}
            """)

            await page.wait_for_timeout(4000)
            await self._shot(page, f"4️⃣ {continent}")

            # نستخرجو الدول من الصفحة الجديدة
            countries = await self._get_countries_from_page(page)
            log.info(f"🌍 الدول: {countries}")

            return countries

        except Exception as e:
            log.error(f"❌ select_continent: {e}", exc_info=True)
            return []

    # ═══════════════════════════════════════
    # 5. اختيار دولة → يفتح صفحة الدولة
    # ═══════════════════════════════════════

    async def select_country(self, country: str) -> bool:
        page = self.page
        log.info(f"🌍 اختيار الدولة: {country}")

        try:
            # نضغطو على "Server list" القريبة من الدولة
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
                # نجربو نضغطو على اسم الدولة مباشرة
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

            # ✅ نعبيو الحقول username/password إذا ظهرو
            # نلقاو inputs
            try:
                username_input = None
                password_input = None

                for sel in [
                    'input[name*="user" i]', 'input[id*="user" i]',
                    'input[placeholder*="user" i]',
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            username_input = el
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
                            password_input = el
                            break
                    except Exception:
                        continue

                if username_input:
                    await username_input.click()
                    await username_input.fill(username)
                if password_input:
                    await password_input.click()
                    await password_input.fill(password)

            except Exception as e:
                log.warning(f"⚠️ inputs: {e}")

            await page.wait_for_timeout(2000)
            await self._shot(page, "7️⃣ بعد تعبئة الحقول")

            # ✅ ندورو على زر Generate/Submit إذا كان كاين
            try:
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
            except Exception:
                pass

            await page.wait_for_timeout(6000)
            await self._shot(page, "8️⃣ بعد Submit")

            # ✅ نستخرجو Host/User/Pass
            info = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    const out = { host: null, user: null, pass: null };

                    // Host (IPv4)
                    const ipv4 = body.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/g) || [];
                    for (const ip of ipv4) {
                        const parts = ip.split('.').map(Number);
                        if (parts.every(p => p >= 0 && p <= 255) &&
                            ip !== '0.0.0.0' && ip !== '127.0.0.1') {
                            out.host = ip;
                            break;
                        }
                    }

                    // Host (hostname)
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

                    // User (u + أرقام)
                    const user = body.match(/\\bu[0-9]{6,12}\\b/);
                    if (user) out.user = user[0];

                    // Pass (بعد كلمة password)
                    const pass = body.match(/(?:password|pass)\\s*[:\\-]\\s*([A-Za-z0-9]{6,16})/i);
                    if (pass) out.pass = pass[1];

                    return out;
                }
            """)

            log.info(f"🔍 info: {info}")

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
