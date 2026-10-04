"""
automation/sshs8.py
دخول sshs8.com → إغلاق الإعلانات → SSH WebSocket → اختيار دولة
"""
import asyncio
import random
import string
import re
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SSHS8")


def generate_username():
    return "u" + "".join(random.choices(string.digits, k=10))


def generate_password():
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
    # إغلاق الإعلانات
    # ═══════════════════════════════════════

    async def _close_ads(self, page):
        """يحاول يغلق أي إعلان"""
        log.info("🚫 نحاولو نغلقو الإعلانات...")

        # ✅ نغلقو popups + modals + iframes إعلانية
        closed_count = 0
        for _ in range(3):  # 3 محاولات
            try:
                clicked = await page.evaluate("""
                    () => {
                        let closed = 0;
                        // 1. Close buttons
                        const close_texts = ['close', '×', '✕', 'x', 'إغلاق', 'تخطي', 'skip'];
                        for (const el of document.querySelectorAll('button, a, span, div, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase();
                            for (const kw of close_texts) {
                                if (t === kw) {
                                    try { el.click(); closed++; break; } catch (e) {}
                                }
                            }
                        }
                        // 2. Popups with class contain close/ads/popup
                        for (const el of document.querySelectorAll('[class*="close" i], [class*="popup" i], [class*="ad-" i], [id*="close" i]')) {
                            if (el.offsetParent === null) continue;
                            try { el.click(); closed++; } catch (e) {}
                        }
                        // 3. نحيّدو الـ overlays
                        for (const el of document.querySelectorAll('[class*="overlay" i], [class*="modal" i]')) {
                            if (el.offsetParent === null) continue;
                            try { el.style.display = 'none'; closed++; } catch (e) {}
                        }
                        return closed;
                    }
                """)
                if clicked:
                    closed_count += clicked
                    await page.wait_for_timeout(500)
            except Exception:
                pass

        # ✅ نضغطو Escape
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        log.info(f"🚫 أغلقنا {closed_count} إعلان")
        return closed_count

    # ═══════════════════════════════════════
    # 1. فتح الموقع
    # ═══════════════════════════════════════

    async def open_ssh_websocket(self) -> list:
        """يفتح sshs8.com → SSH WebSocket → يرجع الدول"""
        log.info("🌐 فتح sshs8.com")

        self.page = await self.context.new_page()
        page = self.page

        try:
            # ✅ نروحو لصفحة SSH WebSocket مباشرة
            # (نبحثو عن الرابط الصحيح)
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
            await self._shot(page, "1️⃣ sshs8.com")

            # ✅ نغلقو الإعلانات
            await self._close_ads(page)
            await page.wait_for_timeout(1500)
            await self._shot(page, "2️⃣ بعد إغلاق الإعلانات")

            # ✅ نروحو لصفحة SSH WebSocket
            log.info("🖱️ SSH WebSocket — نبحثو على الرابط")
            ssh_url = None
            try:
                ssh_url = await page.evaluate("""
                    () => {
                        for (const a of document.querySelectorAll('a')) {
                            const href = a.href || '';
                            const t = (a.innerText || '').trim().toLowerCase();
                            if (href && (href.includes('ssh-websocket') ||
                                         href.includes('sshwebsocket') ||
                                         href.includes('websocket') ||
                                         t === 'ssh websocket')) {
                                return href;
                            }
                        }
                        return null;
                    }
                """)
            except Exception:
                pass

            if ssh_url:
                log.info(f"✅ نروحو مباشرة: {ssh_url}")
                await page.goto(ssh_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(4000)
                await self._close_ads(page)
            else:
                # ✅ نضغطو على الزر
                log.info("🖱️ نضغطو على SSH WebSocket")
                clicked = False
                for sel in [
                    'a[href*="ssh-websocket"]',
                    'a[href*="sshwebsocket"]',
                    'a[href*="websocket"]',
                    'a:has-text("SSH WebSocket")',
                    'a:has-text("SSH-Websocket")',
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click()
                            clicked = True
                            log.info(f"✅ {sel}")
                            break
                    except Exception:
                        continue

                if not clicked:
                    # JS
                    await page.evaluate("""
                        () => {
                            for (const el of document.querySelectorAll('a, button, [role="button"]')) {
                                if (el.offsetParent === null) continue;
                                const t = (el.innerText || '').trim().toLowerCase();
                                if (t === 'ssh websocket' || t.includes('ssh websocket')) {
                                    try { el.click(); return; } catch (e) {}
                                }
                            }
                        }
                    """)

                await page.wait_for_timeout(4000)
                await self._close_ads(page)

            await page.wait_for_timeout(2000)
            await self._shot(page, "3️⃣ صفحة SSH WebSocket")

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
        """يجيب الدول من الـ select أو dropdown"""
        try:
            # ✅ نستناو الـ select يظهر
            for _ in range(5):
                await page.wait_for_timeout(1000)
                countries = await page.evaluate("""
                    () => {
                        const out = [];

                        // 1. نبحثو على <select> فيه دول
                        for (const sel of document.querySelectorAll('select')) {
                            const opts = [];
                            for (const opt of sel.querySelectorAll('option')) {
                                const t = (opt.innerText || opt.textContent || '').trim();
                                if (t && t.length > 1 && t.length < 80 &&
                                    !t.toLowerCase().includes('select') &&
                                    !t.toLowerCase().includes('choose') &&
                                    !t.toLowerCase().includes('---')) {
                                    opts.push(t);
                                }
                            }
                            if (opts.length > 3) {
                                out.push(...opts);
                            }
                        }

                        // 2. إذا ما لقيناش select، نبحثو على dropdown مخصص
                        if (out.length === 0) {
                            for (const el of document.querySelectorAll('[role="listbox"], [class*="dropdown" i], [class*="select" i]')) {
                                const opts = [];
                                for (const opt of el.querySelectorAll('[role="option"], li, a, button')) {
                                    const t = (opt.innerText || '').trim();
                                    if (t && t.length > 1 && t.length < 80 &&
                                        !t.toLowerCase().includes('select') &&
                                        !t.toLowerCase().includes('choose') &&
                                        !t.toLowerCase().includes('back') &&
                                        !t.toLowerCase().includes('close')) {
                                        opts.push(t);
                                    }
                                }
                                if (opts.length > 3) {
                                    out.push(...opts);
                                    break;
                                }
                            }
                        }

                        return [...new Set(out)];
                    }
                """)
                if countries and len(countries) > 3:
                    return countries

            return countries or []

        except Exception as e:
            log.error(f"❌ _get_countries: {e}")
            return []

    # ═══════════════════════════════════════
    # 3. إنشاء حساب
    # ═══════════════════════════════════════

    async def create_account(self, country: str) -> dict:
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
            # ✅ نغلقو الإعلانات مرة أخرى
            await self._close_ads(page)
            await page.wait_for_timeout(1000)

            # ✅ 1. نختارو الدولة
            log.info("🖱️ نختار الدولة")
            clicked_country = await page.evaluate(f"""
                () => {{
                    const target = {country!r}.toLowerCase();

                    // نبحثو في <select>
                    for (const sel of document.querySelectorAll('select')) {{
                        for (const opt of sel.querySelectorAll('option')) {{
                            const t = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                            if (t === target || t.includes(target)) {{
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return t;
                            }}
                        }}
                    }}

                    // نبحثو في dropdown مخصص
                    for (const el of document.querySelectorAll('[role="option"], li, a, button')) {{
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === target || t.includes(target)) {{
                            try {{ el.click(); return t; }} catch (e) {{}}
                        }}
                    }}
                    return null;
                }}
            """)

            if not clicked_country:
                try:
                    await page.select_option('select', label=country)
                except Exception:
                    pass

            await page.wait_for_timeout(2000)
            await self._shot(page, f"4️⃣ اخترنا {country}")

            # ✅ 2. username
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
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(800)

            # ✅ 3. password
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
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(1000)
            await self._shot(page, "5️⃣ الحقول معبأة")

            # ✅ 4. Create
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
                        break
                except Exception:
                    continue

            if not submitted:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, input[type="submit"], [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            if (t.includes('create') || t.includes('submit') || t.includes('generate')) {
                                try { el.click(); return; } catch (e) {}
                            }
                        }
                    }
                """)

            await page.wait_for_timeout(5000)
            await self._close_ads(page)
            await self._shot(page, "6️⃣ بعد Create")

            # ✅ 5. نجيبو host
            host = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    const ip = body.match(/([0-9]{1,3}\\.){3}[0-9]{1,3}/);
                    if (ip) return ip[0];
                    const host = body.match(/([a-zA-Z0-9\\.\\-]+\\.[a-z]{2,})/);
                    if (host) return host[0];
                    return null;
                }
            """)
            result["host"] = host
            log.info(f"🖥️ Host: {host}")

            # ✅ 6. نجيبو username/password
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
