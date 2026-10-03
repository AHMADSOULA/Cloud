"""
automation/skills_register.py
تسجيل skills.google عبر Google Account + CAPTCHA + تصوير
"""
import asyncio
import base64
import io
import json
import os
import time
import requests
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SkillsRegister")


# ═══════════════════════════════════════════
# SCTG CAPTCHA
# ═══════════════════════════════════════════

SCTG_API_KEY = "Uosbi2t23tLFF7D1ro9yyX1EOJ61ER8I"
SCTG_SUBMIT = "https://api.sctg.xyz/in.php"
SCTG_RESULT = "https://api.sctg.xyz/res.php"


def solve_recaptcha_sctg(sitekey: str, pageurl: str) -> str:
    try:
        log.info(f"🔍 SCTG — sitekey={sitekey[:30]}...")
        payload = {
            "key": SCTG_API_KEY,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": pageurl,
            "json": 1,
            "version": "v2",
        }
        r = requests.post(SCTG_SUBMIT, data=payload, timeout=30)
        data = r.json()
        if data.get("status") != 1:
            log.error(f"❌ SCTG submit: {data}")
            return None
        captcha_id = data.get("request")
        log.info(f"✅ SCTG ID: {captcha_id}")

        for i in range(60):
            time.sleep(5)
            params = {"key": SCTG_API_KEY, "action": "get", "id": captcha_id, "json": 1}
            r = requests.get(SCTG_RESULT, params=params, timeout=30)
            data = r.json()
            if data.get("status") == 1:
                log.info(f"✅ SCTG حل")
                return data.get("request")
            elif data.get("request") == "CAPCHA_NOT_READY":
                continue
            else:
                log.error(f"❌ SCTG error: {data}")
                return None
        return None
    except Exception as e:
        log.error(f"❌ SCTG: {e}", exc_info=True)
        return None


# ═══════════════════════════════════════════
# Skills Register
# ═══════════════════════════════════════════

