import logging
from django.conf import settings
from django.db import transaction
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify

from loja.models import AceiteLegal, Loja
from loja.legal import PRIVACY_VERSION, TERMS_VERSION
from loja import supabase_auth

logger = logging.getLogger(__name__)


def request_ip(request):
    """
    Retorna o endereço IP do cliente a partir do request.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def registrar_aceite_legal(request, user, fonte):
    """
    Registra o aceite dos termos legais pelo usuário.
    """
    AceiteLegal.objects.create(
        user=user,
        termos_versao=TERMS_VERSION,
        privacidade_versao=PRIVACY_VERSION,
        fonte=fonte,
        ip=request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )


def username_google_unico(supabase_user):
    """
    Gera um username único no Django a partir do usuário do Google/Supabase.
    """
    metadata = (supabase_user or {}).get("user_metadata") or {}
    email = (supabase_user or {}).get("email", "")
    base = (
        metadata.get("preferred_username")
        or metadata.get("user_name")
        or metadata.get("full_name")
        or email.split("@")[0]
        or "lojista"
    )
    base = slugify(base).replace("-", "_")[:130] or "lojista"
    username = base
    suffix = 2
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base[:140]}_{suffix}"
        suffix += 1
    return username


def autenticar_usuario_google(request, supabase_user):
    """
    Autentica (e cria se necessário) o usuário local a partir do login com Google.
    Retorna a URL de redirecionamento correspondente.
    """
    email = (supabase_user or {}).get("email", "").strip().lower()
    if not email:
        raise ValueError("O Google não retornou um e-mail válido.")

    user = User.objects.filter(email__iexact=email).order_by("id").first()
    usuario_criado = False
    if not user:
        metadata = (supabase_user or {}).get("user_metadata") or {}
        full_name = (metadata.get("full_name") or metadata.get("name") or "").strip()
        first_name, _, last_name = full_name.partition(" ")
        user = User.objects.create_user(
            username=username_google_unico(supabase_user),
            email=email,
            first_name=first_name[:150],
            last_name=last_name[:150],
            is_active=True,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        usuario_criado = True
    elif not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

    if usuario_criado:
        registrar_aceite_legal(request, user, "google_oauth")

    login(request, user)
    loja = user.lojas.order_by("id").first()
    if loja:
        return reverse("painel_loja", kwargs={"slug": loja.slug})
    return reverse("painel")


def ativar_usuario_confirmado(request, supabase_user):
    """
    Ativa o usuário local cuja confirmação de e-mail foi validada pelo Supabase.
    Retorna a URL de redirecionamento correspondente.
    """
    email = (supabase_user or {}).get("email", "").strip()
    if not email:
        raise ValueError("Supabase nao retornou e-mail confirmado.")

    user = User.objects.filter(email__iexact=email).order_by("id").first()
    if not user:
        raise User.DoesNotExist("Usuario local nao encontrado para o e-mail confirmado.")

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])

    login(request, user)
    loja = user.lojas.order_by("id").first()
    if loja:
        return reverse("painel_loja", kwargs={"slug": loja.slug})
    return reverse("painel")


def enviar_email_confirmacao_django(request, user):
    """
    Envia o e-mail de confirmação usando a infraestrutura do Django.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    confirmar_url = request.build_absolute_uri(
        reverse("confirmar_email", kwargs={"uidb64": uidb64, "token": token})
    )
    send_mail(
        "Confirme seu e-mail no VestLink",
        (
            "Recebemos seu cadastro no VestLink.\n\n"
            "Confirme seu e-mail para ativar a conta e acessar o painel:\n"
            f"{confirmar_url}\n\n"
            "Se voce nao fez esse cadastro, pode ignorar este e-mail."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def processar_cadastro(request, form):
    """
    Registra um novo lojista e sua loja correspondente.
    Retorna o usuário se ele já estiver ativado imediatamente, ou None se for pendente.
    """
    with transaction.atomic():
        user = form.save(commit=False)
        user.is_active = False
        user.save()
        loja_nome = form.cleaned_data.get("loja_nome", "").strip()
        loja_slug = form.cleaned_data.get("loja_slug", "").strip()
        loja_telefone = form.cleaned_data.get("loja_telefone", "").strip()
        loja_instagram = form.cleaned_data.get("loja_instagram", "").strip()
        if loja_nome and loja_slug and loja_telefone:
            Loja.objects.create(
                usuario=user,
                nome=loja_nome,
                slug=loja_slug,
                telefone=loja_telefone,
                instagram=loja_instagram,
            )
        registrar_aceite_legal(request, user, "cadastro")

        if supabase_auth.enabled():
            supabase_response = supabase_auth.sign_up(
                user.email,
                form.cleaned_data["password1"],
                metadata={
                    "django_username": user.username,
                    "loja_slug": loja_slug,
                    "source": "vestlink",
                },
                redirect_to=supabase_auth.confirmation_redirect_url(request),
            )
            if supabase_response.get("session"):
                user.is_active = True
                user.save(update_fields=["is_active"])
                return user
        else:
            enviar_email_confirmacao_django(request, user)

    return None


def reenviar_confirmacao(request, user, email):
    """
    Reenvia o link de ativação da conta por email.
    """
    if supabase_auth.enabled():
        supabase_auth.resend_signup_confirmation(
            email,
            redirect_to=supabase_auth.confirmation_redirect_url(request),
        )
    else:
        enviar_email_confirmacao_django(request, user)


def confirmar_email_supabase(request, token_hash, verification_type):
    """
    Valida a confirmação de e-mail no Supabase e ativa o usuário.
    """
    response = supabase_auth.verify_token_hash(token_hash, verification_type)
    return ativar_usuario_confirmado(request, response.get("user") or response)


def confirmar_sessao_supabase(request, access_token):
    """
    Valida o access token do Supabase e ativa/autentica o usuário.
    """
    supabase_user = supabase_auth.get_user(access_token)
    return ativar_usuario_confirmado(request, supabase_user)


def google_sessao_supabase(request, access_token):
    """
    Valida o login do Google no Supabase e autentica/cria o usuário.
    """
    supabase_user = supabase_auth.get_user(access_token)
    return autenticar_usuario_google(request, supabase_user)


def confirmar_email_django(request, uidb64, token):
    """
    Confirma o e-mail local do usuário via token do Django e o ativa/autentica.
    """
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        login(request, user)
        loja = user.lojas.order_by("id").first()
        if loja:
            return reverse("painel_loja", kwargs={"slug": loja.slug})
        return reverse("painel")

    raise ValueError("Token de confirmação inválido ou expirado.")
