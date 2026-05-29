from django.conf import settings
from django.shortcuts import render


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.VESTLINK_MAINTENANCE and not request.path.startswith(settings.STATIC_URL):
            response = render(request, "maintenance.html", status=503)
            response["Retry-After"] = "3600"
            return response
        return self.get_response(request)
