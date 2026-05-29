from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProdutoImagem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("imagem", models.ImageField(upload_to="produtos/galeria/")),
                ("ordem", models.PositiveIntegerField(default=0)),
                ("criada_em", models.DateTimeField(auto_now_add=True)),
                ("produto", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="imagens", to="loja.produto")),
            ],
            options={
                "verbose_name": "Imagem do produto",
                "verbose_name_plural": "Imagens do produto",
                "ordering": ["ordem", "id"],
            },
        ),
    ]
