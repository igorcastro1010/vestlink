import json
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from loja.models import Categoria, Lead, Loja, Produto, ProdutoVariacao, Vendedor


class LeadsTests(TestCase):
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

    def test_whatsapp_produto_contabiliza_clique(self):
        response = self.client.get(
            reverse("whatsapp_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {"tamanho": "P", "cor": "Preto", "cliente_nome": "Ana"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me", response["Location"])
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.cliques_whatsapp, 1)
        lead = Lead.objects.get(loja=self.loja, produto=self.produto, origem=Lead.ORIGEM_PRODUTO)
        self.assertEqual(lead.cliente_nome, "Ana")
        self.assertIn("Cliente: Ana", lead.mensagem)
        self.assertIn("Cliente%3A%20Ana", response["Location"])

    def test_catalogo_com_link_de_vendedor_preserva_referencia(self):
        Vendedor.objects.create(loja=self.loja, nome="Maria", codigo="maria", telefone="85999999999")

        response = self.client.get(reverse("catalogo_curto", kwargs={"slug": self.loja.slug}), {"vendedor": "maria"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-seller-code="maria"')
        self.assertContains(response, f'{reverse("produto_detalhe_curto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id})}?vendedor=maria')

    def test_painel_cadastra_vendedor_com_codigo_automatico(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "criar_vendedor", "nome": "Maria Silva", "codigo": "", "telefone": "85999999999", "ativo": "on"},
        )

        self.assertEqual(response.status_code, 302)
        vendedor = Vendedor.objects.get(loja=self.loja, nome="Maria Silva")
        self.assertEqual(vendedor.codigo, "maria-silva")
        self.assertTrue(vendedor.ativo)

    def test_painel_alterna_e_remove_vendedor(self):
        self.client.force_login(self.user)
        vendedor = Vendedor.objects.create(loja=self.loja, nome="Maria", codigo="maria")

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "alternar_vendedor", "vendedor_id": str(vendedor.id)},
        )

        self.assertEqual(response.status_code, 302)
        vendedor.refresh_from_db()
        self.assertFalse(vendedor.ativo)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "remover_vendedor", "vendedor_id": str(vendedor.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Vendedor.objects.filter(id=vendedor.id).exists())

    def test_whatsapp_produto_atribui_lead_ao_vendedor(self):
        vendedor = Vendedor.objects.create(loja=self.loja, nome="Maria", codigo="maria")

        response = self.client.get(
            reverse("whatsapp_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {"vendedor": "maria", "cliente_nome": "Ana"},
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(loja=self.loja, produto=self.produto, origem=Lead.ORIGEM_PRODUTO)
        self.assertEqual(lead.vendedor, vendedor)
        self.assertIn("Vendedor: Maria", lead.mensagem)
        self.assertIn("Vendedor%3A%20Maria", response["Location"])

    def test_whatsapp_carrinho_cria_lead(self):
        response = self.client.get(
            reverse("whatsapp_carrinho", kwargs={"slug": self.loja.slug}),
            {
                "mensagem": "Olá! Quero fazer um pedido:\n1. Blusa Preta",
                "cliente_nome": "Ana",
                "cliente_telefone": "85988887777",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me", response["Location"])
        lead = Lead.objects.get(loja=self.loja, origem=Lead.ORIGEM_SACOLINHA)
        self.assertEqual(lead.cliente_nome, "Ana")
        self.assertEqual(lead.cliente_telefone, "85988887777")

    def test_painel_atualiza_status_do_pedido(self):
        lead = Lead.objects.create(loja=self.loja, produto=self.produto, origem=Lead.ORIGEM_PRODUTO)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "acao": "atualizar_lead_status",
                "lead_id": str(lead.id),
                "status": Lead.STATUS_CONCLUIDO,
                "observacao": "Cliente pediu entrega",
            },
        )

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.STATUS_CONCLUIDO)
        self.assertEqual(lead.observacao, "Cliente pediu entrega")
        self.assertEqual(lead.status_atualizado_por, self.user)
        self.assertIsNotNone(lead.status_atualizado_em)

    def test_concluir_lead_baixa_estoque_da_variacao_em_um(self):
        variacao = ProdutoVariacao.objects.create(
            produto=self.produto,
            cor="Preto",
            tamanho="P",
            estoque=2,
            disponivel=True,
        )
        lead = Lead.objects.create(
            loja=self.loja,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cor="Preto",
            tamanho="P",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "atualizar_lead_status", "lead_id": str(lead.id), "status": Lead.STATUS_CONCLUIDO},
        )

        self.assertEqual(response.status_code, 302)
        variacao.refresh_from_db()
        self.produto.refresh_from_db()
        self.assertEqual(variacao.estoque, 1)
        self.assertTrue(variacao.disponivel)
        self.assertFalse(self.produto.esgotado)

    def test_concluir_lead_ja_concluido_nao_baixa_estoque_duas_vezes(self):
        variacao = ProdutoVariacao.objects.create(
            produto=self.produto,
            cor="Preto",
            tamanho="P",
            estoque=2,
            disponivel=True,
        )
        lead = Lead.objects.create(
            loja=self.loja,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cor="Preto",
            tamanho="P",
            status=Lead.STATUS_CONCLUIDO,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "atualizar_lead_status", "lead_id": str(lead.id), "status": Lead.STATUS_CONCLUIDO},
        )

        self.assertEqual(response.status_code, 302)
        variacao.refresh_from_db()
        self.assertEqual(variacao.estoque, 2)

    def test_concluir_lead_nao_deixa_estoque_negativo(self):
        variacao = ProdutoVariacao.objects.create(
            produto=self.produto,
            cor="Preto",
            tamanho="P",
            estoque=0,
            disponivel=True,
        )
        lead = Lead.objects.create(
            loja=self.loja,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cor="Preto",
            tamanho="P",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "atualizar_lead_status", "lead_id": str(lead.id), "status": Lead.STATUS_CONCLUIDO},
        )

        self.assertEqual(response.status_code, 302)
        variacao.refresh_from_db()
        self.assertEqual(variacao.estoque, 0)

    def test_concluir_lead_esgota_produto_quando_ultima_variacao_zera(self):
        variacao = ProdutoVariacao.objects.create(
            produto=self.produto,
            cor="Preto",
            tamanho="P",
            estoque=1,
            disponivel=True,
        )
        lead = Lead.objects.create(
            loja=self.loja,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cor="Preto",
            tamanho="P",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "atualizar_lead_status", "lead_id": str(lead.id), "status": Lead.STATUS_CONCLUIDO},
        )

        self.assertEqual(response.status_code, 302)
        variacao.refresh_from_db()
        self.produto.refresh_from_db()
        self.assertEqual(variacao.estoque, 0)
        self.assertFalse(variacao.disponivel)
        self.assertTrue(self.produto.esgotado)


