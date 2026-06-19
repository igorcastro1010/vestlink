import json
import logging
from datetime import timedelta

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
from .services import billing, lead, store, catalog, products, auth


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
    ordenacao = request.GET.get("ordenacao", "").strip()
    page = request.GET.get("page", 1)

    contexto = catalog.obter_contexto_catalogo(
        request=request,
        loja=loja,
        categoria_id=categoria_id,
        busca=busca,
        filtro=filtro,
        produto_id=produto_id,
        vendedor_codigo=vendedor_codigo,
        ordenacao=ordenacao,
        page=page,
    )

    # Verifica se é uma requisição AJAX para retornar apenas o fragmento HTML
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.GET.get("fragment") == "1":
        return render(request, "includes/produto_grid.html", {
            "loja": contexto["loja"],
            "produtos": contexto["produtos"],
            "cache_version": contexto["cache_version"],
            "vendedor_ref": contexto["vendedor_ref"],
            "vendedor_codigo": contexto["vendedor_codigo"],
            "ordenacao": contexto["ordenacao"],
        })

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

    vendedor_codigo = request.GET.get("vendedor", "")
    contexto = catalog.obter_contexto_produto_detalhe(
        loja=loja,
        produto_id=produto_id,
        vendedor_codigo=vendedor_codigo,
    )
    return render(request, "produto_detalhe.html", contexto)


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("painel")
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            usuario_confirmado = auth.processar_cadastro(request, form)
            if usuario_confirmado:
                login(request, usuario_confirmado)
                loja = usuario_confirmado.lojas.order_by("id").first()
                if loja:
                    return redirect("painel_loja", slug=loja.slug)
                return redirect("painel")
            request.session["cadastro_confirmacao_email"] = form.cleaned_data["email"]
            return redirect("cadastro_confirmacao_enviada")
        except Exception as error:
            logger.exception("Erro ao criar cadastro ou solicitar confirmacao: %s", error)
            form.add_error(
                None,
                "Nao conseguimos concluir o cadastro agora. Revise os dados e tente novamente em alguns minutos.",
            )
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
        auth.reenviar_confirmacao(request, user, email)
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
            redirect_url = auth.confirmar_email_supabase(request, token_hash, verification_type)
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
        redirect_url = auth.confirmar_sessao_supabase(request, access_token)
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
        redirect_url = auth.google_sessao_supabase(request, access_token)
        return JsonResponse({"redirect_url": redirect_url})
    except Exception as error:
        logger.exception("Erro ao autenticar com Google pelo Supabase: %s", error)
        return JsonResponse(
            {"error": "Não foi possível entrar com o Google. Verifique a configuração e tente novamente."},
            status=400,
        )


def confirmar_email(request, uidb64, token):
    try:
        redirect_url = auth.confirmar_email_django(request, uidb64, token)
        return redirect(redirect_url)
    except Exception:
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
        products.publicar_produto(loja, request.POST.get("produto_id"))
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
        products.cadastrar_produto(loja, form)
        return redirect(f"{reverse('painel_loja', kwargs={'slug': loja.slug})}#produtos")

    # Restringe leads_base para vendedor logado, se necessário
    vendedor_logado = None
    if request.user != loja.usuario:
        try:
            vendedor_logado = request.user.vendedor_perfil
        except Vendedor.DoesNotExist:
            pass

    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    leads_filtrados = _obter_leads_filtrados(request, loja)

    contexto = store.obter_contexto_dashboard(
        request=request,
        loja=loja,
        usuario_logado=request.user,
        vendedor_logado=vendedor_logado,
        busca=busca,
        status=status,
        categoria_id=categoria_id,
        leads_filtrados=leads_filtrados,
    )
    contexto["form"] = form
    contexto["categoria_form"] = categoria_form
    contexto["vendedor_form"] = vendedor_form

    return render(request, "painel_loja.html", contexto)


@login_required
def baixar_qr_code(request, slug):
    loja = _loja_do_usuario(request, slug)
    image_bytes = store.gerar_qrcode(loja, request)
    response = HttpResponse(image_bytes, content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="qr-code-{loja.slug}.png"'
    return response





def _cadastro_context(form):
    return {
        "form": form,
        "privacy_version": PRIVACY_VERSION,
        "terms_version": TERMS_VERSION,
    }





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

    tamanho = request.GET.get("tamanho", "")
    cor = request.GET.get("cor", "")
    cliente_nome = request.GET.get("cliente_nome", "")
    vendedor_codigo = request.GET.get("vendedor", "")

    destino, mensagem = lead.processar_whatsapp_produto(
        request, loja, produto, tamanho, cor, cliente_nome, vendedor_codigo
    )

    return redirect(f"https://wa.me/55{destino}?text={quote(mensagem)}")


def whatsapp_carrinho(request, slug=None):
    if hasattr(request, "loja"):
        loja = request.loja
    else:
        loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return redirect("catalogo_curto", slug=loja.slug)

    mensagem = request.GET.get("mensagem", "")
    cliente_nome = request.GET.get("cliente_nome", "")
    cliente_telefone = request.GET.get("cliente_telefone", "")
    tipo_entrega = request.GET.get("tipo_entrega", "retirada")
    endereco_completo = request.GET.get("endereco_completo", "")
    vendedor_codigo = request.GET.get("vendedor", "")

    destino, mensagem = lead.processar_whatsapp_carrinho(
        request, loja, mensagem, cliente_nome, cliente_telefone, tipo_entrega, endereco_completo, vendedor_codigo
    )

    return redirect(f"https://wa.me/55{destino}?text={quote(mensagem)}")


@login_required
def editar_produto(request, slug, produto_id):
    loja = _loja_do_usuario(request, slug)
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    form = ProdutoForm(request.POST or None, request.FILES or None, instance=produto, loja=loja)

    if request.method == "POST" and form.is_valid():
        products.editar_produto(loja, produto, form)
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
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)

    if request.method == "POST":
        products.remover_produto(loja, produto, request.user)
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
