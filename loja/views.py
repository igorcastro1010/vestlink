import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Count, F, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import quote, urlencode

from .forms import CadastroForm, CategoriaForm, LojaForm, ProdutoForm
from .models import Categoria, Cupom, Lead, Loja, Pagamento, Produto
from .payments import MercadoPagoError, atualizar_pagamento_mercado_pago, criar_preferencia_premium


class LoginLojistaView(LoginView):
    template_name = "login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("remember_me"):
            self.request.session.set_expiry(60 * 60 * 24 * 30)
        else:
            self.request.session.set_expiry(0)
        return response


def home(request):
    host = request.get_host().split(":")[0].lower()
    if host not in {"127.0.0.1", "localhost"} and not host.endswith(".vercel.app"):
        loja = Loja.objects.filter(dominio_personalizado__iexact=host).first()
        if loja:
            return catalogo(request, loja.slug)
    return render(request, "home.html")


def planos(request):
    return render(request, "planos.html")


def catalogo(request, slug):
    loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return render(request, "catalogo_bloqueado.html", {"loja": loja}, status=402)
    categoria_id = request.GET.get("categoria")
    busca = request.GET.get("q", "").strip()
    filtro = request.GET.get("filtro", "").strip()
    produto_id = request.GET.get("produto", "").strip()

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

    contexto = {
        "loja": loja,
        "categorias": loja.categorias.all(),
        "produtos": produtos,
        "categoria_ativa": categoria_id,
        "busca": busca,
        "filtro": filtro,
        "produto_ativo": produto_id,
    }
    return render(request, "catalogo.html", contexto)


def catalogo_curto(request, slug):
    return catalogo(request, slug)


def produto_detalhe(request, slug, produto_id):
    loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return render(request, "catalogo_bloqueado.html", {"loja": loja}, status=402)
    produto = get_object_or_404(
        loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").filter(publicado=True),
        id=produto_id,
    )
    contexto = {
        "loja": loja,
        "produto": produto,
        "categorias": loja.categorias.all(),
    }
    return render(request, "produto_detalhe.html", contexto)


