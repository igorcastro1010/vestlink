from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


def trial_padrao():
    return timezone.now() + timedelta(days=7)


class Loja(models.Model):
    PLANO_PREMIUM = "premium"
    PLANOS = [
        (PLANO_PREMIUM, "Premium"),
    ]
    ASSINATURA_TRIAL = "trial"
    ASSINATURA_ATIVA = "ativa"
    ASSINATURA_VENCIDA = "vencida"
    ASSINATURA_CANCELADA = "cancelada"
    ASSINATURAS = [
        (ASSINATURA_TRIAL, "Teste gratis"),
        (ASSINATURA_ATIVA, "Ativa"),
        (ASSINATURA_VENCIDA, "Vencida"),
        (ASSINATURA_CANCELADA, "Cancelada"),
    ]
    TEMA_ELEGANTE = "elegante"
    TEMA_MINIMALISTA = "minimalista"
    TEMA_BOUTIQUE = "boutique"
    TEMA_STREETWEAR = "streetwear"
    TEMAS = [
        (TEMA_ELEGANTE, "Elegante"),
        (TEMA_MINIMALISTA, "Minimalista"),
        (TEMA_BOUTIQUE, "Boutique"),
        (TEMA_STREETWEAR, "Streetwear"),
    ]
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lojas",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    telefone = models.CharField(max_length=20, help_text="Somente números com DDD.")
    descricao = models.CharField(max_length=160, blank=True)
    instagram = models.CharField(max_length=80, blank=True)
    dominio_personalizado = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ex.: catalogo.sualoja.com.br",
    )
    cor_principal = models.CharField(max_length=7, default="#111111")
    tema = models.CharField(max_length=20, choices=TEMAS, default=TEMA_ELEGANTE)
    logo = models.ImageField(upload_to="logos/", blank=True)
    banner_titulo = models.CharField(max_length=120, blank=True)
    banner_texto = models.CharField(max_length=220, blank=True)
    banner_imagem = models.ImageField(upload_to="banners/", blank=True)
    plano = models.CharField(max_length=20, choices=PLANOS, default=PLANO_PREMIUM)
    assinatura_status = models.CharField(max_length=20, choices=ASSINATURAS, default=ASSINATURA_TRIAL)
    trial_termina_em = models.DateTimeField(default=trial_padrao, null=True, blank=True)
    assinatura_ativa_em = models.DateTimeField(null=True, blank=True)
    assinatura_cancelada_em = models.DateTimeField(null=True, blank=True)
    pagamento_referencia = models.CharField(max_length=120, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"

    def __str__(self):
        return self.nome

    def get_absolute_url(self):
        return reverse("catalogo", kwargs={"slug": self.slug})

    def get_short_url(self):
        return reverse("catalogo_curto", kwargs={"slug": self.slug})

    @property
    def is_premium(self):
        return self.plano == self.PLANO_PREMIUM

    @property
    def trial_ativo(self):
        return self.assinatura_status == self.ASSINATURA_TRIAL and (
            self.trial_termina_em is None or self.trial_termina_em >= timezone.now()
        )

    @property
    def assinatura_esta_ativa(self):
        return self.assinatura_status == self.ASSINATURA_ATIVA or self.trial_ativo

    @property
    def assinatura_status_label(self):
        if self.assinatura_status == self.ASSINATURA_TRIAL and not self.trial_ativo:
            return "Teste expirado"
        return dict(self.ASSINATURAS).get(self.assinatura_status, "Premium")

    @property
    def trial_dias_restantes(self):
        if not self.trial_termina_em:
            return 0
        segundos = (self.trial_termina_em - timezone.now()).total_seconds()
        if segundos <= 0:
            return 0
        return int((segundos + 86399) // 86400)

    @property
    def dominio_limpo(self):
        return self.dominio_personalizado.replace("https://", "").replace("http://", "").strip().strip("/")


class Categoria(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, related_name="categorias")
    nome = models.CharField(max_length=80)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "nome"]
        unique_together = ["loja", "nome"]
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.nome


class Produto(models.Model):
    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, related_name="produtos")
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        related_name="produtos",
        null=True,
        blank=True,
    )
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    preco_antigo = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    imagem = models.ImageField(upload_to="produtos/")
    tamanhos = models.CharField(max_length=80, blank=True, help_text="Ex.: P, M, G, GG")
    cores = models.CharField(max_length=120, blank=True, help_text="Ex.: Preto, Branco")
    tamanhos_esgotados = models.CharField(
        max_length=80,
        blank=True,
        help_text="Ex.: M, GG. Deixe vazio se todos os tamanhos estiverem disponiveis.",
    )
    cores_esgotadas = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ex.: Azul, Cinza. Deixe vazio se todas as cores estiverem disponiveis.",
    )
    esgotado = models.BooleanField(default=False)
    destaque = models.BooleanField(default=False)
    promocao = models.BooleanField(default=False)
    publicado = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    cliques_whatsapp = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["esgotado", "ordem", "-destaque", "-criado_em"]
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.nome

    @property
    def tamanhos_lista(self):
        return [item.strip() for item in self.tamanhos.split(",") if item.strip()]

    @property
    def cores_lista(self):
        return [item.strip() for item in self.cores.split(",") if item.strip()]

    @property
    def tamanhos_esgotados_lista(self):
        return [item.strip().lower() for item in self.tamanhos_esgotados.split(",") if item.strip()]

    @property
    def cores_esgotadas_lista(self):
        return [item.strip().lower() for item in self.cores_esgotadas.split(",") if item.strip()]

    @property
    def whatsapp_texto(self):
        return f"Ola! Tenho interesse na peca: {self.nome}"


