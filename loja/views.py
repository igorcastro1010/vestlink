import json
import logging
from io import BytesIO
from datetime import timedelta

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.text import slugify
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from urllib.parse import quote, urlencode

from . import supabase_auth
from .forms import CadastroForm, CategoriaForm, LojaForm, ProdutoForm, VendedorForm
from .legal import LEAD_RETENTION_DAYS, PRIVACY_VERSION, TERMS_VERSION
from .models import AceiteLegal, Categoria, Cupom, Lead, Loja, Pagamento, Produto, Vendedor
from .payments import MercadoPagoError
from .validators import limpar_telefone
from .services import billing


logger = logging.getLogger(__name__)


class LoginLojistaView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True
    extra_context = {
        "privacy_version": PRIVACY_VERSION,
        "terms_version": TERMS_VERSION,
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("remember_me"):
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            self.request.session.set_expiry(0)
        return response


def google_oauth_start(request):
    if request.user.is_authenticated:
        return redirect("painel")
    if not supabase_auth.oauth_enabled():
        messages.error(request, "O acesso com Google ainda não está disponível.")
        return redirect("login")

    try:
        if not supabase_auth.google_provider_enabled():
            messages.error(
                request,
                "O login com Google precisa ser ativado no Supabase antes de ser utilizado.",
            )
            return redirect("cadastro" if request.GET.get("origin") == "cadastro" else "login")
        return redirect(supabase_auth.google_authorize_url(request))
    except Exception as error:
        logger.exception("Erro ao iniciar login com Google: %s", error)
        messages.error(request, "Não conseguimos conectar ao Google agora. Tente novamente.")
        return redirect("login")


def home(request):
    host = request.get_host().split(":")[0].lower()
    if host not in {"127.0.0.1", "localhost"} and not host.endswith(".vercel.app"):
        loja = Loja.objects.filter(dominio_personalizado__iexact=host).first()
        if loja:
            return catalogo(request, loja.slug)
    return render(request, "home.html")


def planos(request):
    return render(request, "planos.html")


def termos_uso(request):
    return render(
        request,
        "termos_uso.html",
        {
            "terms_version": TERMS_VERSION,
            "legal_back_url": _legal_back_url(request),
            "legal_back_label": _legal_back_label(request),
        },
    )


def politica_privacidade(request):
    return render(
        request,
        "politica_privacidade.html",
        {
            "privacy_version": PRIVACY_VERSION,
            "legal_back_url": _legal_back_url(request),
            "legal_back_label": _legal_back_label(request),
        },
    )


def _legal_back_target(request):
    alvo = request.GET.get("voltar", "").strip().lower()
    if alvo in {"login", "cadastro"}:
        return alvo
    return "cadastro"


def _legal_back_url(request):
    return reverse("login" if _legal_back_target(request) == "login" else "cadastro")


def _legal_back_label(request):
    return "Voltar para o login" if _legal_back_target(request) == "login" else "Voltar para o cadastro"


def _vendedor_por_codigo(loja, codigo):
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return None
    return loja.vendedores.filter(codigo__iexact=codigo, ativo=True).first()


def catalogo(request, slug=None):
    if hasattr(request, "loja"):
        loja = request.loja
    else:
        loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return render(request, "catalogo_bloqueado.html", {"loja": loja}, status=402)
    categoria_id = request.GET.get("categoria")
    busca = request.GET.get("q", "").strip()
    filtro = request.GET.get("filtro", "").strip()
    produto_id = request.GET.get("produto", "").strip()
    vendedor_codigo = request.GET.get("vendedor", "").strip().lower()
    vendedor_ref = _vendedor_por_codigo(loja, vendedor_codigo)

    ordenacao = request.GET.get("ordenacao", "").strip()

    produtos = loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").filter(publicado=True)
    if produto_id:
        produtos = produtos.filter(id=produto_id)
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)
    if filtro == "novos":
        produtos = produtos.filter(destaque=True)
    elif filtro == "promocoes":
        produtos = produtos.filter(promocao=True)
    elif filtro == "disponiveis":
        produtos = produtos.filter(esgotado=False)
    if busca:
        produtos = produtos.filter(
            Q(nome__icontains=busca)
            | Q(descricao__icontains=busca)
            | Q(cores__icontains=busca)
            | Q(tamanhos__icontains=busca)
        )

    # Ordenação dos produtos
    if ordenacao == "preco_asc":
        produtos = produtos.order_by("esgotado", "preco", "nome")
    elif ordenacao == "preco_desc":
        produtos = produtos.order_by("esgotado", "-preco", "nome")
    elif ordenacao == "nome":
        produtos = produtos.order_by("esgotado", "nome")
    else:
        # Ordenação padrão
        produtos = produtos.order_by("esgotado", "ordem", "-destaque", "-criado_em")

    # Paginação dos produtos
    itens_por_pagina = 12
    paginator = Paginator(produtos, itens_por_pagina)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    from django.core.cache import cache
    cache_version = cache.get_or_set(f"loja_cache_version_{loja.id}", 1)

    # Verifica se é uma requisição AJAX para retornar apenas o fragmento HTML
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("fragment") == "1":
        return render(request, "includes/produto_grid.html", {
            "loja": loja,
            "produtos": page_obj,
            "cache_version": cache_version,
            "vendedor_ref": vendedor_ref,
            "vendedor_codigo": vendedor_ref.codigo if vendedor_ref else "",
            "ordenacao": ordenacao,
        })

    contexto = {
        "loja": loja,
        "categorias": loja.categorias.all(),
        "produtos": page_obj,
        "categoria_ativa": categoria_id,
        "busca": busca,
        "filtro": filtro,
        "ordenacao": ordenacao,
        "produto_ativo": produto_id,
        "tem_proxima_pagina": page_obj.has_next(),
        "proxima_pagina": page_obj.next_page_number() if page_obj.has_next() else None,
        "cache_version": cache_version,
        "vendedor_ref": vendedor_ref,
        "vendedor_codigo": vendedor_ref.codigo if vendedor_ref else "",
    }
    return render(request, "catalogo.html", contexto)


