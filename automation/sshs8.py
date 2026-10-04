"""
automation/sshs8.py
دخول sshs8.com → SSH WebSocket → اختيار دولة → إنشاء حساب
"""
import asyncio
import random
import string
import re
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SSHS8")


def generate_username():
    """username عشوائي"""
    return "u" + "".join(random.choices(string.digits, k=10))


def generate_password():
    """password عشوائي"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=8))


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
            import os
            path = f"/tmp/sshs8_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=8000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
                except Exception:
                    pass
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception:
            pass

    # ═══════════════════════════════════════
    # 1. فتح الموقع + SSH WebSocket
    # ═══════════════════════════════════════

    async def open_ssh_websocket(self) -> list:
        """يفتح sshs8.com ويختار SSH WebSocket، ويرجع الدول"""
        log.info("🌐 فتح sshs8.com")

        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await self._shot(page, "1️⃣ sshs8.com")

            # ✅ نضغطو SSH WebSocket
            log.info("🖱️ SSH WebSocket")
            clicked = False
            for sel in [
                'a:has-text("SSH WebSocket")',
                'button:has-text("SSH WebSocket")',
                '[role="button"]:has-text("SSH WebSocket")',
                'text="SSH WebSocket"',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        log.info(f"✅ SSH WebSocket clicked")
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # JS fallback
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('a, button, [role="button"], div')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'ssh websocket' || t.includes('ssh websocket')) {
                                try { el.click(); return true; } catch (e) {}
                            }
                        }
                        return false;
                    }
                """)

            await page.wait_for_timeout(4000)
            await self._shot(page, "2️⃣ بعد SSH WebSocket")

            # ✅ نجيبو الدول
            countries = await self._get_countries(page)
            log.info(f"🌍 عدد الدول: {len(countries)}")

            return countries

        except Exception as e:
            log.error(f"❌ open_ssh_websocket: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")
            return []

    # ═══════════════════════════════════════
    # 2. جلب الدول
    # ═══════════════════════════════════════

    async def _get_countries(self, page) -> list:
        """يجيب قائمة الدول من الصفحة"""
        try:
            countries = await page.evaluate("""
                () => {
                    const out = [];
                    // نبحثو على dropdowns / buttons / options
                    // 1. select > option
                    for (const sel of document.querySelectorAll('select')) {
                        for (const opt of sel.querySelectorAll('option')) {
                            const t = (opt.innerText || opt.textContent || '').trim();
                            if (t && t.length < 60 && !t.toLowerCase().includes('select')) {
                                out.push(t);
                            }
                        }
                    }
                    // 2. Buttons / links
                    if (out.length === 0) {
                        for (const el of document.querySelectorAll('button, a, [role="button"], [role="option"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 60 &&
                                !t.toLowerCase().includes('select') &&
                                !t.toLowerCase().includes('submit') &&
                                !t.toLowerCase().includes('create') &&
                                !t.toLowerCase().includes('login') &&
                                !t.toLowerCase().includes('menu') &&
                                !t.toLowerCase().includes('home') &&
                                !t.toLowerCase().includes('back')) {
                                out.push(t);
                            }
                        }
                    }
                    // نحيدو التكرار
                    return [...new Set(out)];
                }
            """)
            return countries or []
        except Exception as e:
            log.error(f"❌ _get_countries: {e}")
            return []

    # ═══════════════════════════════════════
    # 3. اختيار دولة + إنشاء حساب
    # ═══════════════════════════════════════

    async def create_account(self, country: str) -> dict:
        """
        يختار الدولة، يكتب username + password عشوائيين،
        يضغط Create/Submit، ويرجع {username, password, host}
        """
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        username = generate_username()
        password = generate_password()

        log.info(f"🌍 الدولة: {country}")
        log.info(f"👤 User: {username}")
        log.info(f"🔑 Pass: {password}")

        result = {
            "success": False,
            "username": username,
            "password": password,
            "country": country,
            "host": None,
        }

        try:
            # ✅ 1. نختارو الدولة
            log.info("🖱️ نختار الدولة")
            clicked_country = await page.evaluate(f"""
                () => {{
                    const target = {country!r}.toLowerCase();
                    for (const el of document.querySelectorAll('option, button, a, [role="option"], [role="button"]')) {{
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (t === target || t.includes(target)) {{
                            try {{ el.click(); return t; }} catch (e) {{}}
                        }}
                    }}
                    return null;
                }}
            """)

            if not clicked_country:
                # select option
                try:
                    await page.select_option('select', label=country)
                except Exception:
                    pass

            await page.wait_for_timeout(2000)
            await self._shot(page, f"3️⃣ اخترنا {country}")

            # ✅ 2. نكتبو username
            log.info("⌨️ username")
            for sel in [
                'input[name*="user" i]',
                'input[id*="user" i]',
                'input[placeholder*="user" i]',
                'input[type="text"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await el.fill("")
                        await page.wait_for_timeout(200)
                        await el.fill(username)
                        log.info(f"✅ username: {username}")
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(800)

            # ✅ 3. نكتبو password
            log.info("⌨️ password")
            for sel in [
                'input[name*="pass" i]',
                'input[id*="pass" i]',
                'input[placeholder*="pass" i]',
                'input[type="password"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await el.fill("")
                        await page.wait_for_timeout(200)
                        await el.fill(password)
                        log.info("✅ password")
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(1000)
            await self._shot(page, "4️⃣ الحقول معبأة")

            # ✅ 4. نضغطو Create / Submit
            log.info("🖱️ Create")
            submitted = False
            for sel in [
                'button:has-text("Create")',
                'button:has-text("Submit")',
                'button:has-text("Create Account")',
                'button:has-text("Generate")',
                'input[type="submit"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        submitted = True
                        log.info(f"✅ {sel}")
                        break
                except Exception:
                    continue

            if not submitted:
                # JS
                submitted = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, input[type="submit"], [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            if (t.includes('create') || t.includes('submit') || t.includes('generate')) {
                                try { el.click(); return true; } catch (e) {}
                            }
                        }
                        return false;
                    }
                """)

            await page.wait_for_timeout(5000)
            await self._shot(page, "5️⃣ بعد Create")

            # ✅ 5. نجيبو host
            host = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    // IP
                    const ip = body.match(/([0-9]{1,3}\\.){3}[0-9]{1,3}/);
                    if (ip) return ip[0];
                    // host:port
                    const host = body.match(/([a-zA-Z0-9\\.\\-]+\\.[a-z]{2,})/);
                    if (host) return host[0];
                    return null;
                }
            """)
            result["host"] = host
            log.info(f"🖥️ Host: {host}")

            # ✅ 6. نجيبو username/password من الصفحة (يمكن تبدلو)
            new_user = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('input, code, pre, span')) {
                        const v = el.value || el.innerText || '';
                        if (/^u[0-9]{6,}$/.test(v.trim())) return v.trim();
                    }
                    return null;
                }
            """)
            new_pass = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('input, code, pre, span')) {
                        const v = el.value || el.innerText || '';
                        if (/^[a-zA-Z0-9]{6,12}$/.test(v.trim()) && v.trim() !== '') {
                            return v.trim();
                        }
                    }
                    return null;
                }
            """)

            if new_user:
                result["username"] = new_user
            if new_pass:
                result["password"] = new_pass

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")

        return result

    async def close(self):
        try:
            await self.page.close()
        except Exception:
            pass
