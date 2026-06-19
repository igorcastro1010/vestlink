import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailError(Exception):
    pass


class ResendEmailBackend(BaseEmailBackend):
    api_url = "https://api.resend.com/emails"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if self.fail_silently:
                return 0
            raise ResendEmailError("RESEND_API_KEY nao configurado.")

        sent = 0
        for message in email_messages:
            if self._send(message, api_key):
                sent += 1
        return sent

    def _send(self, message, api_key):
        payload = self._payload_from_message(message)
        request = urllib.request.Request(
            getattr(settings, "RESEND_API_URL", self.api_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=getattr(settings, "RESEND_TIMEOUT_SECONDS", 10)) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as error:
            if self.fail_silently:
                return False
            body = error.read().decode("utf-8", errors="replace")
            raise ResendEmailError(f"Resend retornou HTTP {error.code}: {body}") from error
        except Exception as error:
            if self.fail_silently:
                return False
            raise ResendEmailError(f"Erro ao enviar e-mail pelo Resend: {error}") from error

    def _payload_from_message(self, message):
        text_body = message.body
        html_body = None

        if getattr(message, "content_subtype", "") == "html":
            html_body = message.body
            text_body = None

        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_body = content
                break

        payload = {
            "from": message.from_email or getattr(settings, "DEFAULT_FROM_EMAIL", ""),
            "to": list(message.to),
            "subject": message.subject,
        }

        if text_body:
            payload["text"] = text_body
        if html_body:
            payload["html"] = html_body
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        return payload
