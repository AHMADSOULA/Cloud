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


# كلمات ممنوعة باش ما ناخذوهاش كـ username/pass
FORBIDDEN_WORDS = {
    'copy', 'copied', 'show', 'hide', 'value', 'field', 'label',
    'username', 'password', 'ipv4', 'domain', 'port', 'ssl', 'tls',
    'none', 'null', 'unknown', 'true', 'false', 'yes', 'no',
    'create', 'account', 'free', 'ssh', 'websocket', 'server',
    'loading', 'please', 'wait', 'error', 'success', 'info',
}


def is_valid_value(val: str, min_len: int = 3) -> bool:
    """نتحققو واش القيمة صحيحة (ماشي كلمة محجوزة، طول مناسب...)"""
    if not val:
        return False
    v = val.strip().lower()
    if len(v) < min_len:
        return False
    if v in FORBIDDEN_WORDS:
        return False
    # ما تكونش كلشي حروف صغيرة وكلمة واحدة (بحال "copy")
    if len(v) <= 6 and v.isalpha() and v.islower():
        return False
    return True


def is_valid_ip(val: str) -> bool:
    """نتحققو واش IP صحيح"""
    if not val:
        return False
    m = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$', val.strip())
    if not m:
        return False
    parts = [int(m.group(i)) for i in range(1, 5)]
    if not all(0 <= p <= 255 for p in parts):
        return False
    if val.startswith('192.168.') or val.startswith('10.') or val.startswith('172.16.'):
        return False
    if val in ('0.0.0.0', '127.0.0.1', '255.255.255.255'):
        return False
    return True


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

            # ═══════════════════════════════════════
            # ✅ نستناو حتى الجدول يتحمّل مزيان
            # ═══════════════════════════════════════
            log.info("⏳ نستناو الحساب يتحمّل...")

            host = None
            username = None
            password = None

            for attempt in range(30):  # 30 × 2s = 60s
                await page.wait_for_timeout(2000)

                # ✅ نستخرجو من inputs (الطريقة الأكثر دقة)
                info = await page.evaluate("""
                    () => {
                        const out = { host: null, user: null, pass: null, domain: null };

                        // ✅ ندورو على كل input (بما فيها readonly)
                        const inputs = document.querySelectorAll('input');
                        
                        for (const inp of inputs) {
                            const val = (inp.value || '').trim();
                            if (!val || val.length < 2) continue;
                            if (val.toLowerCase() === 'copy') continue;

                            // نجيبو الـ label (text قبل input فـ نفس الـ row/div)
                            let label = '';
                            
                            // 1. نجربو الـ <tr><td>label</td><td><input></td></tr>
                            const tr = inp.closest('tr');
                            if (tr) {
                                const tds = tr.querySelectorAll('td, th');
                                if (tds.length >= 1) {
                                    label = (tds[0].innerText || '').trim().toLowerCase();
                                }
                            }
                            
                            // 2. نجربو الـ parent div
                            if (!label) {
                                let p = inp.parentElement;
                                for (let i = 0; i < 4 && p; i++) {
                                    const t = (p.innerText || '').trim().toLowerCase();
                                    if (t.length > 0 && t.length < 100) {
                                        label = t;
                                        break;
                                    }
                                    p = p.parentElement;
                                }
                            }

                            // ✅ نصنّفو حسب label
                            if (/ipv4|^ip\\b|^ip$|\\bhost\\b/i.test(label)) {
                                if (!out.host) out.host = val;
                            } else if (/username|user\\s*name|\\buser\\b/i.test(label)) {
                                if (!out.user) out.user = val;
                            } else if (/password|\\bpass\\b/i.test(label)) {
                                if (!out.pass) out.pass = val;
                            } else if (/domain/i.test(label)) {
                                if (!out.domain) out.domain = val;
                            }
                        }

                        // ✅ إذا مالقيناش كامل، ندورو على الـ regex
                        const body = document.body.innerText || '';
                        if (!out.host) {
                            const ips = body.match(/\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b/g) || [];
                            for (const ip of ips) {
                                const parts = ip.split('.').map(Number);
                                if (parts.every(p => p >= 0 && p <= 255) &&
                                    !ip.startsWith('192.168.') &&
                                    !ip.startsWith('10.') &&
                                    !ip.startsWith('172.16.') &&
                                    ip !== '0.0.0.0' && ip !== '127.0.0.1' &&
                                    ip !== '255.255.255.255') {
                                    out.host = ip;
                                    break;
                                }
                            }
                        }

                        return out;
                    }
                """)

                # ✅ نتحققو من الصلاحية فـ Python
                if info.get("host") and is_valid_ip(info["host"]) and not host:
                    host = info["host"]
                    log.info(f"✅ Host لقيناه: {host}")

                if info.get("user") and is_valid_value(info["user"], 4) and not username:
                    username = info["user"]
                    log.info(f"✅ User لقيناه: {username}")

                if info.get("pass") and is_valid_value(info["pass"], 6) and not password:
                    password = info["pass"]
                    log.info(f"✅ Pass لقيناه: {password}")

                # ✅ إلا لقينا 3 → نوقفو
                if host and username and password:
                    log.info(f"✅ معلومات كاملة بعد {(attempt+1)*2}s")
                    break

            log.info(f"🔍 معلومات نهائية: host={host} user={username} pass={password}")

            await self._send_photo(page, "3️⃣ بعد Create")

            result["host"] = host
            result["username"] = username
            result["password"] = password or password_input_value

            if not host:
                result["success"] = False
                result["message"] = "ما لقيناش host — شوف آخر screenshot."
                return result
            if not username:
                result["success"] = False
                result["message"] = "ما لقيناش username — شوف آخر screenshot."
                return result
            if not password:
                result["success"] = False
                result["message"] = "ما لقيناش password — شوف آخر screenshot."
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
