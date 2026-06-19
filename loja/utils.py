import io
import mimetypes
from PIL import Image
from django.core.files.base import ContentFile

mimetypes.add_type("image/webp", ".webp")

def otimizar_imagem(campo_imagem, max_width=1000):
    """
    Otimiza uma imagem recebida em um ImageField:
    1. Converte o formato para WebP.
    2. Redimensiona para uma largura máxima de 1000px mantendo a proporção.
    3. Comprime com qualidade 75 (ótima relação tamanho/qualidade).
    """
    if not campo_imagem:
        return
        
    try:
        # Abre a imagem a partir do campo de arquivo
        img = Image.open(campo_imagem)
        
        # Converte modos de cor não suportados pelo JPEG/WebP padrão
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            alpha_composite = Image.alpha_composite(background, img)
            img = alpha_composite.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")
            
        # Redimensiona se exceder a largura máxima
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int(float(img.height) * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
        # Salva a imagem comprimida em formato WebP na memória
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=75)
        output.seek(0)
        
        # Altera a extensão do nome do arquivo para .webp
        orig_name = campo_imagem.name
        base_name = orig_name.rsplit(".", 1)[0]
        new_name = f"{base_name}.webp"
        
        # Substitui o conteúdo do campo pelo arquivo otimizado em memória
        content_file = ContentFile(output.read())
        content_file.content_type = "image/webp"
        campo_imagem.save(new_name, content_file, save=False)
    except FileNotFoundError:
        import sys
        if "test" not in sys.argv:
            print("Erro ao otimizar imagem: arquivo não encontrado.")
    except Exception as e:
        # Fallback silencioso para não interromper uploads
        print(f"Erro ao otimizar imagem: {e}")