def catalogo_curto(request, slug):
    return catalogo(request, slug)


def produto_detalhe(request, slug=None, produto_id=None):
    if hasattr(request, "loja"):
        loja = request.loja
    else:
        loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return render(request, "catalogo_bloqueado.html", {"loja": loja}, status=402)
    produto = get_object_or_404(
        loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").filter(publicado=True),
        id=produto_id,
    )
    vendedor_ref = _vendedor_por_codigo(loja, request.GET.get("vendedor", ""))
    contexto = {
        "loja": loja,
        "produto": produto,
        "categorias": loja.categorias.all(),
        "vendedor_ref": vendedor_ref,
        "vendedor_codigo": vendedor_ref.codigo if vendedor_ref else "",
    }
    return render(request, "produto_detalhe.html", contexto)


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("painel")
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario_confirmado = None
        try:
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
                _registrar_aceite_legal(request, user, "cadastro")

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
                        usuario_confirmado = user
                else:
                    _enviar_email_confirmacao_django(request, user)
        except Exception as error:
            logger.exception("Erro ao criar cadastro ou solicitar confirmacao: %s", error)
            form.add_error(
                None,
                "Nao conseguimos concluir o cadastro agora. Revise os dados e tente novamente em alguns minutos.",
            )
            return render(request, "cadastro.html", _cadastro_context(form))
        if usuario_confirmado:
            login(request, usuario_confirmado)
            loja = usuario_confirmado.lojas.order_by("id").first()
            if loja:
                return redirect("painel_loja", slug=loja.slug)
            return redirect("painel")
        request.session["cadastro_confirmacao_email"] = form.cleaned_data["email"]
        return redirect("cadastro_confirmacao_enviada")

    return render(request, "cadastro.html", _cadastro_context(form))


def cadastro_confirmacao_enviada(request):
    return render(
        request,
        "cadastro_confirmacao_enviada.html",
        {"email": request.session.get("cadastro_confirmacao_email", "")},
    )


@require_POST
def reenviar_confirmacao_email(request):
    email = (
        request.POST.get("email")
        or request.session.get("cadastro_confirmacao_email")
        or ""
    ).strip().lower()

    if not email:
        messages.error(request, "Informe o e-mail do cadastro para reenviar a confirmacao.")
        return redirect("cadastro")

    request.session["cadastro_confirmacao_email"] = email
    user = User.objects.filter(email__iexact=email, is_active=False).order_by("-id").first()
    if not user:
        messages.success(request, "Se existir uma conta pendente para esse e-mail, enviaremos um novo link.")
        return redirect("cadastro_confirmacao_enviada")

    try:
        if supabase_auth.enabled():
            supabase_auth.resend_signup_confirmation(
                email,
                redirect_to=supabase_auth.confirmation_redirect_url(request),
            )
        else:
            _enviar_email_confirmacao_django(request, user)
        messages.success(request, "Enviamos outro link de confirmacao. Confira tambem o Spam e Promocoes.")
    except Exception as error:
        logger.exception("Erro ao reenviar confirmacao de e-mail: %s", error)
        messages.error(request, "Nao conseguimos reenviar agora. Tente novamente em alguns minutos.")

    return redirect("cadastro_confirmacao_enviada")


def supabase_confirmar_email(request):
    token_hash = request.GET.get("token_hash")
    verification_type = request.GET.get("type", "email")
    if token_hash:
        try:
            response = supabase_auth.verify_token_hash(token_hash, verification_type)
            redirect_url = _ativar_usuario_confirmado(request, response.get("user") or response)
            return redirect(redirect_url)
        except Exception as error:
            logger.exception("Erro ao confirmar e-mail pelo Supabase: %s", error)
            return render(request, "cadastro_confirmacao_invalida.html", status=400)

    return render(
        request,
        "cadastro_supabase_confirmar.html",
        {"google_oauth": request.GET.get("provider") == "google"},
    )


