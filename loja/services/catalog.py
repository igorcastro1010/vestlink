from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from loja.models import Vendedor, Produto, Categoria, Loja


def obter_vendedor_por_codigo(loja, codigo):
    """
    Busca um vendedor ativo na loja pelo código fornecido.
    """
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return None
    return loja.vendedores.filter(codigo__iexact=codigo, ativo=True).first()


def obter_contexto_catalogo(request, loja, categoria_id, busca, filtro, produto_id, vendedor_codigo, ordenacao, page):
    """
    Filtra, ordena e pagina os produtos da loja, retornando o contexto pronto para a vitrine.
    """
    vendedor_ref = obter_vendedor_por_codigo(loja, vendedor_codigo)

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
    page_obj = paginator.get_page(page)

    cache_version = cache.get_or_set(f"loja_cache_version_{loja.id}", 1)

    return {
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


def obter_contexto_produto_detalhe(loja, produto_id, vendedor_codigo):
    """
    Retorna o contexto necessário para exibir os detalhes de um produto.
    """
    produto = get_object_or_404(
        loja.produtos.select_related("categoria").prefetch_related("imagens", "variacoes").filter(publicado=True),
        id=produto_id,
    )
    vendedor_ref = obter_vendedor_por_codigo(loja, vendedor_codigo)
    return {
        "loja": loja,
        "produto": produto,
        "categorias": loja.categorias.all(),
        "vendedor_ref": vendedor_ref,
        "vendedor_codigo": vendedor_ref.codigo if vendedor_ref else "",
    }
