from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Categoria, Loja, Produto, ProdutoImagem, ProdutoVariacao


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return [single_file_clean(data, initial)] if data else []


class LojaForm(forms.ModelForm):
    class Meta:
        model = Loja
        fields = [
            "nome",
            "slug",
            "telefone",
            "descricao",
            "instagram",
            "dominio_personalizado",
            "cor_principal",
            "tema",
            "logo",
            "banner_titulo",
            "banner_texto",
            "banner_imagem",
        ]
        labels = {
            "slug": "Link da loja",
            "telefone": "WhatsApp",
            "descricao": "Descricao",
            "instagram": "Instagram",
            "dominio_personalizado": "Dominio personalizado",
            "cor_principal": "Cor principal",
            "tema": "Tema da loja",
            "logo": "Logo da loja",
            "banner_titulo": "Titulo do banner",
            "banner_texto": "Texto do banner",
            "banner_imagem": "Imagem do banner",
        }
        widgets = {
            "cor_principal": forms.TextInput(attrs={"type": "color"}),
            "banner_titulo": forms.TextInput(attrs={"placeholder": "Ex.: Novidades da semana"}),
            "banner_texto": forms.TextInput(attrs={"placeholder": "Ex.: Pecas novas com pronta entrega"}),
            "dominio_personalizado": forms.TextInput(attrs={"placeholder": "catalogo.sualoja.com.br"}),
        }


class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nome", "ordem"]
        labels = {
            "nome": "Nome da categoria",
            "ordem": "Ordem",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Vestidos"}),
            "ordem": forms.NumberInput(attrs={"min": 0}),
        }


class CadastroForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=False)
    loja_nome = forms.CharField(label="Nome da loja", required=False)
    loja_slug = forms.SlugField(label="Link da loja", required=False)
    loja_telefone = forms.CharField(label="WhatsApp da loja", required=False)
    loja_instagram = forms.CharField(label="Instagram", required=False)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password1",
            "password2",
            "loja_nome",
            "loja_slug",
            "loja_telefone",
            "loja_instagram",
        ]
        labels = {
            "username": "Usuario",
            "password1": "Senha",
            "password2": "Confirmar senha",
            "loja_nome": "Nome da loja",
            "loja_slug": "Link da loja",
            "loja_telefone": "WhatsApp da loja",
            "loja_instagram": "Instagram",
        }
        widgets = {
            "loja_nome": forms.TextInput(attrs={"placeholder": "Ex.: Bela Meunier"}),
            "loja_slug": forms.TextInput(attrs={"placeholder": "bela-meunier"}),
            "loja_telefone": forms.TextInput(attrs={"placeholder": "85999999999"}),
            "loja_instagram": forms.TextInput(attrs={"placeholder": "sualoja"}),
        }


class ProdutoForm(forms.ModelForm):
    nova_categoria = forms.CharField(
        label="Nova categoria",
        required=False,
        help_text="Preencha se quiser criar uma categoria nova.",
    )
    fotos_adicionais = MultipleFileField(
        label="Fotos adicionais",
        required=False,
        help_text="Voce pode selecionar varias fotos de uma vez.",
    )
    variacoes_estoque = forms.CharField(
        label="Estoque por variacao",
        required=False,
        help_text="Uma por linha. Ex.: Preto, P, 3",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Preto, P, 3\nPreto, M, 0\nAzul, G, 2"}),
    )

    class Meta:
        model = Produto
        fields = [
            "categoria",
            "nova_categoria",
            "nome",
            "descricao",
            "preco",
            "preco_antigo",
            "imagem",
            "fotos_adicionais",
            "tamanhos",
            "tamanhos_esgotados",
            "cores",
            "cores_esgotadas",
            "variacoes_estoque",
            "esgotado",
            "destaque",
            "promocao",
            "publicado",
            "ordem",
        ]
        labels = {
            "categoria": "Categoria existente",
            "nome": "Nome do produto",
            "descricao": "Descricao",
            "preco": "Preco",
            "preco_antigo": "Preco antigo",
            "imagem": "Foto principal",
            "fotos_adicionais": "Fotos adicionais",
            "tamanhos": "Tamanhos",
            "tamanhos_esgotados": "Tamanhos esgotados",
            "cores": "Cores",
            "cores_esgotadas": "Cores esgotadas",
            "esgotado": "Esgotado",
            "destaque": "Novo",
            "promocao": "Promocao",
            "publicado": "Publicado no catalogo",
            "ordem": "Ordem no catalogo",
        }
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "tamanhos": forms.TextInput(attrs={"placeholder": "P, M, G"}),
            "tamanhos_esgotados": forms.TextInput(attrs={"placeholder": "M, GG"}),
            "cores": forms.TextInput(attrs={"placeholder": "Preto, Branco"}),
            "cores_esgotadas": forms.TextInput(attrs={"placeholder": "Azul, Cinza"}),
            "esgotado": forms.CheckboxInput(attrs={"class": "status-checkbox"}),
            "destaque": forms.CheckboxInput(attrs={"class": "status-checkbox"}),
            "promocao": forms.CheckboxInput(attrs={"class": "status-checkbox"}),
            "publicado": forms.CheckboxInput(attrs={"class": "status-checkbox"}),
            "ordem": forms.NumberInput(attrs={"min": 0, "placeholder": "0"}),
        }

    def __init__(self, *args, loja=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loja = loja
        self.fields["categoria"].queryset = Categoria.objects.filter(loja=loja)
        self.fields["categoria"].required = False
        self.fields["ordem"].required = False
        self.fields["preco_antigo"].required = False
        if self.instance.pk is None:
            self.fields["publicado"].initial = True
        else:
            self.fields["variacoes_estoque"].initial = "\n".join(
                f"{variacao.cor}, {variacao.tamanho}, {variacao.estoque}"
                for variacao in self.instance.variacoes.all()
            )

    def _variacoes_informadas(self):
        linhas = self.cleaned_data.get("variacoes_estoque", "").splitlines()
        variacoes = []
        for linha in linhas:
            partes = [parte.strip() for parte in linha.replace("/", ",").replace(";", ",").split(",") if parte.strip()]
            if len(partes) < 2:
                continue
            cor = partes[0]
            tamanho = partes[1]
            try:
                estoque = int(partes[2]) if len(partes) > 2 else 0
            except ValueError:
                estoque = 0
            variacoes.append({
                "cor": cor,
                "tamanho": tamanho,
                "estoque": max(estoque, 0),
            })
        return variacoes

    def save(self, commit=True):
        produto = super().save(commit=False)
        produto.loja = self.loja

        nova_categoria = self.cleaned_data.get("nova_categoria", "").strip()
        if nova_categoria:
            categoria, _ = Categoria.objects.get_or_create(
                loja=self.loja,
                nome=nova_categoria,
                defaults={"ordem": self.loja.categorias.count() + 1},
            )
            produto.categoria = categoria

        if commit:
            produto.save()
            produto.variacoes.all().delete()
            for variacao in self._variacoes_informadas():
                ProdutoVariacao.objects.create(
                    produto=produto,
                    cor=variacao["cor"],
                    tamanho=variacao["tamanho"],
                    estoque=variacao["estoque"],
                    disponivel=variacao["estoque"] > 0,
                )
            ordem_inicial = produto.imagens.count() + 1
            for ordem, imagem in enumerate(self.cleaned_data.get("fotos_adicionais", []), start=ordem_inicial):
                ProdutoImagem.objects.create(produto=produto, imagem=imagem, ordem=ordem)
            self.save_m2m()
        return produto
