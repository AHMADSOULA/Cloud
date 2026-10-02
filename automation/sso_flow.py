"""
automation/console.py
نسخة بسيطة — بلا انتظارات زايدة
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
    # STEP 1
    # ═══════════════════════════════════════

    async def step1_welcome_screen(self, page):
        log.info("🚀 step1")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

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
            await page.wait_for_timeout(600)

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

            await page.mouse.move(target['x'] - 150, target['y'] - 80, steps=8)
            await page.wait_for_timeout(200)
            await page.mouse.move(target['x'] - 50, target['y'] - 20, steps=8)
            await page.wait_for_timeout(200)
            await page.mouse.move(target['x'], target['y'], steps=6)
            await page.wait_for_timeout(300)
            await page.mouse.down()
            await page.wait_for_timeout(100)
            await page.mouse.up()
            log.info("✅ mouse")
        except Exception as e:
            log.warning(f"❌ {e}")
            try:
                await page.get_by_role("button", name="I understand").click(timeout=5000)
            except Exception:
                pass

        for i in range(15):
            await page.wait_for_timeout(1500)
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
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 2
    # ═══════════════════════════════════════

    async def step2_terms_dialog(self, page):
        log.info("🚀 step2")

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
            await page.wait_for_timeout(800)

        if not has_dialog:
            log.info("ℹ️ ما كاينش Dialog")
            return

        # checkbox
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
            try:
                await page.mouse.move(checkbox_info['x'] - 40, checkbox_info['y'] - 40, steps=6)
                await page.wait_for_timeout(200)
                await page.mouse.move(checkbox_info['x'], checkbox_info['y'], steps=6)
                await page.wait_for_timeout(300)
                await page.mouse.down()
                await page.wait_for_timeout(120)
                await page.mouse.up()
                await page.wait_for_timeout(2000)

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
            except Exception:
                pass

        # Agree button
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
            await page.wait_for_timeout(1200)

        if not agree_target:
            return

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
                await page.wait_for_timeout(2000)
            except Exception:
                pass

        try:
            await page.evaluate(f"""
                () => {{
                    const el = document.elementFromPoint({agree_target['x']}, {agree_target['y']});
                    if (el) el.scrollIntoView({{block: 'center', behavior: 'instant'}});
                }}
            """)
            await page.wait_for_timeout(600)

            await page.mouse.move(agree_target['x'] - 100, agree_target['y'] - 50, steps=8)
            await page.wait_for_timeout(200)
            await page.mouse.move(agree_target['x'], agree_target['y'], steps=6)
            await page.wait_for_timeout(300)
            await page.mouse.down()
            await page.wait_for_timeout(120)
            await page.mouse.up()
        except Exception:
            pass

        await page.wait_for_timeout(1500)

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
                await page.wait_for_timeout(2500)
            except Exception:
                pass

        for i in range(15):
            await page.wait_for_timeout(1500)
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
                    break
            except Exception:
                pass

    # ═══════════════════════════════════════
    # STEP 3
    # ═══════════════════════════════════════

    async def step3_enable_api(self, page, project_id, authuser):
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

            await page.wait_for_timeout(1500)

        raise RuntimeError("ما لقيناش زر Enable/Manage")

    # ═══════════════════════════════════════
    # STEP 4 — بسيط
    # ═══════════════════════════════════════

    async def step4_create_cloud_run(self, page, project_id, authuser, image):
        run_url = (
            f"https://console.cloud.google.com/run/create"
            f"?project={project_id}&authuser={authuser}"
        )
        log.info(f"🌐 step4")
        await page.goto(run_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)

        # نلقاو حقل Container Image URL
        try:
            label = page.get_by_text("Container Image URL").first
            await label.click(timeout=30000)
        except Exception:
            # fallback
            try:
                inp = page.locator('input[aria-label*="Container Image URL" i]').first
                await inp.click(timeout=10000)
            except Exception:
                try:
                    inp = page.locator('input[type="text"]').first
                    await inp.click(timeout=10000)
                except Exception as e:
                    raise RuntimeError(f"فشل لقاء حقل Image: {e}")

        await page.wait_for_timeout(600)
        await page.keyboard.type(image, delay=40)
        log.info("✅ رابط الحاوية")

        await page.wait_for_timeout(3000)

        # إعدادات
        try:
            await page.get_by_role("radio", name="Allow public access").click(timeout=15000)
        except Exception:
            pass
        try:
            await page.get_by_role("radio", name="Instance-based").click(timeout=15000)
        except Exception:
            pass
        try:
            await page.get_by_role("button", name="Hide").click(timeout=3000)
        except Exception:
            pass

        await page.keyboard.press("End")
        await page.wait_for_timeout(1000)

        create_btn = page.get_by_role("button", name="Create")
        await create_btn.click(force=True)
        log.info("✅ Create")

    # ═══════════════════════════════════════
    # STEP 5
    # ═══════════════════════════════════════

    async def step5_get_deployed_url(self, page):
        for i in range(120):
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
                    return url

                url = await page.evaluate("""
                    () => {
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

            await page.wait_for_timeout(3000)

            if (i + 1) % 10 == 0:
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass

        raise RuntimeError("ما لقيناش رابط run.app")
