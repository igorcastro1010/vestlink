import json
import mimetypes
import posixpath
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage

mimetypes.add_type("image/webp", ".webp")


class SupabaseStorage(Storage):
    def __init__(self, bucket_name=None, base_url=None, api_key=None):
        self.bucket_name = bucket_name or settings.SUPABASE_STORAGE_BUCKET
        self.base_url = (base_url or settings.SUPABASE_URL).rstrip("/")
        self.api_key = api_key or settings.SUPABASE_STORAGE_KEY

    def _open(self, name, mode="rb"):
        request = self._request("GET", self._object_url(name))
        with urllib.request.urlopen(request, timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as response:
            return ContentFile(response.read(), name=name)

    def _save(self, name, content):
        name = self.get_available_name(self._clean_name(name))
        content_type = getattr(content, "content_type", "") or mimetypes.guess_type(name)[0] or "application/octet-stream"
        body = b"".join(content.chunks()) if hasattr(content, "chunks") else content.read()
        request = self._request(
            "POST",
            self._object_url(name),
            body=body,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "31536000",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as response:
                response.read()
        except urllib.error.HTTPError as error:
            response_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase Storage retornou HTTP {error.code}: {response_body}") from error
        return name

    def delete(self, name):
        if not name:
            return
        body = json.dumps({"prefixes": [self._clean_name(name)]}).encode("utf-8")
        request = self._request(
            "DELETE",
            f"{self.base_url}/storage/v1/object/{urllib.parse.quote(self.bucket_name, safe='')}",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as response:
                response.read()
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise

    def exists(self, name):
        request = self._request("HEAD", self._object_url(name))
        try:
            with urllib.request.urlopen(request, timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS):
                return True
        except urllib.error.HTTPError as error:
            if error.code in {400, 404}:
                return False
            raise

    def url(self, name):
        clean_name = urllib.parse.quote(self._clean_name(name), safe="/")
        bucket = urllib.parse.quote(self.bucket_name, safe="")
        return f"{self.base_url}/storage/v1/object/public/{bucket}/{clean_name}"

    def size(self, name):
        request = self._request("HEAD", self._object_url(name))
        with urllib.request.urlopen(request, timeout=settings.SUPABASE_STORAGE_TIMEOUT_SECONDS) as response:
            return int(response.headers.get("Content-Length", 0))

    def _object_url(self, name):
        bucket = urllib.parse.quote(self.bucket_name, safe="")
        clean_name = urllib.parse.quote(self._clean_name(name), safe="/")
        return f"{self.base_url}/storage/v1/object/{bucket}/{clean_name}"

    def _request(self, method, url, body=None, headers=None):
        if not self.base_url or not self.api_key or not self.bucket_name:
            raise RuntimeError("Supabase Storage nao configurado.")
        request_headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        request_headers.update(headers or {})
        return urllib.request.Request(url, data=body, method=method, headers=request_headers)

    def _clean_name(self, name):
        clean_name = posixpath.normpath(str(name).replace("\\", "/")).lstrip("/")
        if clean_name == ".":
            return ""
        return clean_name
