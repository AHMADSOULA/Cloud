import httpx
import time
import html
from utils.logger import get_logger

log = get_logger("OoredooAPI")

BASE_URL = "https://apis.ooredoo.dz"

# ⚠️ هذه القيم من ملف HAR الخاص بك (قد تحتاج لتحديث التوكن إذا انتهت صلاحيته)
X_SIGNATURE = "f320f896f3da2a5a0284f9af316efb4ab0432b26406413568db116fa9dc60feb"
X_DEVICE_FINGERPRINT = "d4d827cf8063ee5084e5e87be4a16f2b27ca4a7eee499fc2de8d55455f14fa97"
X_INSTANCE_ID = "1992a870-b975-11f1-9fa4-c120a3d6d3ec1790404801655"
X_PLATFORM_INFO = (
    "eyJwbGF0Zm9ybSI6ImFuZHJvaWQiLCJpcy1waHlzaWNhbC1kZXZpY2UiOnRydWUs"
    "ImRldmljZS1pZCI6IjE5OTJhODcwLWI5NzUtMTFmMS05ZmE0LWMxMjBhM2Q2ZDNl"
    "YzE3OTA0MDQ4MDE2NTUifQ=="
)
X_NATIVE_INTEGRITY_TOKEN = (
    "JWBTpxXcH7Ks6mr0fJZ81uKPBTi/jHvP2KXOol9Ooj5r9c41WapD5UeV+zSVHSTe"
    "I6a80widPAncpeyus/9qjQ1xMbytlWLq7bQ3Ky8xW9XDvaiuNC4iJ/wE5WopTbqP"
    "/f70edwIJIH374PWWUvtvpvAiJVL04t/uJpfWx7IOWjlxD4M+UskIYLo7SD0NSaEv"
    "u6Abd54keq9Uo8HNbNSf6Qndmw8+RFXHB/uiFC01E7z2Kavy6RYE1i7x/zuo/OpmT"
    "MCJUjlMj++f0FrVU0AwfDYXsua+uB0JeuBidCRNx0cjbNf+yqW+iDGGLiMhA4KTL"
    "xpGWoUqTyXnNuRrVhP/JiUcT92C+DRKD3eFrhZwwa22zvQrn21RETZ4iMvfdr4I7g"
    "2rBXf+Z1HB8nh7mu5QlFhcZVJyzAMB03ZMO37vzEjoEC2x0laQeN6sT9Vcn2BO+F"
    "rx8hdHb2ZK0cZHWsEmH3gKzavPlRWnqlOegboLrQrtF04CzDUfeCRblHlRr/Q9+ng"
    "Syf7Cv4wiBwfAu+74tFbV2anrMj/V2q4AiiIfHEPtg6Shf/W35PoSu7oIwXklFn4"
    "Bu2vRRMYJJ3LMVtQCSv9BjO1AA1WvSWhqgCe5qTbFM2jCLzG9CH/boGIqyu3CHqF"
    "SxabsSdCAbYrZ0qMYKa474Djh0UxxyaOalBB5ABS/EjQuLjLIgIg8A26STCsxBUBE"
    "EbSZwLvnxtS8GBGfvgPsKtxiuMtS4OVJzGghySD9f4verJiyTlfiR0M"
)

def base_headers(msisdn: str, timestamp: str) -> dict:
    return {
        "user-agent": "Dart/3.11 (dart:io)",
        "x-msisdn": msisdn,
        "x-device-fingerprint": X_DEVICE_FINGERPRINT,
        "x-platform-origin": "mobile-android",
        "platform": "android",
        "x-version": "1.5.15",
        "x-signature": X_SIGNATURE,
        "accept": "*/*",
        "host": "apis.ooredoo.dz",
        "x-timestamp": timestamp,
        "x-instance-id": X_INSTANCE_ID,
        "accept-encoding": "gzip",
    }

async def get_checkpoint_tokens(client: httpx.AsyncClient, msisdn: str) -> tuple[str, str]:
    ts = str(int(time.time() * 1000))
    headers = base_headers(msisdn, ts)
    headers.update({
        "x-path": "/api/auth/realms/myooredoo/protocol/openid-connect/token",
        "x-method": "POST",
        "x-native-integrity-token": X_NATIVE_INTEGRITY_TOKEN,
        "x-platform-info": X_PLATFORM_INFO,
        "content-type": "application/json; charset=utf-8",
        "content-length": "2",
    })
    try:
        r = await client.post(
            f"{BASE_URL}/api/ooredoo-bff/checkpoint/token",
            headers=headers,
            content="{}",
            timeout=30.0,
        )
        nonce = r.headers.get("X-Nonce-Id", "")
        chronos = r.headers.get("X-Chronos-Id", "")
        return nonce, chronos
    except Exception as e:
        log.error(f"Checkpoint error: {e}")
        return "", ""

async def login_ooredoo(msisdn: str, password: str) -> dict:
    async with httpx.AsyncClient(http2=False, verify=True) as client:
        try:
            nonce, chronos = await get_checkpoint_tokens(client, msisdn)
            if not nonce or not chronos:
                return {"success": False, "error": "فشل الحصول على توكن checkpoint (ربما التوكن منتهي)"}

            ts = str(int(time.time() * 1000))
            headers = base_headers(msisdn, ts)
            headers.update({
                "x-nonce-id": nonce,
                "x-chronos-id": chronos,
                "x-platform-info": X_PLATFORM_INFO,
                "x-force-update": "true",
                "content-type": "application/x-www-form-urlencoded; charset=utf-8",
            })

            data = {
                "client_id": "myooredoo-app",
                "grant_type": "password",
                "username": msisdn,
                "password": password,
            }

            r = await client.post(
                f"{BASE_URL}/api/auth/realms/myooredoo/protocol/openid-connect/token",
                headers=headers,
                data=data,
                timeout=30.0,
            )

            if r.status_code == 200:
                j = r.json()
                return {
                    "success": True,
                    "access_token": j.get("access_token"),
                    "refresh_token": j.get("refresh_token"),
                    "expires_in": j.get("expires_in"),
                }
            else:
                try:
                    err = r.json()
                    msg = err.get("error_description") or err.get("error") or str(err)
                except Exception:
                    # في حال تم إرجاع صفحة HTML (حظر WAF)
                    text = r.text
                    clean_text = html.escape(text[:80].replace('\n', ' '))
                    if "Request Rejected" in text:
                        return {"success": False, "error": "محظور من السيرفر (WAF)"}
                    msg = f"HTTP {r.status_code}: {clean_text}"
                return {"success": False, "error": msg}

        except httpx.TimeoutException:
            return {"success": False, "error": "انتهت مهلة الاتصال بالخادم"}
        except Exception as e:
            return {"success": False, "error": f"خطأ: {type(e).__name__}: {html.escape(str(e)[:100])}"}
