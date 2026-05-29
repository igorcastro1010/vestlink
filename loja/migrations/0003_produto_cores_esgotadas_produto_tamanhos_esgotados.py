from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0002_produtoimagem"),
    ]

    operations = [
        migrations.AddField(
            model_name="produto",
            name="cores_esgotadas",
            field=models.CharField(blank=True, help_text="Ex.: Azul, Cinza. Deixe vazio se todas as cores estiverem disponiveis.", max_length=120),
        ),
        migrations.AddField(
            model_name="produto",
            name="tamanhos_esgotados",
            field=models.CharField(blank=True, help_text="Ex.: M, GG. Deixe vazio se todos os tamanhos estiverem disponiveis.", max_length=80),
        ),
    ]
