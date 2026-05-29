from datetime import timedelta

from django.core import mail
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .models import Categoria, Cupom, Lead, Loja, Pagamento, Produto, ProdutoImagem, ProdutoVariacao


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
        self.assertContains(response, "Quero esse")
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
        self.assertContains(response, "Voltar ao catalogo")

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
        self.assertContains(response, "Catalogo pausado", status_code=402)
        self.assertNotContains(response, "Blusa Preta", status_code=402)

    @override_settings(ALLOWED_HOSTS=["catalogo.teste.com"])
    def test_home_renderiza_catalogo_por_dominio_personalizado(self):
        self.loja.dominio_personalizado = "catalogo.teste.com"
        self.loja.save(update_fields=["dominio_personalizado"])

        response = self.client.get("/", HTTP_HOST="catalogo.teste.com")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Teste Moda")
        self.assertContains(response, "Blusa Preta")

    def test_planos_renderiza_oferta_premium(self):
        response = self.client.get(reverse("planos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plano Premium")
        self.assertContains(response, "R$ 39,90")
        self.assertContains(response, "7 dias")
        self.assertNotContains(response, "Plano Gratis")

    def test_home_usa_landing_com_cadastro_e_sem_plano_gratis(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transforme seu WhatsApp")
        self.assertContains(response, "Criar conta e testar 7 dias")
        self.assertContains(response, "Ver catalogo de demonstracao")
        self.assertContains(response, "Perfeito para boutiques")
        self.assertContains(response, "Antes do VestLink")
        self.assertContains(response, "Plano Premium")
        self.assertContains(response, reverse("cadastro"))
        self.assertContains(response, reverse("login"))
        self.assertNotContains(response, "Plano Gratis")

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
        self.assertContains(response, "Interesses recebidos")
        self.assertContains(response, "Produtos mais clicados")
        self.assertContains(response, "Leads por dia")
        self.assertContains(response, "Resumo comercial")
        self.assertContains(response, "Compartilhar catalogo")
        self.assertContains(response, "Loja ativa")
        self.assertContains(response, "Iniciar tour")
        self.assertContains(response, "Mensagens prontas para divulgar")
        self.assertContains(response, "Estoque visual por variacao")
        self.assertContains(response, "O que melhorar agora")
        self.assertContains(response, "Configuracao")
        self.assertContains(response, "Organizar catalogo")
        self.assertContains(response, f'href="{reverse("painel")}"')
        self.assertContains(response, f'href="{reverse("catalogo", kwargs={"slug": self.loja.slug})}"')
        self.assertContains(response, f'action="{reverse("logout")}"')

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cadastro_pode_criar_primeira_loja_e_enviar_email(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "nova",
                "email": "nova@example.com",
                "password1": "senha-forte-123",
                "password2": "senha-forte-123",
                "loja_nome": "Nova Loja",
                "loja_slug": "nova-loja",
                "loja_telefone": "85911112222",
                "loja_instagram": "novaloja",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("painel_loja", kwargs={"slug": "nova-loja"}))
        self.assertTrue(Loja.objects.filter(slug="nova-loja", usuario__username="nova").exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Bem-vindo ao VestLink", mail.outbox[0].subject)

    def test_logout_redireciona_para_login(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("login"))

    def test_painel_renderiza_onboarding_geral(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("painel"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coloque sua vitrine no ar")
        self.assertContains(response, "Criar loja")
        self.assertContains(response, "Cadastrar produto")
        self.assertContains(response, "Compartilhar link")

    def test_painel_exige_login(self):
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_login_sem_manter_conectado_expira_ao_fechar_navegador(self):
        response = self.client.post(
            reverse("login"),
            {"username": "lojista", "password": "senha-forte-123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_login_com_manter_conectado_dura_30_dias(self):
        response = self.client.post(
            reverse("login"),
            {"username": "lojista", "password": "senha-forte-123", "remember_me": "1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 30)

    def test_login_renderiza_botao_mostrar_senha(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-password-toggle')
        self.assertContains(response, 'aria-label="Mostrar senha"')
        self.assertContains(response, 'password-input-wrap')

    def test_painel_cadastra_produto(self):
        self.client.force_login(self.user)
        imagem = SimpleUploadedFile(
            "produto.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        foto_extra_1 = SimpleUploadedFile(
            "produto-extra-1.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        foto_extra_2 = SimpleUploadedFile(
            "produto-extra-2.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Vestido Azul",
                "descricao": "Peça nova",
                "preco": "139.90",
                "imagem": imagem,
                "fotos_adicionais": [foto_extra_1, foto_extra_2],
                "tamanhos": "P, M",
                "tamanhos_esgotados": "M",
                "cores": "Azul",
                "cores_esgotadas": "Azul",
                "variacoes_estoque": "Azul, P, 4\nAzul, M, 0",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Produto.objects.filter(loja=self.loja, nome="Vestido Azul").exists())
        self.assertEqual(ProdutoImagem.objects.filter(produto__nome="Vestido Azul").count(), 2)
        self.assertEqual(ProdutoVariacao.objects.filter(produto__nome="Vestido Azul").count(), 2)

    def test_plano_premium_nao_bloqueia_produto_por_limite_gratis(self):
        self.client.force_login(self.user)
        for indice in range(9):
            Produto.objects.create(
                loja=self.loja,
                categoria=self.categoria,
                nome=f"Produto {indice}",
                preco="10.00",
                imagem="produtos/item.png",
            )
        imagem = SimpleUploadedFile(
            "produto-limite.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Produto liberado",
                "preco": "29.90",
                "imagem": imagem,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Produto.objects.filter(loja=self.loja, nome="Produto liberado").exists())

    def test_assinatura_inativa_bloqueia_cadastro_de_produto(self):
        self.client.force_login(self.user)
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])
        imagem = SimpleUploadedFile(
            "bloqueado.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Produto bloqueado",
                "preco": "29.90",
                "imagem": imagem,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("assinatura", kwargs={"slug": self.loja.slug}))
        self.assertFalse(Produto.objects.filter(loja=self.loja, nome="Produto bloqueado").exists())

    def test_assinatura_ativa_plano_premium(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("assinatura", kwargs={"slug": self.loja.slug}))
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.plano, Loja.PLANO_PREMIUM)
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_ATIVA)
        self.assertIsNotNone(self.loja.assinatura_ativa_em)

    def test_assinatura_renderiza_status_do_teste(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("assinatura", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Controle do Premium")
        self.assertContains(response, "Teste gratis")
        self.assertContains(response, "Ir para checkout")
        self.assertContains(response, "Modo teste/manual")

    def test_checkout_sem_url_externa_renderiza_simulacao(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("checkout_premium", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkout seguro")
        self.assertContains(response, "Simular pagamento aprovado")
        self.assertContains(response, "VESTLINK10")

    @override_settings(VESTLINK_CHECKOUT_URL="https://checkout.example/pay", MERCADO_PAGO_ACCESS_TOKEN="")
    def test_checkout_com_url_externa_redireciona_com_parametros(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("checkout_premium", kwargs={"slug": self.loja.slug}), {"cupom": "VESTLINK10"})

        self.assertEqual(response.status_code, 302)
        self.assertIn("https://checkout.example/pay?", response["Location"])
        self.assertIn("loja=teste-moda", response["Location"])
        self.assertIn("plano=premium", response["Location"])
        self.assertIn("cupom=VESTLINK10", response["Location"])

    @override_settings(MERCADO_PAGO_ACCESS_TOKEN="TEST-123", MERCADO_PAGO_USE_SANDBOX=True)
    def test_checkout_mercado_pago_cria_preferencia_e_redireciona(self):
        self.client.force_login(self.user)
        Cupom.objects.update_or_create(codigo="VESTLINK10", defaults={"percentual_desconto": 10, "ativo": True})

        with patch("loja.payments._post_json") as post_json:
            post_json.return_value = {
                "id": "pref_123",
                "init_point": "https://www.mercadopago.com/checkout",
                "sandbox_init_point": "https://sandbox.mercadopago.com/checkout",
            }
            response = self.client.post(reverse("checkout_premium", kwargs={"slug": self.loja.slug}), {"cupom": "VESTLINK10"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://sandbox.mercadopago.com/checkout")
        pagamento = Pagamento.objects.get(loja=self.loja)
        self.assertEqual(pagamento.preference_id, "pref_123")
        self.assertEqual(pagamento.status, Pagamento.STATUS_PENDENTE)
        self.assertEqual(pagamento.valor_final, pagamento.cupom.aplicar(pagamento.valor))
        payload = post_json.call_args.args[1]
        self.assertEqual(payload["external_reference"], pagamento.external_reference)
        self.assertEqual(payload["items"][0]["currency_id"], "BRL")
        self.assertEqual(payload["items"][0]["unit_price"], 35.91)
        self.assertIn("notification_url", payload)

    def test_retorno_pagamento_aprovado_ativa_assinatura(self):
        self.client.force_login(self.user)
        pagamento = Pagamento.objects.create(loja=self.loja, usuario=self.user, status=Pagamento.STATUS_PENDENTE)

        response = self.client.get(
            reverse("pagamento_retorno", kwargs={"slug": self.loja.slug, "resultado": "success"}),
            {"external_reference": pagamento.external_reference, "payment_id": "pay_123", "status": "approved"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pagamento aprovado")
        pagamento.refresh_from_db()
        self.loja.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.STATUS_APROVADO)
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_ATIVA)
        self.assertEqual(self.loja.pagamento_referencia, pagamento.external_reference)

    def test_webhook_mercado_pago_atualiza_pagamento(self):
        pagamento = Pagamento.objects.create(loja=self.loja, usuario=self.user, status=Pagamento.STATUS_PENDENTE)

        with patch("loja.views.atualizar_pagamento_mercado_pago", return_value=pagamento) as atualizar:
            response = self.client.post(
                reverse("mercado_pago_webhook"),
                data='{"data": {"id": "pay_456"}}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        atualizar.assert_called_once_with("pay_456")
        self.assertEqual(response.json()["status"], Pagamento.STATUS_PENDENTE)

    def test_painel_cria_categoria(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "criar_categoria", "nome": "Vestidos", "ordem": "2"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Categoria.objects.filter(loja=self.loja, nome="Vestidos").exists())

    def test_whatsapp_produto_contabiliza_clique(self):
        response = self.client.get(
            reverse("whatsapp_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {"tamanho": "P", "cor": "Preto"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me", response["Location"])
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.cliques_whatsapp, 1)
        self.assertTrue(Lead.objects.filter(loja=self.loja, produto=self.produto, origem=Lead.ORIGEM_PRODUTO).exists())

    def test_whatsapp_carrinho_cria_lead(self):
        response = self.client.get(
            reverse("whatsapp_carrinho", kwargs={"slug": self.loja.slug}),
            {
                "mensagem": "Ola! Quero fazer um pedido:\n1. Blusa Preta",
                "cliente_nome": "Ana",
                "cliente_telefone": "85988887777",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("wa.me", response["Location"])
        lead = Lead.objects.get(loja=self.loja, origem=Lead.ORIGEM_SACOLINHA)
        self.assertEqual(lead.cliente_nome, "Ana")
        self.assertEqual(lead.cliente_telefone, "85988887777")

    def test_painel_edita_produto(self):
        self.client.force_login(self.user)
        imagem = SimpleUploadedFile(
            "produto-editado.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("editar_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Blusa Branca",
                "descricao": "Produto editado",
                "preco": "89.90",
                "imagem": imagem,
                "tamanhos": "P, M",
                "tamanhos_esgotados": "M",
                "cores": "Branco",
                "cores_esgotadas": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, "Blusa Branca")
        self.assertEqual(str(self.produto.preco), "89.90")

    def test_painel_publica_produto_rascunho(self):
        self.produto.publicado = False
        self.produto.save(update_fields=["publicado"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "publicar_produto", "produto_id": str(self.produto.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.produto.refresh_from_db()
        self.assertTrue(self.produto.publicado)

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

    def test_recuperacao_de_senha_renderiza(self):
        response = self.client.get(reverse("recuperar_senha"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Esqueci minha senha")

    def test_painel_remove_produto(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("remover_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Produto.objects.filter(id=self.produto.id).exists())

    def test_usuario_nao_acessa_loja_de_outro_usuario(self):
        outro = User.objects.create_user(username="outro", password="senha-forte-123")
        self.client.force_login(outro)

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 403)
