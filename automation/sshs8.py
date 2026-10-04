"""
automation/sshs8.py
- vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113
- يعبي Password → Create → يقرا IPv4/Username/Password من الجدول
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
                        log.info(f"✅ password filled: {password_input_value}")
                        break
                except Exception:
                    continue

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

            log.info(f"🎯 Create clicked: {clicked}")

            # ✅ نستناو ظهور "Account successfully created"
            log.info("⏳ نستناو الحساب...")

            # نستناو أن يظهر IPv4 فالـ body
            for attempt in range(25):
                await page.wait_for_timeout(2000)

                # نتأكدو واش "Account successfully created" ظهر
                created = await page.evaluate("""
                    () => {
                        const body = document.body.innerText || '';
                        return body.includes('successfully created') ||
                               body.includes('Account successfully') ||
                               /\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/.test(body);
                    }
                """)
                if created:
                    log.info(f"✅ Account created بعد {(attempt+1)*2}s")
                    break

            await page.wait_for_timeout(2000)

            # ✅ نستخرجو المعلومات من الجدول
            info = await page.evaluate("""
                () => {
                    const out = { host: null, user: null, pass: null, domain: null, all_text: '' };
                    out.all_text = document.body.innerText || '';

                    // ✅ الطريقة 1: ندورو على الـ inputs + الـ label القريب
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {
                        const val = (inp.value || '').trim();
                        if (!val || val.length < 2) continue;

                        // نجيبو النص القريب (label / td قبل)
                        let label = '';
                        // parent div
                        let p = inp.parentElement;
                        for (let i = 0; i < 5 && p; i++) {
                            const txt = (p.innerText || '').toLowerCase();
                            if (txt.length < 200) {
                                label = txt;
                                break;
                            }
                            p = p.parentElement;
                        }

                        // إذا label فيه ipv4 → هذا host
                        if (!out.host && /ipv4|^ip\\b|host/i.test(label)) {
                            const m = val.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/);
                            if (m) out.host = m[0];
                            else if (val.includes('.')) out.host = val;
                        }
                        // username
                        if (!out.user && /username|user\\s*name/i.test(label)) {
                            out.user = val;
                        }
                        // password
                        if (!out.pass && /password|pass/i.test(label)) {
                            out.pass = val;
                        }
                        // domain
                        if (!out.domain && /domain/i.test(label)) {
                            out.domain = val;
                        }
                    }

                    // ✅ الطريقة 2: من الجدول — <tr> فيه <td>IPv4</td><td>value</td>
                    if (!out.host || !out.user || !out.pass) {
                        const rows = document.querySelectorAll('tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length < 2) continue;
                            const label = (cells[0].innerText || '').trim().toLowerCase();
                            // نجيبو القيمة من cell الثاني أو من input داخلها
                            let val = (cells[1].innerText || '').trim();
                            const inpInCell = cells[1].querySelector('input');
                            if (inpInCell && inpInCell.value) {
                                val = inpInCell.value.trim();
                            }

                            if (!val) continue;

                            if (!out.host && /ipv4|^ip$|host/i.test(label)) {
                                const m = val.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/);
                                if (m) out.host = m[0];
                            }
                            if (!out.user && /username|user\\s*name/i.test(label)) {
                                out.user = val;
                            }
                            if (!out.pass && /password|pass/i.test(label)) {
                                out.pass = val;
                            }
                            if (!out.domain && /domain/i.test(label)) {
                                out.domain = val;
                            }
                        }
                    }

                    // ✅ الطريقة 3: regex على النص الكامل
                    if (!out.host) {
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

                    // username من النص: كيكون بعد "Username"
                    if (!out.user) {
                        const m = out.all_text.match(/(?:username|user\\s*name)[\\s:]*([a-zA-Z0-9_\\-]{4,20})/i);
                        if (m) out.user = m[1];
                    }
                    // password من النص
                    if (!out.pass) {
                        const m = out.all_text.match(/(?:password|pass)[\\s:]*([A-Za-z0-9]{6,16})/i);
                        if (m) out.pass = m[1];
                    }

                    return out;
                }
            """)

            log.info(f"🔍 معلومات: host={info.get('host')} user={info.get('user')} pass={info.get('pass')}")

            await self._send_photo(page, "3️⃣ بعد Create")

            log.info(f"🖥️ Host: {info.get('host')}")
            log.info(f"👤 User: {info.get('user')}")
            log.info(f"🔑 Pass: {info.get('pass')}")

            result["host"] = info.get("host")
            result["username"] = info.get("user") or "unknown"
            result["password"] = info.get("pass") or password_input_value

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
