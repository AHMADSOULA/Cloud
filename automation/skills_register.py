"""
automation/skills_register.py
تسجيل حساب في skills.google + حل CAPTCHA
"""
import asyncio
import base64
import io
import json
import os
import random
import string
import time
import requests
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("SkillsRegister")


# ═══════════════════════════════════════════
# SCTG CAPTCHA Solver
# ═══════════════════════════════════════════

SCTG_API_KEY = "Uosbi2t23tLFF7D1ro9yyX1EOJ61ER8I"
SCTG_SUBMIT = "https://api.sctg.xyz/in.php"
SCTG_RESULT = "https://api.sctg.xyz/res.php"


def _b64_pad(s):
    return s + ("=" * ((4 - (len(s) % 4)) % 4)) if s else s


def solve_recaptcha_sctg(sitekey: str, pageurl: str) -> str:
    """يحل reCAPTCHA v2 عبر SCTG"""
    try:
        log.info(f"🔍 SCTG solve reCAPTCHA — sitekey={sitekey[:30]}...")
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
        log.info(f"📥 SCTG submit: {data}")

        if data.get("status") != 1:
            log.error(f"❌ SCTG submit فشل: {data}")
            return None

        captcha_id = data.get("request")
        log.info(f"✅ SCTG ID: {captcha_id}")

        for i in range(60):
            time.sleep(5)
            params = {
                "key": SCTG_API_KEY,
                "action": "get",
                "id": captcha_id,
                "json": 1,
            }
            r = requests.get(SCTG_RESULT, params=params, timeout=30)
            data = r.json()

            if data.get("status") == 1:
                solution = data.get("request")
                log.info(f"✅ SCTG حل: {solution[:50]}...")
                return solution
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
# Skills.google Register
# ═══════════════════════════════════════════

class SkillsRegister:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"

    async def _shot(self, page, caption: str = ""):
        if not self.sender:
            return
        try:
            path = f"/tmp/skills_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=8000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
                except Exception:
                    pass
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception:
            pass

    async def register(self, email: str, password: str) -> dict:
        """يفتح skills.google ويسجل"""
        log.info(f"🚀 Skills register — {email}")
        page = await self.context.new_page()
        result = {"success": False, "email": email, "password": password}

        try:
            # ✅ 1. نفتحو الموقع
            await page.goto("https://www.skills.google/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await self._shot(page, "1️⃣ skills.google")

            # ✅ 2. نضغطو Join
            try:
                join_btn = page.get_by_role("link", name="Join")
                if await join_btn.count() == 0:
                    join_btn = page.get_by_role("button", name="Join")
                if await join_btn.count() > 0:
                    await join_btn.first.click()
                    log.info("✅ Join")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                log.warning(f"⚠️ Join: {e}")

            # ✅ 3. نضغطو Continue with email and password
            try:
                email_btn = page.get_by_text("Continue with email and password", exact=False)
                if await email_btn.count() > 0:
                    await email_btn.first.click()
                    log.info("✅ Continue with email")
                    await page.wait_for_timeout(3000)
            except Exception as e:
                log.warning(f"⚠️ Continue with email: {e}")

            await self._shot(page, "2️⃣ Create account page")

            # ✅ 4. نعبّيو الحقول
            first_name = "Ahmed"
            last_name = "VIP"
            await self._fill_field(page, ["First name"], first_name)
            await self._fill_field(page, ["Last name"], last_name)
            await self._fill_field(page, ["Email"], email)
            await self._fill_field(page, ["Password", "Password confirmation"], password)

            # ✅ Date of birth (January 1, 2000)
            try:
                await page.select_option('select', label="January")
            except Exception:
                pass
            await self._fill_field(page, ["Day"], "1")
            await self._fill_field(page, ["Year"], "2000")

            await page.wait_for_timeout(1000)
            await self._shot(page, "3️⃣ الحقول معبأة")

            # ✅ 5. نحلو CAPTCHA
            try:
                sitekey = await page.evaluate("""
                    () => {
                        const recaptcha = document.querySelector('.g-recaptcha, [data-sitekey]');
                        if (recaptcha) {
                            return recaptcha.getAttribute('data-sitekey');
                        }
                        const iframe = document.querySelector('iframe[src*="recaptcha"]');
                        if (iframe) {
                            const src = iframe.src || '';
                            const m = src.match(/[?&]k=([^&]+)/);
                            if (m) return decodeURIComponent(m[1]);
                        }
                        return null;
                    }
                """)

                if sitekey:
                    log.info(f"🔑 sitekey: {sitekey[:40]}...")
                    token = solve_recaptcha_sctg(sitekey, "https://www.skills.google/")
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
                        log.info("✅ CAPTCHA token set")
            except Exception as e:
                log.warning(f"⚠️ CAPTCHA: {e}")

            await page.wait_for_timeout(2000)

            # ✅ 6. نضغطو Create account
            try:
                create_btn = page.get_by_role("button", name="Create account")
                if await create_btn.count() == 0:
                    create_btn = page.get_by_text("Create account", exact=False)
                await create_btn.first.click()
                log.info("✅ Create account clicked")
                await page.wait_for_timeout(5000)
            except Exception as e:
                log.warning(f"⚠️ Create account: {e}")

            await self._shot(page, "4️⃣ بعد Create account")

            # ✅ 7. نتحققو واش نجح
            await page.wait_for_timeout(3000)
            current_url = page.url
            if "skills.google" in current_url and "sign" not in current_url and "users" not in current_url:
                result["success"] = True
                log.info("✅ تسجيل نجح")
            else:
                log.warning(f"⚠️ ما تسجلش — URL: {current_url}")

        except Exception as e:
            log.error(f"❌ register: {e}", exc_info=True)
            await self._shot(page, f"❌ فشل: {str(e)[:100]}")

        finally:
            try:
                await page.close()
            except Exception:
                pass

        return result

    async def _fill_field(self, page, labels, value):
        """يعبي حقل من labels"""
        for label in labels:
            try:
                inp = page.get_by_label(label, exact=False).first
                if await inp.count() > 0:
                    await inp.click()
                    await inp.fill("")
                    await page.wait_for_timeout(200)
                    await inp.fill(value)
                    log.info(f"✅ {label}: {value}")
                    return True
            except Exception:
                pass

        for label in labels:
            try:
                inp = page.locator(f'input[placeholder*="{label}" i]').first
                if await inp.count() > 0:
                    await inp.click()
                    await inp.fill(value)
                    return True
            except Exception:
                pass
        return False
