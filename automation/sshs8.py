"""
automation/sshs8.py
- vpneurope.sshs8.com/accounts/SSH_WEBSOCKET/113
- يعبي Password → Create → يستنى URL جديد → يقرا IPv4/Username/Password
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
    # 1. فتح الصفحة
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
            "domain": None,
            "message": None,
        }

        try:
            # ✅ 1. نعبيو Password
            filled = False
            for sel in [
                'input[type="password"]',
                'input[name*="pass" i]',
                'input[id*="pass" i]',
                'input[placeholder*="pass" i]',
            ]:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        await page.wait_for_timeout(200)
                        await el.fill("")
                        await page.wait_for_timeout(200)
                        await el.fill(password_input_value)
                        log.info(f"✅ password filled: {password_input_value}")
                        filled = True
                        break
                except Exception:
                    continue

            if not filled:
                log.warning("⚠️ ما لقيناش حقل Password")

            await page.wait_for_timeout(1000)
            await self._send_photo(page, "2️⃣ بعد تعبئة Password")

            url_before = page.url
            log.info(f"🔗 URL قبل Create: {url_before}")

            # ✅ 2. نضغطو Create
            clicked = False
            for sel in [
                'button:has-text("Create an account")',
                'button:has-text("Create account")',
                'input[value="Create an account"]',
                'input[type="submit"]',
                'button:has-text("Create")',
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
                js_clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, input[type="submit"], a, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || el.value || el.textContent || '').trim().toLowerCase();
                            if (t.includes('create')) {
                                try { el.click(); return t; } catch(e) {}
                            }
                        }
                        return null;
                    }
                """)
                if js_clicked:
                    clicked = True
                    log.info(f"✅ JS Clicked: {js_clicked}")

            log.info(f"🎯 Create clicked: {clicked}")

            if not clicked:
                result["message"] = "❌ ما لقيناش زر Create"
                await self._send_photo(page, "❌ ما لقيناش Create")
                return result

            # ✅ 3. نستناو URL يتبدل
            log.info("⏳ نستناو...")
            for i in range(30):
                await page.wait_for_timeout(1000)
                if page.url != url_before:
                    log.info(f"✅ URL تبدل بعد {i+1}s: {page.url}")
                    break

            await page.wait_for_timeout(5000)

            # ✅ 4. استخراج المعلومات — بالترتيب
            log.info("🔍 نستخرجو المعلومات...")
            creds = await self._extract_by_order(page)

            result["host"] = creds.get("host")
            result["username"] = creds.get("username")
            result["password"] = creds.get("password") or password_input_value
            result["domain"] = creds.get("domain")

            log.info(f"🔍 نهائي: host={result['host']} user={result['username']} pass={result['password']} domain={result['domain']}")

            await self._send_photo(page, "3️⃣ بعد Create")

            if not result["host"]:
                result["message"] = f"❌ ما لقيناش IPv4."
                return result
            if not result["username"]:
                result["message"] = f"❌ ما لقيناش Username."
                return result
            if not result["password"] or result["password"] == "Copy":
                result["message"] = f"❌ ما لقيناش Password."
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            await self._send_photo(page, f"❌ خطأ: {str(e)[:80]}")

        return result

    # ═══════════════════════════════════════
    # 3. استخراج المعلومات — بالترتيب (index-based)
    # ═══════════════════════════════════════

    async def _extract_by_order(self, page) -> dict:
        """
        يستخرج المعلومات حسب ترتيب الـ inputs فـ الصفحة:
        1. IPv4
        2. Domain
        3. Username
        4. Password
        """
        result = {"host": None, "domain": None, "username": None, "password": None}

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        for attempt in range(20):
            data = await page.evaluate(r"""
                () => {
                    const out = { all_values: [], host: null, domain: null, username: null, password: null };

                    // ✅ نجيبو كل الـ inputs اللي عندها value
                    const allInputs = Array.from(document.querySelectorAll('input'));
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || '').trim();
                        if (!val) continue;
                        if (val.toLowerCase() === 'copy') continue;
                        if (val.length < 2) continue;
                        
                        out.all_values.push({
                            value: val,
                            type: inp.type || 'text',
                            name: inp.name || '',
                            id: inp.id || '',
                            cls: (inp.className || '').substring(0, 50),
                        });
                    }
                    
                    // ✅ الطريقة 1: نعتمدو على الترتيب (index-based)
                    // فـ sshs8، الترتيب دائماً:
                    // 0: IPv4
                    // 1: Domain
                    // 2: Username
                    // 3: Password
                    
                    const vals = out.all_values.map(x => x.value);
                    
                    // IPv4 — أول قيمة تطابق regex IP
                    for (const v of vals) {
                        if (/^(\d{1,3}\.){3}\d{1,3}$/.test(v)) {
                            const parts = v.split('.').map(Number);
                            if (parts.every(p => p >= 0 && p <= 255) &&
                                !v.startsWith('192.168.') &&
                                !v.startsWith('10.') &&
                                !v.startsWith('172.16.') &&
                                !v.startsWith('127.')) {
                                out.host = v;
                                break;
                            }
                        }
                    }
                    
                    // Domain — قيمة فيها نقطة وحروف وليست IP
                    for (const v of vals) {
                        if (v === out.host) continue;
                        if (/^[a-z0-9\-\.]+\.[a-z]{2,}$/i.test(v) && 
                            !/^(\d{1,3}\.){3}\d{1,3}$/.test(v) &&
                            v.length < 60) {
                            out.domain = v;
                            break;
                        }
                    }
                    
                    // Username — قيمة alphanumeric بدون نقطة، بعد IPv4/domain
                    for (const v of vals) {
                        if (v === out.host || v === out.domain) continue;
                        if (/^[a-z0-9_\-]{4,30}$/i.test(v) && 
                            !/^\d+$/.test(v) &&
                            v.length >= 4 && v.length <= 30) {
                            out.username = v;
                            break;
                        }
                    }
                    
                    // Password — قيمة 8-20 حرف، alphanumeric، بعد username
                    for (const v of vals) {
                        if (v === out.host || v === out.domain || v === out.username) continue;
                        if (/^[a-zA-Z0-9!@#$%^&*_\-]{6,40}$/.test(v) &&
                            v.length >= 6 && v.length <= 40) {
                            out.password = v;
                            break;
                        }
                    }
                    
                    return out;
                }
            """)

            all_vals = data.get("all_values", [])
            log.info(f"🔍 attempt {attempt+1}: {len(all_vals)} values → {[v['value'][:25] for v in all_vals[:8]]}")
            log.info(f"🔍 → host={data.get('host')} domain={data.get('domain')} user={data.get('username')} pass={data.get('password')}")

            if data.get("host") and not result["host"]:
                result["host"] = data["host"]
                log.info(f"✅ Host: {data['host']}")
            if data.get("domain") and not result["domain"]:
                result["domain"] = data["domain"]
                log.info(f"✅ Domain: {data['domain']}")
            if data.get("username") and not result["username"]:
                result["username"] = data["username"]
                log.info(f"✅ User: {data['username']}")
            if data.get("password") and not result["password"]:
                result["password"] = data["password"]
                log.info(f"✅ Pass: {data['password']}")

            if result["host"] and result["username"] and result["password"]:
                log.info("✅ معلومات كاملة!")
                break

            await page.wait_for_timeout(2000)

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
