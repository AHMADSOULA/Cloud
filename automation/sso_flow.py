"""
automation/sso_flow.py
تنسيق العملية — صفحة وحدة + انتظار أطول لـ run.app
"""
import re
import asyncio
from urllib.parse import urlparse, parse_qs

from automation.console import CloudConsole
from utils.logger import get_logger

log = get_logger("SSOFlow")


def extract_project_id(url: str) -> str:
    m = re.search(r'(qwiklabs-gcp-[\w-]+)', url or "")
    return m.group(1) if m else None


def extract_domain_from_service_url(service_url: str) -> str:
    s = (service_url or "").strip()
    if s.startswith("http://") or s.startswith("https://"):
        return urlparse(s).netloc.strip()
    return s.replace("http://", "").replace("https://", "").split("/")[0].strip()


def extract_authuser(page_url: str) -> str:
    try:
        qs = parse_qs(urlparse(page_url).query)
        return qs.get('authuser', ['1'])[0]
    except Exception:
        return '1'


async def wait_for_run_app_url(page, project_id: str, authuser: str, timeout: int = 600) -> str:
    """
    يستنى رابط run.app لمدة 10 دقايق.
    يجرب:
    1. الصفحة الحالية
    2. صفحة Cloud Run services
    3. صفحة Cloud Run service details
    """
    import time
    start = time.time()

    services_url = (
        f"https://console.cloud.google.com/run"
        f"?project={project_id}&authuser={authuser}"
    )

    while time.time() - start < timeout:
        # ✅ محاولة 1: الصفحة الحالية
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
                log.info(f"✅ لقيناه في الصفحة الحالية: {url}")
                return url
        except Exception:
            pass

        # ✅ محاولة 2: نروحو لصفحة Cloud Run services
        try:
            await page.goto(services_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

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
                log.info(f"✅ لقيناه في services: {url}")
                return url

            # ✅ محاولة 3: نلقاو اسم الخدمة ونضغطو عليه
            service_clicked = await page.evaluate("""
                () => {
                    for (const el of document.querySelectorAll('a, [role="link"], [role="button"]')) {
                        if (el.offsetParent === null) continue;
                        const t = (el.innerText || '').trim().toLowerCase();
                        // اسم الخدمة يبدأ بـ ahmed-vip1
                        if (t.includes('ahmed-vip1') || t.includes('service-')) {
                            try { el.click(); return t.substring(0, 50); } catch (e) {}
                        }
                    }
                    return null;
                }
            """)
            if service_clicked:
                log.info(f"🖱️ ضغطنا على: {service_clicked}")
                await page.wait_for_timeout(4000)

                # نلقاو الرابط في صفحة التفاصيل
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
                    log.info(f"✅ لقيناه في تفاصيل الخدمة: {url}")
                    return url
        except Exception as e:
            log.warning(f"⚠️ محاولة: {e}")

        log.info(f"⏳ مازال نستناو run.app... ({int(time.time()-start)}s)")
        await asyncio.sleep(5)

    raise RuntimeError(f"ما لقيناش رابط run.app بعد {timeout}s")


async def run_sso_flow(context, sso_url: str, image: str, sender=None, user_tag="@user") -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO flow — project={project_id}")

    console = CloudConsole(context, sender=sender, user_tag=user_tag)

    # ✅ صفحة وحدة
    page = await context.new_page()
    try:
        # ═══════ 1) SSO ═══════
        await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)

        # ═══════ 2) TOS ═══════
        await console.step1_welcome_screen(page)
        await page.wait_for_timeout(2000)

        # ═══════ 3) Terms Dialog ═══════
        await console.step2_terms_dialog(page)

        # ═══════ نستناو Dashboard ═══════
        try:
            await page.wait_for_url("**/home/dashboard**", timeout=60000)
            log.info("✅ وصلنا Dashboard")
        except Exception:
            log.warning("⚠️ ما وصلناش Dashboard")

        await page.wait_for_timeout(2000)

        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")

        # ═══════ 4) Enable API — اختياري ═══════
        try:
            await console.step3_enable_api(page, project_id, authuser)
            log.info("✅ step3 نجح")
        except Exception as e:
            log.warning(f"⚠️ step3 فشل (نكملو): {e}")
            try:
                await page.goto(
                    f"https://console.cloud.google.com/home/dashboard"
                    f"?project={project_id}&authuser={authuser}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_timeout(3000)
            except Exception:
                pass

        # ═══════ 5) Create Cloud Run ═══════
        await console.step4_create_cloud_run(page, project_id, authuser, image)
        log.info("✅ Create تم")

        # ═══════ 6) انتظار رابط run.app (10 دقايق) ═══════
        final_url = await wait_for_run_app_url(page, project_id, authuser, timeout=600)

    finally:
        try:
            await page.close()
        except Exception:
            pass

    domain = extract_domain_from_service_url(final_url)

    return {
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": domain,
    }
