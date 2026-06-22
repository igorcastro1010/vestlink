import json
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from loja.models import Categoria, Loja, Produto, ProdutoImagem, ProdutoVariacao


class ProductTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lojista", password="senha-forte-123")
        self.loja = Loja.objects.create(
            usuario=self.user,
            nome="Teste Moda",
            slug="teste-moda",
            telefone="85999999999",
        )
        self.categoria = Categoria.objects.create(loja=self.loja, nome="Blusas")
        self.produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Blusa Preta",
            preco="79.90",
            imagem="produtos/blusa.png",
        )

    def test_painel_cadastra_produto(self):
        self.client.force_login(self.user)
        imagem = SimpleUploadedFile(
            "produto.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        foto_extra_1 = SimpleUploadedFile(
            "produto-extra-1.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        foto_extra_2 = SimpleUploadedFile(
            "produto-extra-2.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Vestido Azul",
                "descricao": "Peça nova",
                "preco": "139.90",
                "imagem": imagem,
                "fotos_adicionais": [foto_extra_1, foto_extra_2],
                "tamanhos": "P, M",
                "tamanhos_esgotados": "M",
                "cores": "Azul",
                "cores_esgotadas": "Azul",
                "variacoes_estoque": "Azul, P, 4\nAzul, M, 0",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Produto.objects.filter(loja=self.loja, nome="Vestido Azul").exists())
        self.assertEqual(ProdutoImagem.objects.filter(produto__nome="Vestido Azul").count(), 2)
        self.assertEqual(ProdutoVariacao.objects.filter(produto__nome="Vestido Azul").count(), 2)

    def test_painel_edita_produto(self):
        self.client.force_login(self.user)
        imagem = SimpleUploadedFile(
            "produto-editado.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("editar_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id}),
            {
                "categoria": str(self.categoria.id),
                "nome": "Blusa Branca",
                "descricao": "Produto editado",
                "preco": "89.90",
                "imagem": imagem,
                "tamanhos": "P, M",
                "tamanhos_esgotados": "M",
                "cores": "Branco",
                "cores_esgotadas": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.nome, "Blusa Branca")
        self.assertEqual(str(self.produto.preco), "89.90")

    def test_painel_publica_produto_rascunho(self):
        self.produto.publicado = False
        self.produto.save(update_fields=["publicado"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("painel_loja", kwargs={"slug": self.loja.slug}),
            {"acao": "publicar_produto", "produto_id": str(self.produto.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.produto.refresh_from_db()
        self.assertTrue(self.produto.publicado)

    def test_painel_remove_produto(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("remover_produto", kwargs={"slug": self.loja.slug, "produto_id": self.produto.id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Produto.objects.filter(id=self.produto.id).exists())

    def test_image_optimized_and_converted_to_webp(self):
        gif_content = (
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        image_file = SimpleUploadedFile("mock_product.gif", gif_content, content_type="image/gif")
        
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Vestido Otimizado",
            preco="150.00",
            imagem=image_file
        )
        
        self.assertTrue(produto.imagem.name.endswith(".webp"))
        self.assertIn("mock_product", produto.imagem.name)

    def test_cache_version_invalidation_signals(self):
        from django.core.cache import cache
        cache.clear()
        
        version = cache.get_or_set(f"loja_cache_version_{self.loja.id}", 1)
        self.assertEqual(version, 1)
        
        gif_content = (
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        image_file = SimpleUploadedFile("mock_product.gif", gif_content, content_type="image/gif")
        
        produto = Produto.objects.create(
            loja=self.loja,
            categoria=self.categoria,
            nome="Produto Teste Cache",
            preco="50.00",
            imagem=image_file
        )
        
        new_version = cache.get(f"loja_cache_version_{self.loja.id}")
        self.assertEqual(new_version, 2)
        
        produto.delete()
        new_version = cache.get(f"loja_cache_version_{self.loja.id}")
        self.assertEqual(new_version, 3)