class ProdutoImagem(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="imagens")
    imagem = models.ImageField(upload_to="produtos/galeria/")
    ordem = models.PositiveIntegerField(default=0)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Imagem do produto"
        verbose_name_plural = "Imagens do produto"

    def __str__(self):
        return f"Imagem de {self.produto.nome}"


class ProdutoVariacao(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="variacoes")
    cor = models.CharField(max_length=80)
    tamanho = models.CharField(max_length=40)
    estoque = models.PositiveIntegerField(default=0)
    disponivel = models.BooleanField(default=True)

    class Meta:
        ordering = ["cor", "tamanho"]
        unique_together = ["produto", "cor", "tamanho"]
        verbose_name = "Variacao do produto"
        verbose_name_plural = "Variacoes do produto"

    def __str__(self):
        return f"{self.produto.nome} - {self.cor} / {self.tamanho}"


class Lead(models.Model):
    ORIGEM_PRODUTO = "produto"
    ORIGEM_SACOLINHA = "sacolinha"
    ORIGENS = [
        (ORIGEM_PRODUTO, "Produto"),
        (ORIGEM_SACOLINHA, "Sacolinha"),
    ]
    STATUS_NOVO = "novo"
    STATUS_ATENDIMENTO = "atendimento"
    STATUS_CONCLUIDO = "concluido"
    STATUS_CHOICES = [
        (STATUS_NOVO, "Novo"),
        (STATUS_ATENDIMENTO, "Em atendimento"),
        (STATUS_CONCLUIDO, "Concluido"),
    ]

    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, related_name="leads")
    produto = models.ForeignKey(
        Produto,
        on_delete=models.SET_NULL,
        related_name="leads",
        null=True,
        blank=True,
    )
    origem = models.CharField(max_length=20, choices=ORIGENS, default=ORIGEM_PRODUTO)
    tamanho = models.CharField(max_length=40, blank=True)
    cor = models.CharField(max_length=80, blank=True)
    cliente_nome = models.CharField(max_length=120, blank=True)
    cliente_telefone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NOVO)
    mensagem = models.TextField(blank=True)
    observacao = models.TextField(blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    navegador = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self):
        if self.produto:
            return f"Lead - {self.produto.nome}"
        return f"Lead - {self.loja.nome}"


def pagamento_referencia_padrao():
    return f"vestlink-{uuid4().hex}"


class Cupom(models.Model):
    codigo = models.CharField(max_length=40, unique=True)
    percentual_desconto = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Cupom"
        verbose_name_plural = "Cupons"

    def __str__(self):
        return self.codigo

    def aplicar(self, valor):
        if not self.ativo or self.percentual_desconto <= 0:
            return valor
        desconto = valor * Decimal(self.percentual_desconto) / Decimal("100")
        return max(valor - desconto, Decimal("0.00")).quantize(Decimal("0.01"))


class Pagamento(models.Model):
    PROVEDOR_MERCADO_PAGO = "mercado_pago"
    PROVEDORES = [
        (PROVEDOR_MERCADO_PAGO, "Mercado Pago"),
    ]
    STATUS_CRIADO = "criado"
    STATUS_PENDENTE = "pendente"
    STATUS_APROVADO = "aprovado"
    STATUS_RECUSADO = "recusado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_CRIADO, "Criado"),
        (STATUS_PENDENTE, "Pendente"),
        (STATUS_APROVADO, "Aprovado"),
        (STATUS_RECUSADO, "Recusado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    loja = models.ForeignKey(Loja, on_delete=models.CASCADE, related_name="pagamentos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    cupom = models.ForeignKey(Cupom, on_delete=models.SET_NULL, null=True, blank=True)
    provedor = models.CharField(max_length=30, choices=PROVEDORES, default=PROVEDOR_MERCADO_PAGO)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CRIADO)
    valor = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("39.90"))
    desconto = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    valor_final = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("39.90"))
    external_reference = models.CharField(max_length=80, unique=True, default=pagamento_referencia_padrao)
    preference_id = models.CharField(max_length=120, blank=True)
    init_point = models.URLField(blank=True)
    sandbox_init_point = models.URLField(blank=True)
    payment_id = models.CharField(max_length=120, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self):
        return f"{self.loja.nome} - {self.get_status_display()} - R$ {self.valor}"

    @property
    def checkout_url(self):
        if settings.MERCADO_PAGO_USE_SANDBOX and self.sandbox_init_point:
            return self.sandbox_init_point
        return self.init_point or self.sandbox_init_point

    def marcar_aprovado(self, payment_id=""):
        self.status = self.STATUS_APROVADO
        if payment_id:
            self.payment_id = payment_id
        self.save(update_fields=["status", "payment_id", "atualizado_em"])
        self.loja.plano = Loja.PLANO_PREMIUM
        self.loja.assinatura_status = Loja.ASSINATURA_ATIVA
        self.loja.assinatura_ativa_em = timezone.now()
        self.loja.assinatura_cancelada_em = None
        self.loja.pagamento_referencia = self.external_reference
        self.loja.save(
            update_fields=[
                "plano",
                "assinatura_status",
                "assinatura_ativa_em",
                "assinatura_cancelada_em",
                "pagamento_referencia",
            ]
        )
