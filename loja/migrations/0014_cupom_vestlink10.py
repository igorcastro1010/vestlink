from django.db import migrations


def criar_cupom_vestlink(apps, schema_editor):
    Cupom = apps.get_model("loja", "Cupom")
    Cupom.objects.update_or_create(
        codigo="VESTLINK10",
        defaults={"percentual_desconto": 10, "ativo": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("loja", "0013_cupom_lead_observacao_loja_dominio_personalizado_and_more"),
    ]

    operations = [
        migrations.RunPython(criar_cupom_vestlink, migrations.RunPython.noop),
    ]
