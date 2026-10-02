"""
automation/console.py
كل خطوات Google Cloud Console — مأخوذة من GC.py
مع تصوير في المراحل المهمة
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None):
        self.context = context
        self.sender = sender  # رسالة Telegram باش نبعثو الصور

    # ═══════════════════════════════════════
    # 📸 أداة التصوير
    # ═══════════════════════════════════════

    async def _shot(self, page, caption: str = ""):
        """يصور الصفحة ويبعثها في Telegram"""
        if not self.sender:
            return
        try:
            path = f"/tmp/shot_{int(asyncio.get_event_loop().time()*1000)}.png"
            await page.screenshot(path=path, full_page=False, timeout=15000)
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
        except Exception as e:
            log.warning(f"⚠️ _shot: {e}")

    # ═══════════════════════════════════════
    # STEP 1: TOS الأولى (زر I understand)
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)

        # 📸 نصور الوصول لصفحة Welcome
        await self._shot(page, "3️⃣ صفحة Welcome")

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
        except Exception as e:
            log.warning(f"⚠️ evaluate فشل: {e}")
            return

        if not is_tos:
            log.info("ℹ️ ماشي TOS — نتجاوزو")
            return

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
        except Exception as e:
            log.warning(f"⚠️ search فشل: {e}")
            return

        if not target:
            log.warning("⚠️ ما لقيناش الزر")
            await self._shot(page, "⚠️ ما لقيناش زر I understand")
            return

        log.info(f"🎯 '{target['text']}' @({target['x']},{target['y']})")

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({target['x']}, {target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(800)

            target2 = await page.evaluate("""
                () => {
                    const kws = ['i understand', 'agree and continue', 'accept'];
                    for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                        if (el.offsetParent === null || el.disabled) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                return {
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
            if target2:
                target['x'] = target2['x']
                target['y'] = target2['y']

            await page.mouse.move(target['x'] - 150, target['y'] - 80, steps=12)
            await page.wait_for_timeout(300)
            await page.mouse.move(target['x'] - 50, target['y'] - 20, steps=10)
            await page.wait_for_timeout(300)
            await page.mouse.move(target['x'], target['y'], steps=8)
            await page.wait_for_timeout(500)
            await page.mouse.down()
            await page.wait_for_timeout(120)
            await page.mouse.up()
            log.info("✅ mouse click")

        except Exception as e:
            log.warning(f"❌ mouse فشل: {e}")
            try:
                await page.get_by_role("button", name="I understand").click(timeout=5000)
            except Exception:
                pass

        # نستناو الزر يختفي
        gone = False
        for i in range(20):
            await page.wait_for_timeout(2000)
            try:
                gone = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, a, [role="button"]')) {
                            if (el.offsetParent === null || el.disabled) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('i understand') || t.includes('agree and continue')) return false;
                        }
                        return true;
                    }
                """)
                if gone:
                    log.info(f"✅ TOS اختفت ~{(i+1)*2}s")
                    break
            except Exception:
                log.info(f"⏳ {i+1}")

        if gone:
            await self._shot(page, "✅ تم قبول الشروط الأولى")

        log.info("✅ step1 انتهى")

    # ═══════════════════════════════════════
    # STEP 2: Terms Dialog
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        try:
            has_dialog = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('terms of service') && (t.includes('agree') || t.includes('i agree'))) {
                            return true;
                        }
                    }
                    return false;
                }
            """)
        except Exception as e:
            log.warning(f"⚠️ evaluate فشل: {e}")
            return

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 لقينا Dialog")
        # 📸 نصور Terms Dialog
        await self._shot(page, "📋 Terms Dialog")

        # checkbox
        try:
            checkbox_info = await page.evaluate("""
                () => {
                    const containers = [
                        ...document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog'),
                        document.body
                    ];
                    for (const container of containers) {
                        for (const el of container.querySelectorAll('input[type="checkbox"], [role="checkbox"], mat-checkbox')) {
                            if (el.offsetParent === null) continue;
                            const parent = el.closest('label, div, mat-checkbox') || el.parentElement;
                            const txt = (parent?.innerText || '').toLowerCase();
                            if (txt.includes('i agree') || txt.includes('terms of service') || txt.includes('cloud platform')) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0 || rect.height === 0) continue;
                                return {
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                    checked: el.checked || el.getAttribute('aria-checked') === 'true',
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
        except Exception:
            checkbox_info = None

        if checkbox_info and not checkbox_info['checked']:
            log.info(f"📋 checkbox @({checkbox_info['x']},{checkbox_info['y']})")
            try:
                await page.mouse.move(checkbox_info['x'] - 40, checkbox_info['y'] - 40, steps=10)
                await page.wait_for_timeout(300)
                await page.mouse.move(checkbox_info['x'], checkbox_info['y'], steps=8)
                await page.wait_for_timeout(300)
                await page.mouse.down()
                await page.wait_for_timeout(120)
                await page.mouse.up()
                log.info("✅ checkbox mouse")
                await page.wait_for_timeout(2000)

                try:
                    checked_now = await page.evaluate("""
                        () => {
                            for (const el of document.querySelectorAll('input[type="checkbox"], [role="checkbox"], mat-checkbox')) {
                                if (el.offsetParent === null) continue;
                                const parent = el.closest('label, div, mat-checkbox') || el.parentElement;
                                const txt = (parent?.innerText || '').toLowerCase();
                                if (txt.includes('i agree') || txt.includes('terms of service')) {
                                    return el.checked || el.getAttribute('aria-checked') === 'true';
                                }
                            }
                            return false;
                        }
                    """)
                except Exception:
                    checked_now = False

                if not checked_now:
                    for sel in ['mat-checkbox', '[role="dialog"] input[type="checkbox"]', '[role="dialog"] [role="checkbox"]']:
                        try:
                            el = page.locator(sel).first
                            if await el.count() > 0 and await el.is_visible():
                                await el.click(force=True, timeout=3000)
                                log.info("✅ Playwright checkbox")
                                break
                        except Exception:
                            continue
                    await page.wait_for_timeout(1500)
            except Exception as e:
                log.warning(f"❌ checkbox: {e}")

        await page.wait_for_timeout(1500)

        # زر Agree
        try:
            agree_target = await page.evaluate("""
                () => {
                    const kws = ['agree and continue', 'i agree', 'accept', 'agree'];
                    for (const el of document.querySelectorAll('button, [role="button"], input[type="submit"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || el.value || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t === kw || t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0 || rect.height === 0) continue;
                                const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
                                return {
                                    text: (el.innerText || el.value || '').trim(),
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                    disabled: disabled,
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
        except Exception:
            return

        if not agree_target:
            log.warning("⚠️ ما لقيناش Agree")
            return

        log.info(f"🎯 Agree: '{agree_target['text']}' dis={agree_target['disabled']}")

        if agree_target['disabled']:
            for _ in range(5):
                await page.wait_for_timeout(1500)
                try:
                    agree_target = await page.evaluate("""
                        () => {
                            const kws = ['agree and continue', 'i agree', 'accept', 'agree'];
                            for (const el of document.querySelectorAll('button, [role="button"]')) {
                                if (el.offsetParent === null) continue;
                                const t = (el.innerText || '').trim().toLowerCase();
                                for (const kw of kws) {
                                    if (t === kw || t.includes(kw)) {
                                        const rect = el.getBoundingClientRect();
                                        const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
                                        return {
                                            x: Math.round(rect.x + rect.width / 2),
                                            y: Math.round(rect.y + rect.height / 2),
                                            disabled: disabled,
                                        };
                                    }
                                }
                            }
                            return null;
                        }
                    """)
                except Exception:
                    break
                if agree_target and not agree_target.get('disabled'):
                    break

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({agree_target['x']}, {agree_target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(1000)

            target2 = await page.evaluate("""
                () => {
                    const kws = ['agree and continue', 'i agree', 'accept'];
                    for (const el of document.querySelectorAll('button, [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        for (const kw of kws) {
                            if (t === kw || t.includes(kw)) {
                                const rect = el.getBoundingClientRect();
                                return {
                                    x: Math.round(rect.x + rect.width / 2),
                                    y: Math.round(rect.y + rect.height / 2),
                                };
                            }
                        }
                    }
                    return null;
                }
            """)
            if target2:
                agree_target['x'] = target2['x']
                agree_target['y'] = target2['y']

            await page.mouse.move(agree_target['x'] - 100, agree_target['y'] - 50, steps=10)
            await page.wait_for_timeout(300)
            await page.mouse.move(agree_target['x'], agree_target['y'], steps=8)
            await page.wait_for_timeout(400)
            await page.mouse.down()
            await page.wait_for_timeout(120)
            await page.mouse.up()
            log.info("✅ Agree mouse")

        except Exception as e:
            log.warning(f"❌ Agree mouse: {e}")
            for sel in ['button:has-text("Agree and continue")', 'button:has-text("I agree")', 'button:has-text("Agree")']:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click(force=True, timeout=5000)
                        break
                except Exception:
                    continue

        # نستناو Dialog يختفي
        gone = False
        for i in range(15):
            await page.wait_for_timeout(2000)
            try:
                gone = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') && t.includes('agree')) return false;
                        }
                        return true;
                    }
                """)
                if gone:
                    log.info(f"✅ Dialog اختفت ~{(i+1)*2}s")
                    break
            except Exception:
                log.info(f"⏳ {i+1}")

        if gone:
            await self._shot(page, "✅ تم قبول Terms Dialog")

        log.info("✅ step2 انتهى")

    # ═══════════════════════════════════════
    # STEP 3: Enable API — مع معالجة قوية
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 Enable API — URL: {api_url[:150]}")
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # 📸 نصور وصول Cloud Console
        await self._shot(page, "☁️ وصلنا Google Cloud Console")

        # ✅ نسجل URL الحالي
        try:
            current_url = page.url
            log.info(f"📍 URL الحالي: {current_url[:150]}")
        except Exception:
            pass

        # ✅ نتحققو بلي الصفحة ماشي login/TOS
        try:
            is_blocked = await page.evaluate("""
                () => {
                    const url = window.location.href.toLowerCase();
                    if (url.includes('accounts.google.com') ||
                        url.includes('workspacetermsofservice') ||
                        url.includes('speedbump')) {
                        return url;
                    }
                    const body = (document.body.innerText || '').toLowerCase();
                    if (body.includes('sign in') && body.includes('google')) return 'signin';
                    return null;
                }
            """)
            if is_blocked:
                raise RuntimeError(f"⛔ الصفحة محجوبة — {is_blocked}")
        except Exception as e:
            log.warning(f"⚠️ فحص الحجب: {e}")

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        found = False
        for attempt in range(30):
            try:
                if await enable_btn.count() > 0 and await enable_btn.is_visible():
                    log.info("✅ لقينا زر Enable")
                    await enable_btn.click()
                    log.info("🔄 ضغطنا Enable — نستناو Manage")
                    try:
                        await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=120000)
                        log.info("✅ API مفعّل")
                        await self._shot(page, "✅ Cloud Run API مفعّل")
                    except Exception as e:
                        log.warning(f"⚠️ ما ظهرش Manage بعد Enable: {e}")
                    found = True
                    break

                if await manage_btn.count() > 0 and await manage_btn.is_visible():
                    log.info("ℹ️ API مفعّل من قبل (Manage visible)")
                    found = True
                    break
            except Exception as e:
                log.warning(f"⚠️ محاولة {attempt+1}: {e}")

            await page.wait_for_timeout(2000)

        if not found:
            try:
                info = await page.evaluate("""
                    () => {
                        const url = window.location.href;
                        const buttons = [];
                        for (const el of document.querySelectorAll('button, [role="button"], a')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 50) buttons.push(t);
                        }
                        return { url, buttons: buttons.slice(0, 30) };
                    }
                """)
                log.error(f"❌ ما لقيناش زر Enable/Manage")
                log.error(f"📍 URL: {info.get('url', '')[:200]}")
                log.error(f"🔘 الأزرار: {info.get('buttons', [])}")
            except Exception:
                pass
            await self._shot(page, "❌ ما لقيناش زر Enable")
            raise RuntimeError("ما لقيناش زر Enable ولا Manage بعد 60 ثانية")

    # ═══════════════════════════════════════
    # STEP 4: Create Cloud Run
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 Create Cloud Run")
        await page.goto(run_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)

        # 📸 نصور صفحة Cloud Run
        await self._shot(page, "🚀 صفحة إنشاء Cloud Run")

        try:
            label = page.get_by_text("Container Image URL").first
            await label.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(image, delay=50)
            log.info("✅ رابط الحاوية")
            await self._shot(page, "📦 تم إدخال رابط الحاوية")
        except Exception as e:
            raise RuntimeError(f"فشل كتابة الرابط: {str(e)}")

        await page.wait_for_timeout(3000)

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
            log.info("✅ Create")
            await self._shot(page, "▶️ تم الضغط على Create")
        except Exception as e:
            raise RuntimeError(f"فشل الإعدادات: {str(e)}")

    # ═══════════════════════════════════════
    # STEP 5: Get URL
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        link_locator = page.locator('a[href*="run.app"]')
        await link_locator.wait_for(state="visible", timeout=180000)
        final_url = await link_locator.get_attribute("href")
        log.info(f"✅ URL: {final_url}")
        await self._shot(page, "🎯 Cloud Run جاهز")
        return final_url
