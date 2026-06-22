import json
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from loja.models import Categoria, Lead, Loja, Produto, Vendedor


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
        self.assertContains(response, "Link personalizado")
        self.assertContains(response, "/c/teste-moda/")
        self.assertContains(response, "QR Code")
        self.assertContains(response, reverse("baixar_qr_code", kwargs={"slug": self.loja.slug}))
        self.assertContains(response, "Interesses recebidos")
        self.assertContains(response, "Produtos mais clicados")
        self.assertContains(response, "Leads por dia")
        self.assertContains(response, "Resumo comercial")
        self.assertContains(response, "Compartilhar catálogo")
        self.assertContains(response, "Loja ativa")
        self.assertContains(response, "Iniciar tour")
        self.assertContains(response, "Mensagens prontas para divulgar")
        self.assertContains(response, "Estoque visual por variacao")
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
