"""
automation/console.py
كل خطوات Google Cloud Console — Service name فريد بـ evaluate
"""
import asyncio
import random
import string
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
            await page.screenshot(path=path, full_page=False, timeout=15000)
            with open(path, "rb") as f:
                try:
                    await self.sender.reply_photo(photo=f, caption=caption[:1000])
                    log.info(f"📸 screenshot sent")
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
    # STEP 1
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1: Welcome / TOS")

        await page.wait_for_load_state("domcontentloaded")
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
            log.info("ℹ️ ماشي TOS")
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
        except Exception:
            return

        if not target:
            return

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({target['x']}, {target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(500)

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

            await page.mouse.move(target['x'] - 100, target['y'] - 50, steps=6)
            await page.wait_for_timeout(150)
            await page.mouse.move(target['x'], target['y'], steps=5)
            await page.wait_for_timeout(200)
            await page.mouse.down()
            await page.wait_for_timeout(100)
            await page.mouse.up()
            log.info("✅ mouse click")
        except Exception as e:
            log.warning(f"❌ mouse فشل: {e}")
            try:
                await page.get_by_role("button", name="I understand").click(timeout=5000)
            except Exception:
                pass

        for i in range(12):
            await page.wait_for_timeout(1200)
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
                    log.info(f"✅ TOS اختفت ~{(i+1)*1.2}s")
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 2
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2: Terms Dialog")

        has_dialog = False
        for _ in range(8):
            try:
                has_dialog = await page.evaluate("""
                    () => {
                        for (const el of document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog')) {
                            if (el.offsetParent === null) continue;
                            const t = (el.innerText || '').toLowerCase();
                            if (t.includes('terms of service') || t.includes('i agree to')) return true;
                        }
                        return false;
                    }
                """)
                if has_dialog:
                    break
            except Exception:
                pass
            await page.wait_for_timeout(700)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        log.info("📋 لقينا Dialog")

        checkbox_info = None
        try:
            checkbox_info = await page.evaluate("""
                () => {
                    const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                    for (const dialog of dialogs) {
                        if (dialog.offsetParent === null) continue;
                        for (const el of dialog.querySelectorAll('input[type="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.checked };
                        }
                        for (const el of dialog.querySelectorAll('[role="checkbox"]')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.getAttribute('aria-checked') === 'true' };
                        }
                        for (const el of dialog.querySelectorAll('mat-checkbox')) {
                            if (el.offsetParent === null) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width === 0 || rect.height === 0) continue;
                            return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), checked: el.classList.contains('mat-checkbox-checked') };
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
                await page.mouse.move(checkbox_info['x'] - 30, checkbox_info['y'] - 30, steps=5)
                await page.wait_for_timeout(150)
                await page.mouse.move(checkbox_info['x'], checkbox_info['y'], steps=5)
                await page.wait_for_timeout(200)
                await page.mouse.down()
                await page.wait_for_timeout(100)
                await page.mouse.up()
                log.info("✅ checkbox mouse")
                await page.wait_for_timeout(1800)

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
                    await page.evaluate("""
                        () => {
                            const dialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"], .modal, md-dialog');
                            for (const dialog of dialogs) {
                                if (dialog.offsetParent === null) continue;
                                for (const el of dialog.querySelectorAll('mat-checkbox, [role="checkbox"], input[type="checkbox"]')) {
                                    if (el.offsetParent === null) continue;
                                    try { el.click(); return; } catch (e) {}
                                }
                            }
                        }
                    """)
                    await page.wait_for_timeout(1800)
            except Exception as e:
                log.warning(f"❌ checkbox: {e}")

        agree_target = None
        for _ in range(8):
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
            await page.wait_for_timeout(1000)

        if not agree_target:
            return

        log.info(f"🎯 Agree: '{agree_target['text']}' dis={agree_target['disabled']}")

        if agree_target['disabled']:
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
                await page.wait_for_timeout(1800)
            except Exception:
                pass

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({agree_target['x']}, {agree_target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(500)

            await page.mouse.move(agree_target['x'] - 80, agree_target['y'] - 40, steps=6)
            await page.wait_for_timeout(150)
            await page.mouse.move(agree_target['x'], agree_target['y'], steps=5)
            await page.wait_for_timeout(200)
            await page.mouse.down()
            await page.wait_for_timeout(100)
            await page.mouse.up()
        except Exception:
            pass

        await page.wait_for_timeout(1200)

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
                await page.wait_for_timeout(2000)
            except Exception:
                pass

        for i in range(12):
            await page.wait_for_timeout(1200)
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
                    log.info(f"✅ Dialog اختفى ~{(i+1)*1.2}s")
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 3
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
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
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        api_url = (
            f"https://console.cloud.google.com/apis/library/"
            f"run.googleapis.com?project={project_id}&authuser={authuser}"
        )
        await page.goto(api_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)

        enable_btn = page.get_by_role("button", name="Enable")
        manage_btn = page.get_by_role("button", name="Manage")
        disable_btn = page.get_by_text("Disable API")

        for attempt in range(30):
            try:
                if await enable_btn.count() > 0 and await enable_btn.is_visible():
                    await enable_btn.click()
                    try:
                        await expect(manage_btn.or_(disable_btn)).to_be_visible(timeout=120000)
                    except Exception:
                        pass
                    return

                if await manage_btn.count() > 0 and await manage_btn.is_visible():
                    return
            except Exception:
                pass

            await page.wait_for_timeout(1200)

        raise RuntimeError("ما لقيناش زر Enable ولا Manage")

    # ═══════════════════════════════════════
    # STEP 4 — Service name فريد بـ evaluate
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 Create Cloud Run")
        await page.goto(run_url, wait_until="domcontentloaded")

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await page.wait_for_timeout(4000)

        # حقل Image
        image_found = False
        for attempt in range(15):
            try:
                try:
                    label = page.get_by_text("Container Image URL").first
                    if await label.count() > 0 and await label.is_visible():
                        await label.click()
                        image_found = True
                        break
                except Exception:
                    pass

                try:
                    inp = page.locator('input[aria-label*="Container Image URL" i]').first
                    if await inp.count() > 0 and await inp.is_visible():
                        await inp.click()
                        image_found = True
                        break
                except Exception:
                    pass

                try:
                    el = page.locator('text=/Container Image/i').first
                    if await el.count() > 0 and await el.is_visible():
                        await el.click()
                        image_found = True
                        break
                except Exception:
                    pass

                try:
                    clicked = await page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('*');
                            for (const el of els) {
                                const t = (el.innerText || '').trim();
                                if (t.includes('Container Image URL') && t.length < 100) {
                                    try { el.click(); return 'ok'; } catch (e) {}
                                }
                            }
                            return null;
                        }
                    """)
                    if clicked:
                        image_found = True
                        break
                except Exception:
                    pass
            except Exception:
                pass

            await page.wait_for_timeout(1200)

        if not image_found:
            try:
                inp = page.locator('input[type="text"]').first
                if await inp.count() > 0:
                    await inp.click()
                else:
                    raise RuntimeError("ما لقيناش حقل Image")
            except Exception as e:
                raise RuntimeError(f"فشل لقاء حقل: {str(e)}")

        try:
            await page.wait_for_timeout(400)
            await page.keyboard.type(image, delay=40)
            log.info("✅ رابط الحاوية")
        except Exception as e:
            raise RuntimeError(f"فشل كتابة الرابط: {str(e)}")

        await page.wait_for_timeout(2000)

        # ═══════════════════════════════════════
        # ✅ Service name فريد بـ evaluate مباشرة
        # ═══════════════════════════════════════
        try:
            # نولّدو اسم جديد
            suffix = "".join(random.choices(string.ascii_lowercase, k=2))
            new_name = f"ahmed-vip1-{suffix}"
            log.info(f"🔧 نكتبو Service name: '{new_name}'")

            # ✅ نستعملو evaluate مباشرة باش نكتبو
            result = await page.evaluate(f"""
                () => {{
                    const newName = {new_name!r};

                    // نلقاو كل الحقول
                    const inputs = document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])');

                    for (const el of inputs) {{
                        if (el.offsetParent === null) continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;

                        // نشوفو واش هاد الحقل هو "Service name"
                        // 1. من خلال aria-label
                        const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        const id = (el.id || '').toLowerCase();
                        const name = (el.name || '').toLowerCase();
                        const fc = (el.getAttribute('formcontrolname') || '').toLowerCase();

                        const isServiceName = (
                            aria.includes('service name') ||
                            aria.includes('service-name') ||
                            id.includes('servicename') ||
                            id.includes('service-name') ||
                            name.includes('servicename') ||
                            fc.includes('servicename') ||
                            fc === 'name' ||
                            id.includes('name') && id.includes('service')
                        );

                        // 2. من خلال القيمة الحالية
                        const val = (el.value || '').toLowerCase();
                        const isAhmedVip = val.includes('ahmed-vip1') || val.includes('ahmed-vip');

                        if (isServiceName || isAhmedVip) {{
                            // ✅ نكتبو الاسم الجديد
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            ).set;
                            nativeInputValueSetter.call(el, newName);

                            // نطلقو events
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('blur', {{ bubbles: true }}));

                            return {{
                                ok: true,
                                old_value: val,
                                new_value: el.value,
                                aria: aria,
                                id: id,
                            }};
                        }}
                    }}

                    return {{ ok: false }};
                }}
            """)

            log.info(f"🔧 evaluate result: {result}")

            await page.wait_for_timeout(1000)

            # نتحققو
            try:
                verify = await page.evaluate("""
                    () => {
                        const inputs = document.querySelectorAll('input[type="text"], input[type="search"]');
                        for (const el of inputs) {
                            if (el.offsetParent === null) continue;
                            const val = el.value || '';
                            if (val.includes('ahmed-vip1')) {
                                return val;
                            }
                        }
                        return null;
                    }
                """)
                log.info(f"✅ Service name بعد الكتابة: '{verify}'")
            except Exception as e:
                log.warning(f"⚠️ verify: {e}")

        except Exception as e:
            log.warning(f"⚠️ Service name: {e}", exc_info=True)

        # إعدادات
        try:
            try:
                await page.get_by_role("radio", name="Allow public access").click(timeout=10000)
            except Exception:
                pass
            try:
                await page.get_by_role("radio", name="Instance-based").click(timeout=10000)
            except Exception:
                pass
            try:
                await page.get_by_role("button", name="Hide").click(timeout=2000)
            except Exception:
                pass

            await page.keyboard.press("End")
            await page.wait_for_timeout(600)
        except Exception as e:
            log.warning(f"⚠️ إعدادات: {e}")

        # Create + screenshot
        try:
            create_btn = page.get_by_role("button", name="Create")
            await create_btn.click(force=True)
            log.info("✅ Create")

            await page.wait_for_timeout(2000)
            await self._shot(page, "🚀 بعد الضغط على Create")

        except Exception as e:
            raise RuntimeError(f"فشل Create: {str(e)}")

    # ═══════════════════════════════════════
    # STEP 5
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        log.info("⏳ step5: نستناو run.app...")

        for i in range(240):
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

            await page.wait_for_timeout(2500)

            if (i + 1) % 10 == 0:
                log.info(f"⏳ مازال نستناو... ({(i+1)*2.5}s)")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2500)
                except Exception:
                    pass

        raise RuntimeError("ما لقيناش رابط run.app بعد 10 دقايق")
