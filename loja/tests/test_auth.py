import json
from datetime import timedelta

from django.core import mail
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from loja.models import AceiteLegal, Loja


class AuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Moda",
            slug="teste-moda",
            telefone="85999999999",
        )

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

    def test_recuperacao_de_senha_renderiza(self):
        response = self.client.get(reverse("recuperar_senha"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Esqueci minha senha")

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
