from unittest.mock import patch
from urllib.error import HTTPError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from loja.storage import SupabaseStorage


class SupabaseStorageTests(TestCase):
    class _Response:
        headers = {"Content-Length": "2"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"ok"

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_STORAGE_BUCKET="vestlink-media",
        SUPABASE_STORAGE_KEY="service-role-key",
        SUPABASE_STORAGE_TIMEOUT_SECONDS=20,
    )
    @patch("loja.storage.urllib.request.urlopen")
    def test_save_usa_api_do_supabase_storage(self, mock_urlopen):
        def fake_urlopen(request, timeout):
            if request.method == "HEAD":
                raise HTTPError(request.full_url, 404, "Not Found", None, None)
            return self._Response()

        mock_urlopen.side_effect = fake_urlopen
        storage = SupabaseStorage()

        name = storage.save("produtos/teste.png", ContentFile(b"ok"))

        self.assertEqual(name, "produtos/teste.png")
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://example.supabase.co/storage/v1/object/vestlink-media/produtos/teste.png")
        self.assertEqual(request.headers["Authorization"], "Bearer service-role-key")

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_STORAGE_BUCKET="vestlink-media",
        SUPABASE_STORAGE_KEY="service-role-key",
        SUPABASE_STORAGE_TIMEOUT_SECONDS=20,
    )
    def test_url_publica_do_supabase_storage(self):
        storage = SupabaseStorage()

        url = storage.url("produtos/teste com espaco.png")

        self.assertEqual(
            url,
            "https://example.supabase.co/storage/v1/object/public/vestlink-media/produtos/teste%20com%20espaco.png",
        )