class VendedorRedirecionamentoETelefoneTests(TestCase):
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

    def test_limpeza_telefone_limpa_caracteres_especiais_e_prefixo_55(self):
        from loja.validators import limpar_telefone
        self.assertEqual(limpar_telefone("+55 (85) 91111-2222"), "85911112222")
        self.assertEqual(limpar_telefone("85 91111-2222"), "85911112222")
        self.assertEqual(limpar_telefone("5585911112222"), "85911112222")
        self.assertEqual(limpar_telefone("85911112222"), "85911112222")

    def test_validacao_telefone_rejeita_comprimento_invalido(self):
        from django.core.exceptions import ValidationError
        from loja.validators import validar_whatsapp
        with self.assertRaises(ValidationError):
            validar_whatsapp("123")
        with self.assertRaises(ValidationError):
            validar_whatsapp("123456789012")

    def test_redirecionamento_whatsapp_produto_usa_numero_vendedor_se_preenchido(self):
        response = self.client.get(
            reverse("whatsapp_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {"vendedor": "maria-tel"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me/5585911112222", response["Location"])

    def test_redirecionamento_whatsapp_produto_usa_numero_loja_se_vendedor_sem_numero(self):
        response = self.client.get(
            reverse("whatsapp_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {"vendedor": "maria-sem"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me/5585999999999", response["Location"])


class NovosRecursosLeadsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Saas",
            slug="teste-saas",
            telefone="85999999999",
        )

    def test_whatsapp_carrinho_salva_tipo_entrega_e_endereco(self):
        response = self.client.get(
            reverse("whatsapp_carrinho", kwargs={"slug": self.loja.slug}),
            {
                "mensagem": "Olá! Quero fazer um pedido:\n1. Item",
                "cliente_nome": "Ana",
                "cliente_telefone": "85988887777",
                "tipo_entrega": "entrega",
                "endereco_completo": "Rua das Flores, 123 - Centro - Fortaleza - CEP 60000-000",
            },
        )
        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(loja=self.loja, cliente_nome="Ana")
        self.assertEqual(lead.tipo_entrega, "entrega")
        self.assertEqual(lead.endereco_completo, "Rua das Flores, 123 - Centro - Fortaleza - CEP 60000-000")
        self.assertEqual(lead.origem, Lead.ORIGEM_SACOLINHA)

    def test_exportar_leads_csv_retorna_arquivo_correto(self):
        Lead.objects.create(
            loja=self.loja,
            origem=Lead.ORIGEM_SACOLINHA,
            cliente_nome="Pedro",
            cliente_telefone="85911112222",
            tipo_entrega="retirada",
            endereco_completo="",
            mensagem="Olá",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("exportar_leads_csv", kwargs={"slug": self.loja.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8-sig")
        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("Pedro", content)
        self.assertIn("Retirada na Loja", content)

    def test_exportar_leads_impressao_renderiza_template(self):
        Lead.objects.create(
            loja=self.loja,
            origem=Lead.ORIGEM_SACOLINHA,
            cliente_nome="Maria",
            cliente_telefone="85911113333",
            tipo_entrega="entrega",
            endereco_completo="Endereço de teste",
            mensagem="Olá",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("exportar_leads_impressao", kwargs={"slug": self.loja.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relatório de leads")
        self.assertContains(response, "Maria")
        self.assertContains(response, "Endereço de teste")


class FiltrosLeadsEControleAcessoTests(TestCase):
    def setUp(self):
        # Dono da loja
        self.owner_user = User.objects.create_user(username="dono_loja", password="senha-dono-123")
        self.loja = Loja.objects.create(
            usuario=self.owner_user,
            nome="Loja Teste Filtro",
            slug="loja-teste-filtro",
            telefone="85999999999",
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Roupas")
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Camisa Azul",
            preco="50.00",
            imagem="produtos/camisa.png",
        )

        # Vendedor 1
        self.vendedor_user1 = User.objects.create_user(username="vendedor1", password="senha-vend-1")
        self.vendedor1 = Vendedor.objects.create(
            loja=self.loja,
            usuario=self.vendedor_user1,
            nome="Vendedor Um",
            codigo="vend-1",
            telefone="85911111111",
            ativo=True,
        )

        # Vendedor 2
        self.vendedor_user2 = User.objects.create_user(username="vendedor2", password="senha-vend-2")
        self.vendedor2 = Vendedor.objects.create(
            loja=self.loja,
            usuario=self.vendedor_user2,
            nome="Vendedor Dois",
            codigo="vend-2",
            telefone="85922222222",
            ativo=True,
        )

        # Leads
        self.lead_vendedor1 = Lead.objects.create(
            loja=self.loja,
            vendedor=self.vendedor1,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cliente_nome="Alice",
            cliente_telefone="85988880001",
            status=Lead.STATUS_NOVO,
            mensagem="Quero a camisa azul",
        )
        self.lead_vendedor2 = Lead.objects.create(
            loja=self.loja,
            vendedor=self.vendedor2,
            produto=self.produto,
            origem=Lead.ORIGEM_SACOLINHA,
            cliente_nome="Bob",
            cliente_telefone="85988880002",
            status=Lead.STATUS_ATENDIMENTO,
            mensagem="Olá, sacolinha",
        )
        self.lead_direto = Lead.objects.create(
            loja=self.loja,
            vendedor=None,
            produto=None,
            origem=Lead.ORIGEM_SACOLINHA,
            cliente_nome="Carlos",
            cliente_telefone="85988880003",
            status=Lead.STATUS_CONCLUIDO,
            mensagem="Direto sem vendedor",
        )

    def _kanban_colunas(self, response):
        return {coluna["status"]: coluna for coluna in response.context["leads_kanban_colunas"]}

    def test_kanban_renderiza_colunas_de_status(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-kanban-status="novo"')
        self.assertContains(response, 'data-kanban-status="atendimento"')
        self.assertContains(response, 'data-kanban-status="concluido"')
        self.assertContains(response, "<h3>Novos</h3>", html=True)
        self.assertContains(response, "<h3>Em atendimento</h3>", html=True)
        self.assertContains(response, "<h3>Concluídos</h3>", html=True)

    def test_kanban_coloca_lead_apenas_na_coluna_correta(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["leads"], [self.lead_vendedor1])
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["leads"], [self.lead_vendedor2])
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["leads"], [self.lead_direto])

    def test_kanban_contadores_por_coluna_estao_corretos(self):
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        colunas = self._kanban_colunas(response)
        self.assertEqual(response.context["kanban_total_novos"], 1)
        self.assertEqual(response.context["kanban_total_atendimento"], 1)
        self.assertEqual(response.context["kanban_total_concluidos"], 1)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["contador"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["contador"], 1)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["contador"], 1)

    def test_kanban_total_novos_considera_queryset_filtrado_antes_da_paginacao(self):
        for indice in range(12):
            Lead.objects.create(
                loja=self.loja,
                produto=self.produto,
                origem=Lead.ORIGEM_PRODUTO,
                cliente_nome=f"Cliente novo {indice}",
                status=Lead.STATUS_NOVO,
            )
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        colunas = self._kanban_colunas(response)
        self.assertEqual(response.context["total_leads"], 15)
        self.assertEqual(len(list(response.context["leads_recentes"])), 10)
        self.assertEqual(response.context["kanban_total_novos"], 13)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 13)
        self.assertLess(colunas[Lead.STATUS_NOVO]["contador"], colunas[Lead.STATUS_NOVO]["total_status"])
        self.assertContains(response, "13")
        self.assertContains(response, "10 nesta página")

    def test_vendedor_so_visualiza_proprios_leads(self):
        self.client.force_login(self.vendedor_user1)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))
        self.assertEqual(response.status_code, 200)

        # Deve ver apenas o lead atribuído a ele
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_vendedor1)

        # Métricas devem refletir apenas os dele
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["pedidos_novos"], 1)
        self.assertEqual(response.context["pedidos_atendimento"], 0)
        self.assertEqual(response.context["pedidos_concluidos"], 0)
        
        # Como é vendedor, o total_leads_global/pedidos_novos_global também são baseados no leads_base que foi filtrado.
        self.assertEqual(response.context["total_leads_global"], 1)
        self.assertEqual(response.context["pedidos_novos_global"], 1)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["leads"], [self.lead_vendedor1])
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["leads"], [])
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["leads"], [])
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 0)

    def test_vendedor_consegue_concluir_lead_proprio(self):
        self.client.force_login(self.vendedor_user1)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "acao": "atualizar_lead_status",
                "lead_id": str(self.lead_vendedor1.id),
                "status": Lead.STATUS_CONCLUIDO,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.lead_vendedor1.refresh_from_db()
        self.assertEqual(self.lead_vendedor1.status, Lead.STATUS_CONCLUIDO)
        self.assertEqual(self.lead_vendedor1.status_atualizado_por, self.vendedor_user1)
        self.assertIsNotNone(self.lead_vendedor1.status_atualizado_em)

    def test_vendedor_nao_consegue_concluir_lead_de_outro_vendedor(self):
        self.client.force_login(self.vendedor_user1)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "acao": "atualizar_lead_status",
                "lead_id": str(self.lead_vendedor2.id),
                "status": Lead.STATUS_CONCLUIDO,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.lead_vendedor2.refresh_from_db()
        self.assertEqual(self.lead_vendedor2.status, Lead.STATUS_ATENDIMENTO)

    def test_conclusao_feita_por_vendedor_baixa_estoque(self):
        variacao = ProdutoVariacao.objects.create(
            produto=self.produto,
            cor="Azul",
            tamanho="M",
            estoque=2,
            disponivel=True,
        )
        lead = Lead.objects.create(
            loja=self.loja,
            vendedor=self.vendedor1,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cor="Azul",
            tamanho="M",
            status=Lead.STATUS_NOVO,
        )
        self.client.force_login(self.vendedor_user1)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "acao": "atualizar_lead_status",
                "lead_id": str(lead.id),
                "status": Lead.STATUS_CONCLUIDO,
            },
        )

        self.assertEqual(response.status_code, 302)
        variacao.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(variacao.estoque, 1)
        self.assertEqual(lead.status_atualizado_por, self.vendedor_user1)

    def test_dono_ve_quem_atualizou_status_do_lead_no_painel(self):
        self.client.force_login(self.vendedor_user1)
        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "acao": "atualizar_lead_status",
                "lead_id": str(self.lead_vendedor1.id),
                "status": Lead.STATUS_CONCLUIDO,
            },
        )
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atualizado por:")
        self.assertContains(response, "Vendedor Um")
        self.assertContains(response, "Em:")

    def test_dono_visualiza_todos_leads_sem_filtro(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))
        self.assertEqual(response.status_code, 200)

        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 3)

        self.assertEqual(response.context["total_leads_global"], 3)
        self.assertEqual(response.context["pedidos_novos_global"], 1)
        self.assertEqual(response.context["total_leads"], 3)
        self.assertEqual(response.context["pedidos_novos"], 1)
        self.assertEqual(response.context["pedidos_atendimento"], 1)
        self.assertEqual(response.context["pedidos_concluidos"], 1)
        colunas = self._kanban_colunas(response)
        self.assertEqual(sum(coluna["contador"] for coluna in colunas.values()), 3)
        self.assertIn(self.lead_vendedor1, colunas[Lead.STATUS_NOVO]["leads"])
        self.assertIn(self.lead_vendedor2, colunas[Lead.STATUS_ATENDIMENTO]["leads"])
        self.assertIn(self.lead_direto, colunas[Lead.STATUS_CONCLUIDO]["leads"])
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)

    def test_dono_filtra_por_vendedor(self):
        self.client.force_login(self.owner_user)
        
        # Filtrar por vendedor 1
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"vendedor_leads": self.vendedor1.id})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_vendedor1)
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["total_leads_global"], 3)  # Global não muda
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 0)

        # Filtrar por sem vendedor (Direto)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"vendedor_leads": "sem_vendedor"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_direto)
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["total_leads_global"], 3)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)

    def test_dono_filtra_por_status(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"status_leads": Lead.STATUS_CONCLUIDO})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_direto)
        self.assertEqual(response.context["total_leads"], 1)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["contador"], 0)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["contador"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["leads"], [self.lead_direto])
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)

    def test_dono_filtra_por_status_novo_pendente(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"status_leads": Lead.STATUS_NOVO})

        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(leads, [self.lead_vendedor1])
        self.assertEqual(response.context["total_leads"], 1)

    def test_dono_filtra_por_status_em_atendimento(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"status_leads": Lead.STATUS_ATENDIMENTO})

        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(leads, [self.lead_vendedor2])
        self.assertEqual(response.context["total_leads"], 1)

    def test_dono_filtra_por_termo_busca(self):
        self.client.force_login(self.owner_user)
        Lead.objects.create(
            loja=self.loja,
            vendedor=self.vendedor1,
            produto=self.produto,
            origem=Lead.ORIGEM_PRODUTO,
            cliente_nome="Alice retorno",
            cliente_telefone="85988880004",
            status=Lead.STATUS_CONCLUIDO,
            mensagem="Pedido Alice concluido",
        )
        
        # Buscar por nome "Alice"
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"q_leads": "Alice"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 2)
        self.assertIn(self.lead_vendedor1, leads)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["leads"], [self.lead_vendedor1])
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["leads"], [])
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)

        # Buscar por telefone do Bob
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"q_leads": "0002"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_vendedor2)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["leads"], [])
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["leads"], [self.lead_vendedor2])
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["leads"], [])

    def test_exportar_csv_respeita_filtros(self):
        self.client.force_login(self.owner_user)
        
        # Exportar filtrando por vendedor 1
        response = self.client.get(reverse("exportar_leads_csv", kwargs={"slug": self.loja.slug}), {"vendedor_leads": self.vendedor1.id})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("Alice", content)
        self.assertNotIn("Bob", content)
        self.assertNotIn("Carlos", content)

    def test_exportar_impressao_respeita_filtros(self):
        self.client.force_login(self.owner_user)
        
        # Impressão filtrando por status "concluido"
        response = self.client.get(reverse("exportar_leads_impressao", kwargs={"slug": self.loja.slug}), {"status_leads": Lead.STATUS_CONCLUIDO})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carlos")
        self.assertNotContains(response, "Alice")
        self.assertNotContains(response, "Bob")

    def test_paginacao_limita_leads_exibidos(self):
        for indice in range(12):
            Lead.objects.create(
                loja=self.loja,
                produto=self.produto,
                origem=Lead.ORIGEM_PRODUTO,
                cliente_nome=f"Cliente extra {indice}",
                status=Lead.STATUS_NOVO,
            )
        self.client.force_login(self.owner_user)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_leads"], 15)
        self.assertEqual(len(list(response.context["leads_recentes"])), 10)
        self.assertEqual(response.context["leads_page_obj"].number, 1)
        colunas = self._kanban_colunas(response)
        self.assertEqual(sum(coluna["contador"] for coluna in colunas.values()), 10)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 13)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 1)
        self.assertContains(response, "Exibindo 1-10 de 15 pedido(s)")

    def test_paginacao_preserva_filtros_ativos(self):
        for indice in range(12):
            Lead.objects.create(
                loja=self.loja,
                produto=self.produto,
                origem=Lead.ORIGEM_PRODUTO,
                cliente_nome=f"Concluido extra {indice}",
                status=Lead.STATUS_CONCLUIDO,
            )
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"status_leads": Lead.STATUS_CONCLUIDO},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_leads"], 13)
        self.assertEqual(len(list(response.context["leads_recentes"])), 10)
        self.assertEqual(response.context["leads_querystring_sem_pagina"], "status_leads=concluido")
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 13)
        self.assertContains(response, "page_leads=2")

    def test_paginacao_respeita_permissao_do_vendedor(self):
        for indice in range(12):
            Lead.objects.create(
                loja=self.loja,
                vendedor=self.vendedor2,
                produto=self.produto,
                origem=Lead.ORIGEM_PRODUTO,
                cliente_nome=f"Lead outro vendedor {indice}",
                status=Lead.STATUS_NOVO,
            )
        self.client.force_login(self.vendedor_user1)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(leads, [self.lead_vendedor1])
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["total_leads_global"], 1)
        colunas = self._kanban_colunas(response)
        self.assertEqual(colunas[Lead.STATUS_NOVO]["total_status"], 1)
        self.assertEqual(colunas[Lead.STATUS_ATENDIMENTO]["total_status"], 0)
        self.assertEqual(colunas[Lead.STATUS_CONCLUIDO]["total_status"], 0)