def cadastro(request):
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        loja_nome = form.cleaned_data.get("loja_nome", "").strip()
        loja_slug = form.cleaned_data.get("loja_slug", "").strip()
        loja_telefone = form.cleaned_data.get("loja_telefone", "").strip()
        loja_instagram = form.cleaned_data.get("loja_instagram", "").strip()
        loja = None
        if loja_nome and loja_slug and loja_telefone:
            loja = Loja.objects.create(
                usuario=user,
                nome=loja_nome,
                slug=loja_slug,
                telefone=loja_telefone,
                instagram=loja_instagram,
            )
        if user.email:
            send_mail(
                "Bem-vindo ao VestLink",
                (
                    "Sua conta foi criada com sucesso.\n\n"
                    "Entre no painel, cadastre seus produtos e compartilhe o link do catalogo com seus clientes.\n"
                    f"Painel: {request.build_absolute_uri(reverse('painel'))}"
                ),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        login(request, user)
        if loja:
            return redirect("painel_loja", slug=loja.slug)
        return redirect("painel")

    return render(request, "cadastro.html", {"form": form})


@login_required
def painel(request):
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
                "descricao": "Adicione a primeira peca com foto, preco, tamanho e cor.",
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
        loja.usuario = request.user
        loja.save(update_fields=["usuario"])
    elif loja.usuario != request.user:
        raise PermissionDenied("Voce nao tem acesso a essa loja.")
    return loja


@login_required
def painel_loja(request, slug):
    loja = _loja_do_usuario(request, slug)
    form = ProdutoForm(request.POST or None, request.FILES or None, loja=loja)
    categoria_form = CategoriaForm()

    if request.method == "POST" and request.POST.get("acao") == "criar_categoria":
        categoria_form = CategoriaForm(request.POST)
        if categoria_form.is_valid():
            categoria = categoria_form.save(commit=False)
            categoria.loja = loja
            categoria.save()
            return redirect("painel_loja", slug=loja.slug)

    elif request.method == "POST" and request.POST.get("acao") == "publicar_produto":
        produto = get_object_or_404(Produto, id=request.POST.get("produto_id"), loja=loja)
        produto.publicado = True
        produto.save(update_fields=["publicado"])
        return redirect("painel_loja", slug=loja.slug)

    elif request.method == "POST" and request.POST.get("acao") == "atualizar_lead_status":
        lead = get_object_or_404(Lead, id=request.POST.get("lead_id"), loja=loja)
        novo_status = request.POST.get("status")
        lead.observacao = request.POST.get("observacao", "").strip()
        if novo_status in dict(Lead.STATUS_CHOICES):
            lead.status = novo_status
            lead.save(update_fields=["status", "observacao"])
        return redirect("painel_loja", slug=loja.slug)

    elif request.method == "POST" and not loja.assinatura_esta_ativa:
        return redirect("assinatura", slug=loja.slug)

    elif request.method == "POST" and form.is_valid():
        form.save()
        return redirect("painel_loja", slug=loja.slug)

    produtos_base = loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").all()
    leads_base = loja.leads.select_related("produto").all()
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
        avisos.append("Configure o WhatsApp da loja para os clientes conseguirem chamar voce.")
    if total_produtos := produtos_base.count():
        if produtos_sem_foto_extra:
            avisos.append(f"{produtos_sem_foto_extra} produto(s) ainda tem apenas a foto principal.")
    else:
        avisos.append("Cadastre seu primeiro produto para publicar a vitrine.")
    if loja.categorias.count() == 0:
        avisos.append("Crie pelo menos uma categoria para facilitar a navegacao do cliente.")
    if not loja.banner_titulo and not loja.banner_imagem:
        avisos.append("Personalize o banner do catalogo para destacar novidades ou promocoes.")
    if not loja.assinatura_esta_ativa:
        avisos.append("Seu teste expirou ou a assinatura esta inativa. Regularize para manter o catalogo profissional no ar.")
    rascunhos = produtos_base.filter(publicado=False).count()
    if rascunhos:
        avisos.append(f"{rascunhos} produto(s) estao como rascunho e nao aparecem no catalogo.")
    total_leads = leads_base.count()
    pedidos_novos = leads_base.filter(status=Lead.STATUS_NOVO).count()
    pedidos_atendimento = leads_base.filter(status=Lead.STATUS_ATENDIMENTO).count()
    pedidos_concluidos = leads_base.filter(status=Lead.STATUS_CONCLUIDO).count()
    total_cliques = sum(produto.cliques_whatsapp for produto in produtos_base)
    produtos_mais_clicados = produtos_base.order_by("-cliques_whatsapp", "nome")[:5]
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
        f"Oi! Confira o catalogo da {loja.nome}: {catalogo_url}"
    )
    onboarding = [
        {
            "numero": "1",
            "titulo": "Loja criada",
            "descricao": "Seu link publico ja esta pronto.",
            "feito": True,
        },
        {
            "numero": "2",
            "titulo": "Primeiro produto",
            "descricao": "Cadastre foto, preco, tamanho e cor.",
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
        "form": form,
        "categoria_form": categoria_form,
        "produtos": produtos,
        "total_produtos": total_produtos,
        "total_esgotados": produtos_base.filter(esgotado=True).count(),
        "total_categorias": loja.categorias.count(),
        "total_fotos": sum(1 + produto.imagens.count() for produto in produtos_base),
        "total_cliques": total_cliques,
        "total_leads": total_leads,
        "leads_produto": leads_base.filter(origem=Lead.ORIGEM_PRODUTO).count(),
        "leads_sacolinha": leads_base.filter(origem=Lead.ORIGEM_SACOLINHA).count(),
        "leads_recentes": leads_base[:8],
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
        "onboarding": onboarding,
        "onboarding_concluidos": onboarding_concluidos,
        "onboarding_total": len(onboarding),
        "onboarding_percentual": round(onboarding_concluidos / len(onboarding) * 100),
    }
    return render(request, "painel_loja.html", contexto)


def _request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@login_required
def editar_loja(request, slug):
    loja = _loja_do_usuario(request, slug)
    form = LojaForm(request.POST or None, request.FILES or None, instance=loja)

    if request.method == "POST" and form.is_valid():
        loja = form.save()
        return redirect("painel_loja", slug=loja.slug)

    return render(request, "editar_loja.html", {"loja": loja, "form": form})


@login_required
def remover_loja(request, slug):
    loja = _loja_do_usuario(request, slug)

    if request.method == "POST":
        loja.delete()
        return redirect("painel")

    return render(request, "remover_loja.html", {"loja": loja})


@login_required
def assinatura(request, slug):
    loja = _loja_do_usuario(request, slug)

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
    cupom_codigo = (request.POST.get("cupom") or request.GET.get("cupom") or "").strip().upper()
    cupom = Cupom.objects.filter(codigo__iexact=cupom_codigo, ativo=True).first() if cupom_codigo else None
    valor = Pagamento._meta.get_field("valor").default
    valor_final = cupom.aplicar(valor) if cupom else valor

    if request.method == "POST":
        if getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", ""):
            try:
                pagamento = criar_preferencia_premium(request, loja, request.user, cupom=cupom)
                if pagamento.checkout_url:
                    return redirect(pagamento.checkout_url)
            except MercadoPagoError as error:
                return render(
                    request,
                    "checkout_premium.html",
                    {"loja": loja, "erro_pagamento": str(error), "cupom": cupom, "cupom_codigo": cupom_codigo},
                )

        checkout_url = getattr(settings, "VESTLINK_CHECKOUT_URL", "") or getattr(settings, "MODALINK_CHECKOUT_URL", "")
        if checkout_url:
            parametros = urlencode(
                {
                    "loja": loja.slug,
                    "plano": Loja.PLANO_PREMIUM,
                    "email": request.user.email or request.user.username,
                    "cupom": cupom.codigo if cupom else "",
                }
            )
            separador = "&" if "?" in checkout_url else "?"
            return redirect(f"{checkout_url}{separador}{parametros}")

    return render(
        request,
        "checkout_premium.html",
        {
            "loja": loja,
            "cupom": cupom,
            "cupom_codigo": cupom_codigo,
            "valor": valor,
            "valor_final": valor_final,
            "mercado_pago_configurado": bool(getattr(settings, "MERCADO_PAGO_ACCESS_TOKEN", "")),
        },
    )


@login_required
def pagamento_retorno(request, slug, resultado):
    loja = _loja_do_usuario(request, slug)
    external_reference = request.GET.get("external_reference", "")
    payment_id = request.GET.get("payment_id", "")
    status = request.GET.get("status", "")
    pagamento = None
    if external_reference:
        pagamento = Pagamento.objects.filter(loja=loja, external_reference=external_reference).first()
    if not pagamento and payment_id:
        pagamento = Pagamento.objects.filter(loja=loja, payment_id=payment_id).first()

    if pagamento and (resultado == "success" or status == "approved"):
        pagamento.marcar_aprovado(payment_id=payment_id)
    elif pagamento and resultado == "pending":
        pagamento.status = Pagamento.STATUS_PENDENTE
        if payment_id:
            pagamento.payment_id = payment_id
        pagamento.save(update_fields=["status", "payment_id", "atualizado_em"])
    elif pagamento and resultado == "failure":
        pagamento.status = Pagamento.STATUS_RECUSADO
        if payment_id:
            pagamento.payment_id = payment_id
        pagamento.save(update_fields=["status", "payment_id", "atualizado_em"])

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
        pagamento = atualizar_pagamento_mercado_pago(str(payment_id))
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
        return redirect("painel_loja", slug=loja.slug)

    return render(request, "editar_categoria.html", {"loja": loja, "categoria": categoria, "form": form})


@login_required
def remover_categoria(request, slug, categoria_id):
    loja = _loja_do_usuario(request, slug)
    categoria = get_object_or_404(Categoria, id=categoria_id, loja=loja)

    if request.method == "POST":
        categoria.delete()
        return redirect("painel_loja", slug=loja.slug)

    return render(request, "remover_categoria.html", {"loja": loja, "categoria": categoria})


def whatsapp_produto(request, slug, produto_id):
    loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return redirect("catalogo_curto", slug=loja.slug)
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    Produto.objects.filter(id=produto.id).update(cliques_whatsapp=F("cliques_whatsapp") + 1)

    detalhes = []
    tamanho = request.GET.get("tamanho", "").strip()
    cor = request.GET.get("cor", "").strip()
    if tamanho:
        detalhes.append(f"tamanho {tamanho}")
    if cor:
        detalhes.append(f"cor {cor}")

    complemento = f", {', '.join(detalhes)}" if detalhes else ""
    mensagem = f"Ola! Tenho interesse na peca: {produto.nome}{complemento}"
    Lead.objects.create(
        loja=loja,
        produto=produto,
        origem=Lead.ORIGEM_PRODUTO,
        tamanho=tamanho,
        cor=cor,
        status=Lead.STATUS_NOVO,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    return redirect(f"https://wa.me/55{loja.telefone}?text={quote(mensagem)}")


def whatsapp_carrinho(request, slug):
    loja = get_object_or_404(Loja, slug=slug)
    if not loja.assinatura_esta_ativa:
        return redirect("catalogo_curto", slug=loja.slug)
    mensagem = request.GET.get("mensagem", "").strip()
    cliente_nome = request.GET.get("cliente_nome", "").strip()
    cliente_telefone = request.GET.get("cliente_telefone", "").strip()
    if not mensagem:
        mensagem = "Ola! Quero fazer um pedido pelo catalogo."

    Lead.objects.create(
        loja=loja,
        origem=Lead.ORIGEM_SACOLINHA,
        cliente_nome=cliente_nome,
        cliente_telefone=cliente_telefone,
        status=Lead.STATUS_NOVO,
        mensagem=mensagem,
        ip=_request_ip(request),
        navegador=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    return redirect(f"https://wa.me/55{loja.telefone}?text={quote(mensagem)}")


@login_required
def editar_produto(request, slug, produto_id):
    loja = _loja_do_usuario(request, slug)
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    form = ProdutoForm(request.POST or None, request.FILES or None, instance=produto, loja=loja)

    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("painel_loja", slug=loja.slug)

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
        produto.delete()
        return redirect("painel_loja", slug=loja.slug)

    contexto = {
        "loja": loja,
        "produto": produto,
    }
    return render(request, "remover_produto.html", contexto)
