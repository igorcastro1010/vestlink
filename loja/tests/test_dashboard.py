import json
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from loja.models import Categoria, Lead, Loja, Produto, Vendedor, ProdutoVariacao


class DashboardTests(TestCase):
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

    def test_painel_renderiza_area_da_loja(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publique sua loja em poucos passos")
        self.assertContains(response, "WhatsApp testado")
        self.assertContains(response, "Adicionar produto")
        self.assertContains(response, "Produtos cadastrados")
        self.assertContains(response, "Copiar link")
        self.assertContains(response, "Link do catálogo")
        self.assertContains(response, "/c/teste-moda/")
        self.assertContains(response, "QR Code")
        self.assertContains(response, reverse("baixar_qr_code", kwargs={"slug": self.loja.slug}))
        self.assertContains(response, "Interesses recebidos")
        self.assertContains(response, "Produtos mais clicados")
        self.assertContains(response, "Leads por dia")
        self.assertContains(response, "Resumo comercial")
        self.assertContains(response, "Painel geral")
        self.assertContains(response, "Loja ativa")
        self.assertContains(response, "Iniciar tour")
        self.assertContains(response, "Mensagens prontas para divulgar")
        self.assertContains(response, "Estoque visual por variação")
        self.assertContains(response, "O que melhorar agora")
        self.assertContains(response, "Configuração")
        self.assertContains(response, "Organizar catálogo")
        self.assertContains(response, f'href="{reverse("painel")}"')
        self.assertContains(response, f'href="{reverse("catalogo", kwargs={"slug": self.loja.slug})}"')
        self.assertContains(response, f'action="{reverse("logout")}"')

    def test_dono_pode_baixar_qr_code_da_loja(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("baixar_qr_code", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")

    def test_painel_loja_vendedor_nao_ve_assinatura(self):
        vendedor_user = User.objects.create_user(username="vendedor", password="senha-vendedor-123")
        Vendedor.objects.create(
            loja=self.loja,
            usuario=vendedor_user,
            nome="Vendedor Teste",
            codigo="vend-123",
            telefone="85988888888",
        )
        self.client.force_login(vendedor_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Assinatura")
        self.assertNotContains(response, "Minha Assinatura")

    def test_painel_renderiza_onboarding_geral(self):
        self.client.force_login(self.user)
        # Loja sem telefone/categoria/produto deve exibir onboarding
        self.loja.telefone = ""
        self.loja.save(update_fields=["telefone"])
        self.produto.delete()
        self.categoria.delete()

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Onboarding")

    def test_painel_redireciona_vendedor_ativo(self):
        vendedor_user = User.objects.create_user(username="vendedor_ativo", password="senha-vendedor-123")
        Vendedor.objects.create(
            loja=self.loja,
            usuario=vendedor_user,
            nome="Vendedor Ativo",
            codigo="vend-ativo",
            ativo=True,
        )
        self.client.force_login(vendedor_user)

        response = self.client.get(reverse("painel"))

        # Deve redirecionar para a loja do vendedor
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("painel_loja", kwargs={"slug": self.loja.slug}))

    def test_painel_bloqueia_vendedor_inativo(self):
        vendedor_user = User.objects.create_user(username="vendedor_inativo", password="senha-vendedor-123")
        Vendedor.objects.create(
            loja=self.loja,
            usuario=vendedor_user,
            nome="Vendedor Inativo",
            codigo="vend-inativo",
            ativo=False,
        )
        self.client.force_login(vendedor_user)

        response = self.client.get(reverse("painel"))

        self.assertEqual(response.status_code, 403)

    def test_painel_exige_login(self):
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_painel_cria_categoria(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "criar_categoria", "nome": "Vestidos", "ordem": "2"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(loja=self.loja, nome="Vestidos").exists())

    def test_usuario_nao_acessa_loja_de_outro_usuario(self):
        outro = User.objects.create_user(username="outro", password="senha-forte-123")
        self.client.force_login(outro)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 403)

    def test_usuario_nao_remove_loja_de_outro_usuario(self):
        outro = User.objects.create_user(username="outro_remover", password="senha-forte-123")
        self.client.force_login(outro)

        response = self.client.post(
            reverse("remover_loja", kwargs={"slug": self.loja.slug}),
            {"confirmacao": self.loja.slug},
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Loja.objects.filter(id=self.loja.id).exists())

    def test_remover_loja_exige_confirmacao_com_slug(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("remover_loja", kwargs={"slug": self.loja.slug}),
            {"confirmacao": "texto-errado"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Digite {self.loja.slug}")
        self.assertTrue(Loja.objects.filter(id=self.loja.id).exists())

    def test_remover_loja_com_confirmacao_exclui(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("remover_loja", kwargs={"slug": self.loja.slug}),
            {"confirmacao": self.loja.slug},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("painel"))
        self.assertFalse(Loja.objects.filter(id=self.loja.id).exists())


class DashboardChartsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Cache",
            slug="teste-cache",
            telefone="85999999999",
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Roupas")

    def test_dashboard_charts_context_variables(self):
        # Authenticate
        self.client.force_login(self.user)
        
        # Create some leads to generate chart data
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Vestido Festa",
            preco="250.00",
            imagem="produtos/vestido.png",
            cliques_whatsapp=10
        )
        Lead.objects.create(
            loja=self.loja,
            produto=produto,
            origem=Lead.ORIGEM_PRODUTO,
            cliente_nome="Maria",
            cliente_telefone="85988888888",
            status=Lead.STATUS_NOVO
        )
        
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("chart_leads_labels", response.context)
        self.assertIn("chart_leads_valores", response.context)
        self.assertIn("chart_horarios_labels", response.context)
        self.assertIn("chart_horarios_valores", response.context)
        self.assertIn("chart_produtos_labels", response.context)
        self.assertIn("chart_produtos_valores", response.context)
        
        # Load as JSON and assert contents
        leads_labels = json.loads(response.context["chart_leads_labels"])
        leads_valores = json.loads(response.context["chart_leads_valores"])
        produtos_labels = json.loads(response.context["chart_produtos_labels"])
        produtos_valores = json.loads(response.context["chart_produtos_valores"])
        
        self.assertEqual(len(leads_valores), 1)
        self.assertEqual(leads_valores[0], 1)
        self.assertIn("Vestido Festa", produtos_labels)
        self.assertIn(10, produtos_valores)


class DashboardVendedorTests(TestCase):
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
        )
        self.vendedor_com_tel = Vendedor.objects.create(
            loja=self.loja,
            nome="Maria com Tel",
            codigo="maria-tel",
            telefone="(85) 91111-2222",
        )
        self.vendedor_sem_tel = Vendedor.objects.create(
            loja=self.loja,
            nome="Maria sem Tel",
            codigo="maria-sem",
            telefone="",
        )

    def test_contexto_painel_inclui_grafico_vendedores(self):
        self.client.force_login(self.user)
        Lead.objects.create(
            loja=self.loja,
            vendedor=self.vendedor_com_tel,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cliente_nome="Ana",
        )
        
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("chart_vendedores_labels", response.context)
        self.assertIn("chart_vendedores_valores", response.context)
        
        labels = json.loads(response.context["chart_vendedores_labels"])
        valores = json.loads(response.context["chart_vendedores_valores"])
        self.assertIn("Maria com Tel", labels)
        self.assertIn(1, valores)


class DashboardStockAlertTests(TestCase):
    def setUp(self):
        # Lojista and Store A
        self.user_a = User.objects.create_user(username="lojista_a", password="password123")
        self.loja_a = Loja.objects.create(
            usuario=self.user_a,
            nome="Loja A",
            slug="loja-a",
            telefone="85999999999",
        )
        self.prod_a = Produto.objects.create(
            loja=self.loja_a,
            nome="Produto A",
            preco="50.00",
            imagem="produtos/a.png",
        )

        # Lojista and Store B
        self.user_b = User.objects.create_user(username="lojista_b", password="password123")
        self.loja_b = Loja.objects.create(
            usuario=self.user_b,
            nome="Loja B",
            slug="loja-b",
            telefone="85988888888",
        )
        self.prod_b = Produto.objects.create(
            loja=self.loja_b,
            nome="Produto B",
            preco="60.00",
            imagem="produtos/b.png",
        )

    def test_painel_shows_low_stock_variation(self):
        self.client.force_login(self.user_a)
        # Create a low stock variation (estoque = 2, disponivel = True)
        var = ProdutoVariacao.objects.create(
            produto=self.prod_a,
            cor="Preto",
            tamanho="M",
            estoque=2,
            disponivel=True,
        )
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_a.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertIn("variacoes_criticas", response.context)
        self.assertEqual(len(response.context["variacoes_criticas"]), 1)
        self.assertEqual(response.context["variacoes_criticas"][0], var)
        self.assertContains(response, "Produto A")
        self.assertContains(response, "Cor: Preto")
        self.assertContains(response, "Tamanho: M")
        self.assertContains(response, "2 un.")
        self.assertContains(response, "Estoque baixo")

    def test_painel_shows_sold_out_variation(self):
        self.client.force_login(self.user_a)
        # Create a sold out variation (estoque = 0)
        var1 = ProdutoVariacao.objects.create(
            produto=self.prod_a,
            cor="Branco",
            tamanho="P",
            estoque=0,
            disponivel=True,
        )
        # Create a variation with estoque > 3 but unavailable
        var2 = ProdutoVariacao.objects.create(
            produto=self.prod_a,
            cor="Azul",
            tamanho="G",
            estoque=5,
            disponivel=False,
        )
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_a.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["variacoes_criticas"]), 2)
        self.assertIn(var1, response.context["variacoes_criticas"])
        self.assertIn(var2, response.context["variacoes_criticas"])
        self.assertContains(response, "Cor: Branco")
        self.assertContains(response, "Tamanho: P")
        self.assertContains(response, "0 un.")
        self.assertContains(response, "Cor: Azul")
        self.assertContains(response, "Tamanho: G")
        self.assertContains(response, "5 un.")

    def test_painel_limits_to_5_items_and_orders_correctly(self):
        self.client.force_login(self.user_a)
        # Create 6 variations:
        # V1: low stock 3, disp True
        # V2: low stock 1, disp True
        # V3: stock 0, disp True (Esgotado)
        # V4: stock 5, disp False (Esgotado)
        # V5: stock 2, disp True
        # V6: stock 0, disp False (Esgotado)
        
        v1 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C1", tamanho="T1", estoque=3, disponivel=True)
        v2 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C2", tamanho="T2", estoque=1, disponivel=True)
        v3 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C3", tamanho="T3", estoque=0, disponivel=True)
        v4 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C4", tamanho="T4", estoque=5, disponivel=False)
        v5 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C5", tamanho="T5", estoque=2, disponivel=True)
        v6 = ProdutoVariacao.objects.create(produto=self.prod_a, cor="C6", tamanho="T6", estoque=0, disponivel=False)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_a.slug}))
        self.assertEqual(response.status_code, 200)
        
        criticas = response.context["variacoes_criticas"]
        self.assertEqual(len(criticas), 5)  # Limit 5
        
        # Check sorting:
        # Esgotados: v3, v4, v6 (is_esgotado=True)
        # Low stock: v2, v5, v1 (is_esgotado=False)
        # Ordered by -is_esgotado, estoque, product_name, cor, tamanho
        # Esgotados sorted by estoque:
        # v3 (0), v6 (0), v4 (5) -> v3 and v6 have estoque=0. v3 has cor "C3", v6 has cor "C6". C3 comes before C6.
        # So esgotados order: v3, v6, v4
        # Low stock sorted by estoque:
        # v2 (1), v5 (2), v1 (3)
        # So expected top 5: v3, v6, v4, v2, v5
        expected = [v3, v6, v4, v2, v5]
        self.assertEqual(criticas, expected)

    def test_painel_shows_positive_state_when_no_critical_stock(self):
        self.client.force_login(self.user_a)
        # Create a healthy variation (estoque = 10, disponivel = True)
        ProdutoVariacao.objects.create(
            produto=self.prod_a,
            cor="Preto",
            tamanho="M",
            estoque=10,
            disponivel=True,
        )
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_a.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["variacoes_criticas"]), 0)
        self.assertContains(response, "Nenhum item crítico no estoque agora.")

    def test_vendedor_isolation_and_permissions(self):
        # Create seller for Loja A
        vendedor_user = User.objects.create_user(username="vendedor_a", password="password123")
        Vendedor.objects.create(
            loja=self.loja_a,
            usuario=vendedor_user,
            nome="Vendedor A",
            codigo="venda-a",
        )

        # Create seller for Loja B
        vendedor_b_user = User.objects.create_user(username="vendedor_b", password="password123")
        Vendedor.objects.create(
            loja=self.loja_b,
            usuario=vendedor_b_user,
            nome="Vendedor B",
            codigo="venda-b",
        )

        # Create a critical variation in Loja A
        var_a = ProdutoVariacao.objects.create(
            produto=self.prod_a,
            cor="Rosa",
            tamanho="G",
            estoque=1,
            disponivel=True,
        )

        # Create a critical variation in Loja B
        var_b = ProdutoVariacao.objects.create(
            produto=self.prod_b,
            cor="Verde",
            tamanho="GG",
            estoque=1,
            disponivel=True,
        )

        # Log in as Vendedor A and request Loja A's dashboard
        self.client.force_login(vendedor_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_a.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertIn(var_a, response.context["variacoes_criticas"])
        self.assertNotIn(var_b, response.context["variacoes_criticas"])

        # Try to request Loja B's dashboard as Vendedor A -> should be forbidden (403)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja_b.slug}))
        self.assertEqual(response.status_code, 403)
