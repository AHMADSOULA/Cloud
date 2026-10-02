"""
automation/console.py
كل خطوات Google Cloud Console — سريع + step3 اختياري بدون انتظار
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None, user_tag=None):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"

    async def _shot(self, page, caption: str = ""):
        if not self.sender:
            return
        try:
            path = f"/tmp/err_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=f"❌ {caption}"[:1000])
                except Exception:
                    pass
            import os
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 1 — سريع
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1")

        await page.wait_for_timeout(1500)

        try:
            is_tos = await page.evaluate("""
                () => {
                    const url = window.location.href.toLowerCase();
                    if (url.includes('workspacetermsofservice') || url.includes('speedbump')) return true;
                    const text = (document.body.innerText || '').toLowerCase();
                    if (text.includes('welcome to your new account')) return true;
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('i understand')) return true;
                    }
                    return false;
                }
            """)
        except Exception:
            return

        if not is_tos:
            return

        try:
            await page.keyboard.press("Enter")
        except Exception:
            pass

        try:
            clicked = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                    }
                    return null;
                }
            """)
            if clicked:
                log.info(f"✅ TOS: {clicked}")
        except Exception:
            pass

        await page.wait_for_timeout(1000)

    # ═══════════════════════════════════════
    # STEP 2 — سريع
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2")

        # فحص سريع — 3 محاولات × 500ms
        has_dialog = False
        for _ in range(3):
            try:
                has_dialog = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], md-dialog, mat-dialog-container, .cdk-overlay-pane')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree')) return true;
                        }
                        return false;
                    }
                """)
                if has_dialog:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(500)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 Dialog")

        # JS click على checkbox + Agree مرة وحدة
        try:
            result = await page.evaluate("""
                () => {
                    const out = { checkbox: false, agree: false };

                    for (const el of document.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"], .mdc-checkbox')) {
                        if (el.offsetParent === null) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.width > 200) continue;
                        try {
                            el.click();
                            const inner = el.querySelector('input');
                            if (inner) inner.click();
                            out.checkbox = true;
                        } catch (e) {}
                        break;
                    }

                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('agree and continue') || t === 'agree') {
                            try {
                                el.disabled = false;
                                el.removeAttribute('disabled');
                                el.removeAttribute('aria-disabled');
                                el.click();
                                out.agree = true;
                            } catch (e) {}
                            break;
                        }
                    }
                    return out;
                }
            """)
            log.info(f"✅ Dialog: {result}")
        except Exception as e:
            log.warning(f"⚠️ {e}")

        await page.wait_for_timeout(1200)

    # ═══════════════════════════════════════
    # STEP 3 — سريع (اختياري: إذا ما لقاش زر يتخطاه فورا)
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        log.info("🚀 step3")

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )

        try:
            await page.goto(api_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            raise RuntimeError(f"goto: {e}")

        # ✅ نستناو فقط 2 ثواني
        await page.wait_for_timeout(2000)

        # ✅ فحص Sign in
        try:
            if "accounts.google.com" in page.url.lower():
                log.warning("⚠️ sign in — نتجاوزو")
                return  # ✅ ما نطيحوش، نكملو
        except Exception:
            pass

        # ✅ فحص سريع لزر Enable/Manage — 3 محاولات × 500ms فقط
        clicked = None
        for _ in range(3):
            try:
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'enable' || t === 'manage') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if clicked:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(500)

        if clicked:
            log.info(f"✅ API: {clicked}")
            await page.wait_for_timeout(1500)
        else:
            log.warning("⚠️ ما لقيناش زر — نتجاوزو")
            return  # ✅ ما نطيحوش، نكملو

    # ═══════════════════════════════════════
    # STEP 4 — سريع
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info("🌐 step4")

        try:
            await page.goto(run_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            try:
                await page.goto(run_url, wait_until="commit", timeout=60000)
            except Exception:
                pass

        # نستناو الحقل — 20s
        try:
            await page.wait_for_selector('text="Container Image URL"', timeout=20000)
        except Exception:
            log.warning("⚠️ الحقل ما ظهرش")

        await page.wait_for_timeout(1000)

        # نكتبو الرابط
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click(timeout=5000)
            await page.wait_for_timeout(200)
            await page.keyboard.type(image, delay=20)
            log.info("✅ رابط الحاوية")
        except Exception:
            try:
                await page.keyboard.type(image, delay=20)
                log.info("✅ رابط الحاوية (fallback)")
            except Exception as e2:
                raise RuntimeError(f"فشل: {e2}")

        await page.wait_for_timeout(1000)

        # إعدادات + Create
        try:
            try:
                await page.get_by_role("radio", name="Allow public access").click(timeout=5000)
            except Exception:
                pass
            try:
                await page.get_by_role("radio", name="Instance-based").click(timeout=5000)
            except Exception:
                pass
            try:
                await page.get_by_role("button", name="Hide").click(timeout=1500)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(500)

            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True, timeout=5000)
            log.info("✅ Create")
        except Exception as e:
            raise RuntimeError(f"فشل: {e}")

    # ═══════════════════════════════════════
    # STEP 5 — سريع: يروح مباشرة لـ services
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5")

        services_url = "https://console.cloud.google.com/run"

        # ✅ أول حاجة: نروحو مباشرة لـ services
        try:
            await page.goto(services_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)
        except Exception:
            pass

        # 20 محاولة × 3s = 60s
        for i in range(20):
            try:
                url = await page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a');
                        for (const a of links) {
                            const href = a.href || '';
                            if (href.includes('.run.app')) return href.split('?')[0].split('#')[0];
                        }
                        return null;
                    }
                """)
                if url:
                    log.info(f"✅ {url}")
                    return url
            except Exception:
                pass

            await page.wait_for_timeout(3000)

            if (i + 1) % 5 == 0:
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass

        raise RuntimeError("ما لقيناش رابط run.app")
