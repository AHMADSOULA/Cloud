"""
automation/sshs8.py
- vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113
- يعبي Password → Create → يقرا المعلومات من الجدول
"""
import asyncio
import random
import string
import re
import os
from utils.logger import get_logger

log = get_logger("SSHS8")


FRANCE_CREATE_URL = "https://vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113"


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
    # 1. فتح صفحة Create
    # ═══════════════════════════════════════

    async def open_france_page(self) -> bool:
        log.info(f"🌐 فتح: {FRANCE_CREATE_URL}")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(FRANCE_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            await self._send_photo(page, "1️⃣ صفحة Create")
            return True
        except Exception as e:
            log.error(f"❌ open_france_page: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # 2. تعبئة Password + Create
    # ═══════════════════════════════════════

    async def create_account(self) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password_input_value = generate_password()

        result = {
            "success": False,
            "username": None,
            "password": password_input_value,
            "country": "France",
            "host": None,
            "message": None,
        }

        try:
            # ✅ نعبيو Password
            pass_filled = False
            for sel in [
                'input[type="password"]',
                'input[name*="pass" i]',
                'input[id*="pass" i]',
                'input[placeholder*="pass" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        await el.fill("")
                        await page.wait_for_timeout(200)
                        await el.fill(password_input_value)
                        pass_filled = True
                        log.info(f"✅ password filled: {password_input_value}")
                        break
                except Exception:
                    continue

            if not pass_filled:
                log.warning("⚠️ مالقيناش password input")

            await page.wait_for_timeout(1000)
            await self._send_photo(page, "2️⃣ بعد تعبئة Password")

            # ✅ نضغطو Create an account
            clicked = False
            for sel in [
                'button:has-text("Create an account")',
                'input[value="Create an account"]',
                'a:has-text("Create an account")',
                'button:has-text("Create account")',
                'button:has-text("Create")',
                'input[type="submit"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(300)
                        await el.click(timeout=5000)
                        clicked = True
                        log.info(f"✅ Clicked via {sel}")
                        break
                except Exception:
                    continue

            if not clicked:
                c = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, input[type="submit"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            if (t.includes('create an account') || t.includes('create account')) {
                                try { el.scrollIntoView({block: 'center'}); el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if c:
                    clicked = True
                    log.info(f"✅ Clicked via JS: {c}")

            log.info(f"🎯 Create clicked: {clicked}")

            # ✅ نستناو ظهور الجدول (Account successfully created)
            log.info("⏳ نستناو الحساب...")

            # نستناو ظهور "Account successfully created" أو جدول فيه IPv4
            host = None
            for attempt in range(25):  # 25 × 2s = 50s
                await page.wait_for_timeout(2000)

                found = await page.evaluate("""
                    () => {
                        const out = { host: null, user: null, pass: null, all_text: '' };
                        out.all_text = document.body.innerText || '';

                        // ✅ الطريقة 1: ندورو على الصفوف اللي فيها label: IPv4, Username, Password
                        // نجيبو كل الـ labels والقيم اللي بعدهم

                        // طريقة أ: كل الـ inputs مع labels قريبين
                        const allInputs = document.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
                        for (const inp of allInputs) {
                            const val = (inp.value || '').trim();
                            if (!val) continue;

                            // نجيبو النص القريب (label)
                            let labelText = '';
                            // parent
                            let p = inp.parentElement;
                            for (let i = 0; i < 4 && p; i++) {
                                const t = (p.innerText || '').toLowerCase();
                                if (t.includes('ipv4') || t.includes('username') ||
                                    t.includes('password') || t.includes('domain') ||
                                    t.includes('host')) {
                                    labelText = t;
                                    break;
                                }
                                p = p.parentElement;
                            }

                            if (labelText.includes('ipv4') && !out.host) {
                                const m = val.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/);
                                if (m) out.host = m[0];
                            }
                            if ((labelText.includes('username') || labelText.includes('user name')) && !out.user) {
                                out.user = val;
                            }
                            if (labelText.includes('password') && !out.pass) {
                                out.pass = val;
                            }
                        }

                        // طريقة ب: إلا مالقيناش، ندورو بالـ regex على النص
                        if (!out.host) {
                            // IPv4 من النص — نستثنيو 192.168, 10., 127., 0.0
                            const ipv4All = out.all_text.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/g) || [];
                            for (const ip of ipv4All) {
                                const parts = ip.split('.').map(Number);
                                if (parts.every(p => p >= 0 && p <= 255) &&
                                    !ip.startsWith('192.168.') &&
                                    !ip.startsWith('10.') &&
                                    !ip.startsWith('172.16.') &&
                                    ip !== '0.0.0.0' && ip !== '127.0.0.1') {
                                    out.host = ip;
                                    break;
                                }
                            }
                        }

                        // User من الصفحة (regex عام)
                        if (!out.user) {
                            const m = out.all_text.match(/(?:username|user)[\\s:]*([a-zA-Z0-9_\\-]{4,20})/i);
                            if (m) out.user = m[1];
                        }
                        // Pass من الصفحة
                        if (!out.pass) {
                            const m = out.all_text.match(/(?:password|pass)[\\s:]*([A-Za-z0-9]{6,16})/i);
                            if (m) out.pass = m[1];
                        }

                        return out;
                    }
                """)

                if found.get("host") and found.get("user") and found.get("pass"):
                    host = found["host"]
                    result["username"] = found["user"]
                    result["password"] = found["pass"]
                    log.info(f"✅ معلومات كاملة بعد {(attempt+1)*2}s")
                    break
                elif found.get("host") and not host:
                    host = found["host"]
                    if found.get("user"):
                        result["username"] = found["user"]
                    if found.get("pass"):
                        result["password"] = found["pass"]

            await self._send_photo(page, "3️⃣ بعد Create")

            log.info(f"🖥️ Host: {result.get('host')}")
            log.info(f"👤 User: {result.get('username')}")
            log.info(f"🔑 Pass: {result.get('password')}")

            if not result.get("host"):
                result["success"] = False
                result["message"] = "ما لقيناش host — شوف آخر screenshot."
                return result

            if not result.get("username"):
                result["username"] = "unknown"

            if not result.get("password"):
                result["password"] = password_input_value

            result["host"] = result["host"] or host
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
