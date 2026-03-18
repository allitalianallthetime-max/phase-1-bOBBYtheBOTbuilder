"""
APP HELPERS — HTTP Client + Utilities
=======================================
Every internal API call goes through these helpers.

Features:
  - Internal key auth on every request
  - Optional JWT bearer token for user-authenticated requests
  - Configurable timeouts with sane defaults (10s read, 5s connect)
  - Friendly error messages for all HTTP status codes
  - Structured APIError for clean Streamlit handling
"""

import os
import httpx
import logging

log = logging.getLogger("app_helpers")

INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "")

# Default timeout: 5s to connect, 10s to read. Override per-call as needed.
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _headers(jwt_token: str = "") -> dict:
    """Build request headers with internal key + optional JWT."""
    h = {"x-internal-key": INTERNAL_KEY}
    if jwt_token:
        h["Authorization"] = f"Bearer {jwt_token}"
    return h


class APIError:
    """Structured API error for clean handling in Streamlit."""
    def __init__(self, status: int, detail: str, raw: str = ""):
        self.status = status
        self.detail = detail
        self.raw = raw

    def __str__(self):
        return self.detail

    def __bool__(self):
        return False  # So `if result:` works naturally


def api_get(url: str, timeout: float = 10.0, jwt_token: str = ""):
    """
    GET an internal service endpoint. Returns parsed JSON or APIError.

    Usage:
        result = api_get(f"{AI_URL}/health")
        if isinstance(result, APIError):
            st.error(result.detail)
        else:
            # result is the parsed JSON dict/list
    """
    try:
        resp = httpx.get(
            url,
            headers=_headers(jwt_token),
            timeout=httpx.Timeout(timeout, connect=5.0)
        )
        if resp.status_code == 200:
            return resp.json()
        return APIError(resp.status_code, _friendly_error(resp), resp.text[:200])
    except httpx.TimeoutException:
        return APIError(0, "Service is waking up. Try again in a few seconds.")
    except httpx.ConnectError:
        return APIError(0, "Service is offline. It may be restarting.")
    except Exception as e:
        log.warning("api_get failed for %s: %s", url[:60], e)
        return APIError(0, f"Connection failed: {e}")


def api_post(url: str, payload: dict = None, timeout: float = 10.0, jwt_token: str = ""):
    """
    POST to an internal service endpoint. Returns parsed JSON or APIError.
    """
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers=_headers(jwt_token),
            timeout=httpx.Timeout(timeout, connect=5.0)
        )
        if resp.status_code == 200:
            return resp.json()
        return APIError(resp.status_code, _friendly_error(resp), resp.text[:200])
    except httpx.TimeoutException:
        return APIError(0, "Service is waking up. Try again in a few seconds.")
    except httpx.ConnectError:
        return APIError(0, "Service is offline. It may be restarting.")
    except Exception as e:
        log.warning("api_post failed for %s: %s", url[:60], e)
        return APIError(0, f"Connection failed: {e}")


def api_get_raw(url: str, timeout: float = 10.0, jwt_token: str = ""):
    """
    GET raw bytes (for file downloads). Returns (bytes, True) or (error_msg, False).
    """
    try:
        resp = httpx.get(
            url,
            headers=_headers(jwt_token),
            timeout=httpx.Timeout(timeout, connect=5.0)
        )
        if resp.status_code == 200:
            return resp.content, True
        return f"Download failed: HTTP {resp.status_code}", False
    except Exception as e:
        return f"Download failed: {e}", False


def ping_service(url: str, timeout: float = 3.0) -> bool:
    """Silent health check ping. Returns True if service responded."""
    try:
        httpx.get(url, timeout=httpx.Timeout(timeout, connect=2.0))
        return True
    except Exception:
        return False


def _friendly_error(resp) -> str:
    """Convert HTTP response to a human-friendly error message."""
    try:
        detail = resp.json().get("detail", "")
    except Exception:
        detail = ""

    status = resp.status_code
    messages = {
        400: f"Invalid input: {detail}" if detail else "Invalid input.",
        401: "Authentication expired. Please log in again.",
        402: detail or "Build quota exceeded.",
        403: detail or "Request blocked.",
        409: detail or "Already exists.",
        429: detail or "Too many requests. Please wait.",
    }
    if status in messages:
        return messages[status]
    if status >= 500:
        return "Service error. Try again in a moment."
    return detail or f"Unexpected error (HTTP {status})."