class SkillsRegister:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None

    async def _shot(self, page, caption: str = ""):
        if not self.sender:
            return
        try:
            path = f"/tmp/skills_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=f"📸 {caption}"[:1000])
                    log.info(f"📸 {caption}")
                except Exception as e:
                    log.warning(f"⚠️ reply_photo: {e}")
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    async def open_signin(self, email: str) -> bool:
        """يفتح skills.google → Sign in → Google → إيميل → Next"""
        log.info(f"🚀 Skills — {email}")
        page = await self.context.new_page()
        self.page = page

        try:
            # 1. نفتحو الموقع
            await page.goto("https://www.skills.google/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await self._shot(page, "1️⃣ skills.google")

            # 2. Sign in
            try:
                signin = page.get_by_role("link", name="Sign in")
                if await signin.count() == 0:
                    signin = page.get_by_role("button", name="Sign in")
                await signin.first.click()
                log.info("✅ Sign in clicked")
                await page.wait_for_timeout(3000)
                await self._shot(page, "2️⃣ Sign in")
            except Exception as e:
                log.warning(f"⚠️ Sign in: {e}")

            # 3. Sign in with Google
            try:
                google_btn = page.get_by_role("button", name="Sign in with Google")
                if await google_btn.count() == 0:
                    google_btn = page.get_by_text("Sign in with Google", exact=False)
                await google_btn.first.click()
                log.info("✅ Google clicked")
                await page.wait_for_timeout(4000)
                await self._shot(page, "3️⃣ Google sign in")
            except Exception as e:
                log.warning(f"⚠️ Google: {e}")

            # 4. الإيميل
            email_filled = False
            for sel in ['input[type="email"]', 'input[name="identifier"]', 'input[type="text"]']:
                try:
                    inp = page.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible():
                        await inp.click()
                        await inp.fill("")
                        await page.wait_for_timeout(200)
                        await inp.fill(email)
                        log.info(f"✅ Email: {email}")
                        email_filled = True
                        break
                except Exception:
                    pass

            if not email_filled:
                await self._shot(page, "⚠️ ما لقيناش الإيميل")
                return False

            # 5. Next
            try:
                next_btn = page.get_by_role("button", name="Next")
                if await next_btn.count() == 0:
                    next_btn = page.locator('#identifierNext')
                await next_btn.first.click()
                log.info("✅ Next")
                await page.wait_for_timeout(5000)
                await self._shot(page, "4️⃣ بعد Next")
            except Exception as e:
                log.warning(f"⚠️ Next: {e}")

            # 6. تحقق كلمة السر
            await page.wait_for_timeout(2000)
            has_password = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('input[type="password"]')) {
                        if (el.offsetParent !== null) return true;
                    }
                    return false;
                }
            """)

            if has_password:
                log.info("✅ صفحة كلمة السر")
                await self._shot(page, "5️⃣ كلمة السر")
                return True

            await self._shot(page, "❓ صفحة غير متوقعة")
            return False

        except Exception as e:
            log.error(f"❌ open_signin: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")
            return False

    async def enter_password_and_signin(self, password: str) -> dict:
        """يدخل كلمة السر → Next → يحل CAPTCHA → ينشئ حساب"""
        page = self.page
        result = {"success": False, "final_url": None}

        try:
            # 1. كلمة السر
            pwd_filled = False
            for sel in ['input[type="password"]', 'input[name="password"]']:
                try:
                    inp = page.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible():
                        await inp.click()
                        await inp.fill("")
                        await page.wait_for_timeout(200)
                        await inp.fill(password)
                        log.info("✅ كلمة السر")
                        pwd_filled = True
                        break
                except Exception:
                    pass

            if not pwd_filled:
                await self._shot(page, "❌ ما لقيناش كلمة السر")
                return result

            # 2. Next
            try:
                next_btn = page.locator('#passwordNext')
                if await next_btn.count() == 0:
                    next_btn = page.get_by_role("button", name="Next")
                await next_btn.first.click()
                log.info("✅ Password Next")
                await page.wait_for_timeout(8000)
                await self._shot(page, "6️⃣ بعد كلمة السر")
            except Exception as e:
                log.warning(f"⚠️ Next pwd: {e}")

            # 3. ننتظرو نرجعو لـ skills
            for i in range(30):
                await page.wait_for_timeout(2000)
                current = page.url
                if "skills.google" in current and "accounts.google.com" not in current:
                    log.info(f"✅ رجعنا لـ skills: {current}")
                    await self._shot(page, "7️⃣ رجعنا لـ skills")
                    break

            await page.wait_for_timeout(2000)
            await self._shot(page, "8️⃣ الصفحة الحالية")

            # 4. reCAPTCHA
            try:
                sitekey = await page.evaluate("""
                    () => {
                        const r = document.querySelector('.g-recaptcha, [data-sitekey]');
                        if (r) return r.getAttribute('data-sitekey');
                        const iframe = document.querySelector('iframe[src*="recaptcha"]');
                        if (iframe) {
                            const m = (iframe.src || '').match(/[?&]k=([^&]+)/);
                            if (m) return decodeURIComponent(m[1]);
                        }
                        return null;
                    }
                """)

                if sitekey:
                    log.info(f"🔑 sitekey: {sitekey[:40]}...")
                    token = solve_recaptcha_sctg(sitekey, page.url)
                    if token:
                        await page.evaluate("""
                            (token) => {
                                let el = document.getElementById('g-recaptcha-response');
                                if (!el) {
                                    el = document.createElement('textarea');
                                    el.id = 'g-recaptcha-response';
                                    el.name = 'g-recaptcha-response';
                                    el.style.display = 'none';
                                    document.body.appendChild(el);
                                }
                                el.value = token;
                            }
                        """, token)
                        log.info("✅ CAPTCHA set")
                        await self._shot(page, "9️⃣ CAPTCHA")

                        # زر قبول
                        try:
                            for name in ["قبول", "Accept", "Aceito", "إرسال", "Submit"]:
                                accept = page.get_by_role("button", name=name)
                                if await accept.count() > 0:
                                    await accept.first.click()
                                    log.info(f"✅ {name} clicked")
                                    await page.wait_for_timeout(5000)
                                    await self._shot(page, f"🔟 بعد {name}")
                                    break
                        except Exception:
                            pass
            except Exception as e:
                log.warning(f"⚠️ CAPTCHA: {e}")

            await page.wait_for_timeout(3000)
            await self._shot(page, "1️⃣1️⃣ بعد CAPTCHA")

            # 5. Create account إذا ظهر
            try:
                create = page.get_by_role("button", name="Create account")
                if await create.count() > 0:
                    await create.first.click()
                    log.info("✅ Create account")
                    await page.wait_for_timeout(5000)
                    await self._shot(page, "1️⃣2️⃣ Create account")
            except Exception:
                pass

            # 6. النتيجة
            result["final_url"] = page.url
            if "skills.google" in page.url:
                result["success"] = True
                await self._shot(page, "✅ تم إنشاء الحساب")

        except Exception as e:
            log.error(f"❌ enter_password: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")

        return result

    async def close(self):
        try:
            await self.page.close()
        except Exception:
            pass
