import json
from datetime import timedelta

from django.core import mail
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from urllib.error import HTTPError
from unittest.mock import patch

from loja.models import AceiteLegal, Categoria, Cupom, Lead, Loja, Pagamento, Produto, ProdutoImagem, ProdutoVariacao, Vendedor
from loja.storage import SupabaseStorage


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
        self.assertContains(response, "Ver catálogo de demonstração")
        self.assertContains(response, "Perfeito para lojas e vendedores de moda")
        self.assertContains(response, "Antes do VestLink")
        self.assertContains(response, "Plano Premium")
        self.assertContains(response, reverse("cadastro"))
        self.assertContains(response, reverse("login"))
        self.assertNotContains(response, "Plano Gratis")

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
        self.assertContains(response, "Teste grátis")
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

    def test_validar_cupom_retorna_desconto_correto(self):
        self.client.force_login(self.user)
        Cupom.objects.update_or_create(codigo="TESTE15", defaults={"percentual_desconto": 15, "ativo": True})

        response = self.client.get(reverse("validar_cupom", kwargs={"slug": self.loja.slug}), {"codigo": "teste15"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["valido"])
        self.assertEqual(data["codigo"], "TESTE15")
        self.assertEqual(data["percentual_desconto"], 15)
        self.assertEqual(data["desconto_formatado"], "R$ 5,98")
        self.assertEqual(data["valor_final_formatado"], "R$ 33,92")

    def test_validar_cupom_invalido(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("validar_cupom", kwargs={"slug": self.loja.slug}), {"codigo": "invalido"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["valido"])

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

        with patch("loja.views.billing.processar_webhook_pagamento", return_value=pagamento) as atualizar:
            response = self.client.post(
                reverse("mercado_pago_webhook"),
                data='{"data": {"id": "pay_456"}}',
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        atualizar.assert_called_once_with("pay_456")
        self.assertEqual(response.json()["status"], Pagamento.STATUS_PENDENTE)

    def test_webhook_mercado_pago_recusa_get(self):
        response = self.client.get(reverse("mercado_pago_webhook"), {"id": "pay_456"})

        self.assertEqual(response.status_code, 405)

class SaasTenantCronTests(TestCase):
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

    @override_settings(CRON_SECRET="segredo-teste")
    def test_cron_view_runs_successfully(self):
        lead = Lead.objects.create(
            loja=self.loja,
            origem=Lead.ORIGEM_SACOLINHA,
            cliente_nome="Cliente Antiga",
            cliente_telefone="85988887777",
            endereco_completo="Rua Teste, 123",
            mensagem="Pedido com dados pessoais",
            ip="127.0.0.1",
            navegador="Teste",
        )
        Lead.objects.filter(id=lead.id).update(criado_em=timezone.now() - timedelta(days=400))

        with override_settings(DEBUG=False):
            response = self.client.post("/api/tasks/cron/")
            self.assertEqual(response.status_code, 401)
            
            response = self.client.post("/api/tasks/cron/", HTTP_AUTHORIZATION="Bearer segredo-teste")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["trials_expirados_processados"], 1)
            self.assertEqual(response.json()["leads_anonimizados"], 1)
            
            self.loja.refresh_from_db()
            lead.refresh_from_db()
            self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_VENCIDA)
            self.assertEqual(lead.cliente_nome, "")
            self.assertIsNotNone(lead.anonimizado_em)

    def test_management_command_runs_successfully(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("verificar_assinaturas", stdout=out)
        self.assertIn("foi marcada como VENCIDA", out.getvalue())
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_VENCIDA)


