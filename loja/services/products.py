from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied
from loja.models import Produto


def cadastrar_produto(loja, form):
    """
    Salva o formulário de cadastro de um novo produto se for válido.
    Retorna True se salvo com sucesso, False caso contrário.
    """
    if form.is_valid():
        form.save()
        return True
    return False


def editar_produto(loja, produto, form):
    """
    Salva o formulário de edição de um produto se for válido.
    Retorna True se salvo com sucesso, False caso contrário.
    """
    if form.is_valid():
        form.save()
        return True
    return False


def publicar_produto(loja, produto_id):
    """
    Marca um produto como publicado.
    """
    produto = get_object_or_404(Produto, id=produto_id, loja=loja)
    produto.publicado = True
    produto.save(update_fields=["publicado"])
    return produto


def remover_produto(loja, produto, usuario):
    """
    Remove um produto da loja. Apenas o proprietário da loja tem essa permissão.
    """
    if usuario != loja.usuario:
        raise PermissionDenied("Apenas o proprietário da loja pode excluir produtos.")
    produto.delete()
