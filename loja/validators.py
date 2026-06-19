import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class UppercasePasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-ZÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇ]", password):
            raise ValidationError(
                _("Sua senha precisa ter pelo menos uma letra maiúscula."),
                code="password_no_uppercase",
            )

    def get_help_text(self):
        return _("Sua senha precisa ter pelo menos uma letra maiúscula.")


class SpecialCharacterPasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r"[^A-Za-z0-9ÁÀÂÃÉÈÊÍÏÓÔÕÖÚÇáàâãéèêíïóôõöúç]", password):
            raise ValidationError(
                _("Sua senha precisa ter pelo menos um caractere especial."),
                code="password_no_special",
            )

    def get_help_text(self):
        return _("Sua senha precisa ter pelo menos um caractere especial.")


def limpar_telefone(telefone):
    """
    Remove todos os caracteres não numéricos.
    Se começar com 55 e tiver 12 ou 13 dígitos, remove o 55.
    """
    apenas_digitos = re.sub(r"\D", "", str(telefone))
    if apenas_digitos.startswith("55") and len(apenas_digitos) in (12, 13):
        apenas_digitos = apenas_digitos[2:]
    return apenas_digitos


def validar_whatsapp(value):
    digitos = limpar_telefone(value)
    if len(digitos) < 10 or len(digitos) > 11:
        raise ValidationError(
            _("O número de WhatsApp deve conter o DDD mais 8 ou 9 dígitos (ex: 85999999999)."),
            code="whatsapp_invalido",
        )

