"""
automation/sshs8.py
دخول sshs8.com → إغلاق الإعلانات → SSH WebSocket → اختيار دولة
+ تصوير كل خطوة
"""
import asyncio
import random
import string
import re
import os
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SSHS8")


def generate_username():
    return "u" + "".join(random.choices(string.digits, k=10))


def generate_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=8))


# ═══════════════════════════════════════════
# الدول المعروفة (fallback)
# ═══════════════════════════════════════════

KNOWN_COUNTRIES = [
    "بلجيكا 🇧🇪", "أمريكا 🇺🇸", "ألمانيا 🇩🇪", "فرنسا 🇫🇷",
    "هولندا 🇳🇱", "بريطانيا 🇬🇧", "كندا 🇨🇦", "سويسرا 🇨🇭",
    "السويد 🇸🇪", "النرويج 🇳🇴", "فنلندا 🇫🇮", "الدنمارك 🇩🇰",
    "النمسا 🇦🇹", "إيرلندا 🇮🇪", "إيطاليا 🇮🇹", "إسبانيا 🇪🇸",
    "بولندا 🇵🇱", "البرتغال 🇵🇹", "رومانيا 🇷🇴", "تركيا 🇹🇷",
    "اليابان 🇯🇵", "كوريا الجنوبية 🇰🇷", "سنغافورة 🇸🇬",
    "هونغ كونغ 🇭🇰", "أستراليا 🇦🇺", "الهند 🇮🇳",
    "الإمارات 🇦🇪", "السعودية 🇸🇦",
]


