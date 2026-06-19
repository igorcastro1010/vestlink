from django.core.management.base import BaseCommand
from django.utils import timezone
from loja.models import Loja

class Command(BaseCommand):
    help = "Verifica assinaturas/trials vencidos e atualiza seus status."

    def handle(self, *args, **options):
        self.stdout.write("Iniciando verificação de assinaturas...")
        hoje = timezone.now()
        
        # Encontrar lojas no período de trial que já expiraram
        lojas_trial_expirado = Loja.objects.filter(
            assinatura_status=Loja.ASSINATURA_TRIAL,
            trial_termina_em__lt=hoje
        )
        total_expirados = lojas_trial_expirado.count()
        
        for loja in lojas_trial_expirado:
            loja.assinatura_status = Loja.ASSINATURA_VENCIDA
            loja.save(update_fields=["assinatura_status"])
            self.stdout.write(self.style.SUCCESS(f"Loja '{loja.nome}' (slug: {loja.slug}) foi marcada como VENCIDA."))
            
        self.stdout.write(self.style.SUCCESS(f"Verificação concluída. {total_expirados} lojas marcadas como vencidas."))
