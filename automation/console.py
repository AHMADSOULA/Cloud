"""
automation/console.py
كل خطوات Google Cloud Console — مع تصوير في المراحل المهمة
+ معالجة قوية لـ Terms Dialog (4 استراتيجيات للـ checkbox)
"""
import asyncio
from playwright.async_api import expect
from utils.logger import get_logger

log = get_logger("Console")


class CloudConsole:
    def __init__(self, context, sender=None):
        self.context = context
        self.sender = sender

    # ═══════════════════════════════════════
    # 📸 أداة التصوير
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
    # STEP 1: TOS الأولى
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)

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
    # STEP 2: Terms Dialog — نسخة قوية
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        # ✅ نستناو الـ Dialog يظهر
        has_dialog = False
        for _ in range(10):
            try:
                has_dialog = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree to')) {
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                if has_dialog:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1000)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 لقينا Dialog")
        await self._shot(page, "📋 Terms Dialog")

        # ═══════════════════════════════════════
        # ✅ نلقاو الـ checkbox — 4 استراتيجيات
        # ═══════════════════════════════════════

        checkbox_info = None
        try:
            checkbox_info = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                    for (const dialog of dialogs) {
                        if (dialog.offsetParent === null) continue;

                        // 1: input[type=checkbox]
                        for (const el of dialog.querySelectorAll('input[type="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return {
                                x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2),
                                checked: el.checked,
                                kind: 'input',
                            };
                        }

                        // 2: [role=checkbox]
                        for (const el of dialog.querySelectorAll('[role="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return {
                                x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2),
                                checked: el.getAttribute('aria-checked') === 'true',
                                kind: 'role',
                            };
                        }

                        // 3: mat-checkbox
                        for (const el of dialog.querySelectorAll('mat-checkbox')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return {
                                x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2),
                                checked: el.classList.contains('mat-checkbox-checked'),
                                kind: 'mat',
                            };
                        }

                        // 4: أي عنصر فيه class checkbox
                        for (const el of dialog.querySelectorAll('[class*="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            if (rect.width > 50) continue;
                            return {
                                x: Math.round(rect.x + rect.width / 2),
                                y: Math.round(rect.y + rect.height / 2),
                                checked: (el.className || '').includes('checked'),
                                kind: 'class',
                            };
                        }
                    }
                    return null;
                }
            """)
        except Exception as e:
            log.warning(f"⚠️ checkbox evaluate: {e}")

        if checkbox_info and not checkbox_info['checked']:
            log.info(f"📋 checkbox [{checkbox_info['kind']}] @({checkbox_info['x']},{checkbox_info['y']})")
            try:
                await page.mouse.move(checkbox_info['x'] - 40, checkbox_info['y'] - 40, steps=8)
                await page.wait_for_timeout(300)
                await page.mouse.move(checkbox_info['x'], checkbox_info['y'], steps=8)
                await page.wait_for_timeout(400)
                await page.mouse.down()
                await page.wait_for_timeout(150)
                await page.mouse.up()
                log.info("✅ mouse click على checkbox")
                await page.wait_for_timeout(2500)

                checked_now = await page.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                        for (const dialog of dialogs) {
                            if (dialog.offsetParent === null) continue;
                            for (const el of dialog.querySelectorAll('input[type="checkbox"]')) {
                                if (el.offsetParent === null) continue;
                                if (el.checked) return true;
                            }
                            for (const el of dialog.querySelectorAll('[role="checkbox"]')) {
                                if (el.offsetParent === null) continue;
                                if (el.getAttribute('aria-checked') === 'true') return true;
                            }
                            for (const el of dialog.querySelectorAll('mat-checkbox')) {
                                if (el.offsetParent === null) continue;
                                if (el.classList.contains('mat-checkbox-checked')) return true;
                            }
                        }
                        return false;
                    }
                """)

                if not checked_now:
                    log.warning("⚠️ mouse ما خدمش — JS click")
                    clicked = await page.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                            for (const dialog of dialogs) {
                                if (dialog.offsetParent === null) continue;
                                for (const el of dialog.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                                    if (el.offsetParent === null) continue;
                                    try { el.click(); return 'ok'; } catch (e) {}
                                }
                            }
                            return null;
                        }
                    """)
                    if clicked:
                        log.info(f"✅ JS click: {clicked}")
                        await page.wait_for_timeout(2500)

            except Exception as e:
                log.warning(f"❌ checkbox: {e}")

        await self._shot(page, "✅ checkbox مفعّل")

        # ═══════════════════════════════════════
        # ✅ نستناو زر Agree يتفعّل
        # ═══════════════════════════════════════

        log.info("⏳ نستناو زر Agree يتفعّل...")
        agree_target = None
        for _ in range(10):
            try:
                agree_target = await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept', 'agree'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || el.value || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width === 0 || rect.height === 0) continue;
                                    const disabled = el.disabled ||
                                                    el.getAttribute('aria-disabled') === 'true' ||
                                                    el.classList.contains('disabled') ||
                                                    el.classList.contains('mat-button-disabled');
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
                if agree_target and not agree_target['disabled']:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(1500)

        if not agree_target:
            log.warning("⚠️ ما لقيناش زر Agree")
            return

        log.info(f"🎯 Agree: '{agree_target['text']}' dis={agree_target['disabled']}")

        if agree_target['disabled']:
            log.warning("⚠️ زر Agree معطّل — نجربو dispatchEvent")
            try:
                await page.evaluate("""
                    () => {
                        const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                        for (const dialog of dialogs) {
                            if (dialog.offsetParent === null) continue;
                            for (const el of dialog.querySelectorAll('mat-checkbox')) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width === 0 || rect.height === 0) continue;
                                const evt = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
                                el.dispatchEvent(evt);
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(2500)

                agree_target = await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    const rect = el.getBoundingClientRect();
                                    if (rect.width === 0) continue;
                                    const disabled = el.disabled ||
                                                    el.getAttribute('aria-disabled') === 'true' ||
                                                    el.classList.contains('mat-button-disabled');
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
                pass

        # ✅ mouse click
        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({agree_target['x']}, {agree_target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(800)

            await page.mouse.move(agree_target['x'] - 100, agree_target['y'] - 50, steps=10)
            await page.wait_for_timeout(300)
            await page.mouse.move(agree_target['x'], agree_target['y'], steps=8)
            await page.wait_for_timeout(400)
            await page.mouse.down()
            await page.wait_for_timeout(150)
            await page.mouse.up()
            log.info("✅ mouse click على Agree")
        except Exception as e:
            log.warning(f"❌ mouse: {e}")

        # ✅ إذا مازال مفتوح → JS click
        await page.wait_for_timeout(2000)

        still_open = await page.evaluate("""
            () => {
                for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                    if (el.offsetParent === null) continue;
                    const t = (el.innerText || '').toLowerCase();
                    if (t.includes('terms of service') || t.includes('i agree')) return true;
                }
                return false;
            }
        """)

        if still_open:
            log.warning("⚠️ Dialog مازال مفتوح — JS click مباشر")
            try:
                await page.evaluate("""
                    () => {
                        const kws = ['agree and continue', 'i agree', 'accept'];
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').trim().toLowerCase();
                            for (const kw of kws) {
                                if (t === kw || t.includes(kw)) {
                                    try {
                                        el.disabled = false;
                                        el.removeAttribute('disabled');
                                        el.removeAttribute('aria-disabled');
                                        el.click();
                                    } catch (e) {}
                                }
                            }
                        }
                    }
                """)
                log.info("✅ JS click")
                await page.wait_for_timeout(3000)
            except Exception as e:
                log.warning(f"❌ JS click: {e}")

        # نستناو Dialog يختفي
        gone = False
        for i in range(20):
            await page.wait_for_timeout(2000)
            try:
                gone = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree')) return false;
                        }
                        return true;
                    }
                """)
                if gone:
                    log.info(f"✅ Dialog اختفى بعد ~{(i+1)*2}s")
                    break
            except Exception:
                log.info(f"⏳ {i+1}")

        if gone:
            await self._shot(page, "✅ تم قبول Terms Dialog")
        else:
            log.warning("⚠️ Dialog مازال ما اختفاش")
            await self._shot(page, "⚠️ Dialog مازال")

        log.info("✅ step2 انتهى")

    # ═══════════════════════════════════════
    # STEP 3: Enable API
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
        # ✅ نتحققو واش Dialog مازال مفتوح
        try:
            dialog_open = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').toLowerCase();
                        if (t.includes('terms of service') || t.includes('i agree')) return true;
                    }
                    return false;
                }
            """)
            if dialog_open:
                log.warning("⚠️ Terms Dialog مازال مفتوح — نغلقو")
                await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('button, [role="button"]')) {
                            const t = (el.innerText || '').trim().toLowerCase();
                            if (t.includes('agree')) {
                                try { el.disabled = false; el.click(); } catch (e) {}
                            }
                        }
                    }
                """)
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 Enable API — URL: {api_url[:150]}")
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        await self._shot(page, "☁️ وصلنا Google Cloud Console")

        try:
            current_url = page.url
            log.info(f"📍 URL الحالي: {current_url[:150]}")
        except Exception:
            pass

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
                        log.warning(f"⚠️ ما ظهرش Manage: {e}")
                    found = True
                    break

                if await manage_btn.count() > 0 and await manage_btn.is_visible():
                    log.info("ℹ️ API مفعّل من قبل")
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
