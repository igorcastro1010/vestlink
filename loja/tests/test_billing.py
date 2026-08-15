from datetime import timedelta
import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from loja.models import Categoria, Cupom, Lead, Loja, Pagamento, Produto


class BillingPlanoAssinaturaTests(TestCase):
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
        self.assertContains(response, "Demo")
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

    @override_settings(PREMIUM_PIX_KEY="pix@vestlink.test", PREMIUM_WHATSAPP_NUMBER="5585999999999")
    def test_assinatura_renderiza_pagamento_manual_sem_gateways(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("assinatura", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Premium da Teste Moda")
        self.assertContains(response, "Pagamento manual")
        self.assertContains(response, "Após pagar via Pix, envie o comprovante pelo WhatsApp.")
        self.assertContains(response, "Sua assinatura será ativada após confirmação manual.")
        self.assertContains(response, "Copiar chave Pix")
        self.assertContains(response, "Enviar comprovante")
        self.assertContains(response, "Ver instruções de pagamento")
        self.assertNotContains(response, "Marcar como pago")
        self.assertNotContains(response, "Abacate Pay")
        self.assertNotContains(response, "Mercado Pago")
        self.assertNotContains(response, "Checkout")
        self.assertNotContains(response, "Webhook")
        self.assertNotContains(response, "Pagamento online")
        self.assertNotContains(response, "Pagar assinatura")

    @override_settings(PREMIUM_PIX_KEY="pix@vestlink.test", PREMIUM_WHATSAPP_NUMBER="5585999999999")
    def test_instrucoes_pagamento_manual_mostram_pix_e_whatsapp(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("checkout_premium", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pagamento manual")
        self.assertContains(response, "Copiar chave Pix")
        self.assertContains(response, "Enviar comprovante")
        self.assertContains(response, "pix@vestlink.test")
        self.assertNotContains(response, "Abacate Pay")
        self.assertNotContains(response, "Mercado Pago")
        self.assertNotContains(response, "Webhook")
        self.assertNotContains(response, "Pagamento online")
        self.assertNotContains(response, "Pagar assinatura")

    @override_settings(PREMIUM_PIX_KEY="", PREMIUM_WHATSAPP_NUMBER="")
    def test_pagamento_manual_sem_variaveis_nao_quebra_tela(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("checkout_premium", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pagamento manual")
        self.assertContains(response, "Chave Pix em configuração")
        self.assertContains(response, "As instruções de pagamento estão sendo configuradas")
        self.assertContains(response, "Copiar chave Pix")
        self.assertContains(response, "Enviar comprovante")
        self.assertNotContains(response, "ABACATE_PAY")
        self.assertNotContains(response, "MERCADO_PAGO")

    def test_planos_explica_pagamento_manual(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("planos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plano Premium")
        self.assertContains(response, "R$ 39,90")
        self.assertContains(response, "pagamento é manual via Pix")
        self.assertContains(response, "Ver instruções de pagamento")
        self.assertNotContains(response, "Abacate Pay")
        self.assertNotContains(response, "Mercado Pago")
        self.assertNotContains(response, "Webhook")

    def test_painel_mostra_pagamento_consistente_sem_termo_tecnico(self):
        self.client.force_login(self.user)
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])

        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Assinatura cancelada")
        self.assertContains(response, "Pagamento pendente de confirmação manual")
        self.assertContains(response, "Pagamento")
        self.assertNotContains(response, "Abacate Pay")
        self.assertNotContains(response, "Mercado Pago")
        self.assertNotContains(response, "Webhook")

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

    def test_retorno_pagamento_nao_aprova_assinatura(self):
        self.client.force_login(self.user)
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])
        pagamento = Pagamento.objects.create(loja=self.loja, usuario=self.user, status=Pagamento.STATUS_PENDENTE)

        response = self.client.get(
            reverse("pagamento_retorno", kwargs={"slug": self.loja.slug, "resultado": "success"}),
            {"external_reference": pagamento.external_reference, "payment_id": "pay_123", "status": "approved"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não foi alterada automaticamente")
        pagamento.refresh_from_db()
        self.loja.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.STATUS_PENDENTE)
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_CANCELADA)

    def test_webhook_externo_nao_ativa_assinatura(self):
        pagamento = Pagamento.objects.create(loja=self.loja, usuario=self.user, status=Pagamento.STATUS_PENDENTE)
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])

        response = self.client.post(
            reverse("abacate_pay_webhook"),
            data=json.dumps({"event": "checkout.completed", "data": {"externalId": pagamento.external_reference}}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)
        pagamento.refresh_from_db()
        self.loja.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.STATUS_PENDENTE)
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_CANCELADA)

    def test_lojista_nao_consegue_marcar_como_pago(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}), {"acao": "ativar_manual"})

        self.assertEqual(response.status_code, 403)
        self.loja.refresh_from_db()
        self.assertNotEqual(self.loja.assinatura_status, Loja.ASSINATURA_ATIVA)

    def test_admin_marca_como_pago_manual_e_renova_assinatura(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.client.force_login(self.user)

        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}), {"acao": "ativar_manual"})

        self.assertEqual(response.status_code, 302)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.plano, Loja.PLANO_PREMIUM)
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_ATIVA)
        self.assertIsNotNone(self.loja.assinatura_ativa_em)
        self.assertEqual(Pagamento.objects.filter(loja=self.loja, status=Pagamento.STATUS_APROVADO).count(), 1)

        historico = self.client.get(reverse("assinatura", kwargs={"slug": self.loja.slug}))
        self.assertContains(historico, "Aprovado")
        self.assertContains(historico, Pagamento.objects.filter(loja=self.loja).first().external_reference)

        primeira_ativacao = self.loja.assinatura_ativa_em
        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}), {"acao": "ativar_manual"})

        self.assertEqual(response.status_code, 302)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_ATIVA)
        self.assertGreaterEqual(self.loja.assinatura_ativa_em, primeira_ativacao)
        self.assertEqual(Pagamento.objects.filter(loja=self.loja, status=Pagamento.STATUS_APROVADO).count(), 2)

    def test_renovar_teste_manual_continua_funcionando(self):
        self.client.force_login(self.user)
        self.loja.assinatura_status = Loja.ASSINATURA_CANCELADA
        self.loja.save(update_fields=["assinatura_status"])

        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}), {"acao": "renovar_teste"})

        self.assertEqual(response.status_code, 302)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_TRIAL)
        self.assertIsNotNone(self.loja.trial_termina_em)

    def test_cancelar_assinatura_continua_funcionando(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("assinatura", kwargs={"slug": self.loja.slug}), {"acao": "cancelar"})

        self.assertEqual(response.status_code, 302)
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_CANCELADA)
        self.assertIsNotNone(self.loja.assinatura_cancelada_em)

    def test_webhook_manual_recusa_get(self):
        response = self.client.get(reverse("abacate_pay_webhook"), {"id": "pay_456"})

        self.assertEqual(response.status_code, 405)


class BillingCronTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Moda",
            slug="teste-moda",
            telefone="85999999999",
            dominio_personalizado="catalogo.teste.com",
            assinatura_status=Loja.ASSINATURA_TRIAL,
            trial_termina_em=timezone.now() - timedelta(days=1),
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
        from io import StringIO

        out = StringIO()
        call_command("verificar_assinaturas", stdout=out)
        self.assertIn("foi marcada como VENCIDA", out.getvalue())
        self.loja.refresh_from_db()
        self.assertEqual(self.loja.assinatura_status, Loja.ASSINATURA_VENCIDA)
