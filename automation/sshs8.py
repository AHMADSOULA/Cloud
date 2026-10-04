"""
automation/sshs8.py
- sshs8.com → Menu → SSH Websocket → قارة → دولة → Create Account
- تصوير فكل خطوة للتشخيص
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
        self.sender = sender  # message object باش نقدرو نصورو
        self.user_tag = user_tag or "@user"
        self.page = None
        self.chat_id = None  # ✅ نحتاجوه للتصوير

    def set_chat(self, chat_id):
        """نحددو الـ chat_id باش نقدرو نبعثو الصور"""
        self.chat_id = chat_id

    async def _send_photo(self, page, caption: str):
        """نصورو ونبعثو مباشرة عبر البوت"""
        if not self.chat_id:
            log.warning("⚠️ chat_id ماشي محدد — ما نقدروش نبعثو صورة")
            return
        try:
            path = f"/tmp/sshs8_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=True, timeout=15000)

            # نبعثو عبر الـ context مباشرة (bot)
            with open(path, "rb") as photo:
                try:
                    from telegram import Bot
                    # نحاولو نستعملو self.sender إلا كان متوفر
                    if self.sender and hasattr(self.sender, "reply_photo"):
                        await self.sender.reply_photo(photo=photo, caption=f"📸 {caption}"[:1000])
                    else:
                        # نستعملو الـ chat_id مباشرة
                        await self._send_photo_direct(photo, caption, path)
                except Exception as e:
                    log.warning(f"⚠️ reply_photo فشل: {e}")

            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _send_photo: {e}")

    async def _send_photo_direct(self, photo, caption, path):
        """نبعثو الصورة عبر الـ bot API مباشرة"""
        try:
            # نستعملو self.context.bot (ما كاينش هنا) — بدل نستعملو الـ chat_id
            # الطريقة: نخزنو ref للبوت فـ self
            if hasattr(self, "bot") and self.bot:
                with open(path, "rb") as p:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=p,
                        caption=f"📸 {caption}"[:1000],
                    )
        except Exception as e:
            log.warning(f"⚠️ _send_photo_direct: {e}")

    # ═══════════════════════════════════════
    # 1. فتح الموقع
    # ═══════════════════════════════════════

    async def open_ssh_websocket(self) -> list:
        log.info("🌐 فتح sshs8.com")
        self.page = await self.context.new_page()
        page = self.page

        try:
            # ✅ step 1: الصفحة الرئيسية
            await page.goto("https://sshs8.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
            await self._send_photo(page, "1️⃣ الصفحة الرئيسية")

            # ✅ step 2: نفتحو Menu
            menu_opened = False
            for sel in [
                'button:has-text("Menu")',
                'a:has-text("Menu")',
                '[aria-label*="Menu" i]',
                '[class*="menu" i] button',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        menu_opened = True
                        log.info(f"✅ Menu opened via {sel}")
                        break
                except Exception:
                    continue

            if not menu_opened:
                # نجربو بالـ JS
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, span, div')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'menu' || t.includes('☰')) {
                                try { el.click(); return; } catch (e) {}
                            }
                        }
                    }
                """)

            await page.wait_for_timeout(2000)
            await self._send_photo(page, "2️⃣ بعد فتح Menu")

            # ✅ step 3: نضغطو SSH Websocket
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
                        log.info(f"✅ SSH Websocket clicked via {sel}")
                        break
                except Exception:
                    continue

            if not ssh_clicked:
                # نجربو بـ JS
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('a, li, span, button, div')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim();
                            if (t === 'SSH Websocket') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if clicked:
                    ssh_clicked = True

            await page.wait_for_timeout(5000)
            await self._send_photo(page, "3️⃣ بعد SSH Websocket")

            # ✅ نستخرجو القارات
            continents = await self._get_continents(page)
            log.info(f"🌍 القارات اللي لقينا: {continents}")

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
            # نضغطو على أي عنصر فيه كلمة قارة ونحاولو نلقاوهم
            continents = await page.evaluate("""
                () => {
                    const out = [];
                    const keywords = ['Europe and West Asia', 'East Asia', 'North America', 'Africa'];
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, h5, p, div, span, a, button')) {
                        const t = (el.innerText || '').trim();
                        for (const kw of keywords) {
                            if (t === kw) {
                                out.push(t);
                            }
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
                    // نلقاو كل "Create Account" و "Server list" ثم نستخرجو اسم الدولة من الأب
                    for (const el of document.querySelectorAll('a, button, span, div')) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === 'server list' || t.includes('server list')) {
                            const parent = el.closest('div, section, article');
                            if (!parent) continue;
                            // اسم الدولة كيكون فـ عنصر قبل الزر
                            const candidates = parent.querySelectorAll('h1, h2, h3, h4, h5, span, p, div');
                            for (const c of candidates) {
                                const txt = (c.innerText || '').trim();
                                // اسم دولة: كلمة أو كلمتين بحروف كبيرة
                                if (/^[A-Z][a-zA-Z\\s\\-]{2,40}$/.test(txt) &&
                                    txt.length > 3 && txt.length < 40 &&
                                    !txt.toLowerCase().includes('server') &&
                                    !txt.toLowerCase().includes('list') &&
                                    !txt.toLowerCase().includes('create') &&
                                    !txt.toLowerCase().includes('account') &&
                                    !txt.toLowerCase().includes('ssh') &&
                                    !txt.toLowerCase().includes('location')) {
                                    out.push(txt);
                                    break;
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
            # ✅ نضغطو على القارة
            clicked = await page.evaluate(f"""
                () => {{
                    const target = {continent!r}.toLowerCase();
                    // نلقاو أعمق عنصر فيه النص
                    let best = null;
                    let bestLen = 99999;
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, h5, p, div, span, a, button')) {{
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === target || t.includes(target)) {{
                            if (t.length < bestLen) {{
                                best = el;
                                bestLen = t.length;
                            }}
                        }}
                    }}
                    if (best) {{
                        try {{ best.click(); return 'clicked'; }} catch (e) {{}}
                    }}
                    return null;
                }}
            """)
            log.info(f"🔘 Click result: {clicked}")

            await page.wait_for_timeout(5000)
            await self._send_photo(page, f"4️⃣ بعد اختيار {continent}")

            # ✅ نستخرجو الدول
            countries = await self._get_countries_from_page(page)
            log.info(f"🌍 الدول اللي لقينا فـ {continent}: {countries}")

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
                    // نلقاو زر "Server list" قريب من اسم الدولة
                    for (const el of document.querySelectorAll('a, button, span, div')) {{
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('server list')) {{
                            const parent = el.closest('div, section, article');
                            if (parent && parent.innerText.toLowerCase().includes(target)) {{
                                try {{ el.click(); return 'server_list'; }} catch (e) {{}}
                            }}
                        }}
                    }}
                    // نجربو نضغطو على اسم الدولة مباشرة
                    for (const el of document.querySelectorAll('h1, h2, h3, h4, a, button, div, span')) {{
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t === target) {{
                            try {{ el.click(); return 'country'; }} catch (e) {{}}
                        }}
                    }}
                    return null;
                }}
            """)
            log.info(f"🔘 Select country result: {clicked}")

            await page.wait_for_timeout(5000)
            await self._send_photo(page, f"5️⃣ بعد اختيار {country}")

            return clicked is not None

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
            # ✅ step 6: قبل Create
            await self._send_photo(page, "6️⃣ قبل Create Account")

            # ✅ نضغطو Create Account
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
                        log.info(f"✅ {sel} clicked")
                        break
                except Exception:
                    continue

            if not clicked:
                c = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('create account') || t === 'create') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if c:
                    clicked = True

            await page.wait_for_timeout(4000)
            await self._send_photo(page, "7️⃣ بعد Create Account")

            # ✅ نعبيو الحقول إذا ظهرو
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
            except Exception as e:
                log.warning(f"⚠️ inputs: {e}")

            await page.wait_for_timeout(2000)
            await self._send_photo(page, "8️⃣ بعد تعبئة الحقول")

            # ✅ نضغطو زر Submit/Generate إذا كان كاين
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

            await page.wait_for_timeout(7000)
            await self._send_photo(page, "9️⃣ بعد Submit — الصفحة النهائية")

            # ✅ نستخرجو المعلومات
            info = await page.evaluate("""
                () => {
                    const body = document.body.innerText || '';
                    const out = { host: null, user: null, pass: null, all_text: '' };
                    out.all_text = body;

                    // IPv4
                    const ipv4 = body.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/g) || [];
                    for (const ip of ipv4) {
                        const parts = ip.split('.').map(Number);
                        if (parts.every(p => p >= 0 && p <= 255) &&
                            ip !== '0.0.0.0' && ip !== '127.0.0.1') {
                            out.host = ip;
                            break;
                        }
                    }

                    // hostname
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

                    // User
                    const user = body.match(/\\bu[0-9]{6,12}\\b/);
                    if (user) out.user = user[0];

                    // Pass
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
                log.warning("❌ مالقيناش host")
                result["success"] = False
                result["message"] = "ما لقيناش host — شوف الـ screenshot الأخير."
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
