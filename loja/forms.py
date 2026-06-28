from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.text import slugify

from .models import Categoria, Loja, Produto, ProdutoImagem, ProdutoVariacao, Vendedor
from .validators import limpar_telefone, validar_whatsapp


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
            "descricao": "Descrição",
            "instagram": "Instagram",
            "cor_principal": "Cor principal",
            "tema": "Tema da loja",
            "logo": "Logo da loja",
            "banner_titulo": "Título do banner",
            "banner_texto": "Texto do banner",
            "banner_imagem": "Imagem do banner",
        }
        widgets = {
            "cor_principal": forms.TextInput(attrs={"type": "color"}),
            "banner_titulo": forms.TextInput(attrs={"placeholder": "Ex.: Novidades da semana"}),
            "banner_texto": forms.TextInput(attrs={"placeholder": "Ex.: Peças novas com pronta entrega"}),
        }

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone", "").strip()
        validar_whatsapp(telefone)
        return limpar_telefone(telefone)


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


class VendedorForm(forms.ModelForm):
    username = forms.CharField(
        label="Usuário (login)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: maria_vendas"}),
    )
    password = forms.CharField(
        label="Senha",
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Defina uma senha"}),
    )

    class Meta:
        model = Vendedor
        fields = ["nome", "codigo", "telefone", "ativo"]
        labels = {
            "nome": "Nome do vendedor",
            "codigo": "Código do link",
            "telefone": "WhatsApp do vendedor",
            "ativo": "Ativo",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Maria"}),
            "codigo": forms.TextInput(attrs={"placeholder": "maria"}),
            "telefone": forms.TextInput(attrs={"placeholder": "85999999999"}),
        }

    def __init__(self, *args, loja=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loja = loja
        self.fields["codigo"].required = False

    def clean_telefone(self):
        telefone = self.cleaned_data.get("telefone", "").strip()
        if not telefone:
            return ""
        validar_whatsapp(telefone)
        return limpar_telefone(telefone)

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if username:
            if User.objects.filter(username__iexact=username).exists():
                raise forms.ValidationError("Este nome de usuário já está em uso.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if username and not password:
            self.add_error("password", "Defina uma senha para o usuário.")
        if password and not username:
            self.add_error("username", "Defina o usuário para a senha informada.")
        return cleaned_data

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "").strip().lower()
        if not codigo:
            codigo = slugify(self.cleaned_data.get("nome", ""))
        if not codigo:
            raise forms.ValidationError("Informe um nome ou código para gerar o link.")
        qs = Vendedor.objects.filter(loja=self.loja, codigo__iexact=codigo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Esse código já está em uso nesta loja.")
        return codigo

    def save(self, commit=True):
        vendedor = super().save(commit=False)
        vendedor.loja = self.loja

        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            user = User.objects.create_user(username=username, password=password)
            vendedor.usuario = user

        if commit:
            vendedor.save()
            self.save_m2m()
        return vendedor


class CadastroForm(UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    loja_nome = forms.CharField(label="Nome da loja", required=True)
    loja_slug = forms.SlugField(label="Link da loja", required=True)
    loja_telefone = forms.CharField(label="WhatsApp da loja", required=True)
    loja_instagram = forms.CharField(label="Instagram", required=False)
    aceite_termos = forms.BooleanField(
        label="Li e aceito os Termos de Uso e a Política de Privacidade.",
        required=True,
        error_messages={"required": "Você precisa aceitar os Termos de Uso e a Política de Privacidade para criar a conta."},
    )

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
            "aceite_termos",
        ]
        labels = {
            "username": "Usuário",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({
            "data-password-primary": "",
            "aria-describedby": "password-requirements",
        })
        self.fields["password2"].widget.attrs.update({
            "data-password-confirm": "",
            "aria-describedby": "password-requirements",
        })

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ja existe uma conta com este e-mail.")
        return email

    def clean_loja_slug(self):
        slug = self.cleaned_data["loja_slug"].strip().lower()
        if Loja.objects.filter(slug__iexact=slug).exists():
            raise forms.ValidationError("Esse link de loja ja esta em uso. Tente outro, como salombrashop2.")
        return slug

    def clean_loja_telefone(self):
        telefone = self.cleaned_data.get("loja_telefone", "").strip()
        validar_whatsapp(telefone)
        return limpar_telefone(telefone)


class ProdutoForm(forms.ModelForm):
    nova_categoria = forms.CharField(
        label="Nova categoria",
        required=False,
        help_text="Preencha se quiser criar uma categoria nova.",
    )
    fotos_adicionais = MultipleFileField(
        label="Fotos adicionais",
        required=False,
        help_text="Você pode selecionar várias fotos de uma vez.",
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
            "descricao": "Descrição",
            "preco": "Preço",
            "preco_antigo": "Preço antigo",
            "imagem": "Foto principal",
            "fotos_adicionais": "Fotos adicionais",
            "tamanhos": "Tamanhos",
            "tamanhos_esgotados": "Tamanhos esgotados",
            "cores": "Cores",
            "cores_esgotadas": "Cores esgotadas",
            "esgotado": "Esgotado",
            "destaque": "Novo",
            "promocao": "Promoção",
            "publicado": "Publicado no catálogo",
            "ordem": "Ordem no catálogo",
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

    def clean_ordem(self):
        ordem = self.cleaned_data.get("ordem")
        return ordem if ordem is not None else 0

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
