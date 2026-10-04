"""
automation/sshs8.py
- يدخل ديراكت لصفحة فرنسا → يضغط Create Account → يستخرج البيانات
"""
import asyncio
import random
import string
import re
import os
from utils.logger import get_logger

log = get_logger("SSHS8")


FRANCE_URL = "https://sshs8.com/SSH-Websocket-config-France-free-servers"


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
        self.chat_id = None
        self.bot = None

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    async def _send_photo(self, page, caption: str):
        if not self.bot or not self.chat_id:
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
    # 1. فتح صفحة فرنسا
    # ═══════════════════════════════════════

    async def open_france_page(self) -> bool:
        log.info("🌐 فتح صفحة فرنسا")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(FRANCE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            await self._send_photo(page, "1️⃣ صفحة فرنسا")
            return True
        except Exception as e:
            log.error(f"❌ open_france_page: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # 2. Create Account — نضغطو بأي طريقة
    # ═══════════════════════════════════════

    async def create_account(self) -> dict:
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
            "country": "France",
            "host": None,
            "message": None,
        }

        try:
            # ✅ نحاولو نضغطو Create Account بكل الطرق
            clicked = False

            # 1. نجربو Playwright locator (button / a / input / span / div)
            for sel in [
                'button:has-text("Create Account")',
                'a:has-text("Create Account")',
                'input[value="Create Account"]',
                '[role="button"]:has-text("Create Account")',
                'span:has-text("Create Account")',
                'div:has-text("Create Account")',
            ]:
                try:
                    loc = page.locator(sel)
                    cnt = await loc.count()
                    log.info(f"🔍 {sel}: count={cnt}")
                    if cnt > 0:
                        # نجربو نضغطو أول واحد
                        for i in range(min(cnt, 3)):
                            el = loc.nth(i)
                            try:
                                if await el.is_visible():
                                    await el.scroll_into_view_if_needed()
                                    await page.wait_for_timeout(300)
                                    await el.click(timeout=5000)
                                    clicked = True
                                    log.info(f"✅ Clicked via {sel} #{i}")
                                    break
                            except Exception as e:
                                log.warning(f"⚠️ click {sel} #{i}: {e}")
                                continue
                        if clicked:
                            break
                except Exception as e:
                    log.warning(f"⚠️ locator {sel}: {e}")
                    continue

            # 2. إذا مازال، نجربو JS مباشر
            if not clicked:
                log.info("⚠️ نجربو JS للضغط على Create Account")
                js_clicked = await page.evaluate("""
                    () => {
                        const targets = ['create account', 'deploy'];
                        // ندورو على كل العناصر
                        for (const el of document.querySelectorAll('button, a, input, span, div')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            for (const tg of targets) {
                                if (t === tg) {
                                    try {
                                        el.scrollIntoView({block: 'center'});
                                        el.click();
                                        return t;
                                    } catch (e) {}
                                }
                            }
                        }
                        return null;
                    }
                """)
                if js_clicked:
                    clicked = True
                    log.info(f"✅ Clicked via JS: {js_clicked}")

            log.info(f"🎯 Create Account clicked: {clicked}")

            # ✅ نستناو باش تتحول الصفحة
            await page.wait_for_timeout(7000)
            await self._send_photo(page, "2️⃣ بعد Create Account")

            # ✅ نشوفو URL — إلا تبدل معناها دخلنا لصفحة جديدة
            new_url = page.url
            log.info(f"🔗 URL بعد Create: {new_url}")

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

            # ✅ نضغطو زر Generate/Submit إذا كان كاين
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

            await page.wait_for_timeout(10000)
            await self._send_photo(page, "3️⃣ بعد Submit")

            # ✅ نستخرجو البيانات
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
                result["message"] = (
                    f"ما لقيناش host.\n"
                    f"URL الحالي: {new_url}\n"
                    f"شوف الصور باش نعرفو المشكل."
                )
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
