"""Logique métier clients — normalisation des numéros de téléphone.

Au comptoir, le numéro est saisi tel quel (espaces, +226, tirets...) : on
normalise en chiffres uniquement avant stockage ET avant chaque recherche,
pour que la recherche par préfixe fonctionne quel que soit le format saisi.
"""
import re

from rest_framework.exceptions import ValidationError

# 8 chiffres au Burkina Faso, jusqu'à 15 au format E.164 international.
PHONE_RE = re.compile(r"\d{8,15}")


def normalize_phone(value: str) -> str:
    """« 70 12 34 56 » ou « +226 70 12 34 56 » → « 70123456 » / « 22670123456 »."""
    return re.sub(r"\D", "", value or "")


def clean_phone(value: str) -> str:
    """Normalise puis valide : 8 à 15 chiffres exactement, sinon 400."""
    digits = normalize_phone(value)
    if not PHONE_RE.fullmatch(digits):
        raise ValidationError(
            "Numéro invalide : 8 à 15 chiffres attendus (ex. 70123456)."
        )
    return digits
