import json
import logging
import qrcode
from io import BytesIO
from urllib.parse import quote
from django.conf import settings
from django.urls import reverse
from django.db.models import Count, Q, Case, When, Value, BooleanField
from django.db.models.functions import ExtractHour, TruncDate

from loja.models import Produto, Lead, Vendedor, Categoria, Loja, ProdutoVariacao

logger = logging.getLogger(__name__)


def gerar_qrcode(loja, request):
    """
    Gera o QR Code da loja em formato PNG (bytes).
    """
    catalogo_url = request.build_absolute_uri(reverse("catalogo_curto", kwargs={"slug": loja.slug}))
    if loja.dominio_limpo:
        catalogo_url = f"https://{loja.dominio_limpo}/"

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(catalogo_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="#151129", back_color="#ffffff")
    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    return image_buffer.getvalue()


def obter_leads_novos_painel(leads_base):
    return leads_base.filter(
        status__in=[Lead.STATUS_NOVO, Lead.STATUS_ATENDIMENTO],
    ).order_by("-criado_em")[:5]


def obter_contexto_dashboard(request, loja, usuario_logado, vendedor_logado, busca, status, categoria_id, leads_filtrados):
    """
    Calcula KPIs, alertas, métricas de onboarding e dados de gráficos para o dashboard da loja.
    Retorna o dicionário de contexto pronto para renderização.
    """
    produtos_base = loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").annotate(
        total_variacoes=Count("variacoes", distinct=True),
        variacoes_com_estoque=Count(
            "variacoes",
            filter=Q(variacoes__estoque__gt=0, variacoes__disponivel=True),
            distinct=True,
        ),
        variacoes_estoque_baixo=Count(
            "variacoes",
            filter=Q(variacoes__estoque__gte=1, variacoes__estoque__lte=3, variacoes__disponivel=True),
            distinct=True,
        ),
    )

    leads_base = loja.leads.select_related("produto", "vendedor").all()
    if vendedor_logado:
        leads_base = leads_base.filter(vendedor=vendedor_logado)

    vendedores_base = loja.vendedores.all()
    produtos = produtos_base

    if busca:
        produtos = produtos.filter(nome__icontains=busca)
    if categoria_id:
        produtos = produtos.filter(categoria_id=categoria_id)
    if status in {"esgotados", "esgotado"}:
        produtos = produtos.filter(Q(esgotado=True) | Q(total_variacoes__gt=0, variacoes_com_estoque=0))
    elif status in {"ativos", "disponivel"}:
        produtos = produtos.filter(publicado=True, esgotado=False).filter(
            Q(total_variacoes=0) | Q(variacoes_com_estoque__gt=0)
        )
    elif status in {"inativos", "rascunho"}:
        produtos = produtos.filter(publicado=False)
    elif status == "estoque_baixo":
        produtos = produtos.filter(variacoes_estoque_baixo__gt=0)

    total_produtos_filtrados = produtos.count()

    produtos_sem_foto_extra = produtos_base.filter(imagens__isnull=True).count()
    avisos = []
    if not loja.telefone:
        avisos.append("Configure o WhatsApp da loja para os clientes conseguirem chamar você.")
    
    total_produtos = produtos_base.count()
    if total_produtos:
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
    leads_novos_painel = list(obter_leads_novos_painel(leads_base))

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
            "descricao": "Adicione a primeira peça com foto, preço, tamanho e cor.",
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
    
    variacoes_criticas = ProdutoVariacao.objects.filter(
        produto__loja=loja
    ).filter(
        Q(estoque__lte=3) | Q(disponivel=False)
    ).annotate(
        is_esgotado=Case(
            When(Q(estoque=0) | Q(disponivel=False), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    ).select_related('produto').order_by(
        '-is_esgotado',
        'estoque',
        'produto__nome',
        'cor',
        'tamanho',
    )[:5]
    
    return {
        "loja": loja,
        "is_owner": usuario_logado == loja.usuario,
        "produtos": produtos,
        "total_produtos": total_produtos,
        "total_produtos_filtrados": total_produtos_filtrados,
        "total_esgotados": produtos_base.filter(esgotado=True).count(),
        "total_categorias": loja.categorias.count(),
        "total_fotos": sum(1 + produto.imagens.count() for produto in produtos_base),
        "total_cliques": total_cliques,
        "total_leads_global": total_leads_global,
        "pedidos_novos_global": pedidos_novos_global,
        "leads_novos_painel": leads_novos_painel,
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
        "variacoes_criticas": list(variacoes_criticas),
    }
