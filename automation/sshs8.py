"""
automation/sshs8.py
- vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113
- يعبي Password → Create an account → يستخرج Host/User/Pass
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
    # 1. فتح صفحة Create ديراكت
    # ═══════════════════════════════════════

    async def open_france_page(self) -> bool:
        log.info(f"🌐 فتح: {FRANCE_CREATE_URL}")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(FRANCE_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            await self._send_photo(page, "1️⃣ صفحة Create Account")
            return True
        except Exception as e:
            log.error(f"❌ open_france_page: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════
    # 2. تعبئة Password + Create an account
    # ═══════════════════════════════════════

    async def create_account(self) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password = generate_password()
        username = None

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
            # ✅ 1. نجيبو الـ Username اللي معبّي مسبقاً
            try:
                username_input = page.locator(
                    'input[name*="user" i], input[id*="user" i], '
                    'input[placeholder*="user" i]'
                ).first
                if await username_input.count() > 0:
                    existing = await username_input.input_value()
                    if existing:
                        username = existing.strip()
                        log.info(f"👤 Username موجود: {username}")
            except Exception as e:
                log.warning(f"⚠️ username input: {e}")

            if not username:
                # نولّدو واحد
                username = "u" + "".join(random.choices(string.digits, k=10))
                try:
                    u_inp = page.locator(
                        'input[name*="user" i], input[id*="user" i], '
                        'input[placeholder*="user" i]'
                    ).first
                    if await u_inp.count() > 0:
                        await u_inp.click()
                        await u_inp.fill(username)
                        log.info(f"✅ username filled: {username}")
                except Exception as e:
                    log.warning(f"⚠️ fill username: {e}")

            result["username"] = username

            # ✅ 2. نعبيو الـ Password
            pass_input = None
            for sel in [
                'input[name*="pass" i]', 'input[id*="pass" i]',
                'input[placeholder*="pass" i]', 'input[type="password"]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        pass_input = el
                        break
                except Exception:
                    continue

            if pass_input:
                await pass_input.click()
                await pass_input.fill("")
                await page.wait_for_timeout(200)
                await pass_input.fill(password)
                log.info(f"✅ password filled")
            else:
                log.warning("⚠️ مالقيناش password input")

            await page.wait_for_timeout(1000)
            await self._send_photo(page, "2️⃣ بعد تعبئة Password")

            # ✅ 3. نضغطو Create an account
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
                except Exception as e:
                    log.warning(f"⚠️ {sel}: {e}")
                    continue

            if not clicked:
                # JS fallback
                c = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, input[type="submit"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            if (t.includes('create an account') || t.includes('create account')) {
                                try {
                                    el.scrollIntoView({block: 'center'});
                                    el.click();
                                    return t;
                                } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if c:
                    clicked = True
                    log.info(f"✅ Clicked via JS: {c}")

            log.info(f"🎯 Create clicked: {clicked}")

            # ✅ 4. نستناو حتى يظهر الحساب (Loading → Do not refresh)
            log.info("⏳ نستناو الحساب...")

            host = None
            for attempt in range(20):  # 20 × 2s = 40s
                await page.wait_for_timeout(2000)

                # نجيبو host
                found = await page.evaluate("""
                    () => {
                        const body = document.body.innerText || '';
                        const out = { host: null, user: null, pass: null };

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
                        const u = body.match(/\\bu[0-9]{6,12}\\b/);
                        if (u) out.user = u[0];

                        // Pass
                        const p = body.match(/(?:password|pass)\\s*[:\\-]\\s*([A-Za-z0-9]{6,16})/i);
                        if (p) out.pass = p[1];

                        return out;
                    }
                """)

                if found.get("host"):
                    host = found["host"]
                    log.info(f"✅ Host بعد {(attempt+1)*2}s: {host}")
                    if found.get("user"):
                        result["username"] = found["user"]
                    if found.get("pass"):
                        result["password"] = found["pass"]
                    break

            await self._send_photo(page, "3️⃣ بعد Create")

            log.info(f"🖥️ Host final: {host}")
            log.info(f"👤 User: {result['username']}")
            log.info(f"🔑 Pass: {result['password']}")

            if not host:
                result["success"] = False
                result["message"] = "ما لقيناش host بعد 40s — شوف آخر screenshot."
                return result

            result["host"] = host
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
