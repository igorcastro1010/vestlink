from django.conf import settings
from django.urls import path, re_path
from django.views.static import serve as static_serve
from loja.views import (
    catalogo,
    produto_detalhe,
    whatsapp_produto,
    whatsapp_carrinho,
)

urlpatterns = [
    re_path(r"^static/(?P<path>.*)$", static_serve, {"document_root": settings.BASE_DIR / "static"}),
    path("", catalogo, {"slug": None}, name="catalogo"),
    path("", catalogo, {"slug": None}, name="catalogo_curto"),
    path("produto/<int:produto_id>/", produto_detalhe, {"slug": None}, name="produto_detalhe"),
    path("produto/<int:produto_id>/", produto_detalhe, {"slug": None}, name="produto_detalhe_curto"),
    path("produto/<int:produto_id>/whatsapp/", whatsapp_produto, {"slug": None}, name="whatsapp_produto"),
    path("carrinho/whatsapp/", whatsapp_carrinho, {"slug": None}, name="whatsapp_carrinho"),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
