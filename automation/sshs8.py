
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

            # ═══════════════════════════════════════
            # ✅ 4. استخراج المعلومات — الطريقة الجديدة
            # ═══════════════════════════════════════
            log.info("🔍 نستخرجو المعلومات...")

            creds = await self._extract_from_labels(page)

            result["host"] = creds.get("host")
            result["username"] = creds.get("username")
            result["password"] = creds.get("password") or password_input_value
            result["domain"] = creds.get("domain")

            log.info(f"🔍 نهائي: host={result['host']} user={result['username']} pass={result['password']} domain={result['domain']}")

            await self._send_photo(page, "3️⃣ بعد Create")

            if not result["host"]:
                result["message"] = f"❌ ما لقيناش IPv4.\nURL: {page.url}"
                return result
            if not result["username"]:
                result["message"] = f"❌ ما لقيناش Username.\nURL: {page.url}"
                return result
            if not result["password"] or result["password"] == "Copy":
                result["message"] = f"❌ ما لقيناش Password.\nURL: {page.url}"
                return result

            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            await self._send_photo(page, f"❌ خطأ: {str(e)[:80]}")

        return result

    # ═══════════════════════════════════════
    # 3. استخراج المعلومات — طريقة Labels
    # ═══════════════════════════════════════

    async def _extract_from_labels(self, page) -> dict:
        """
        يستخرج المعلومات بناءً على أسماء الـ labels الظاهرة فـ الصفحة:
        IPv4, Domain, Username, Password
        """
        result = {"host": None, "domain": None, "username": None, "password": None}

        # نستناو الصفحة تكمل
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

        # ═══════════════════════════════════════
        # ✅ المحاولة 1: ندورو على label → input بعدو
        # ═══════════════════════════════════════

        for attempt in range(20):
            data = await page.evaluate(r"""
                () => {
                    const out = { host: null, domain: null, username: null, password: null, debug: [] };

                    // ✅ نجيبو كل النصوص اللي فيها labels
                    const labels = ['IPv4', 'Domain', 'Username', 'Password', 'Host', 'User'];

                    // ✅ ندورو على كل الـ inputs
                    const allInputs = document.querySelectorAll('input');
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || '').trim();
                        
                        // نجيبو النص اللي قبل الـ input (label)
                        let labelText = '';
                        
                        // ✅ الطريقة 1: الـ input داخل <tr> وفيه <td>label</td><td>input</td>
                        const tr = inp.closest('tr');
                        if (tr) {
                            const tds = tr.querySelectorAll('td, th');
                            if (tds.length >= 2) {
                                // الـ td الأول فيه label
                                for (let i = 0; i < tds.length; i++) {
                                    if (tds[i].contains(inp)) continue;
                                    const t = (tds[i].innerText || '').trim();
                                    if (t.length > 0 && t.length < 30) {
                                        labelText = t;
                                        break;
                                    }
                                }
                            }
                        }
                        
                        // ✅ الطريقة 2: الـ input داخل <div> والـ label في div/span قبليه
                        if (!labelText) {
                            let parent = inp.parentElement;
                            for (let d = 0; d < 6 && parent; d++) {
                                // ندور على كل العناصر النصية داخل parent
                                const walker = document.createTreeWalker(
                                    parent,
                                    NodeFilter.SHOW_ELEMENT
                                );
                                let node;
                                while (node = walker.nextNode()) {
                                    if (node.contains(inp) || node === inp) continue;
                                    const txt = (node.innerText || '').trim();
                                    if (txt.length > 0 && txt.length < 30 &&
                                        !txt.includes('\n') &&
                                        node.children.length === 0) {
                                        labelText = txt;
                                        break;
                                    }
                                }
                                if (labelText) break;
                                parent = parent.parentElement;
                            }
                        }
                        
                        // ✅ الطريقة 3: ندورو على الـ label الأقرب بالـ previousSibling
                        if (!labelText) {
                            let prev = inp.previousElementSibling;
                            for (let i = 0; i < 5 && prev; i++) {
                                const t = (prev.innerText || prev.textContent || '').trim();
                                if (t.length > 0 && t.length < 30) {
                                    labelText = t;
                                    break;
                                }
                                prev = prev.previousElementSibling;
                            }
                        }
                        
                        out.debug.push({
                            label: labelText.substring(0, 30),
                            val: val.substring(0, 40),
                            type: inp.type || '',
                            name: inp.name || '',
                            id: inp.id || ''
                        });
                        
                        if (!val || val.length < 1) continue;
                        if (val.toLowerCase() === 'copy') continue;
                        
                        const lbl = labelText.toLowerCase();
                        
                        // ✅ نصنّفو حسب label
                        if (lbl.includes('ipv4') || lbl === 'ip' || lbl === 'host' || lbl.includes('host')) {
                            if (!out.host && /^(\d{1,3}\.){3}\d{1,3}$/.test(val)) {
                                out.host = val;
                            }
                        } else if (lbl.includes('domain')) {
                            if (!out.domain) out.domain = val;
                        } else if (lbl.includes('username') || lbl === 'user' || lbl.includes('user name')) {
                            if (!out.username && val.toLowerCase() !== 'copy') {
                                out.username = val;
                            }
                        } else if (lbl.includes('password') || lbl === 'pass') {
                            if (!out.password && val.toLowerCase() !== 'copy') {
                                out.password = val;
                            }
                        }
                    }
                    
                    // ✅ Backup: ندورو على label → nextSibling input بالـ DOM traversal
                    if (!out.host || !out.domain || !out.username || !out.password) {
                        const allText = document.body.querySelectorAll('*');
                        for (const el of allText) {
                            const txt = (el.innerText || '').trim();
                            
                            // ندورو على "IPv4" مثلاً
                            if (txt === 'IPv4' || txt === 'IPv4:') {
                                // نجيبو الـ input اللي بعدو
                                let next = el.nextElementSibling;
                                for (let i = 0; i < 3 && next; i++) {
                                    const inp = next.querySelector?.('input') || (next.tagName === 'INPUT' ? next : null);
                                    if (inp && inp.value) {
                                        out.host = inp.value.trim();
                                        break;
                                    }
                                    next = next.nextElementSibling;
                                }
                            }
                            if (txt === 'Domain' || txt === 'Domain:') {
                                let next = el.nextElementSibling;
                                for (let i = 0; i < 3 && next; i++) {
                                    const inp = next.querySelector?.('input') || (next.tagName === 'INPUT' ? next : null);
                                    if (inp && inp.value) {
                                        out.domain = inp.value.trim();
                                        break;
                                    }
                                    next = next.nextElementSibling;
                                }
                            }
                            if (txt === 'Username' || txt === 'Username:') {
                                let next = el.nextElementSibling;
                                for (let i = 0; i < 3 && next; i++) {
                                    const inp = next.querySelector?.('input') || (next.tagName === 'INPUT' ? next : null);
                                    if (inp && inp.value && inp.value.toLowerCase() !== 'copy') {
                                        out.username = inp.value.trim();
                                        break;
                                    }
                                    next = next.nextElementSibling;
                                }
                            }
                            if (txt === 'Password' || txt === 'Password:') {
                                let next = el.nextElementSibling;
                                for (let i = 0; i < 3 && next; i++) {
                                    const inp = next.querySelector?.('input') || (next.tagName === 'INPUT' ? next : null);
                                    if (inp && inp.value && inp.value.toLowerCase() !== 'copy') {
                                        out.password = inp.value.trim();
                                        break;
                                    }
                                    next = next.nextElementSibling;
                                }
                            }
                        }
                    }
                    
                    return out;
                }
            """)

            log.info(f"🔍 attempt {attempt+1}: host={data.get('host')} domain={data.get('domain')} user={data.get('username')} pass={data.get('password')}")
            log.info(f"🔍 debug: {data.get('debug', [])[:6]}")

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

            # ✅ fallback من النص (regex)
            if not result["host"] or not result["username"] or not result["password"]:
                body = await page.evaluate("() => document.body.innerText")
                
                if not result["host"]:
                    ips = re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', body)
                    for ip in ips:
                        parts = [int(x) for x in ip.split('.')]
                        if all(0 <= p <= 255 for p in parts) and \
                           not ip.startswith(('192.168.', '10.', '172.16.', '127.', '0.')):
                            result["host"] = ip
                            log.info(f"✅ Host from text: {ip}")
                            break
                
                if not result["username"]:
                    m = re.search(r'Username[\s\S]{0,20}?\n([a-zA-Z0-9_\-]{4,30})', body, re.I)
                    if m and m.group(1).lower() != 'copy':
                        result["username"] = m.group(1).strip()
                        log.info(f"✅ User from text: {result['username']}")
                
                if not result["domain"]:
                    m = re.search(r'\b([a-z0-9\-]+\.sshws\.com)\b', body, re.I)
                    if m:
                        result["domain"] = m.group(1)
                        log.info(f"✅ Domain from text: {result['domain']}")
                
                if not result["password"] or result["password"] == "Copy":
                    m = re.search(r'Password[\s\S]{0,20}?\n([a-zA-Z0-9!@#$%^&*_\-]{6,40})', body, re.I)
                    if m and m.group(1).lower() != 'copy':
                        result["password"] = m.group(1).strip()
                        log.info(f"✅ Pass from text: {result['password']}")

            if result["host"] and result["username"] and result["password"]:
                break

            await page.wait_for_timeout(2000)

        # ═══════════════════════════════════════
        # ✅ Password - كليك على Copy
        # ═══════════════════════════════════════
        if not result["password"] or result["password"] == "Copy":
            log.info("🔑 نحاولو Copy للـ Password...")

            try:
                # كليك على زر Copy اللي قريب من Password
                clicked = await page.evaluate(r"""
                    () => {
                        // 1. نلقاو حقل Password
                        let passInput = null;
                        const allInputs = document.querySelectorAll('input');
                        for (const inp of allInputs) {
                            const val = (inp.value || '').toLowerCase().trim();
                            if (val === 'copy') {
                                passInput = inp;
                                break;
                            }
                        }
                        
                        if (!passInput) {
                            // نجربو نجيبو input اللي بعد "Password"
                            const allEls = document.querySelectorAll('*');
                            for (const el of allEls) {
                                if ((el.innerText || '').trim() === 'Password') {
                                    let next = el.parentElement;
                                    for (let d = 0; d < 3 && next; d++) {
                                        const inp = next.querySelector('input');
                                        if (inp) { passInput = inp; break; }
                                        next = next.parentElement;
                                    }
                                    if (passInput) break;
                                }
                            }
                        }
                        
                        if (!passInput) return { clicked: false, reason: 'no_pass_input' };
                        
                        // 2. نلقاو زر Copy داخل نفس الحاوية
                        let container = passInput.parentElement;
                        for (let d = 0; d < 5 && container; d++) {
                            const btns = container.querySelectorAll('button, a, span, div, [role="button"]');
                            for (const b of btns) {
                                const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                                if (t === 'copy') {
                                    b.click();
                                    return { clicked: true, reason: 'clicked' };
                                }
                            }
                            container = container.parentElement;
                        }
                        
                        return { clicked: false, reason: 'no_copy_btn' };
                    }
                """)

                log.info(f"🔑 Copy result: {clicked}")

                if clicked.get("clicked"):
                    await page.wait_for_timeout(2000)

                    # نقراو من الـ clipboard
                    try:
                        clip = await page.evaluate("async () => { try { return await navigator.clipboard.readText(); } catch(e) { return null; } }")
                        if clip and len(clip.strip()) > 3 and clip.lower().strip() != 'copy':
                            result["password"] = clip.strip()
                            log.info(f"✅ Pass from clipboard: {result['password']}")
                    except Exception as e:
                        log.warning(f"⚠️ clipboard: {e}")
                    
                    # ✅ من بعد كليك، نعاودو نقراو الـ input
                    if not result["password"] or result["password"] == "Copy":
                        try:
                            pass_val = await page.evaluate(r"""
                                () => {
                                    const allInputs = document.querySelectorAll('input');
                                    for (const inp of allInputs) {
                                        const val = (inp.value || '').trim();
                                        if (val && val.toLowerCase() !== 'copy' && val.length >= 6) {
                                            // نتأكدو أنها password
                                            const parent = inp.closest('div, tr, td');
                                            if (parent) {
                                                const ptxt = (parent.innerText || '').toLowerCase();
                                                if (ptxt.includes('password')) {
                                                    return val;
                                                }
                                            }
                                        }
                                    }
                                    return null;
                                }
                            """)
                            if pass_val:
                                result["password"] = pass_val
                                log.info(f"✅ Pass after Copy: {pass_val}")
                        except Exception:
                            pass
            except Exception as e:
                log.warning(f"⚠️ password copy: {e}")

        return result

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
