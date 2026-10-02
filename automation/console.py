"""
automation/console.py
كل خطوات Google Cloud Console — سريع (بلا تصوير)
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
        return  # معطّل

    # ═══════════════════════════════════════
    # STEP 1 — سريع
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: TOS")

        await page.wait_for_timeout(1500)

        # فحص سريع: واش في TOS؟
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
            log.info("ℹ️ ماشي TOS — نتجاوزو")
            return

        # ✅ Enter
        try:
            await page.keyboard.press("Enter")
        except Exception:
            pass

        # ✅ JS click على الزر
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
                log.info(f"✅ TOS clicked: {clicked}")
        except Exception as e:
            log.warning(f"⚠️ {e}")

        await page.wait_for_timeout(1500)

    # ═══════════════════════════════════════
    # STEP 2 — سريع (بلا انتظار طويل)
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        # ✅ فحص سريع: واش Dialog موجود؟
        has_dialog = False
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
        except Exception:
            pass

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog — نتجاوزو")
            return

        log.info("📋 لقينا Dialog")

        # ✅ JS: نحولو نضغطو checkbox + زر Agree مرة وحدة
        try:
            result = await page.evaluate("""
                () => {
                    const out = { checkbox: false, agree: false };

                    // checkbox
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

                    // زر Agree
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

        # نستناو شوية
        await page.wait_for_timeout(2000)

        # ✅ فحص أخير
        try:
            still_open = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('[role="dialog"], md-dialog, mat-dialog-container')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('terms of service') || t.includes('i agree')) return true;
                    }
                    return false;
                }
            """)
            if still_open:
                log.warning("⚠️ مازال مفتوح — إعادة محاولة")
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            try {
                                el.click();
                                const inner = el.querySelector('input');
                                if (inner) inner.click();
                            } catch (e) {}
                        }
                        setTimeout(() => {
                            for (const el of document.querySelectorAll('button, [role="button"]')) {
                                const t = (el.innerText || '').trim().toLowerCase();
                                if (t.includes('agree')) {
                                    try {
                                        el.disabled = false;
                                        el.click();
                                    } catch (e) {}
                                }
                            }
                        }, 500);
                    }
                """)
                await page.wait_for_timeout(2000)
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 3 — سريع (اختياري)
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        log.info("🚀 step3: Enable API")

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )

        try:
            await page.goto(api_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log.warning(f"⚠️ goto: {e}")
            raise RuntimeError(f"فشل فتح API: {e}")

        await page.wait_for_timeout(2000)

        # ✅ فحص سريع: واش في Sign in؟
        try:
            url_now = page.url.lower()
            if "accounts.google.com" in url_now:
                log.warning("⚠️ رجعنا لـ sign in")
                raise RuntimeError("رجعنا لـ sign in")
        except Exception as e:
            if "sign in" in str(e):
                raise

        # ✅ نحاولو نضغطو Enable/Manage
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
                log.info(f"✅ API clicked: {clicked}")
                await page.wait_for_timeout(3000)
            else:
                log.warning("⚠️ ما لقيناش Enable/Manage")
                raise RuntimeError("ما لقيناش زر Enable/Manage")
        except Exception as e:
            raise RuntimeError(f"step3: {e}")

    # ═══════════════════════════════════════
    # STEP 4 — سريع
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info("🌐 Create Cloud Run")

        # ✅ goto مع timeout معقول
        try:
            await page.goto(run_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            log.warning(f"⚠️ goto: {e}")
            try:
                await page.goto(run_url, wait_until="commit", timeout=60000)
            except Exception:
                pass

        # ✅ نستناو الحقل يظهر — 30s
        try:
            await page.wait_for_selector('text="Container Image URL"', timeout=30000)
            log.info("✅ Container Image URL ظهر")
        except Exception:
            log.warning("⚠️ الحقل ما ظهرش — نكملو")

        await page.wait_for_timeout(1500)

        # ✅ نكتبو الرابط
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click(timeout=5000)
            await page.wait_for_timeout(300)
            await page.keyboard.type(image, delay=30)
            log.info("✅ رابط الحاوية")
        except Exception as e:
            # fallback
            try:
                await page.keyboard.type(image, delay=30)
                log.info("✅ رابط الحاوية (fallback)")
            except Exception as e2:
                raise RuntimeError(f"فشل كتابة الرابط: {e2}")

        await page.wait_for_timeout(1500)

        # ✅ إعدادات + Create
        try:
            # radios
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

            # Create
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True, timeout=5000)
            log.info("✅ Create")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات: {e}")

    # ═══════════════════════════════════════
    # STEP 5 — انتظار رابط النشر
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5: نستناو run.app...")

        for i in range(60):  # 60 × 3s = 180s
            try:
                url = await page.evaluate("""
                    () => {
                        const links = document.querySelectorAll('a');
                        for (const a of links) {
                            const href = a.href || '';
                            if (href.includes('.run.app')) return href.split('?')[0].split('#')[0];
                        }
                        const body = document.body.innerText || '';
                        const m = body.match(/https:\\/\\/[a-zA-Z0-9\\-]+\\.run\\.app/);
                        if (m) return m[0];
                        return null;
                    }
                """)
                if url:
                    log.info(f"✅ لقيناه: {url}")
                    return url
            except Exception:
                pass

            await page.wait_for_timeout(3000)

            if (i + 1) % 10 == 0:
                log.info(f"⏳ مازال... ({(i+1)*3}s)")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass

        raise RuntimeError("ما لقيناش رابط run.app")
