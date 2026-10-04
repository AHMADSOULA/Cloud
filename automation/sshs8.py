"""
automation/sshs8.py
دخول sshs8.com → إغلاق الإعلانات → SSH WebSocket → اختيار دولة
+ بلا تصوير
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


# ═══════════════════════════════════════════
# الدول المعروفة (إنترنت سريع)
# ═══════════════════════════════════════════

KNOWN_COUNTRIES = [
    "Belgium 🇧🇪",
    "United States 🇺🇸",
    "Germany 🇩🇪",
    "France 🇫🇷",
    "Netherlands 🇳🇱",
    "United Kingdom 🇬🇧",
    "Canada 🇨🇦",
    "Switzerland 🇨🇭",
    "Sweden 🇸🇪",
    "Norway 🇳🇴",
    "Finland 🇫🇮",
    "Denmark 🇩🇰",
    "Austria 🇦🇹",
    "Ireland 🇮🇪",
    "Italy 🇮🇹",
    "Spain 🇪🇸",
    "Poland 🇵🇱",
    "Portugal 🇵🇹",
    "Romania 🇷🇴",
    "Turkey 🇹🇷",
    "Japan 🇯🇵",
    "South Korea 🇰🇷",
    "Singapore 🇸🇬",
    "Hong Kong 🇭🇰",
    "Australia 🇦🇺",
    "India 🇮🇳",
    "UAE 🇦🇪",
    "Saudi Arabia 🇸🇦",
]


class SSHS8:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None

    async def _shot(self, page, caption: str = ""):
        """معطّلة"""
        return

    # ═══════════════════════════════════════
    # إغلاق الإعلانات
    # ═══════════════════════════════════════

    async def _close_ads(self, page):
        log.info("🚫 نحاولو نغلقو الإعلانات...")
        closed_count = 0
        for _ in range(3):
            try:
                clicked = await page.evaluate("""
                    () => {
                        let closed = 0;
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
                        for (const el of document.querySelectorAll('[class*="close" i], [class*="popup" i], [class*="ad-" i], [id*="close" i]')) {
                            if (el.offsetParent === null) continue;
                            try { el.click(); closed++; } catch (e) {}
                        }
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

        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
        except Exception:
            pass

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
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            await self._close_ads(page)
            await page.wait_for_timeout(1500)

            # ✅ نروحو مباشرة لصفحة SSH WebSocket
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
                await page.goto(ssh_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(4000)
                await self._close_ads(page)
            else:
                for sel in [
                    'a[href*="ssh-websocket"]',
                    'a[href*="sshwebsocket"]',
                    'a[href*="websocket"]',
                    'a:has-text("SSH WebSocket")',
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() > 0 and await el.is_visible():
                            await el.click()
                            break
                    except Exception:
                        continue

                await page.wait_for_timeout(4000)
                await self._close_ads(page)

            await page.wait_for_timeout(2000)

            # ✅ نرجعو الدول المعروفة فقط
            # (نشوفو واش الدول موجودة في الصفحة)
            available = await self._filter_available(page)
            log.info(f"🌍 الدول المتوفرة: {len(available)}")

            return available if available else KNOWN_COUNTRIES

        except Exception as e:
            log.error(f"❌ open_ssh_websocket: {e}", exc_info=True)
            return KNOWN_COUNTRIES

    # ═══════════════════════════════════════
    # 2. فلترة الدول المتوفرة
    # ═══════════════════════════════════════

    async def _filter_available(self, page) -> list:
        """يشوف واش الدول موجودة في الصفحة"""
        try:
            page_text = await page.evaluate("""
                () => {
                    return (document.body.innerText || '').toLowerCase();
                }
            """)

            available = []
            for c in KNOWN_COUNTRIES:
                # ناخدو الاسم فقط (بلا flag)
                name = c.split(" ")[0].lower()
                if name in page_text:
                    available.append(c)

            return available
        except Exception:
            return []

    # ═══════════════════════════════════════
    # 3. إنشاء حساب
    # ═══════════════════════════════════════

    async def create_account(self, country: str) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        # نحيّدو الـ flag
        country_name = country.split(" ")[0]

        username = generate_username()
        password = generate_password()

        log.info(f"🌍 {country_name}")
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
            await self._close_ads(page)
            await page.wait_for_timeout(1000)

            # ✅ 1. نختارو الدولة
            clicked_country = await page.evaluate(f"""
                () => {{
                    const target = {country_name!r}.toLowerCase();
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
                    await page.select_option('select', label=country_name)
                except Exception:
                    pass

            await page.wait_for_timeout(2000)

            # ✅ 2. username
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

            # ✅ 4. Create
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

            # ✅ 5. host
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

            # ✅ 6. username/password من الصفحة
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

        return result

    async def close(self):
        try:
            await self.page.close()
        except Exception:
            pass
