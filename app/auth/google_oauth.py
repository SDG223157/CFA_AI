from __future__ import annotations

from dataclasses import dataclass
import os
import hmac
import hashlib
import json
import time
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    app_base_url: str  # e.g. https://dailytask.biz
    allowed_email_domains: list[str]
    allowed_emails: list[str]

    @property
    def redirect_uri(self) -> str:
        # Streamlit runs at the root; Coolify domain should point to the app.
        return self.app_base_url.rstrip("/") + "/"


def load_google_oauth_config() -> GoogleOAuthConfig | None:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    app_base_url = os.getenv("APP_BASE_URL", "").strip()
    if not client_id or not client_secret or not app_base_url:
        return None

    allowed_domains = [
        d.strip().lower()
        for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
        if d.strip()
    ]
    allowed_emails = [
        e.strip().lower()
        for e in os.getenv("ALLOWED_EMAILS", "").split(",")
        if e.strip()
    ]

    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        app_base_url=app_base_url,
        allowed_email_domains=allowed_domains,
        allowed_emails=allowed_emails,
    )


def new_state() -> str:
    return secrets.token_urlsafe(32)

def _b64url_encode(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    import base64

    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def sign_state(*, secret: str, ttl_seconds: int = 15 * 60) -> str:
    """
    Build a stateless OAuth state token that can be verified without Streamlit session state.
    Helps in deployments where the Streamlit session may change during redirects.
    """
    payload = {
        "n": secrets.token_urlsafe(16),
        "exp": int(time.time()) + int(ttl_seconds),
    }
    payload_b = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_s = _b64url_encode(payload_b)
    sig = hmac.new(secret.encode("utf-8"), payload_s.encode("utf-8"), hashlib.sha256).digest()
    return payload_s + "." + _b64url_encode(sig)


def verify_state(*, state: str, secret: str) -> bool:
    try:
        payload_s, sig_s = state.split(".", 1)
        expected = hmac.new(secret.encode("utf-8"), payload_s.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected), sig_s):
            return False
        payload = json.loads(_b64url_decode(payload_s).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        return time.time() <= exp
    except Exception:
        return False


def build_auth_url(cfg: GoogleOAuthConfig, *, state: str) -> str:
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(cfg: GoogleOAuthConfig, *, code: str) -> dict[str, Any]:
    data = {
        "code": code,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "redirect_uri": cfg.redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(GOOGLE_TOKEN_URL, data=data)
        resp.raise_for_status()
        return resp.json()


def fetch_userinfo(*, access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=30) as client:
        resp = client.get(GOOGLE_USERINFO_URL, headers=headers)
        resp.raise_for_status()
        return resp.json()


def is_allowed(cfg: GoogleOAuthConfig, *, email: str) -> bool:
    email_lc = email.strip().lower()
    if not email_lc:
        return False

    if cfg.allowed_emails and email_lc in set(cfg.allowed_emails):
        return True

    if cfg.allowed_email_domains:
        domain = email_lc.split("@")[-1]
        return domain in set(cfg.allowed_email_domains)

    # If no allowlist configured, allow any Google account.
    return True


