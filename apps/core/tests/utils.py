"""Utilitaires partagés des tests.

Règle anti-fuite (alertes GitGuardian) : le dépôt ne doit contenir AUCUNE
chaîne littérale ressemblant à un mot de passe. Les identifiants de test
sont donc générés à l'exécution et stockés dans des variables — jamais
écrits en dur dans le code source.

Les valeurs produites restent conformes aux validateurs de mot de passe
Django (longueur, complexité, pas entièrement numériques).
"""
import uuid


def fake_password() -> str:
    """Mot de passe factice aléatoire, suffisamment fort pour les validateurs."""
    return f"Faso-{uuid.uuid4().hex}"


def fake_phone(index: int = 0) -> str:
    """Numéro de téléphone factice burkinabé (8 chiffres, préfixe 70)."""
    return f"70{index:06d}"
