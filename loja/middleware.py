import threading
from urllib.parse import urlparse
from django.conf import settings
from django.shortcuts import render
from .models import Loja

_thread_locals = threading.local()

def get_current_tenant():
    return getattr(_thread_locals, "tenant", None)

def set_current_tenant(tenant):
    _thread_locals.tenant = tenant


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        loja = None

        # Exclude local main hosts and base domain
        base_url = getattr(settings, "VESTLINK_BASE_URL", "")
        base_domain = ""
        if base_url:
            parsed = urlparse(base_url)
            base_domain = parsed.hostname.lower() if parsed.hostname else ""

        # Avoid processing main domain as tenant
        if host in {"127.0.0.1", "localhost", "testserver"} or (base_domain and host == base_domain):
            pass
        elif host.endswith(".localhost"):
            subdomain = host[:-10] # remove ".localhost"
            loja = Loja.objects.filter(slug=subdomain).first()
        elif base_domain and host.endswith("." + base_domain):
            subdomain = host[:-(len(base_domain) + 1)]
            loja = Loja.objects.filter(slug=subdomain).first()
        elif host.endswith(".vercel.app") and host != "vestlink.vercel.app":
            parts = host.split(".")
            if len(parts) >= 3:
                subdomain = parts[0]
                loja = Loja.objects.filter(slug=subdomain).first()
        
        # If not matched by subdomain, check custom domain
        if not loja and host not in {"127.0.0.1", "localhost", "testserver"} and host != base_domain:
            loja = Loja.objects.filter(dominio_personalizado__iexact=host).first()

        if loja:
            request.loja = loja
            request.urlconf = "config.urls_tenant"
            set_current_tenant(loja)
        else:
            set_current_tenant(None)

        try:
            response = self.get_response(request)
        finally:
            set_current_tenant(None)

        return response


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.VESTLINK_MAINTENANCE and not request.path.startswith(settings.STATIC_URL):
            response = render(request, "maintenance.html", status=503)
            response["Retry-After"] = "3600"
            return response
        return self.get_response(request)