@csrf_exempt
@require_POST
def supabase_confirmar_sessao(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        access_token = payload.get("access_token", "")
        if not access_token:
            raise ValueError("access_token ausente.")
        supabase_user = supabase_auth.get_user(access_token)
        redirect_url = _ativar_usuario_confirmado(request, supabase_user)
        return JsonResponse({"redirect_url": redirect_url})
    except Exception as error:
        logger.exception("Erro ao confirmar sessao Supabase: %s", error)
        return JsonResponse({"error": "Link de confirmacao invalido ou expirado."}, status=400)


@csrf_exempt
@require_POST
def supabase_google_sessao(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        access_token = payload.get("access_token", "")
        if not access_token:
            raise ValueError("access_token ausente.")
        supabase_user = supabase_auth.get_user(access_token)
        redirect_url = _autenticar_usuario_google(request, supabase_user)
        return JsonResponse({"redirect_url": redirect_url})
    except Exception as error:
        logger.exception("Erro ao autenticar com Google pelo Supabase: %s", error)
        return JsonResponse(
            {"error": "Não foi possível entrar com o Google. Verifique a configuração e tente novamente."},
            status=400,
        )


def _username_google_unico(supabase_user):
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


def _autenticar_usuario_google(request, supabase_user):
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
            username=_username_google_unico(supabase_user),
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
        _registrar_aceite_legal(request, user, "google_oauth")

    login(request, user)
    loja = user.lojas.order_by("id").first()
    if loja:
        return reverse("painel_loja", kwargs={"slug": loja.slug})
    return reverse("painel")


def _ativar_usuario_confirmado(request, supabase_user):
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


def _enviar_email_confirmacao_django(request, user):
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


def confirmar_email(request, uidb64, token):
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
            return redirect("painel_loja", slug=loja.slug)
        return redirect("painel")

    return render(request, "cadastro_confirmacao_invalida.html", status=400)


@login_required
def painel(request):
    try:
        vendedor = request.user.vendedor_perfil
        if vendedor:
            if vendedor.ativo:
                return redirect("painel_loja", slug=vendedor.loja.slug)
            else:
                raise PermissionDenied("Sua conta de vendedor está inativa.")
    except Vendedor.DoesNotExist:
        pass

    form = LojaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        loja = form.save(commit=False)
        loja.usuario = request.user
        loja.save()
        return redirect("painel_loja", slug=loja.slug)

    lojas = Loja.objects.filter(usuario=request.user)
    tem_loja = lojas.exists()
    tem_produto = Produto.objects.filter(loja__in=lojas).exists()
    contexto = {
        "form": form,
        "lojas": lojas,
        "onboarding_painel": [
            {
                "titulo": "Criar loja",
                "descricao": "Defina nome, link e WhatsApp para gerar sua vitrine.",
                "feito": tem_loja,
            },
            {
                "titulo": "Cadastrar produto",
                "descricao": "Adicione a primeira peça com foto, preço, tamanho e cor.",
                "feito": tem_produto,
            },
            {
                "titulo": "Compartilhar link",
                "descricao": "Copie o link curto e coloque na bio ou envie no WhatsApp.",
                "feito": tem_loja,
            },
        ],
    }
    return render(request, "painel.html", contexto)


def _loja_do_usuario(request, slug):
    loja = get_object_or_404(Loja, slug=slug)
    if loja.usuario is None:
        raise PermissionDenied("Essa loja ainda nao tem um lojista responsavel definido.")
    elif loja.usuario != request.user:
        # Permite acesso se o usuário logado for um vendedor ativo da loja
        is_vendedor = Vendedor.objects.filter(loja=loja, usuario=request.user, ativo=True).exists()
        if not is_vendedor:
            raise PermissionDenied("Você não tem acesso a essa loja.")
    return loja


def _obter_leads_filtrados(request, loja):
    leads = loja.leads.select_related("produto", "vendedor").all()
    vendedor_logado = None
    if request.user != loja.usuario:
        try:
            vendedor_logado = request.user.vendedor_perfil
        except Vendedor.DoesNotExist:
            pass

    if vendedor_logado:
        leads = leads.filter(vendedor=vendedor_logado)

    busca_leads = request.GET.get("q_leads", "").strip()
    vendedor_leads = request.GET.get("vendedor_leads", "").strip()
    status_leads = request.GET.get("status_leads", "").strip()

    if busca_leads:
        leads = leads.filter(
            Q(cliente_nome__icontains=busca_leads)
            | Q(cliente_telefone__icontains=busca_leads)
            | Q(produto__nome__icontains=busca_leads)
            | Q(mensagem__icontains=busca_leads)
        )
    if not vendedor_logado and vendedor_leads:
        if vendedor_leads == "sem_vendedor":
            leads = leads.filter(vendedor__isnull=True)
        else:
            leads = leads.filter(vendedor_id=vendedor_leads)
    if status_leads:
        leads = leads.filter(status=status_leads)

    return leads


@login_required
def painel_loja(request, slug):
    loja = _loja_do_usuario(request, slug)
    form = ProdutoForm(request.POST or None, request.FILES or None, loja=loja)
    categoria_form = CategoriaForm()
    vendedor_form = VendedorForm(loja=loja)

    if request.method == "POST" and request.POST.get("acao") == "criar_categoria":
        categoria_form = CategoriaForm(request.POST)
        if categoria_form.is_valid():
            categoria = categoria_form.save(commit=False)
            categoria.loja = loja
            categoria.save()
            return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    elif request.method == "POST" and request.POST.get("acao") == "criar_vendedor":
        if request.user != loja.usuario:
            raise PermissionDenied("Apenas o proprietário da loja pode criar vendedores.")
        vendedor_form = VendedorForm(request.POST, loja=loja)
        if vendedor_form.is_valid():
            vendedor_form.save()
            return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#vendedores")

    elif request.method == "POST" and request.POST.get("acao") == "alternar_vendedor":
        if request.user != loja.usuario:
            raise PermissionDenied("Apenas o proprietário da loja pode desativar/ativar vendedores.")
        vendedor = get_object_or_404(Vendedor, id=request.POST.get("vendedor_id"), loja=loja)
        vendedor.ativo = not vendedor.ativo
        vendedor.save(update_fields=["ativo"])
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#vendedores")

    elif request.method == "POST" and request.POST.get("acao") == "remover_vendedor":
        if request.user != loja.usuario:
            raise PermissionDenied("Apenas o proprietário da loja pode remover vendedores.")
        vendedor = get_object_or_404(Vendedor, id=request.POST.get("vendedor_id"), loja=loja)
        vendedor.delete()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#vendedores")

    elif request.method == "POST" and request.POST.get("acao") == "publicar_produto":
        produto = get_object_or_404(Produto, id=request.POST.get("produto_id"), loja=loja)
        produto.publicado = True
        produto.save(update_fields=["publicado"])
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    elif request.method == "POST" and request.POST.get("acao") == "atualizar_lead_status":
        lead = get_object_or_404(Lead, id=request.POST.get("lead_id"), loja=loja)
        novo_status = request.POST.get("status")
        lead.observacao = request.POST.get("observacao", "").strip()
        if novo_status in dict(Lead.STATUS_CHOICES):
            lead.status = novo_status
            lead.save(update_fields=["status", "observacao"])
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#leads")

    elif request.method == "POST" and not loja.assinatura_esta_ativa:
        return redirect("assinatura", slug=loja.slug)

    elif request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    produtos_base = loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").all()
    
    # Restringe leads_base para vendedor logado, se necessário
    vendedor_logado = None
    if request.user != loja.usuario:
        try:
            vendedor_logado = request.user.vendedor_perfil
        except Vendedor.DoesNotExist:
            pass

    leads_base = loja.leads.select_related("produto", "vendedor").all()
    if vendedor_logado:
        leads_base = leads_base.filter(vendedor=vendedor_logado)

    vendedores_base = loja.vendedores.all()
    produtos = produtos_base
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()

    if busca:
        produtos = produtos.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)
    if status == "esgotado":
        produtos = produtos.filter(esgotado=True)
    elif status == "novo":
        produtos = produtos.filter(destaque=True)
    elif status == "promocao":
        produtos = produtos.filter(promocao=True)
    elif status == "rascunho":
        produtos = produtos.filter(publicado=False)
    elif status == "disponivel":
        produtos = produtos.filter(esgotado=False)

    produtos_sem_foto_extra = produtos_base.filter(imagens__isnull=True).count()
    avisos = []
    if not loja.telefone:
        avisos.append("Configure o WhatsApp da loja para os clientes conseguirem chamar você.")
    if total_produtos := produtos_base.count():
        if produtos_sem_foto_extra:
            avisos.append(f"{produtos_sem_foto_extra} produto(s) ainda tem apenas a foto principal.")
    else:
        avisos.append("Cadastre seu primeiro produto para publicar a vitrine.")
    if loja.categorias.count() == 0:
        avisos.append("Crie pelo menos uma categoria para facilitar a navegacao do cliente.")
    if not loja.banner_titulo and not loja.banner_imagem:
        avisos.append("Personalize o banner do catálogo para destacar novidades ou promoções.")
    if not loja.assinatura_esta_ativa:
        avisos.append("Seu teste expirou ou a assinatura está inativa. Regularize para manter o catálogo profissional no ar.")
    rascunhos = produtos_base.filter(publicado=False).count()
    if rascunhos:
        avisos.append(f"{rascunhos} produto(s) estão como rascunho e não aparecem no catálogo.")
    total_leads_global = leads_base.count()
    pedidos_novos_global = leads_base.filter(status=Lead.STATUS_NOVO).count()

    leads_filtrados = _obter_leads_filtrados(request, loja)
    total_leads = leads_filtrados.count()
    pedidos_novos = leads_filtrados.filter(status=Lead.STATUS_NOVO).count()
    pedidos_atendimento = leads_filtrados.filter(status=Lead.STATUS_ATENDIMENTO).count()
    pedidos_concluidos = leads_filtrados.filter(status=Lead.STATUS_CONCLUIDO).count()
    total_cliques = sum(produto.cliques_whatsapp for produto in produtos_base)
    produtos_mais_clicados = produtos_base.order_by("-cliques_whatsapp", "nome")[:5]
    vendedores_resumo = vendedores_base.annotate(
        total_leads=Count("leads"),
        leads_concluidos=Count("leads", filter=Q(leads__status=Lead.STATUS_CONCLUIDO)),
    )
    leads_por_dia = (
        leads_base.annotate(dia=TruncDate("criado_em"))
        .values("dia")
        .annotate(total=Count("id"))
        .order_by("-dia")[:7]
    )
    horarios_pico = (
        leads_base.annotate(hora=ExtractHour("criado_em"))
        .values("hora")
        .annotate(total=Count("id"))
        .order_by("-total", "hora")[:5]
    )
    taxa_conversao = round((pedidos_concluidos / total_leads) * 100) if total_leads else 0
    taxa_interesse = round((total_leads / total_cliques) * 100) if total_cliques else 0
    ticket_estimado = sum(produto.preco for produto in produtos_base.filter(leads__isnull=False).distinct())
    catalogo_url = request.build_absolute_uri(reverse("catalogo_curto", kwargs={"slug": loja.slug}))
    if loja.dominio_limpo:
        catalogo_url = f"https://{loja.dominio_limpo}/"
    mensagem_compartilhar = quote(
        f"Oi! Confira o catálogo da {loja.nome}: {catalogo_url}"
    )

    # Serialização de dados para gráficos (Chart.js)
    leads_por_dia_cronologico = list(leads_por_dia)[::-1]
    chart_leads_labels = json.dumps([item["dia"].strftime("%d/%m") if item["dia"] else "" for item in leads_por_dia_cronologico])
    chart_leads_valores = json.dumps([item["total"] for item in leads_por_dia_cronologico])

    horarios_pico_cronologico = sorted(list(horarios_pico), key=lambda x: x["hora"] if x["hora"] is not None else 0)
    chart_horarios_labels = json.dumps([f"{item['hora']}h" if item["hora"] is not None else "" for item in horarios_pico_cronologico])
    chart_horarios_valores = json.dumps([item["total"] for item in horarios_pico_cronologico])

    chart_produtos_labels = json.dumps([p.nome for p in produtos_mais_clicados])
    chart_produtos_valores = json.dumps([p.cliques_whatsapp for p in produtos_mais_clicados])

    # Serialização do gráfico de vendedores (Doughnut Chart)
    leads_sem_vendedor = leads_base.filter(vendedor__isnull=True).count()
    vendedores_labels = [v.nome for v in vendedores_resumo if v.total_leads > 0]
    vendedores_valores = [v.total_leads for v in vendedores_resumo if v.total_leads > 0]
    if leads_sem_vendedor > 0:
        vendedores_labels.append("Sem Vendedor (Direto)")
        vendedores_valores.append(leads_sem_vendedor)
    chart_vendedores_labels = json.dumps(vendedores_labels)
    chart_vendedores_valores = json.dumps(vendedores_valores)

    onboarding = [
        {
            "numero": "1",
            "titulo": "Loja criada",
            "descricao": "Seu link público já está pronto.",
            "feito": True,
        },
        {
            "numero": "2",
            "titulo": "Primeiro produto",
            "descricao": "Cadastre foto, preço, tamanho e cor.",
            "feito": total_produtos > 0,
        },
        {
            "numero": "3",
            "titulo": "Link compartilhado",
            "descricao": "Copie o link curto para usar na bio e no WhatsApp.",
            "feito": total_produtos > 0,
        },
        {
            "numero": "4",
            "titulo": "WhatsApp testado",
            "descricao": "Clique em um produto como se fosse cliente.",
            "feito": total_leads > 0,
        },
    ]
    onboarding_concluidos = sum(1 for passo in onboarding if passo["feito"])
    contexto = {
        "loja": loja,
        "is_owner": request.user == loja.usuario,
        "form": form,
        "categoria_form": categoria_form,
        "vendedor_form": vendedor_form,
        "produtos": produtos,
        "total_produtos": total_produtos,
        "total_esgotados": produtos_base.filter(esgotado=True).count(),
        "total_categorias": loja.categorias.count(),
        "total_fotos": sum(1 + produto.imagens.count() for produto in produtos_base),
        "total_cliques": total_cliques,
        "total_leads_global": total_leads_global,
        "pedidos_novos_global": pedidos_novos_global,
        "total_leads": total_leads,
        "leads_produto": leads_filtrados.filter(origem=Lead.ORIGEM_PRODUTO).count(),
        "leads_sacolinha": leads_filtrados.filter(origem=Lead.ORIGEM_SACOLINHA).count(),
        "leads_recentes": leads_filtrados[:50],
        "vendedores": vendedores_resumo,
        "total_vendedores": vendedores_base.count(),
        "vendedores_ativos": vendedores_base.filter(ativo=True).count(),
        "pedidos_novos": pedidos_novos,
        "pedidos_atendimento": pedidos_atendimento,
        "pedidos_concluidos": pedidos_concluidos,
        "status_lead_choices": Lead.STATUS_CHOICES,
        "produtos_mais_clicados": produtos_mais_clicados,
        "leads_por_dia": leads_por_dia,
        "horarios_pico": horarios_pico,
        "taxa_conversao": taxa_conversao,
        "taxa_interesse": taxa_interesse,
        "ticket_estimado": ticket_estimado,
        "catalogo_url": catalogo_url,
        "mensagem_compartilhar": mensagem_compartilhar,
        "avisos": avisos,
        "busca_painel": busca,
        "status_painel": status,
        "categoria_painel": categoria_id,
        "busca_leads": request.GET.get("q_leads", "").strip(),
        "vendedor_leads_ativo": request.GET.get("vendedor_leads", "").strip(),
        "status_leads_ativo": request.GET.get("status_leads", "").strip(),
        "onboarding": onboarding,
        "onboarding_concluidos": onboarding_concluidos,
        "onboarding_total": len(onboarding),
        "onboarding_percentual": round(onboarding_concluidos / len(onboarding) * 100),
        "chart_leads_labels": chart_leads_labels,
        "chart_leads_valores": chart_leads_valores,
        "chart_horarios_labels": chart_horarios_labels,
        "chart_horarios_valores": chart_horarios_valores,
        "chart_produtos_labels": chart_produtos_labels,
        "chart_produtos_valores": chart_produtos_valores,
        "chart_vendedores_labels": chart_vendedores_labels,
        "chart_vendedores_valores": chart_vendedores_valores,
    }
    return render(request, "painel_loja.html", contexto)


@login_required
def baixar_qr_code(request, slug):
    loja = _loja_do_usuario(request, slug)
    catalogo_url = request.build_absolute_uri(reverse("catalogo_curto", kwargs={"slug": loja.slug}))
    if loja.dominio_limpo:
        catalogo_url = f"https://{loja.dominio_limpo}/"

    qr_code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr_code.add_data(catalogo_url)
    qr_code.make(fit=True)

    image = qr_code.make_image(fill_color="#151129", back_color="#ffffff")
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")

    response = HttpResponse(image_buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="qr-code-{loja.slug}.png"'
    return response


def _request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _cadastro_context(form):
    return {
        "form": form,
        "privacy_version": PRIVACY_VERSION,
        "terms_version": TERMS_VERSION,
    }


def _registrar_aceite_legal(request, user, fonte):
    AceiteLegal.objects.create(
        user=user,
        termos_versao=TERMS_VERSION,
        privacidade_versao=PRIVACY_VERSION,
        fonte=fonte,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )


@login_required
def editar_loja(request, slug):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode editar as configurações.")
    form = LojaForm(request.POST or None, request.FILES or None, instance=loja)

    if request.method == "POST" and form.is_valid():
        loja = form.save()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#configuracoes")

    return render(request, "editar_loja.html", {"loja": loja, "form": form})


@login_required
def remover_loja(request, slug):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode excluir a loja.")
    erro_confirmacao = ""

    if request.method == "POST":
        confirmacao = request.POST.get("confirmacao", "").strip()
        if confirmacao != loja.slug:
            erro_confirmacao = f"Digite {loja.slug} para confirmar a exclusao da loja."
        else:
            loja.delete()
            return redirect("painel")

    return render(request, "remover_loja.html", {"loja": loja, "erro_confirmacao": erro_confirmacao})


@login_required
def assinatura(request, slug):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode gerenciar a assinatura.")

    if request.method == "POST":
        acao = request.POST.get("acao", "ativar_manual")
        if acao == "renovar_teste":
            loja.assinatura_status = Loja.ASSINATURA_TRIAL
            loja.trial_termina_em = timezone.now() + timedelta(days=7)
            loja.assinatura_cancelada_em = None
            loja.save(update_fields=["assinatura_status", "trial_termina_em", "assinatura_cancelada_em"])
        elif acao == "cancelar":
            loja.assinatura_status = Loja.ASSINATURA_CANCELADA
            loja.assinatura_cancelada_em = timezone.now()
            loja.save(update_fields=["assinatura_status", "assinatura_cancelada_em"])
        else:
            loja.plano = Loja.PLANO_PREMIUM
            loja.assinatura_status = Loja.ASSINATURA_ATIVA
            loja.assinatura_ativa_em = timezone.now()
            loja.assinatura_cancelada_em = None
            loja.save(update_fields=["plano", "assinatura_status", "assinatura_ativa_em", "assinatura_cancelada_em"])
        return redirect("assinatura", slug=loja.slug)

    return render(
        request,
        "assinatura.html",
        {
            "loja": loja,
            "checkout_configurado": bool(
                getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", "")
                or getattr(settings, "VESTLINK_CHECKOUT_URL", "")
                or getattr(settings, "MODALINK_CHECKOUT_URL", "")
            ),
            "mercado_pago_configurado": bool(getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", "")),
            "ultimos_pagamentos": loja.pagamentos.all()[:5],
        },
    )


@login_required
def checkout_premium(request, slug):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode gerenciar pagamentos.")
    cupom_codigo = (request.POST.get("cupom") or request.GET.get("cupom") or "").strip().upper()
    dados = billing.obter_dados_checkout(cupom_codigo)

    if request.method == "POST":
        try:
            redirect_url = billing.processar_checkout(request, loja, request.user, dados["cupom"])
            if redirect_url:
                return redirect(redirect_url)
        except MercadoPagoError as error:
            return render(
                request,
                "checkout_premium.html",
                {
                    "loja": loja,
                    "erro_pagamento": str(error),
                    "cupom": dados["cupom"],
                    "cupom_codigo": dados["cupom_codigo"],
                },
            )

    contexto = {
        "loja": loja,
        "cupom": dados["cupom"],
        "cupom_codigo": dados["cupom_codigo"],
        "valor": dados["valor"],
        "valor_final": dados["valor_final"],
        "mercado_pago_configurado": dados["mercado_pago_configurado"],
    }
    return render(request, "checkout_premium.html", contexto)


@login_required
def pagamento_retorno(request, slug, resultado):
    loja = _loja_do_usuario(request, slug)
    external_reference = request.GET.get("external_reference", "")
    payment_id = request.GET.get("payment_id", "")
    status = request.GET.get("status", "")
    
    pagamento = billing.processar_pagamento_retorno(
        loja, external_reference, payment_id, status, resultado
    )

    return render(
        request,
        "pagamento_retorno.html",
        {
            "loja": loja,
            "resultado": resultado,
            "pagamento": pagamento,
        },
    )


@csrf_exempt
@require_POST
def mercado_pago_webhook(request):
    payment_id = request.GET.get("id") or request.GET.get("data.id")
    if request.content_type == "application/json" and request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except ValueError:
            payload = {}
        data = payload.get("data") or {}
        payment_id = payment_id or data.get("id") or payload.get("id")
    if not payment_id:
        return JsonResponse({"ok": False, "erro": "payment_id ausente"}, status=400)
    try:
        pagamento = billing.processar_webhook_pagamento(payment_id)
    except Exception as error:
        return JsonResponse({"ok": False, "erro": str(error)}, status=400)
    return JsonResponse({"ok": True, "pagamento": pagamento.id, "status": pagamento.status})



@login_required
def editar_categoria(request, slug, categoria_id):
    loja = _loja_do_usuario(request, slug)
    categoria = get_object_or_404(Categoria, id=categoria_id, loja=loja)
    form = CategoriaForm(request.POST or None, instance=categoria)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    return render(request, "editar_categoria.html", {"loja": loja, "categoria": categoria, "form": form})


@login_required
def remover_categoria(request, slug, categoria_id):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode excluir categorias.")
    categoria = get_object_or_404(Categoria, id=categoria_id, loja=loja)

    if request.method == "POST":
        categoria.delete()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    return render(request, "remover_categoria.html", {"loja": loja, "categoria": categoria})


def whatsapp_produto(request, slug=None, produto_id=None):
    if hasattr(request, "loja"):
        loja = request.loja
    else:
        loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return redirect("catalogo_curto", slug=loja.slug)
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    Produto.objects.filter(id=produto.id).update(cliques_whatsapp=F("cliques_whatsapp") + 1)

    detalhes = []
    tamanho = request.GET.get("tamanho", "").strip()
    cor = request.GET.get("cor", "").strip()
    cliente_nome = request.GET.get("cliente_nome", "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, request.GET.get("vendedor", ""))
    if tamanho:
        detalhes.append(f"tamanho {tamanho}")
    if cor:
        detalhes.append(f"cor {cor}")

    complemento = f", {', '.join(detalhes)}" if detalhes else ""
    mensagem = f"Olá! Tenho interesse na peça: {produto.nome}{complemento}"
    if cliente_nome:
        mensagem = f"{mensagem}\nCliente: {cliente_nome}"
    if vendedor_ref:
        mensagem = f"{mensagem}\nVendedor: {vendedor_ref.nome}"

    Lead.objects.create(
        loja=loja,
        vendedor=vendedor_ref,
        produto=produto,
        origem=Lead.ORIGEM_PRODUTO,
        cliente_nome=cliente_nome,
        tamanho=tamanho,
        cor=cor,
        status=Lead.STATUS_NOVO,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    destino = loja.telefone
    if vendedor_ref and vendedor_ref.telefone:
        destino_vendedor = limpar_telefone(vendedor_ref.telefone)
        if destino_vendedor:
            destino = destino_vendedor
    return redirect(f"https://wa.me/55{destino}?text={quote(mensagem)}")


def whatsapp_carrinho(request, slug=None):
    if hasattr(request, "loja"):
        loja = request.loja
    else:
        loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return redirect("catalogo_curto", slug=loja.slug)
    mensagem = request.GET.get("mensagem", "").strip()
    cliente_nome = request.GET.get("cliente_nome", "").strip()
    cliente_telefone = request.GET.get("cliente_telefone", "").strip()
    tipo_entrega = request.GET.get("tipo_entrega", "retirada").strip()
    endereco_completo = request.GET.get("endereco_completo", "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, request.GET.get("vendedor", ""))
    if not mensagem:
        mensagem = "Olá! Quero fazer um pedido pelo catálogo."
    if vendedor_ref and "Vendedor:" not in mensagem:
        mensagem = f"{mensagem}\nVendedor: {vendedor_ref.nome}"

    Lead.objects.create(
        loja=loja,
        vendedor=vendedor_ref,
        origem=Lead.ORIGEM_SACOLINHA,
        cliente_nome=cliente_nome,
        cliente_telefone=cliente_telefone,
        status=Lead.STATUS_NOVO,
        tipo_entrega=tipo_entrega,
        endereco_completo=endereco_completo,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    destino = loja.telefone
    if vendedor_ref and vendedor_ref.telefone:
        destino_vendedor = limpar_telefone(vendedor_ref.telefone)
        if destino_vendedor:
            destino = destino_vendedor
    return redirect(f"https://wa.me/55{destino}?text={quote(mensagem)}")


@login_required
def editar_produto(request, slug, produto_id):
    loja = _loja_do_usuario(request, slug)
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    form = ProdutoForm(request.POST or None, request.FILES or None, instance=produto, loja=loja)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    contexto = {
        "loja": loja,
        "produto": produto,
        "form": form,
    }
    return render(request, "editar_produto.html", contexto)


@login_required
def remover_produto(request, slug, produto_id):
    loja = _loja_do_usuario(request, slug)
    if request.user != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode excluir produtos.")
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)

    if request.method == "POST":
        produto.delete()
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    contexto = {
        "loja": loja,
        "produto": produto,
    }
    return render(request, "remover_produto.html", contexto)


@csrf_exempt
def cron_verificar_assinaturas(request):
    import os
    cron_secret = getattr(settings, "CRON_SECRET", os.environ.get("CRON_SECRET"))
    auth_header = request.headers.get("Authorization")
    
    if not settings.DEBUG:
        if not cron_secret or auth_header != f"Bearer {cron_secret}":
            return JsonResponse({"status": "unauthorized"}, status=401)
        
    # Rotina para expirar trials vencidos
    hoje = timezone.now()
    lojas_trial_expirado = Loja.objects.filter(
        assinatura_status=Loja.ASSINATURA_TRIAL,
        trial_termina_em__lt=hoje
    )
    total_expirados = lojas_trial_expirado.count()
    
    for loja in lojas_trial_expirado:
        loja.assinatura_status = Loja.ASSINATURA_VENCIDA
        loja.save(update_fields=["assinatura_status"])

    limite_leads = hoje - timedelta(days=getattr(settings, "LEAD_RETENTION_DAYS", LEAD_RETENTION_DAYS))
    leads_antigos = Lead.objects.filter(
        criado_em__lt=limite_leads,
        anonimizado_em__isnull=True,
    )
    total_leads_anonimizados = leads_antigos.count()

    for lead in leads_antigos.iterator():
        lead.anonimizar()
        
    return JsonResponse({
        "status": "success",
        "trials_expirados_processados": total_expirados,
        "leads_anonimizados": total_leads_anonimizados,
    })


@login_required
def validar_cupom(request, slug):
    loja = _loja_do_usuario(request, slug)
    codigo = request.GET.get("codigo", "").strip().upper()
    if not codigo:
        return JsonResponse({"valido": False, "mensagem": "Código do cupom vazio."})
    
    cupom = Cupom.objects.filter(codigo__iexact=codigo, ativo=True).first()
    if not cupom:
        return JsonResponse({"valido": False, "mensagem": "Cupom inválido ou expirado."})
    
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor)
    desconto = valor - valor_final
    
    return JsonResponse({
        "valido": True,
        "codigo": cupom.codigo,
        "percentual_desconto": cupom.percentual_desconto,
        "desconto_formatado": f"R$ {desconto:.2f}".replace(".", ","),
        "valor_final_formatado": f"R$ {valor_final:.2f}".replace(".", ","),
    })


import csv

@login_required
def exportar_leads_csv(request, slug):
    loja = _loja_do_usuario(request, slug)
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="leads-{loja.slug}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Data",
        "Origem",
        "Cliente",
        "Telefone",
        "Vendedor",
        "Produto",
        "Tamanho",
        "Cor",
        "Tipo de Entrega",
        "Endereço Completo",
        "Status",
        "Mensagem",
        "Observação Interna"
    ])

    leads = _obter_leads_filtrados(request, loja)
    for lead in leads:
        writer.writerow([
            lead.criado_em.strftime("%d/%m/%Y %H:%M:%S"),
            lead.get_origem_display(),
            lead.cliente_nome,
            lead.cliente_telefone,
            lead.vendedor.nome if lead.vendedor else "Direto",
            lead.produto.nome if lead.produto else "Sacolinha",
            lead.tamanho,
            lead.cor,
            lead.get_tipo_entrega_display(),
            lead.endereco_completo,
            lead.get_status_display(),
            lead.mensagem,
            lead.observacao
        ])
    return response


@login_required
def exportar_leads_impressao(request, slug):
    loja = _loja_do_usuario(request, slug)
    leads = _obter_leads_filtrados(request, loja)
    return render(
        request,
        "leads_impressao.html",
        {
            "loja": loja,
            "leads": leads,
        }
    )
