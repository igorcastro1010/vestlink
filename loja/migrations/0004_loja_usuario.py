from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("loja", "0003_produto_cores_esgotadas_produto_tamanhos_esgotados"),
    ]

    operations = [
        migrations.AddField(
            model_name="loja",
            name="usuario",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="lojas", to=settings.AUTH_USER_MODEL),
        ),
    ]
