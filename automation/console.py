"""
automation/console.py
كل خطوات Google Cloud Console — سريع جدا + region تلقائي
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
            path = f"/tmp/shot_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=8000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
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
    # STEP 1
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1")
        await page.wait_for_timeout(1200)

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
            await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                try { el.click(); return; } catch (e) {}
                            }
                        }
                    }
                }
            """)
        except Exception:
            pass

        await page.wait_for_timeout(800)

    # ═══════════════════════════════════════
    # STEP 2
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2")

        has_dialog = False
        for _ in range(4):
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
            return

        try:
            await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"], .mdc-checkbox')) {
                        if (el.offsetParent === null) continue;
                        try { el.click(); const i = el.querySelector('input'); if (i) i.click(); } catch (e) {}
                    }
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        const t = (el.innerText || '').trim().toLowerCase();
                        if (t.includes('agree and continue') || t === 'agree') {
                            try { el.disabled = false; el.click(); } catch (e) {}
                        }
                    }
                }
            """)
        except Exception:
            pass

        await page.wait_for_timeout(1200)

    # ═══════════════════════════════════════
    # STEP 3
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

        await page.wait_for_timeout(1500)

        try:
            if "accounts.google.com" in page.url.lower():
                return
        except Exception:
            pass

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
            await page.wait_for_timeout(400)

        if clicked:
            await page.wait_for_timeout(1500)

    # ═══════════════════════════════════════
    # STEP 4
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image, region="us-central1"):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}&region={region}"
        )
        log.info(f"🌐 step4 — region={region}")

        try:
            await page.goto(run_url, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            try:
                await page.goto(run_url, wait_until="commit", timeout=45000)
            except Exception:
                pass

        try:
            await page.wait_for_selector('text="Container Image URL"', timeout=20000)
        except Exception:
            pass

        await page.wait_for_timeout(1200)

        try:
            label = page.get_by_text("Container Image URL").first
            await label.click(timeout=5000)
            await page.wait_for_timeout(200)
            await page.keyboard.type(image, delay=20)
        except Exception:
            try:
                await page.keyboard.type(image, delay=20)
            except Exception as e:
                raise RuntimeError(f"فشل: {e}")

        await page.wait_for_timeout(800)

        try:
            region_current = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('input[aria-label*="Region" i], [role="combobox"][aria-label*="Region" i]')) {
                        if (el.offsetParent === null) continue;
                        return el.value || '';
                    }
                    return null;
                }
            """)
            if not region_current or region not in (region_current or ""):
                try:
                    inp = page.locator('input[aria-label*="Region" i], [role="combobox"][aria-label*="Region" i]').first
                    if await inp.count() > 0:
                        await inp.click()
                        await page.wait_for_timeout(400)
                        await page.keyboard.press("Control+A")
                        await page.keyboard.type(region, delay=30)
                        await page.wait_for_timeout(600)
                        await page.keyboard.press("Enter")
                except Exception:
                    pass
        except Exception:
            pass

        await page.wait_for_timeout(800)

        try:
            await page.get_by_role("radio", name="Allow public access").click(timeout=5000)
        except Exception:
            pass
        try:
            await page.get_by_role("radio", name="Instance-based").click(timeout=5000)
        except Exception:
            pass
        try:
            await page.get_by_role("button", name="Hide").click(timeout=1200)
        except Exception:
            pass

        await page.keyboard.press("End")
        await page.wait_for_timeout(400)

        try:
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True, timeout=5000)
        except Exception as e:
            try:
                clicked = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t === 'create' || t === 'deploy') {
                                try { el.click(); return t; } catch (e) {}
                            }
                        }
                        return null;
                    }
                """)
                if not clicked:
                    raise RuntimeError(f"فشل Create: {e}")
            except Exception as e2:
                raise RuntimeError(f"فشل Create: {e2}")

    # ═══════════════════════════════════════
    # STEP 5
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5")

        for i in range(60):
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
                    return url
            except Exception:
                pass
            await page.wait_for_timeout(1000)

        raise RuntimeError("ما لقيناش رابط run.app")
