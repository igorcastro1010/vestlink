from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from loja.models import Categoria, Loja, Produto


class CatalogoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Moda",
            slug="teste-moda",
            telefone="85999999999",
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Blusas")
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Blusa Preta",
            preco="79.90",
            imagem="produtos/blusa.png",
            tamanhos="P, M, G",
            tamanhos_esgotados="M",
            cores="Preto, Branco",
            cores_esgotadas="Branco",
        )

    def test_catalogo_publico_renderiza_produto(self):
        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teste Moda")
        self.assertContains(response, "Blusa Preta")
        self.assertContains(response, "Comprar pelo WhatsApp")
        self.assertContains(response, 'class="choice-option size-option"')
        self.assertContains(response, 'data-size="M"')
        self.assertContains(response, 'class="choice-option color-option"')
        self.assertContains(response, 'data-color="Preto"')
        self.assertContains(response, "Tamanho esgotado")
        self.assertContains(response, "Cor esgotada")
        self.assertContains(response, "Escolha tamanho e cor")
        self.assertContains(response, "store-filters")
        self.assertContains(response, "WhatsApp da loja")
        self.assertContains(response, "store-theme-elegante")
        self.assertContains(response, "Sacolinha")
        self.assertContains(response, "Adicionar a sacolinha")

    def test_catalogo_curto_renderiza_loja(self):
        response = self.client.get(reverse("catalogo_curto", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teste Moda")

    def test_produto_detalhe_renderiza_link_individual(self):
        response = self.client.get(
            reverse("produto_detalhe_curto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blusa Preta")
        self.assertContains(response, "Voltar ao catálogo")

    def test_catalogo_nao_exibe_produto_rascunho(self):
        self.produto.publicado = False
        self.produto.save(update_fields=["publicado"])

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Blusa Preta")

    def test_catalogo_exibe_preco_antigo(self):
        self.produto.preco_antigo = "99.90"
        self.produto.promocao = True
        self.produto.save(update_fields=["preco_antigo", "promocao"])

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "R$ 99,90")

    def test_catalogo_filtra_produtos_novos(self):
        self.produto.destaque = True
        self.produto.save(update_fields=["destaque"])

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}), {"filtro": "novos"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blusa Preta")
        self.assertContains(response, "Novos produtos")

    def test_catalogo_bloqueia_assinatura_inativa(self):
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 402)
        self.assertContains(response, "Catálogo pausado", status_code=402)
        self.assertNotContains(response, "Blusa Preta", status_code=402)

    @override_settings(ALLOWED_HOSTS=["catalogo.teste.com"])
    def test_home_renderiza_catalogo_por_dominio_personalizado(self):
        self.loja.dominio_personalizado = "catalogo.teste.com"
        self.loja.save(update_fields=["dominio_personalizado"])

        response = self.client.get("/", HTTP_HOST="catalogo.teste.com")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teste Moda")
        self.assertContains(response, "Blusa Preta")

    def test_busca_filtra_produtos(self):
        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}), {"q": "preta"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blusa Preta")

    def test_categoria_filtra_produtos(self):
        response = self.client.get(
            reverse("catalogo", kwargs={"slug": self.loja.slug}),
            {"categoria": str(self.categoria.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blusa Preta")

    def test_paginacao_catalogo_primeira_pagina(self):
        # Cria mais 14 produtos para termos 15 no total (um já é criado no setUp)
        for i in range(14):
            Produto.objects.create(
                loja=self.loja,
                categoria=self.categoria,
                nome=f"Blusa Extra {i}",
                preco="49.90",
                imagem="produtos/extra.png",
            )

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}))
        
        self.assertEqual(response.status_code, 200)
        # Deve conter no máximo 12 produtos na primeira página (11 extras + o inicial)
        self.assertContains(response, 'id="produto-', count=12)
        # Deve exibir o botão "Carregar Mais" com o link da página 2
        self.assertContains(response, 'id="btn-carregar-mais"')
        self.assertContains(response, 'data-next-page="2"')

    def test_paginacao_catalogo_segunda_pagina(self):
        for i in range(14):
            Produto.objects.create(
                loja=self.loja,
                categoria=self.categoria,
                nome=f"Blusa Extra {i}",
                preco="49.90",
                imagem="produtos/extra.png",
            )

        response = self.client.get(reverse("catalogo", kwargs={"slug": self.loja.slug}), {"page": "2"})
        
        self.assertEqual(response.status_code, 200)
        # A segunda página deve conter os 3 produtos restantes (15 no total, 12 na primeira, 3 na segunda)
        self.assertContains(response, 'id="produto-', count=3)
        # Não deve conter o botão "Carregar Mais" pois não há mais páginas
        self.assertNotContains(response, 'id="btn-carregar-mais"')

    def test_paginacao_catalogo_requisicao_fragmento(self):
        for i in range(14):
            Produto.objects.create(
                loja=self.loja,
                categoria=self.categoria,
                nome=f"Blusa Extra {i}",
                preco="49.90",
                imagem="produtos/extra.png",
            )

        # Simula requisição com parâmetro fragment=1
        response = self.client.get(
            reverse("catalogo", kwargs={"slug": self.loja.slug}),
            {"page": "1", "fragment": "1"}
        )
        
        self.assertEqual(response.status_code, 200)
        # Deve renderizar os 12 produtos
        self.assertContains(response, 'id="produto-', count=12)
        # Deve conter o indicador oculto de próxima página no fragmento
        self.assertContains(response, 'id="next-page-indicator"')
        self.assertContains(response, 'data-next-page="2"')
        # Não deve conter tags estruturais do catálogo completo (ex.: header ou aside)
        self.assertNotContains(response, '<header class="store-header"')
        self.assertNotContains(response, '<body class="storefront')


class SaasTenantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Moda",
            slug="teste-moda",
            telefone="85999999999",
            dominio_personalizado="catalogo.teste.com",
            assinatura_status=Loja.ASSINATURA_TRIAL,
            trial_termina_em=timezone.now() - timedelta(days=1)
        )

    @override_settings(ALLOWED_HOSTS=["teste-moda.localhost", "catalogo.teste.com"])
    def test_tenant_middleware_resolves_subdomain(self):
        response = self.client.get("/", HTTP_HOST="teste-moda.localhost")
        self.assertEqual(response.status_code, 402)

    @override_settings(ALLOWED_HOSTS=["catalogo.teste.com"])
    def test_tenant_middleware_resolves_custom_domain(self):
        response = self.client.get("/", HTTP_HOST="catalogo.teste.com")
        self.assertEqual(response.status_code, 402)