class SSHS8:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None

    async def _shot(self, page, caption: str = ""):
        """screenshot + send"""
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
    # Flag
    # ═══════════════════════════════════════

    def _get_flag(self, name: str) -> str:
        name_lower = name.lower()
        flags = {
            "belgium": "🇧🇪", "united states": "🇺🇸", "usa": "🇺🇸", "america": "🇺🇸",
            "germany": "🇩🇪", "france": "🇫🇷", "netherlands": "🇳🇱", "holland": "🇳🇱",
            "united kingdom": "🇬🇧", "uk": "🇬🇧", "england": "🇬🇧",
            "canada": "🇨🇦", "switzerland": "🇨🇭", "sweden": "🇸🇪", "norway": "🇳🇴",
            "finland": "🇫🇮", "denmark": "🇩🇰", "austria": "🇦🇹", "ireland": "🇮🇪",
            "italy": "🇮🇹", "spain": "🇪🇸", "poland": "🇵🇱", "portugal": "🇵🇹",
            "romania": "🇷🇴", "turkey": "🇹🇷", "japan": "🇯🇵",
            "south korea": "🇰🇷", "korea": "🇰🇷", "singapore": "🇸🇬",
            "hong kong": "🇭🇰", "australia": "🇦🇺", "india": "🇮🇳",
            "uae": "🇦🇪", "emirates": "🇦🇪", "saudi": "🇸🇦",
            "brazil": "🇧🇷", "mexico": "🇲🇽", "russia": "🇷🇺", "china": "🇨🇳",
        }
        for k, v in flags.items():
            if k in name_lower:
                return v
        return ""

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
                                if (t === kw) { try { el.click(); closed++; break; } catch (e) {} }
                            }
                        }
                        for (const el of document.querySelectorAll('[class*="close" i], [class*="popup" i], [class*="ad-" i]')) {
                            if (el.offsetParent === null) continue;
                            try { el.click(); closed++; } catch (e) {}
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
        log.info("🌐 فتح sshs8.com")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
            await self._shot(page, "1️⃣ sshs8.com")

            await self._close_ads(page)
            await page.wait_for_timeout(1500)
            await self._shot(page, "2️⃣ بعد إغلاق الإعلانات")

            # ✅ نروحو SSH WebSocket
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
            await self._shot(page, "3️⃣ صفحة SSH WebSocket")

            countries = await self._get_countries(page)
            log.info(f"🌍 الدول: {len(countries)}")

            if countries and len(countries) > 3:
                final = []
                for c in countries:
                    name = c.strip()
                    flag = self._get_flag(name)
                    final.append(f"{name} {flag}" if flag else name)
                return final

            return KNOWN_COUNTRIES

        except Exception as e:
            log.error(f"❌ open_ssh_websocket: {e}", exc_info=True)
            return KNOWN_COUNTRIES

    # ═══════════════════════════════════════
    # 2. جلب الدول
    # ═══════════════════════════════════════

    async def _get_countries(self, page) -> list:
        try:
            countries = await page.evaluate("""
                () => {
                    const out = [];
                    for (const sel of document.querySelectorAll('select')) {
                        for (const opt of sel.querySelectorAll('option')) {
                            const t = (opt.innerText || opt.textContent || '').trim();
                            if (t && t.length > 1 && t.length < 80 &&
                                !t.toLowerCase().includes('select') &&
                                !t.toLowerCase().includes('choose') &&
                                !t.toLowerCase().includes('---') &&
                                !t.toLowerCase().includes('option')) {
                                out.push(t);
                            }
                        }
                    }
                    if (out.length === 0) {
                        for (const el of document.querySelectorAll('[role="listbox"], [class*="dropdown" i], [class*="select" i]')) {
                            for (const opt of el.querySelectorAll('[role="option"], li, a, button')) {
                                const t = (opt.innerText || '').trim();
                                if (t && t.length > 1 && t.length < 80 &&
                                    !t.toLowerCase().includes('select') &&
                                    !t.toLowerCase().includes('choose') &&
                                    !t.toLowerCase().includes('back') &&
                                    !t.toLowerCase().includes('close')) {
                                    out.push(t);
                                }
                            }
                        }
                    }
                    return [...new Set(out)];
                }
            """)
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
            await self._shot(page, "4️⃣ قبل اختيار الدولة")

            # ✅ 1. اختيار الدولة
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
            await self._shot(page, f"5️⃣ بعد اختيار {country_name}")

            # ✅ 2. username
            for sel in [
                'input[name*="user" i]', 'input[id*="user" i]',
                'input[placeholder*="user" i]', 'input[type="text"]',
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
                'input[name*="pass" i]', 'input[id*="pass" i]',
                'input[placeholder*="pass" i]', 'input[type="password"]',
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
            await self._shot(page, "6️⃣ بعد تعبئة الحقول")

            # ✅ 4. Create
            submitted = False
            for sel in [
                'button:has-text("Create")', 'button:has-text("Submit")',
                'button:has-text("Create Account")', 'button:has-text("Generate")',
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

            # ✅ 5. انتظار أطول + إغلاق أي ads
            await page.wait_for_timeout(6000)
            await self._close_ads(page)
            await page.wait_for_timeout(2000)
            await self._shot(page, "7️⃣ بعد Create")

            # ✅ 6. انتظار ظهور معلومات الحساب (host)
            host = None
            for attempt in range(15):  # 15 محاولة × 2s = 30s
                host = await page.evaluate("""
                    () => {
                        // 1. IPv4
                        const body = document.body.innerText || '';
                        const ipv4 = body.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/);
                        if (ipv4 && ipv4[0] !== '0.0.0.0' && ipv4[0] !== '127.0.0.1') {
                            return ipv4[0];
                        }

                        // 2. hostname
                        const hostname = body.match(/\\b([a-z0-9][a-z0-9\\-]{1,63}\\.)+[a-z]{2,}\\b/i);
                        if (hostname && !hostname[0].includes('sshs8') && !hostname[0].includes('google')) {
                            return hostname[0];
                        }

                        // 3. من input/value
                        for (const el of document.querySelectorAll('input, textarea, code, pre, span, div, td')) {
                            const v = (el.value || el.innerText || '').trim();
                            const m = v.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/);
                            if (m) return m[0];
                        }

                        return null;
                    }
                """)

                if host:
                    log.info(f"✅ Host بعد {attempt * 2}s: {host}")
                    break

                await page.wait_for_timeout(2000)

            result["host"] = host
            log.info(f"🖥️ Host final: {host}")

            # ✅ 7. نجيبو username/password من الصفحة
            page_data = await page.evaluate("""
                () => {
                    const out = { user: null, pass: null, all_text: '' };
                    out.all_text = document.body.innerText || '';

                    // ندورو على u + أرقام
                    const userMatch = out.all_text.match(/\\bu[0-9]{6,12}\\b/);
                    if (userMatch) out.user = userMatch[0];

                    // ندورو على password
                    const passMatch = out.all_text.match(/(?:password|pass)[\\s:]*([A-Za-z0-9]{6,16})/i);
                    if (passMatch) out.pass = passMatch[1];

                    return out;
                }
            """)

            if page_data.get("user"):
                result["username"] = page_data["user"]
            if page_data.get("pass"):
                result["password"] = page_data["pass"]

            log.info(f"👤 User final: {result['username']}")
            log.info(f"🔑 Pass final: {result['password']}")
            log.info(f"📄 All text preview: {page_data.get('all_text', '')[:800]}")

            # ✅ 8. إذا مازال host None → فشل
            if not host:
                log.warning("❌ مالقيناش host — نرجعو فشل")
                result["success"] = False
                result["message"] = "ما قدرناش نلقاو host. تأكد أن الحساب تبدا بنجاح."
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
