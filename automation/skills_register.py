"""
automation/skills_register.py
تسجيل skills.google — مع screenshot + رابط VNC لحل CAPTCHA
"""
import asyncio
import os
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SkillsRegister")


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

    async def _send_vnc_link(self, reason: str = "CAPTCHA"):
        """يبعت رابط noVNC"""
        if not self.sender:
            return
        vnc_url = os.getenv("VNC_URL", "")
        if not vnc_url:
            vnc_url = "https://YOUR-RAILWAY-DOMAIN.railway.app/vnc.html?autoconnect=1&resize=scale"

        try:
            await self.sender.reply_text(
                f"🚨 *{reason} ظهرت!*\n\n"
                f"🌐 *ادخل لهذا الرابط وحلها:*\n"
                f"`{vnc_url}`\n\n"
                f"📝 *طريقة الحل:*\n"
                f"1. افتح الرابط\n"
                f"2. اضغط على checkbox في الـ CAPTCHA\n"
                f"3. اختر الصور المطلوبة\n"
                f"4. اضغط Verify\n"
                f"5. رجع للبوت واضغط *✅ حليتها*",
                parse_mode="Markdown"
            )
            log.info(f"✅ VNC link sent")
        except Exception as e:
            log.warning(f"⚠️ send_vnc: {e}")

    async def _has_captcha(self, page) -> bool:
        try:
            return await page.evaluate("""
                () => {
                    for (const iframe of document.querySelectorAll('iframe')) {
                        const src = (iframe.src || '').toLowerCase();
                        if (src.includes('recaptcha') || src.includes('google.com/recaptcha')) {
                            if (iframe.offsetParent !== null) return true;
                        }
                    }
                    for (const el of document.querySelectorAll('.g-recaptcha, [data-sitekey], #recaptcha, .recaptcha-checkbox')) {
                        if (el.offsetParent !== null) return true;
                    }
                    const body = (document.body.innerText || '').toLowerCase();
                    if (body.includes("i'm not a robot") || body.includes('verify it\\'s you') ||
                        body.includes('confirm you\\'re not a robot')) return true;
                    return false;
                }
            """)
        except Exception:
            return False

    # ═══════════════════════════════════════
    # open_signin
    # ═══════════════════════════════════════

    async def open_signin(self, email: str) -> dict:
        log.info(f"🚀 Skills — {email}")
        page = await self.context.new_page()
        self.page = page

        try:
            await page.goto("https://www.skills.google/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await self._shot(page, "1️⃣ skills.google")

            # Sign in
            try:
                signin = page.get_by_role("link", name="Sign in")
                if await signin.count() == 0:
                    signin = page.get_by_role("button", name="Sign in")
                await signin.first.click()
                log.info("✅ Sign in")
                await page.wait_for_timeout(3000)
            except Exception as e:
                log.warning(f"⚠️ Sign in: {e}")

            # Google
            try:
                google_btn = page.get_by_role("button", name="Sign in with Google")
                if await google_btn.count() == 0:
                    google_btn = page.get_by_text("Sign in with Google", exact=False)
                await google_btn.first.click()
                log.info("✅ Google")
                await page.wait_for_timeout(4000)
                await self._shot(page, "3️⃣ Google")
            except Exception as e:
                log.warning(f"⚠️ Google: {e}")

            # Email
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
                return {"status": "error", "message": "ما قدرناش نكتبو الإيميل."}

            # Next
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

            # ✅ نستناو
            for i in range(15):
                await page.wait_for_timeout(1000)

                if await self._has_captcha(page):
                    log.info("🚨 CAPTCHA")
                    await self._shot(page, "🚨 CAPTCHA")
                    await self._send_vnc_link("CAPTCHA بعد الإيميل")
                    return {"status": "captcha", "message": "CAPTCHA ظهرت"}

                has_password = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('input[type="password"]')) {
                            if (el.offsetParent !== null) return true;
                        }
                        return false;
                    }
                """)
                if has_password:
                    log.info("✅ كلمة السر")
                    await self._shot(page, "5️⃣ كلمة السر")
                    return {"status": "password", "message": "صفحة كلمة السر"}

            await self._shot(page, "❓ صفحة غير متوقعة")
            return {"status": "error", "message": "صفحة غير متوقعة."}

        except Exception as e:
            log.error(f"❌ open_signin: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")
            return {"status": "error", "message": str(e)[:200]}

    async def enter_password_and_signin(self, password: str) -> dict:
        page = self.page
        result = {"status": "error", "message": "", "final_url": None}

        try:
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
                return {"status": "error", "message": "ما لقيناش حقل كلمة السر."}

            await page.wait_for_timeout(1000)
            if await self._has_captcha(page):
                log.info("🚨 CAPTCHA")
                await self._shot(page, "🚨 CAPTCHA")
                await self._send_vnc_link("CAPTCHA بعد كلمة السر")
                return {"status": "captcha", "message": "CAPTCHA ظهرت"}

            # Next
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

            # نستناو
            for i in range(20):
                await page.wait_for_timeout(1000)

                if await self._has_captcha(page):
                    log.info("🚨 CAPTCHA")
                    await self._shot(page, "🚨 CAPTCHA")
                    await self._send_vnc_link("CAPTCHA بعد كلمة السر")
                    return {"status": "captcha", "message": "CAPTCHA ظهرت"}

                if "skills.google" in page.url and "accounts.google.com" not in page.url:
                    log.info(f"✅ رجعنا لـ skills")
                    await self._shot(page, "7️⃣ رجعنا")
                    result["status"] = "success"
                    result["final_url"] = page.url
                    return result

            await self._shot(page, "❓ صفحة غير متوقعة")
            return {"status": "error", "message": "صفحة غير متوقعة."}

        except Exception as e:
            log.error(f"❌ enter_password: {e}", exc_info=True)
            await self._shot(page, f"❌ {str(e)[:100]}")
            return {"status": "error", "message": str(e)[:200]}

    async def resume(self) -> dict:
        page = self.page
        if not page:
            return {"status": "error", "message": "ما كايناش صفحة."}

        try:
            log.info("▶️ نكملو...")
            await page.wait_for_timeout(2000)
            await self._shot(page, "▶️ بعد حلك")

            has_password = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('input[type="password"]')) {
                        if (el.offsetParent !== null) return true;
                    }
                    return false;
                }
            """)
            if has_password:
                return {"status": "password", "message": "صفحة كلمة السر"}

            if await self._has_captcha(page):
                return {"status": "captcha", "message": "مازال CAPTCHA"}

            if "skills.google" in page.url and "accounts.google.com" not in page.url:
                return {"status": "success", "final_url": page.url}

            return {"status": "unknown", "message": "حالة غير معروفة"}

        except Exception as e:
            return {"status": "error", "message": str(e)[:200]}

    async def close(self):
        try:
            await self.page.close()
        except Exception:
            pass
