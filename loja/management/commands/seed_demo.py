from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw

from loja.models import Categoria, Loja, Produto


class Command(BaseCommand):
    help = "Cria uma loja e produtos de demonstração para testar o catálogo."

    def handle(self, *args, **options):
        loja, _ = Loja.objects.update_or_create(
            slug="bela-meunier",
            defaults={
                "nome": "Bela Meunier",
                "telefone": "85999999999",
                "descricao": "Novidades selecionadas para comprar pelo WhatsApp.",
                "instagram": "belameunier",
                "cor_principal": "#191716",
            },
        )

        categorias = {}
        for ordem, nome in enumerate(["Blusas", "Vestidos", "Calças"], start=1):
            categorias[nome], _ = Categoria.objects.update_or_create(
                loja=loja,
                nome=nome,
                defaults={"ordem": ordem},
            )

        produtos = [
            ("Blusa Canelada", "Blusas", "79.90", "P, M, G", "Preto, Off white", True, False, "#d8b89f"),
            ("Vestido Midi", "Vestidos", "149.90", "P, M", "Verde oliva", True, True, "#7c8f74"),
            ("Calça Alfaiataria", "Calças", "129.90", "M, G, GG", "Areia", False, False, "#b7a58e"),
            ("Cropped Linho", "Blusas", "69.90", "P, M", "Azul claro", False, True, "#9bbbd0"),
        ]

        for nome, categoria, preco, tamanhos, cores, destaque, promocao, cor in produtos:
            produto, created = Produto.objects.update_or_create(
                loja=loja,
                nome=nome,
                defaults={
                    "categoria": categorias[categoria],
                    "preco": preco,
                    "tamanhos": tamanhos,
                    "cores": cores,
                    "destaque": destaque,
                    "promocao": promocao,
                    "descricao": f"Disponível em {cores.lower()}.",
                },
            )
            if created or not produto.imagem:
                produto.imagem.save(f"{slugify(produto.nome)}.png", self._image(nome, cor), save=True)

        self.stdout.write(self.style.SUCCESS("Demo criada: http://127.0.0.1:8000/c/bela-meunier/"))

    def _image(self, label, background):
        image = Image.new("RGB", (900, 1125), background)
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 60, 840, 1065), outline="#ffffff", width=8)
        draw.text((90, 940), label, fill="#ffffff")

        media_dir = Path(settings.MEDIA_ROOT)
        media_dir.mkdir(parents=True, exist_ok=True)

        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return ContentFile(buffer.getvalue())
