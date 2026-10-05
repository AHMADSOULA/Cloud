"""
automation/vmess.py
- ينشئ حساب VMESS
- يستخرج link TLS
- يبني ملف dark
"""
import asyncio
import random
import string
import re
import os
import base64
import json
from utils.logger import get_logger

log = get_logger("VMESS")


VMESS_CREATE_URL = "https://vpnnamerica.sshs8.com/accounts/VMESS/3"


def generate_password():
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=10))


class VMESS:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None
        self.chat_id = None
        self.bot = None

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    async def open_page(self, url: str = None) -> bool:
        url = url or VMESS_CREATE_URL
        log.info(f"🌐 فتح: {url}")
        self.page = await self.context.new_page()
        page = self.page

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            return True
        except Exception as e:
            log.error(f"❌ open_page: {e}", exc_info=True)
            return False

    async def create_account(self) -> dict:
        page = self.page
        if not page:
            return {"success": False, "error": "no_page"}

        password_value = generate_password()

        result = {
            "success": False,
            "password": password_value,
            "link_tls": None,
            "vmess_config": None,
            "dark_uri": None,
            "message": None,
        }

        try:
            # 1. تعبئة Password
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
                        await page.wait_for_timeout(100)
                        await el.fill("")
                        await page.wait_for_timeout(100)
                        await el.fill(password_value)
                        log.info(f"✅ password filled: {password_value}")
                        filled = True
                        break
                except Exception:
                    continue

            await page.wait_for_timeout(500)
            url_before = page.url

            # 2. ضغط Create
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
                        await page.wait_for_timeout(150)
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

            if not clicked:
                result["message"] = "❌ ما لقيناش زر Create"
                return result

            # 3. نستناو URL يتبدل
            for i in range(20):
                await page.wait_for_timeout(500)
                if page.url != url_before:
                    log.info(f"✅ URL تبدل بعد {(i+1)*0.5}s")
                    break

            await page.wait_for_timeout(3000)

            # 4. Link TLS
            link_tls = await self._extract_link_tls(page)
            if not link_tls:
                result["message"] = "❌ ما لقيناش Link TLS."
                return result

            result["link_tls"] = link_tls

            # 5. نفكو base64
            vmess_data = self._decode_vmess_link(link_tls)
            if not vmess_data:
                result["message"] = "❌ ما قدرناش نفكو Link TLS."
                return result

            result["vmess_config"] = vmess_data

            # 6. ملف dark
            dark_uri = self._build_vmess_dark(vmess_data, password_value)
            if not dark_uri:
                result["message"] = "❌ فشل بناء ملف dark."
                return result

            result["dark_uri"] = dark_uri
            result["success"] = True

        except Exception as e:
            log.error(f"❌ create_account: {e}", exc_info=True)
            result["message"] = f"❌ خطأ: {str(e)[:200]}"

        return result

    async def _extract_link_tls(self, page) -> str:
        for attempt in range(30):
            link = await page.evaluate(r"""
                () => {
                    const labels = document.querySelectorAll('*');
                    
                    for (const el of labels) {
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (txt === 'Link TLS' || txt === 'Link TLS:') {
                            let parent = el.parentElement;
                            for (let d = 0; d < 5 && parent; d++) {
                                const inp = parent.querySelector('input, textarea');
                                if (inp) {
                                    const val = (inp.value || inp.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                parent = parent.parentElement;
                            }
                            let next = el.nextElementSibling;
                            for (let i = 0; i < 5 && next; i++) {
                                const inp = next.querySelector ? next.querySelector('input, textarea') : null;
                                if (inp) {
                                    const val = (inp.value || inp.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                if (next.tagName === 'INPUT' || next.tagName === 'TEXTAREA') {
                                    const val = (next.value || next.textContent || '').trim();
                                    if (val && val.length > 20) return val;
                                }
                                next = next.nextElementSibling;
                            }
                        }
                    }
                    
                    const allInputs = document.querySelectorAll('input, textarea');
                    for (const inp of allInputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (val && (val.startsWith('vmess://') || val.startsWith('eyJ'))) {
                            const parent = inp.closest('div, tr, td');
                            if (parent) {
                                const ptxt = (parent.innerText || '').toLowerCase();
                                if (ptxt.includes('tls') && !ptxt.includes('no tls') && !ptxt.includes('notls')) {
                                    return val;
                                }
                            }
                        }
                    }
                    
                    for (const inp of allInputs) {
                        const val = (inp.value || inp.textContent || '').trim();
                        if (val && val.length > 30 && !val.toLowerCase().includes('copy')) {
                            if (/^[A-Za-z0-9+/=]+$/.test(val.substring(0, 50))) {
                                return val;
                            }
                        }
                    }
                    
                    return null;
                }
            """)

            if link:
                log.info(f"✅ Link TLS: {link[:80]}...")
                return link.strip()

            log.info(f"🔍 attempt {attempt+1}: Link TLS ما ظهرش بعد...")
            await page.wait_for_timeout(2000)

        return None

    def _decode_vmess_link(self, link: str) -> dict:
        try:
            if link.startswith("vmess://"):
                b64 = link.replace("vmess://", "").strip()
            else:
                b64 = link.strip()

            b64 = b64 + ("=" * ((4 - (len(b64) % 4)) % 4))

            try:
                decoded = base64.b64decode(b64).decode("utf-8")
            except Exception:
                decoded = base64.urlsafe_b64decode(b64).decode("utf-8")

            try:
                data = json.loads(decoded)
                log.info(f"✅ فك JSON: {data}")
                return data
            except Exception:
                log.warning(f"⚠️ ماشي JSON: {decoded[:200]}")
                return None

        except Exception as e:
            log.error(f"❌ _decode_vmess_link: {e}")
            return None

    def _build_vmess_dark(self, vmess_data: dict, password: str) -> str:
        try:
            host = vmess_data.get("add") or vmess_data.get("host") or ""
            port = int(vmess_data.get("port") or 443)
            uuid = vmess_data.get("id") or ""
            sni = vmess_data.get("sni") or vmess_data.get("host") or "youtube.com"
            path = vmess_data.get("path") or "/vmess/"
            ws_header_host = vmess_data.get("host") or "googlevideo.com"

            outer = {
                "type": "VMESS",
                "name": password or "vmess_user",
                "vmessTunnelConfig": {
                    "v2rayConfig": {
                        "host": host,
                        "port": port,
                        "uuid": uuid,
                        "serverNameIndication": sni,
                        "wsPath": path,
                        "wsHeaderHost": ws_header_host,
                    },
                    "injectConfig": {
                        "enabled": True,
                        "mode": "PROXY",
                        "proxyHost": "34.43.46.91",
                        "proxyPort": 443,
                        "payload": "CONNECT [host_port] HTTP/1.1[crlf]Host: youtubekids.com[crlf]X-Online-Host: youtubekids.com[crlf]Connection: Keep-Alive[crlf]User-Agent: Mozilla/5.0[crlf][crlf]",
                    },
                },
            }

            raw = json.dumps(outer, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            b64 = base64.b64encode(raw).decode("utf-8")
            return "darktunnel://" + b64

        except Exception as e:
            log.error(f"❌ _build_vmess_dark: {e}", exc_info=True)
            return None

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
