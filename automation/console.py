"""
automation/console.py
كل خطوات Google Cloud Console — مأخوذة من GC.py + تصوير كل خطوة
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

    # ═══════════════════════════════════════
    # 📸 التصوير
    # ═══════════════════════════════════════

    async def _shot(self, page, caption: str = ""):
        if not self.sender:
            return
        try:
            path = f"/tmp/shot_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=15000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
                    log.info(f"📸 {caption}")
                except Exception as e:
                    log.warning(f"⚠️ reply_photo: {e}")
            import os
            try:
                os.remove(path)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    # ═══════════════════════════════════════
    # STEP 1 — Welcome / TOS الأولى
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        # ✅ كيما GC.py: نستناو networkidle + Enter
        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        await self._shot(page, "3️⃣ صفحة Welcome")

        # ✅ GC.py: keyboard.press("Enter") الأول
        try:
            await page.keyboard.press("Enter")
            log.info("⌨️ Enter pressed")
        except Exception:
            pass

        # ✅ GC.py: locator "text='I understand'"
        try:
            button = page.locator("text='I understand'")
            if await button.is_visible(timeout=3000):
                await button.click()
                log.info("✅ clicked I understand (GC.py way)")
                await self._shot(page, "✅ تم قبول الشروط الأولى")
        except Exception:
            pass

        # ✅ طريقة إضافية: JS
        try:
            target = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                return {
                                    text: (el.innerText || el.value || '').trim(),
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
            if target:
                log.info(f"🎯 '{target['text']}'")
                await page.mouse.move(target['x'] - 100, target['y'] - 50, steps=6)
                await page.wait_for_timeout(150)
                await page.mouse.move(target['x'], target['y'], steps=5)
                await page.wait_for_timeout(200)
                await page.mouse.down()
                await page.wait_for_timeout(100)
                await page.mouse.up()
                log.info("✅ mouse click")
                await self._shot(page, "✅ تم قبول الشروط الأولى")
        except Exception:
            pass

        try:
            await page.wait_for_load_state("networkidle")
        except Exception:
            pass

    # ═══════════════════════════════════════
    # STEP 2 — Terms Dialog (checkbox + Agree)
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        # ✅ كيما GC.py: get_by_role("button", name="Agree and continue")
        agree_btn = page.get_by_role("button", name="Agree and continue")

        try:
            await agree_btn.wait_for(state="visible", timeout=10000)
            log.info("✅ Agree and continue ظهر")
            await self._shot(page, "📋 Terms Dialog")

            # ✅ GC.py: checkboxes.nth(0).click() + nth(1).click()
            checkboxes = page.get_by_role("checkbox")

            # محاولة 1: checkboxes.nth(0) + nth(1)
            try:
                cnt = await checkboxes.count()
                log.info(f"📋 عدد checkboxes: {cnt}")

                if cnt >= 2:
                    await checkboxes.nth(0).click()
                    await asyncio.sleep(1)
                    await checkboxes.nth(1).click()
                    log.info("✅ checkbox nth(0) + nth(1) (GC.py way)")
                elif cnt == 1:
                    await checkboxes.nth(0).click()
                    log.info("✅ checkbox nth(0)")
            except Exception as e:
                log.warning(f"⚠️ checkboxes: {e}")

            await self._shot(page, "✅ checkbox مفعّل")

            # ✅ كيما GC.py: agree_btn.click()
            try:
                await agree_btn.click()
                log.info("✅ Agree and continue clicked (GC.py way)")
            except Exception as e:
                log.warning(f"⚠️ click agree: {e}")
                # JS fallback
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
                await page.wait_for_load_state("domcontentloaded")
            except Exception:
                pass

            await page.wait_for_timeout(2000)
            await self._shot(page, "✅ تم قبول Terms Dialog")

        except Exception as e:
            log.warning(f"⚠️ Terms Dialog ما ظهرش: {e}")
            # نجربو JS fallback
            try:
                has_dialog = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], md-dialog, mat-dialog-container')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree')) return true;
                        }
                        return false;
                    }
                """)
                if has_dialog:
                    log.info("📋 Dialog موجود بـ JS — نجربو checkbox")
                    await page.evaluate("""
                        () => {
                            for (const el of document.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                                if (el.offsetParent === null) continue;
                                try { el.click(); } catch (e) {}
                            }
                        }
                    """)
                    await asyncio.sleep(2)
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
                    await asyncio.sleep(2)
                    await self._shot(page, "✅ تم قبول Terms Dialog (JS)")
            except Exception as e2:
                log.warning(f"⚠️ fallback: {e2}")

    # ═══════════════════════════════════════
    # STEP 3 — Enable API
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        await self._shot(page, "☁️ صفحة تفعيل Cloud Run API")

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        try:
            await expect(enable_btn.or_(manage_btn)).to_be_visible(timeout=15000)
            if await enable_btn.is_visible():
                await enable_btn.click()
                try:
                    await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=90000)
                except Exception:
                    pass
                await self._shot(page, "✅ Cloud Run API مفعّل")
            elif await manage_btn.is_visible():
                log.info("ℹ️ API مفعّل مسبقا")
        except Exception as e:
            raise RuntimeError(f"عطل في زر تفعيل API: {e}")

    # ═══════════════════════════════════════
    # STEP 4 — Create Cloud Run
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        await page.goto(run_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        await self._shot(page, "🚀 صفحة إنشاء Cloud Run")

        # ✅ كيما GC.py: get_by_text("Container Image URL").first.click()
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(image, delay=50)
            log.info("✅ رابط الحاوية (GC.py way)")
            await self._shot(page, "📦 تم إدخال رابط الحاوية")
        except Exception as e:
            raise RuntimeError(f"فشل في الضغط وكتابة الرابط: {e}")

        await page.wait_for_timeout(3000)

        # ✅ كيما GC.py: radios
        try:
            await page.get_by_role("radio", name="Allow public access").click()
            await page.get_by_role("radio", name="Instance-based").click()
            try:
                await page.get_by_role("button", name="Hide").click(timeout=2000)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(1000)

            await self._shot(page, "⚙️ الإعدادات جاهزة")

            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True)
            log.info("✅ Create (GC.py way)")

            await page.wait_for_timeout(1500)
            await self._shot(page, "▶️ تم الضغط على Create")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات أو Create: {e}")

    # ═══════════════════════════════════════
    # STEP 5 — Get URL
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5: نستناو run.app...")

        link_locator = page.locator('a[href*="run.app"]')
        try:
            await link_locator.wait_for(state="visible", timeout=180000)
            final_url = await link_locator.get_attribute("href")
            await self._shot(page, "🎯 Cloud Run جاهز")
            return final_url
        except Exception:
            # fallback: JS
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
                        await self._shot(page, "🎯 Cloud Run جاهز")
                        return url
                except Exception:
                    pass
                await page.wait_for_timeout(3000)
            raise RuntimeError("ما لقيناش رابط run.app")
