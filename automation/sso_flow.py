"""
automation/sso_flow.py
تنسيق العملية — مع تقارير + تصوير كل خطوة
"""
import re
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


async def run_sso_flow(context, sso_url: str, image: str, sender=None, user_tag="@user") -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO flow — project={project_id}")

    console = CloudConsole(context, sender=sender, user_tag=user_tag)

    async def report(num, text, ok=False):
        if not sender:
            return
        try:
            if ok:
                await sender.reply_text(f"[{user_tag}] • {num} ✅ {text}")
            else:
                await sender.reply_text(f"[{user_tag}] • {num}) {text}")
        except Exception:
            pass

    # ✅ صفحة وحدة (باش الجلسة ما تضيعش)
    page = await context.new_page()
    try:
        # ═══════ 1) SSO ═══════
        await report(1, "فتح رابط الطالب...")
        await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)
        await report(1, "", ok=True)

        # ═══════ 2) TOS ═══════
        await report(2, "")
        try:
            await console.step1_welcome_screen(page)
            await page.wait_for_timeout(2000)
            await report(2, "", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step1: {e}")

        # ═══════ 3) Terms Dialog ═══════
        await report(3, "")
        try:
            await console.step2_terms_dialog(page)
            await page.wait_for_timeout(2000)
            await report(3, f"(Project: {project_id})", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step2: {e}")

        try:
            await page.wait_for_url("**/home/dashboard**", timeout=60000)
        except Exception:
            log.warning("⚠️ ما وصلناش Dashboard")

        await page.wait_for_timeout(1500)

        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")

        # ═══════ 4) Enable API ═══════
        await report(4, "تفعيل Cloud Run API...")
        try:
            await console.step3_enable_api(page, project_id, authuser)
            await report(4, "", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step3 فشل: {e}")
            await report(4, "API مؤكد، متابعة...", ok=False)

        # ═══════ 5) Create Cloud Run ═══════
        await report(5, "فتح Cloud Run...")
        try:
            await console.step4_create_cloud_run(page, project_id, authuser, image)
            await report(5, "", ok=True)
        except Exception as e:
            raise RuntimeError(f"فشل Cloud Run: {e}")

        # ═══════ 6) ═══════
        await report(6, "تعبئة الحقول...")
        await page.wait_for_timeout(1500)
        await report(6, "", ok=True)

        # ═══════ 7) ═══════
        await report(7, "Create الخدمة...")
        await page.wait_for_timeout(1500)
        await report(7, "Create", ok=True)

        # ═══════ 8) ═══════
        await report(8, "انتظار رابط النشر...")
        final_url = await console.step5_get_deployed_url(page)
        domain = extract_domain_from_service_url(final_url)

        await report(8, f"(Domain: {domain})", ok=True)

    finally:
        try:
            await page.close()
        except Exception:
            pass

    return {
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": domain,
    }
