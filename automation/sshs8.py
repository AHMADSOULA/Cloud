"""
automation/sshs8.py
- sshs8.com → SSH Websocket → Servers list → Create Account
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
        self.chat_id = None
        self.bot = None

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    async def _send_photo(self, page, caption: str):
        if not self.bot or not self.chat_id:
            log.warning("⚠️ bot/chat_id ماشي محددين")
            return
        path = f"/tmp/sshs8_{int(asyncio.get_event_loop().time()*1000)}.png"
        try:
            await page.screenshot(path=path, full_page=True, timeout=15000)
            with open(path, "rb") as photo:
                try:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=photo,
                        caption=f"📸 {caption}"[:1000],
                    )
                    log.info(f"📸 Sent: {caption}")
                except Exception as e:
                    log.warning(f"⚠️ send_photo: {e}")
        except Exception as e:
            log.warning(f"⚠️ screenshot: {e}")
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

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
            await self._send_photo(page, "1️⃣ الصفحة الرئيسية")

            # ✅ Menu
            for sel in [
                'button:has-text("Menu")',
                'a:has-text("Menu")',
                '[aria-label*="Menu" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        log.info(f"✅ Menu opened via {sel}")
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(2000)
            await self._send_photo(page, "2️⃣ بعد فتح Menu")

            # ✅ SSH Websocket
            ssh_clicked = False
            for sel in [
                'a:has-text("SSH Websocket")',
                'li:has-text("SSH Websocket")',
                'span:has-text("SSH Websocket")',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        ssh_clicked = True
                        log.info(f"✅ SSH Websocket clicked via {sel}")
                        break
                except Exception:
                    continue

            if not ssh_clicked:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('a, li, span, button, div')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim();
                            if (t === 'SSH Websocket') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                    }
                """)

            await page.wait_for_timeout(6000)
            await self._send_photo(page, "3️⃣ صفحة SSH Websocket")

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
                    const keywords = ['Europe and West Asia', 'East Asia', 'North America', 'Africa'];
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, h5, p, div, span, a')) {
                        const t = (el.innerText || '').trim();
                        for (const kw of keywords) {
                            if (t === kw && !out.includes(t)) out.push(t);
                        }
                    }
                    return out;
                }
            """)
            return continents or []
        except Exception as e:
            log.error(f"❌ _get_continents: {e}")
            return []

    # ═══════════════════════════════════════
    # 3. اختيار قارة — نستعملو Playwright Locator
    # ═══════════════════════════════════════

    async def select_continent(self, continent: str) -> list:
        page = self.page
        log.info(f"🌍 اختيار القارة: {continent}")

        try:
            # ✅ 1. ندورو على كل الأزرار "Servers list"
            servers_btns = page.locator('button:has-text("Servers list"), a:has-text("Servers list")')
            total = await servers_btns.count()
            log.info(f"🔍 لقينا {total} زر 'Servers list'")

            target_btn = None
            for i in range(total):
                btn = servers_btns.nth(i)
                try:
                    # ✅ نجيبو الـ parent card ونتحققو من النص
                    card_text = await btn.evaluate("""
                        (el) => {
                            let p = el.closest('div, section, article');
                            for (let i = 0; i < 5 && p; i++) {
                                const t = p.innerText || '';
                                if (t.length > 50 && t.length < 2000) return t;
                                p = p.parentElement ? p.parentElement.closest('div, section, article') : null;
                            }
                            return '';
                        }
                    """)
                    log.info(f"🔍 Card {i}: {card_text[:200]}")

                    if continent.lower() in card_text.lower():
                        target_btn = btn
                        log.info(f"✅ لقينا الزر ديال {continent} فـ card {i}")
                        break
                except Exception as e:
                    log.warning(f"⚠️ card {i}: {e}")
                    continue

            # ✅ 2. إذا مالقيناش، نضغطو على أول زر
            if not target_btn and total > 0:
                target_btn = servers_btns.first
                log.info("⚠️ مالقيناش القارة — نضغطو على أول زر")

            if target_btn:
                await target_btn.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await target_btn.click()
                log.info("✅ Servers list clicked")
            else:
                log.error("❌ مالقيناش أي زر Servers list")

            await page.wait_for_timeout(6000)
            await self._send_photo(page, f"4️⃣ بعد اختيار {continent}")

            countries = await self._get_countries_from_page(page)
            log.info(f"🌍 الدول: {countries}")
            return countries

        except Exception as e:
            log.error(f"❌ select_continent: {e}", exc_info=True)
            return []

    # ═══════════════════════════════════════
    # 4. استخراج الدول
    # ═══════════════════════════════════════

    async def _get_countries_from_page(self, page) -> list:
        try:
            countries = await page.evaluate("""
                () => {
                    const out = [];
                    // ندورو على كل الأزرار "Create Account"
                    for (const btn of document.querySelectorAll('a, button, span, div')) {
                        const t = (btn.innerText || '').trim().toLowerCase();
                        if (t === 'create account') {
                            let card = btn.closest('div, section, article');
                            if (!card) continue;
                            const cardText = card.innerText || '';
                            if (cardText.length > 2000) continue;
                            
                            const headings = card.querySelectorAll('h1, h2, h3, h4, h5, span, strong, b, p, div');
                            for (const h of headings) {
                                const ht = (h.innerText || '').trim();
                                if (ht.length >= 3 && ht.length <= 50 &&
                                    /^[A-Z][a-zA-Z\\s\\-'\\.]+$/.test(ht) &&
                                    !ht.toLowerCase().includes('create') &&
                                    !ht.toLowerCase().includes('account') &&
                                    !ht.toLowerCase().includes('ssh') &&
                                    !ht.toLowerCase().includes('server') &&
                                    !ht.toLowerCase().includes('location') &&
                                    !ht.toLowerCase().includes('free') &&
                                    !ht.toLowerCase().includes('city') &&
                                    !ht.toLowerCase().includes('support') &&
                                    !ht.toLowerCase().includes('torrent') &&
                                    ht.split(' ').length <= 4) {
                                    if (!out.includes(ht)) out.push(ht);
                                    break;
                                }
                            }
                        }
                    }
                    return out;
                }
            """)
            return countries or []
        except Exception as e:
            log.error(f"❌ _get_countries_from_page: {e}")
            return []

    # ═══════════════════════════════════════
    # 5. اختيار دولة — نضغطو "Create Account" ديال card
    # ═══════════════════════════════════════

    async def select_country(self, country: str) -> bool:
        page = self.page
        log.info(f"🌍 اختيار الدولة: {country}")

        try:
            # ✅ نستعملو Playwright locator
            create_btns = page.locator('button:has-text("Create Account"), a:has-text("Create Account")')
            total = await create_btns.count()
            log.info(f"🔍 لقينا {total} زر 'Create Account'")

            target_btn = None
            for i in range(total):
                btn = create_btns.nth(i)
                try:
                    card_text = await btn.evaluate("""
                        (el) => {
                            let p = el.closest('div, section, article');
                            for (let i = 0; i < 5 && p; i++) {
                                const t = p.innerText || '';
                                if (t.length > 50 && t.length < 2000) return t;
                                p = p.parentElement ? p.parentElement.closest('div, section, article') : null;
                            }
                            return '';
                        }
                    """)
                    if country.lower() in card_text.lower():
                        target_btn = btn
                        log.info(f"✅ لقينا الزر ديال {country} فـ card {i}")
                        break
                except Exception as e:
                    log.warning(f"⚠️ btn {i}: {e}")
                    continue

            if target_btn:
                await target_btn.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                await target_btn.click()
                log.info("✅ Create Account clicked")
            else:
                log.error(f"❌ مالقيناش زر Create Account لـ {country}")

            await page.wait_for_timeout(5000)
            await self._send_photo(page, f"5️⃣ بعد اختيار {country}")
            return target_btn is not None

        except Exception as e:
            log.error(f"❌ select_country: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # 6. Create Account (الصفحة اللي فيها الفورم)
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
            await self._send_photo(page, "6️⃣ صفحة الفورم")

            # ✅ نعبيو الحقول
            for sel in [
                'input[name*="user" i]', 'input[id*="user" i]',
                'input[placeholder*="user" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await el.fill(username)
                        log.info(f"✅ username filled via {sel}")
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
                        log.info(f"✅ password filled via {sel}")
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(2000)

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

            await page.wait_for_timeout(8000)
            await self._send_photo(page, "7️⃣ بعد Submit")

            # ✅ استخراج
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

            log.info(f"🔍 host={info.get('host')} user={info.get('user')} pass={info.get('pass')}")
            log.info(f"📄 Preview: {info.get('all_text', '')[:500]}")

            if info.get("host"):
                result["host"] = info["host"]
            if info.get("user"):
                result["username"] = info["user"]
            if info.get("pass"):
                result["password"] = info["pass"]

            if not result["host"]:
                result["success"] = False
                result["message"] = "ما لقيناش host — شوف آخر screenshot."
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            await self._send_photo(page, f"❌ خطأ: {str(e)[:80]}")

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
