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


# ---------------------------------------------------------------------------
# Compte client (portail) — Issue : le client crée un compte et se connecte
# ---------------------------------------------------------------------------

import secrets

from django.contrib.auth.hashers import check_password, make_password


def set_client_password(client, raw_password: str) -> None:
    """Hash et enregistre le mot de passe du compte client."""
    client.password = make_password(raw_password)
    client.save(update_fields=["password", "updated_at"])


def verify_client_password(client, raw_password: str) -> bool:
    """True si le client a un compte ET que le mot de passe correspond."""
    if not client.password:
        return False
    return check_password(raw_password, client.password)


def issue_portal_token(client) -> str:
    """Génère (et stocke) un nouveau jeton de session portail — invalide l'ancien."""
    client.portal_token = secrets.token_hex(32)
    client.save(update_fields=["portal_token", "updated_at"])
    return client.portal_token


def clear_portal_token(client) -> None:
    """Déconnexion portail : le jeton stocké ne vaut plus rien."""
    client.portal_token = ""
    client.save(update_fields=["portal_token", "updated_at"])
