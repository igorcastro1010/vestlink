from django.contrib import admin

from .models import Categoria, Loja, Produto, ProdutoImagem


class CategoriaInline(admin.TabularInline):
    model = Categoria
    extra = 1


class ProdutoImagemInline(admin.TabularInline):
    model = ProdutoImagem
    extra = 1


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "telefone", "criada_em")
    prepopulated_fields = {"slug": ("nome",)}
    search_fields = ("nome", "slug", "telefone")
    inlines = [CategoriaInline]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "loja", "ordem")
    list_filter = ("loja",)
    search_fields = ("nome",)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "loja", "categoria", "preco", "esgotado", "destaque", "promocao")
    list_filter = ("loja", "categoria", "esgotado", "destaque", "promocao")
    search_fields = ("nome", "descricao")
    list_editable = ("preco", "esgotado", "destaque", "promocao")
    inlines = [ProdutoImagemInline]
