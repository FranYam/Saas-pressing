"""Tests du modèle Pressing."""
from django.test import TestCase

from apps.tenants.models import Pressing


class PressingModelTests(TestCase):
    def test_create_with_defaults(self):
        pressing = Pressing.objects.create(name="Lavage Éclat")

        self.assertIsNotNone(pressing.id)  # UUID auto-généré
        self.assertEqual(pressing.primary_color, "#1E90FF")
        self.assertEqual(pressing.secondary_color, "#FF8C00")
        self.assertIsNotNone(pressing.created_at)
        self.assertEqual(str(pressing), "Lavage Éclat")

    def test_full_creation(self):
        pressing = Pressing.objects.create(
            name="Pressing Faso",
            address="Secteur 15, Ouagadougou",
            phone="+226 70 00 00 00",
            owner_name="Mme Kaboré",
            primary_color="#2E8B57",
            secondary_color="#FFD700",
        )
        self.assertEqual(pressing.owner_name, "Mme Kaboré")
        self.assertEqual(pressing.primary_color, "#2E8B57")
