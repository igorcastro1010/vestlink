import logging
from django.db.models import F
from django.utils.text import slugify
from urllib.parse import quote

from loja.models import Lead, Vendedor, Produto
from loja.validators import limpar_telefone

logger = logging.getLogger(__name__)


def _request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _vendedor_por_codigo(loja, codigo):
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return None
    return loja.vendedores.filter(codigo__iexact=codigo, ativo=True).first()


def processar_whatsapp_produto(request, loja, produto, tamanho, cor, cliente_nome, vendedor_codigo):
    """
    Registra o clique de WhatsApp no produto, cria o Lead e retorna o telefone de destino e a mensagem formatada.
    """
    Produto.objects.filter(id=produto.id).update(cliques_whatsapp=F("cliques_whatsapp") + 1)

    detalhes = []
    tamanho = (tamanho or "").strip()
    cor = (cor or "").strip()
    cliente_nome = (cliente_nome or "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, vendedor_codigo)
    
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
            
    return destino, mensagem


def processar_whatsapp_carrinho(request, loja, mensagem, cliente_nome, cliente_telefone, tipo_entrega, endereco_completo, vendedor_codigo):
    """
    Registra o Lead da sacolinha/carrinho e retorna o telefone de destino e a mensagem formatada.
    """
    mensagem = (mensagem or "").strip()
    cliente_nome = (cliente_nome or "").strip()
    cliente_telefone = (cliente_telefone or "").strip()
    tipo_entrega = (tipo_entrega or "retirada").strip()
    endereco_completo = (endereco_completo or "").strip()
    vendedor_ref = _vendedor_por_codigo(loja, vendedor_codigo)

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
            
    return destino, mensagem
