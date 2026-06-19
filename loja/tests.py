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

from .models import AceiteLegal, Categoria, Cupom, Lead, Loja, Pagamento, Produto, ProdutoImagem, ProdutoVariacao, Vendedor
from .storage import SupabaseStorage


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
        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="qr-code-{self.loja.slug}.png"',
        )
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_painel_loja_vendedor_nao_ve_assinatura(self):
        vendedor_user = User.objects.create_user(username="vend_view", password="senha-forte-123")
        Vendedor.objects.create(loja=self.loja, usuario=vendedor_user, nome="Maria", codigo="maria", ativo=True)
        self.client.force_login(vendedor_user)
        
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Loja ativa")
        self.assertNotContains(response, "Ver assinatura")
        self.assertNotContains(response, "Premium ativo")
        self.assertNotContains(response, "Teste acaba em")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cadastro_cria_conta_pendente_e_confirma_por_email(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "nova",
                "email": "nova@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Nova Loja",
                "loja_slug": "nova-loja",
                "loja_telefone": "85911112222",
                "loja_instagram": "novaloja",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("cadastro_confirmacao_enviada"))
        user = User.objects.get(username="nova")
        self.assertFalse(user.is_active)
        self.assertTrue(AceiteLegal.objects.filter(user=user, fonte="cadastro").exists())
        self.assertTrue(Loja.objects.filter(slug="nova-loja", usuario=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirme seu e-mail", mail.outbox[0].subject)
        self.assertIn(reverse("confirmar_email", kwargs={"uidb64": "placeholder", "token": "placeholder"}).split("placeholder")[0], mail.outbox[0].body)

        confirm_path = mail.outbox[0].body.split("http://testserver", 1)[1].split()[0]
        confirm_response = self.client.get(confirm_path)

        self.assertEqual(confirm_response.status_code, 302)
        self.assertEqual(confirm_response["Location"], reverse("painel_loja", kwargs={"slug": "nova-loja"}))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    @override_settings(
        SUPABASE_AUTH_EMAIL_CONFIRMATION=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
        SUPABASE_EMAIL_REDIRECT_URL="",
    )
    @patch("loja.views.supabase_auth.sign_up")
    def test_cadastro_usa_supabase_auth_para_confirmar_email(self, sign_up):
        sign_up.return_value = {"user": {"id": "supabase-user", "email": "supabase@example.com"}, "session": None}

        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "supabase_user",
                "email": "supabase@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Loja Supabase",
                "loja_slug": "loja-supabase",
                "loja_telefone": "85911112222",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("cadastro_confirmacao_enviada"))
        user = User.objects.get(username="supabase_user")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.client.session["cadastro_confirmacao_email"], "supabase@example.com")
        sign_up.assert_called_once()
        args, kwargs = sign_up.call_args
        self.assertEqual(args[0], "supabase@example.com")
        self.assertEqual(args[1], "SenhaForte123!")
        self.assertIn(reverse("supabase_confirmar_email"), kwargs["redirect_to"])

    @override_settings(
        SUPABASE_AUTH_EMAIL_CONFIRMATION=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
        SUPABASE_EMAIL_REDIRECT_URL="",
    )
    @patch("loja.views.supabase_auth.resend_signup_confirmation")
    def test_reenviar_confirmacao_usa_supabase_auth(self, resend_signup_confirmation):
        user = User.objects.create_user(
            username="pendente_supabase",
            email="pendente@example.com",
            password="SenhaForte123!",
            is_active=False,
        )
        Loja.objects.create(usuario=user, nome="Pendente", slug="pendente", telefone="85911112222")

        response = self.client.post(
            reverse("reenviar_confirmacao_email"),
            {"email": "pendente@example.com"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("cadastro_confirmacao_enviada"))
        resend_signup_confirmation.assert_called_once()
        args, kwargs = resend_signup_confirmation.call_args
        self.assertEqual(args[0], "pendente@example.com")
        self.assertIn(reverse("supabase_confirmar_email"), kwargs["redirect_to"])
        self.assertEqual(self.client.session["cadastro_confirmacao_email"], "pendente@example.com")

    def test_tela_confirmacao_exibe_botao_de_reenvio_quando_tem_email(self):
        session = self.client.session
        session["cadastro_confirmacao_email"] = "pendente@example.com"
        session.save()

        response = self.client.get(reverse("cadastro_confirmacao_enviada"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pendente@example.com")
        self.assertContains(response, reverse("reenviar_confirmacao_email"))
        self.assertContains(response, "Reenviar e-mail de confirma")

    @override_settings(
        SUPABASE_AUTH_EMAIL_CONFIRMATION=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
    )
    @patch("loja.views.supabase_auth.get_user")
    def test_supabase_confirmar_sessao_ativa_usuario_local(self, get_user):
        user = User.objects.create_user(
            username="confirmado_supabase",
            email="confirmado@example.com",
            password="SenhaForte123!",
            is_active=False,
        )
        Loja.objects.create(usuario=user, nome="Confirmada", slug="confirmada", telefone="85911112222")
        get_user.return_value = {
            "email": "confirmado@example.com",
            "email_confirmed_at": "2026-06-04T12:00:00Z",
        }

        response = self.client.post(
            reverse("supabase_confirmar_sessao"),
            data=json.dumps({"access_token": "token-confirmado"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(response.json()["redirect_url"], reverse("painel_loja", kwargs={"slug": "confirmada"}))

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
    )
    def test_login_e_cadastro_exibem_acesso_com_google(self):
        login_response = self.client.get(reverse("login"))
        cadastro_response = self.client.get(reverse("cadastro"))

        self.assertContains(login_response, "Continuar com Google")
        self.assertContains(cadastro_response, "Criar conta com Google")
        self.assertContains(login_response, reverse("google_oauth_start"))
        self.assertContains(cadastro_response, reverse("google_oauth_start"))

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
    )
    @patch("loja.views.supabase_auth.google_provider_enabled", return_value=True)
    def test_google_oauth_start_redireciona_para_supabase(self, google_provider_enabled):
        response = self.client.get(reverse("google_oauth_start"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://example.supabase.co/auth/v1/authorize?"))
        self.assertIn("provider=google", response["Location"])
        self.assertIn("redirect_to=", response["Location"])
        google_provider_enabled.assert_called_once()

    @override_settings(
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_AUTH_KEY="anon-key",
    )
    @patch("loja.views.supabase_auth.get_user")
    def test_google_oauth_cria_usuario_local_e_autentica(self, get_user):
        get_user.return_value = {
            "email": "nova.google@example.com",
            "user_metadata": {"full_name": "Nova Google"},
        }

        response = self.client.post(
            reverse("supabase_google_sessao"),
            data=json.dumps({"access_token": "token-google"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="nova.google@example.com")
        self.assertEqual(user.first_name, "Nova")
        self.assertEqual(user.last_name, "Google")
        self.assertFalse(user.has_usable_password())
        self.assertTrue(AceiteLegal.objects.filter(user=user, fonte="google_oauth").exists())
        self.assertEqual(response.json()["redirect_url"], reverse("painel"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_paginas_legais_abrem(self):
        termos = self.client.get(reverse("termos_uso"))
        privacidade = self.client.get(reverse("politica_privacidade"))

        self.assertEqual(termos.status_code, 200)
        self.assertContains(termos, "Termos de Uso")
        self.assertEqual(privacidade.status_code, 200)
        self.assertContains(privacidade, "Política de Privacidade")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cadastro_exige_aceite_legal(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "sem_aceite",
                "email": "sem-aceite@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Loja Sem Aceite",
                "loja_slug": "loja-sem-aceite",
                "loja_telefone": "85911112222",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Termos de Uso")
        self.assertFalse(User.objects.filter(username="sem_aceite").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cadastro_registra_aceite_legal(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "com_aceite",
                "email": "com-aceite@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Loja Com Aceite",
                "loja_slug": "loja-com-aceite",
                "loja_telefone": "85911112222",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="com_aceite")
        aceite = AceiteLegal.objects.get(user=user)
        self.assertEqual(aceite.fonte, "cadastro")
        self.assertTrue(aceite.termos_versao)
        self.assertTrue(aceite.privacidade_versao)

    @override_settings(EMAIL_BACKEND="loja.email_backends.ResendEmailBackend", RESEND_API_KEY="")
    def test_cadastro_nao_cria_conta_quando_email_falha(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "falha_email",
                "email": "falha@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Loja Falha",
                "loja_slug": "loja-falha",
                "loja_telefone": "85911112222",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nao conseguimos concluir o cadastro")
        self.assertFalse(User.objects.filter(username="falha_email").exists())
        self.assertFalse(Loja.objects.filter(slug="loja-falha").exists())

    def test_cadastro_avisa_quando_link_da_loja_ja_existe(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "slug_repetido",
                "email": "slug-repetido@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "Outra Loja",
                "loja_slug": self.loja.slug,
                "loja_telefone": "85911112222",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Esse link de loja ja esta em uso")
        self.assertFalse(User.objects.filter(username="slug_repetido").exists())

    def test_cadastro_renderiza_requisitos_de_senha(self):
        response = self.client.get(reverse("cadastro"))

        self.assertContains(response, 'data-password-requirements')
        self.assertContains(response, 'data-password-primary')
        self.assertContains(response, 'data-password-confirm')
        self.assertContains(response, "Pelo menos 8 caracteres")
        self.assertContains(response, "Uma letra maiúscula")
        self.assertContains(response, "Um caractere especial")
        self.assertContains(response, "Confirmação igual à senha")

    def test_cadastro_rejeita_senha_sem_maiuscula_e_caractere_especial(self):
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "senha_fraca",
                "email": "senha@example.com",
                "password1": "senhaforte123",
                "password2": "senhaforte123",
                "loja_nome": "Senha Loja",
                "loja_slug": "senha-loja",
                "loja_telefone": "85911112222",
                "aceite_termos": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="senha_fraca").exists())
        self.assertContains(response, "letra maiúscula")
        self.assertContains(response, "caractere especial")

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
        self.assertNotContains(response, "Ver inicio")
        self.assertNotContains(response, 'href="/"')

    def test_painel_redireciona_vendedor_ativo(self):
        vendedor_user = User.objects.create_user(username="vend_ativo", password="senha-forte-123")
        Vendedor.objects.create(loja=self.loja, usuario=vendedor_user, nome="Maria", codigo="maria", ativo=True)
        self.client.force_login(vendedor_user)
        
        response = self.client.get(reverse("painel"))
        
        self.assertRedirects(response, reverse("painel_loja", kwargs={"slug": self.loja.slug}))

    def test_painel_bloqueia_vendedor_inativo(self):
        vendedor_user = User.objects.create_user(username="vend_inativo", password="senha-forte-123")
        Vendedor.objects.create(loja=self.loja, usuario=vendedor_user, nome="Maria", codigo="maria", ativo=False)
        self.client.force_login(vendedor_user)
        
        response = self.client.get(reverse("painel"))
        
        self.assertEqual(response.status_code, 403)

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
        self.assertContains(response, "Manter conectado")
        self.assertNotContains(response, "Manter conectado por 30 dias")

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

        with patch("loja.views.atualizar_pagamento_mercado_pago", return_value=pagamento) as atualizar:
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

    def test_cadastro_requer_campos_da_loja(self):
        # Tenta cadastrar sem preencher os dados da loja
        response = self.client.post(
            reverse("cadastro"),
            {
                "username": "nova_sem_loja",
                "email": "nova_sem_loja@example.com",
                "password1": "SenhaForte123!",
                "password2": "SenhaForte123!",
                "loja_nome": "",
                "loja_slug": "",
                "loja_telefone": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertFalse(form.is_valid())
        self.assertIn("loja_nome", form.errors)
        self.assertIn("loja_slug", form.errors)
        self.assertIn("loja_telefone", form.errors)

    def test_redirecionamento_usuario_autenticado_no_cadastro_e_login(self):
        self.client.force_login(self.user)
        
        # Tentativa de acessar cadastro
        response_cadastro = self.client.get(reverse("cadastro"))
        self.assertEqual(response_cadastro.status_code, 302)
        self.assertEqual(response_cadastro["Location"], reverse("painel"))
        
        # Tentativa de acessar login
        response_login = self.client.get(reverse("login"))
        self.assertEqual(response_login.status_code, 302)
        self.assertEqual(response_login["Location"], reverse("painel"))

    def test_url_admin_secreta(self):
        # A URL padrão /admin/ deve retornar 404
        response_padrao = self.client.get("/admin/")
        self.assertEqual(response_padrao.status_code, 404)
        
        # A nova URL secreta não deve retornar 404 (geralmente 302 redirecionando para login de admin)
        response_secreta = self.client.get("/gerenciador-vestlink/")
        self.assertNotEqual(response_secreta.status_code, 404)


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

    @override_settings(ALLOWED_HOSTS=["teste-moda.localhost", "catalogo.teste.com"])
    def test_tenant_middleware_resolves_subdomain(self):
        response = self.client.get("/", HTTP_HOST="teste-moda.localhost")
        self.assertEqual(response.status_code, 402)

    @override_settings(ALLOWED_HOSTS=["catalogo.teste.com"])
    def test_tenant_middleware_resolves_custom_domain(self):
        response = self.client.get("/", HTTP_HOST="catalogo.teste.com")
        self.assertEqual(response.status_code, 402)

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


class SaasOptimizationsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Cache",
            slug="teste-cache",
            telefone="85999999999",
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Roupas")

    def test_image_optimized_and_converted_to_webp(self):
        gif_content = (
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        image_file = SimpleUploadedFile("mock_product.gif", gif_content, content_type="image/gif")
        
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Vestido Otimizado",
            preco="150.00",
            imagem=image_file
        )
        
        self.assertTrue(produto.imagem.name.endswith(".webp"))
        self.assertIn("mock_product", produto.imagem.name)

    def test_cache_version_invalidation_signals(self):
        from django.core.cache import cache
        cache.clear()
        
        version = cache.get_or_set(f"loja_cache_version_{self.loja.id}", 1)
        self.assertEqual(version, 1)
        
        gif_content = (
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        image_file = SimpleUploadedFile("mock_product.gif", gif_content, content_type="image/gif")
        
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Produto Teste Cache",
            preco="50.00",
            imagem=image_file
        )
        
        new_version = cache.get(f"loja_cache_version_{self.loja.id}")
        self.assertEqual(new_version, 2)
        
        produto.delete()
        new_version = cache.get(f"loja_cache_version_{self.loja.id}")
        self.assertEqual(new_version, 3)

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
        import json
        leads_labels = json.loads(response.context["chart_leads_labels"])
        leads_valores = json.loads(response.context["chart_leads_valores"])
        produtos_labels = json.loads(response.context["chart_produtos_labels"])
        produtos_valores = json.loads(response.context["chart_produtos_valores"])
        
        self.assertEqual(len(leads_valores), 1)
        self.assertEqual(leads_valores[0], 1)
        self.assertIn("Vestido Festa", produtos_labels)
        self.assertIn(10, produtos_valores)


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
        from .validators import limpar_telefone
        self.assertEqual(limpar_telefone("+55 (85) 91111-2222"), "85911112222")
        self.assertEqual(limpar_telefone("85 91111-2222"), "85911112222")
        self.assertEqual(limpar_telefone("5585911112222"), "85911112222")
        self.assertEqual(limpar_telefone("85911112222"), "85911112222")

    def test_validacao_telefone_rejeita_comprimento_invalido(self):
        from django.core.exceptions import ValidationError
        from .validators import validar_whatsapp
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
        
        import json
        labels = json.loads(response.context["chart_vendedores_labels"])
        valores = json.loads(response.context["chart_vendedores_valores"])
        self.assertIn("Maria com Tel", labels)
        self.assertIn(1, valores)


class NovosRecursosSaaSTests(TestCase):
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

        # Filtrar por sem vendedor (Direto)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"vendedor_leads": "sem_vendedor"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_direto)
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["total_leads_global"], 3)

    def test_dono_filtra_por_status(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"status_leads": Lead.STATUS_CONCLUIDO})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_direto)
        self.assertEqual(response.context["total_leads"], 1)

    def test_dono_filtra_por_termo_busca(self):
        self.client.force_login(self.owner_user)
        
        # Buscar por nome "Alice"
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"q_leads": "Alice"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_vendedor1)

        # Buscar por telefone do Bob
        response = self.client.get(reverse("painel_loja", kwargs={"slug": self.loja.slug}), {"q_leads": "0002"})
        self.assertEqual(response.status_code, 200)
        leads = list(response.context["leads_recentes"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], self.lead_vendedor2)

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
