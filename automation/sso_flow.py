"""
automation/sso_flow.py
تنسيق العملية — مع تصوير عند الفشل + توقف
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


def extract_email_from_url(url: str) -> str:
    try:
        m = re.search(r'Email%3D([^%&]+%40qwiklabs\.net)', url or "")
        if m:
            from urllib.parse import unquote
            return unquote(m.group(1))
        m = re.search(r'Email=([^&\s#]+@qwiklabs\.net)', url or "")
        if m:
            return m.group(1)
        m = re.search(r'([a-zA-Z0-9\.\-]+@qwiklabs\.net)', url or "")
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def extract_password_from_url(url: str) -> str:
    try:
        m = re.search(r'Password=([^&\s#]+)', url or "")
        if m:
            from urllib.parse import unquote
            return unquote(m.group(1))
    except Exception:
        pass
    return None


async def run_sso_flow(context, sso_url: str, image: str, sender=None, user_tag="@user") -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO — project={project_id}")

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

    # ✅ صفحة وحدة
    page = await context.new_page()
    try:
        # ═══════ 1) SSO ═══════
        await report(1, "فتح رابط الطالب...")
        try:
            await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            await page.goto(sso_url, wait_until="commit", timeout=60000)
        await report(1, "", ok=True)

        # ═══════ نتحققو من الأخطاء ═══════
        await page.wait_for_timeout(3000)

        # ❌ 1. SSO منتهي؟
        try:
            expired = await page.evaluate("""
                () => {
                    const text = (document.body.innerText || '').toLowerCase();
                    if (text.includes('session expired') ||
                        text.includes('expired') ||
                        text.includes('رابط منتهي') ||
                        text.includes('invalid') ||
                        text.includes('no longer valid') ||
                        text.includes('try again')) {
                        return true;
                    }
                    // link to login
                    const url = window.location.href.toLowerCase();
                    if (url.includes('accounts.google.com/signin') && !url.includes('addsession')) {
                        return true;
                    }
                    return false;
                }
            """)

            if expired:
                log.warning("⚠️ SSO منتهي")
                await console._shot(page, "❌ SSO منتهي")
                await report(1, "❌ SSO منتهي أو غير صالح — توقفنا", ok=False)
                return {
                    "success": False,
                    "error": "expired_sso",
                    "message": "SSO منتهي أو غير صالح",
                    "final_url": page.url,
                }
        except Exception as e:
            log.warning(f"⚠️ فحص SSO: {e}")

        # ═══════ 2) TOS ═══════
        await report(2, "")
        try:
            await console.step1_welcome_screen(page)
            await report(2, "", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step1: {e}")
            await console._shot(page, "❌ step1 فشل")
            await report(2, "❌ step1 فشل — توقفنا", ok=False)
            return {"success": False, "error": "step1_failed", "message": str(e)[:200]}

        # ═══════ 3) Terms Dialog ═══════
        await report(3, "")
        try:
            await console.step2_terms_dialog(page)
            await report(3, "", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step2: {e}")
            await console._shot(page, "❌ step2 فشل")
            await report(3, "❌ step2 فشل — توقفنا", ok=False)
            return {"success": False, "error": "step2_failed", "message": str(e)[:200]}

        # ═══════ نستناو Dashboard ═══════
        try:
            await page.wait_for_url("**/home/dashboard**", timeout=45000)
            log.info("✅ Dashboard")
        except Exception:
            log.warning("⚠️ ما وصلناش Dashboard")
            # ✅ نصورو + نوقف
            await console._shot(page, "❌ ما وصلناش Dashboard")
            await report(3, "❌ ما وصلناش Dashboard — توقفنا", ok=False)
            return {"success": False, "error": "no_dashboard", "message": "ما وصلناش Dashboard"}

        await page.wait_for_timeout(1000)
        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")

        # ═══════ 4) Enable API ═══════
        await report(4, "تفعيل Cloud Run API...")
        try:
            await console.step3_enable_api(page, project_id, authuser)
            await report(4, "", ok=True)
        except Exception as e:
            log.warning(f"⚠️ step3: {e}")
            await console._shot(page, "❌ step3 فشل")
            # ✅ نكملو — بعض المرات API مفعّل من قبل
            await report(4, "⚠️ API ما تأكدش، نكملو...", ok=False)

        # ═══════ 5) Create Cloud Run ═══════
        await report(5, "فتح Cloud Run...")
        try:
            await console.step4_create_cloud_run(page, project_id, authuser, image)
            await report(5, "", ok=True)
        except Exception as e:
            log.error(f"❌ step4 فشل: {e}")
            await console._shot(page, "❌ step4 فشل — توقفنا")
            await report(5, "❌ step4 فشل — توقفنا", ok=False)
            return {"success": False, "error": "step4_failed", "message": str(e)[:200]}

        # ═══════ 6) ═══════
        await report(6, "", ok=True)
        # ═══════ 7) ═══════
        await report(7, "Create", ok=True)

        # ═══════ 8) انتظار الرابط ═══════
        await report(8, "انتظار رابط النشر...")
        try:
            final_url = await console.step5_get_deployed_url(page)
            domain = extract_domain_from_service_url(final_url)
            await report(8, f"(Domain: {domain})", ok=True)
        except Exception as e:
            log.error(f"❌ step5 فشل: {e}")
            await console._shot(page, "❌ step5 فشل — توقفنا")
            await report(8, "❌ step5 فشل — توقفنا", ok=False)
            return {"success": False, "error": "step5_failed", "message": str(e)[:200]}

    finally:
        try:
            await page.close()
        except Exception:
            pass

    return {
        "success": True,
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": domain,
    }
