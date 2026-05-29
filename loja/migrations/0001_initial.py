# Generated for the catalog SaaS MVP.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Loja",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120)),
                ("slug", models.SlugField(unique=True)),
                ("telefone", models.CharField(help_text="Somente números com DDD.", max_length=20)),
                ("descricao", models.CharField(blank=True, max_length=160)),
                ("instagram", models.CharField(blank=True, max_length=80)),
                ("cor_principal", models.CharField(default="#111111", max_length=7)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Loja",
                "verbose_name_plural": "Lojas",
                "ordering": ["nome"],
            },
        ),
        migrations.CreateModel(
            name="Categoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=80)),
                ("ordem", models.PositiveIntegerField(default=0)),
                ("loja", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="categorias", to="loja.loja")),
            ],
            options={
                "verbose_name": "Categoria",
                "verbose_name_plural": "Categorias",
                "ordering": ["ordem", "nome"],
                "unique_together": {("loja", "nome")},
            },
        ),
        migrations.CreateModel(
            name="Produto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120)),
                ("descricao", models.TextField(blank=True)),
                ("preco", models.DecimalField(decimal_places=2, max_digits=8)),
                ("imagem", models.ImageField(upload_to="produtos/")),
                ("tamanhos", models.CharField(blank=True, help_text="Ex.: P, M, G, GG", max_length=80)),
                ("cores", models.CharField(blank=True, help_text="Ex.: Preto, Branco", max_length=120)),
                ("esgotado", models.BooleanField(default=False)),
                ("destaque", models.BooleanField(default=False)),
                ("promocao", models.BooleanField(default=False)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("categoria", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="produtos", to="loja.categoria")),
                ("loja", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="produtos", to="loja.loja")),
            ],
            options={
                "verbose_name": "Produto",
                "verbose_name_plural": "Produtos",
                "ordering": ["esgotado", "-destaque", "-criado_em"],
            },
        ),
    ]
