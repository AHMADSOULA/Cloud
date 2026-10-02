"""
automation/console.py
كل خطوات Google Cloud Console — مأخوذة من GC.py + سريع
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
            await page.screenshot(path=path, full_page=False, timeout=10000)
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
    # STEP 1 — كيما GC.py
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(1500)

        # ✅ GC.py: keyboard.press("Enter")
        try:
            await page.keyboard.press("Enter")
        except Exception:
            pass

        # ✅ GC.py: locator("text='I understand'")
        try:
            button = page.locator("text='I understand'")
            if await button.is_visible(timeout=3000):
                await button.click()
                log.info("✅ clicked I understand (GC.py)")
        except Exception:
            pass

        # ✅ إضافي: JS click
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
                log.info(f"✅ TOS JS: {clicked}")
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 2 — كيما GC.py
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        # ✅ GC.py: get_by_role("button", name="Agree and continue")
        agree_btn = page.get_by_role("button", name="Agree and continue")

        try:
            await agree_btn.wait_for(state="visible", timeout=10000)
            log.info("✅ Agree and continue ظهر")

            # ✅ GC.py: checkboxes.nth(0) + nth(1)
            checkboxes = page.get_by_role("checkbox")
            try:
                cnt = await checkboxes.count()
                log.info(f"📋 عدد checkboxes: {cnt}")

                if cnt >= 2:
                    await checkboxes.nth(0).click()
                    await asyncio.sleep(0.5)
                    await checkboxes.nth(1).click()
                    log.info("✅ checkbox nth(0)+nth(1) (GC.py)")
                elif cnt == 1:
                    await checkboxes.nth(0).click()
                    log.info("✅ checkbox nth(0)")
            except Exception as e:
                log.warning(f"⚠️ checkboxes: {e}")

            # ✅ GC.py: agree_btn.click()
            try:
                await agree_btn.click()
                log.info("✅ Agree and continue clicked (GC.py)")
            except Exception as e:
                log.warning(f"⚠️ click agree: {e}")
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('agree and continue')) {
                                try { el.disabled = false; el.click(); } catch (e) {}
                            }
                        }
                    }
                """)

            try:
                await page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass

            await page.wait_for_timeout(1500)

        except Exception as e:
            log.warning(f"⚠️ Terms Dialog ما ظهرش: {e}")
            # fallback: JS
            try:
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            try { el.click(); } catch (e) {}
                        }
                    }
                """)
                await asyncio.sleep(1)
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('agree and continue')) {
                                try { el.disabled = false; el.click(); } catch (e) {}
                            }
                        }
                    }
                """)
                await asyncio.sleep(1)
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 3 — كيما GC.py
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        log.info("🚀 step3: Enable API")

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # فحص Sign in
        try:
            if "accounts.google.com" in page.url.lower():
                log.warning("⚠️ sign in — نتجاوزو")
                return
        except Exception:
            pass

        # ✅ GC.py: get_by_role
        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        try:
            await expect(enable_btn.or_(manage_btn)).to_be_visible(timeout=10000)
            if await enable_btn.is_visible():
                await enable_btn.click()
                try:
                    await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=45000)
                except Exception:
                    pass
                log.info("✅ Enable clicked (GC.py)")
            elif await manage_btn.is_visible():
                log.info("ℹ️ API مفعّل مسبقا")
        except Exception as e:
            log.warning(f"⚠️ step3 فشل (نكملو): {e}")

    # ═══════════════════════════════════════
    # STEP 4 — كيما GC.py + screenshot عند Create
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info("🌐 step4: Create Cloud Run")

        await page.goto(run_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        # ✅ GC.py: get_by_text("Container Image URL").first.click()
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(image, delay=50)
            log.info("✅ رابط الحاوية (GC.py)")
        except Exception as e:
            raise RuntimeError(f"فشل في الضغط وكتابة الرابط: {e}")

        await page.wait_for_timeout(3000)

        # ✅ GC.py: radios + Create
        try:
            await page.get_by_role("radio", name="Allow public access").click()
            await page.get_by_role("radio", name="Instance-based").click()
            try:
                await page.get_by_role("button", name="Hide").click(timeout=2000)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)

            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True)
            log.info("✅ Create (GC.py)")

            await page.wait_for_timeout(1500)
            await self._shot(page, "🚀 بعد الضغط على Create")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات: {e}")

    # ═══════════════════════════════════════
    # STEP 5 — كيما GC.py: locator على نفس الصفحة
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5: نستناو run.app (GC.py)")

        # ✅ GC.py: locator('a[href*="run.app"]') مع timeout
        link_locator = page.locator('a[href*="run.app"]')
        try:
            await link_locator.wait_for(state="visible", timeout=120000)
            final_url = await link_locator.get_attribute("href")
            log.info(f"✅ لقيناه: {final_url}")
            return final_url
        except Exception:
            # fallback: JS
            for i in range(40):  # 40 × 3s = 120s
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
                        log.info(f"✅ لقيناه (JS): {url}")
                        return url
                except Exception:
                    pass
                await page.wait_for_timeout(3000)

            raise RuntimeError("ما لقيناش رابط run.app")
