import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.urls import reverse


class SupabaseAuthError(Exception):
    pass


def enabled():
    return bool(settings.SUPABASE_AUTH_EMAIL_CONFIRMATION and _supabase_url() and _supabase_key())


def oauth_enabled():
    return bool(_supabase_url() and _supabase_key())


def google_provider_enabled():
    settings_response = _request_json("GET", "/auth/v1/settings")
    return bool((settings_response.get("external") or {}).get("google"))


def confirmation_redirect_url(request):
    if settings.SUPABASE_EMAIL_REDIRECT_URL:
        return settings.SUPABASE_EMAIL_REDIRECT_URL
    return request.build_absolute_uri(reverse("supabase_confirmar_email"))


def google_redirect_url(request):
    callback_url = request.build_absolute_uri(reverse("supabase_confirmar_email"))
    return f"{callback_url}?provider=google"


def google_authorize_url(request):
    return _build_url(
        "/auth/v1/authorize",
        query={
            "provider": "google",
            "redirect_to": google_redirect_url(request),
            "scopes": "openid email profile",
        },
    )


def sign_up(email, password, metadata=None, redirect_to=None):
    payload = {
        "email": email,
        "password": password,
    }
    if metadata:
        payload["data"] = metadata

    query = {}
    if redirect_to:
        query["redirect_to"] = redirect_to

    return _request_json("POST", "/auth/v1/signup", payload=payload, query=query)


def resend_signup_confirmation(email, redirect_to=None):
    payload = {
        "type": "signup",
        "email": email,
    }
    if redirect_to:
        payload["options"] = {"email_redirect_to": redirect_to}
    return _request_json("POST", "/auth/v1/resend", payload=payload)


def get_user(access_token):
    return _request_json("GET", "/auth/v1/user", access_token=access_token)


def verify_token_hash(token_hash, verification_type="email"):
    return _request_json(
        "POST",
        "/auth/v1/verify",
        payload={
            "token_hash": token_hash,
            "type": verification_type,
        },
    )


def _request_json(method, path, payload=None, query=None, access_token=None):
    url = _build_url(path, query=query)
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    key = _supabase_key()
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {access_token or key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.SUPABASE_AUTH_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8", errors="replace")
        raise SupabaseAuthError(_error_message(response_body, fallback=f"Supabase Auth retornou HTTP {error.code}")) from error
    except Exception as error:
        raise SupabaseAuthError(f"Erro ao chamar Supabase Auth: {error}") from error


def _build_url(path, query=None):
    base_url = _supabase_url()
    if not base_url:
        raise SupabaseAuthError("SUPABASE_URL nao configurado.")
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    return url


def _supabase_url():
    return settings.SUPABASE_URL.rstrip("/")


def _supabase_key():
    key = settings.SUPABASE_AUTH_KEY
    if not key:
        raise SupabaseAuthError("SUPABASE_AUTH_KEY, SUPABASE_ANON_KEY ou SUPABASE_PUBLISHABLE_KEY nao configurado.")
    return key


def _error_message(response_body, fallback):
    if not response_body:
        return fallback
    try:
        data = json.loads(response_body)
    except json.JSONDecodeError:
        return response_body
    return data.get("msg") or data.get("message") or data.get("error_description") or data.get("error") or fallback
