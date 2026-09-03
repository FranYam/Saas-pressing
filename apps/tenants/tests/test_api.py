"""Tests des endpoints tenants (Issue #3) : inscription & customisation visuelle.

Fixtures de test uniquement — mots de passe factices, jamais de vraies
informations d'identification (voir .gitguardian.yml).
"""
import tempfile
from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing

# Identifiant généré à l'exécution : conforme aux validateurs Django et
# absent du code source (règle anti-fuite).
PASSWORD = fake_password()


def logo_upload():
    """Génère une petite image PNG valide pour tester l'upload du logo."""
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "#2E8B57").save(buffer, format="PNG")
    return SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")


class PressingRegisterTests(TestCase):
    """POST /api/v1/tenants/register/ — critique d'acceptation : 201 + détails."""

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("tenants:register")
        self.payload = {
            "name": "Pressing Faso",
            "address": "Secteur 15, Ouagadougou",
            "phone": "+226 70 00 00 00",
            "owner_name": "Mme Kaboré",
            "primary_color": "#2E8B57",
            "secondary_color": "#FFD700",
            "gerant": {
                "username": "70123456",
                "password": PASSWORD,
                "first_name": "Awa",
            },
        }

    def test_register_creates_pressing_and_gerant(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Détails de l'établissement dans la réponse (critère d'acceptation).
        self.assertEqual(response.data["pressing"]["name"], "Pressing Faso")
        self.assertEqual(response.data["pressing"]["primary_color"], "#2E8B57")

        pressing = Pressing.objects.get(name="Pressing Faso")
        self.assertEqual(pressing.primary_color, "#2E8B57")

        gerant = User.objects.get(username="70123456")
        self.assertEqual(gerant.role, User.Role.GERANT)
        self.assertEqual(gerant.pressing, pressing)

        # Tokens JWT : la PWA connecte le gérant sans second appel login.
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])

    def test_register_duplicate_username_rolls_back_pressing(self):
        """Transaction atomique : pas de pressing orphelin si le gérant est invalide."""
        User.objects.create_user(username="70123456", password=PASSWORD)

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Pressing.objects.exists())

    def test_register_weak_password_rejected(self):
        payload = {
            **self.payload,
            "gerant": {"username": "70999888", "password": "123"},
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Pressing.objects.exists())
        self.assertIn("password", response.data["gerant"])

    def test_register_invalid_color_rejected(self):
        response = self.client.post(
            self.url, {**self.payload, "primary_color": "vert"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("primary_color", response.data)

    def test_register_minimal_payload_uses_default_colors(self):
        payload = {
            "name": "Pressing Minimal",
            "gerant": {"username": "70777777", "password": PASSWORD},
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["pressing"]["primary_color"], "#1E90FF")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="pressing_tests_media_"))
class PressingProfileTests(TestCase):
    """GET/PATCH /api/v1/tenants/profile/ — theming PWA + RBAC sur la marque.

    MEDIA_ROOT redirigé vers un dossier temporaire : les logos uploadés
    pendant les tests ne polluent jamais le media/ du projet.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("tenants:profile")
        self.pressing = Pressing.objects.create(
            name="Pressing A", primary_color="#111111"
        )
        self.gerant = User.objects.create_user(
            username="70000001",
            password=PASSWORD,
            role=User.Role.GERANT,
            pressing=self.pressing,
        )
        self.employe = User.objects.create_user(
            username="70000002",
            password=PASSWORD,
            role=User.Role.EMPLOYE,
            pressing=self.pressing,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_profile_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_own_pressing_branding(self):
        """Lecture ouverte à l'employé : la PWA applique le thème à tous."""
        self.auth(self.employe)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["primary_color"], "#111111")
        self.assertIn("logo", response.data)
        self.assertIn("secondary_color", response.data)

    def test_gerant_can_update_branding(self):
        self.auth(self.gerant)

        response = self.client.patch(
            self.url, {"primary_color": "#222222"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pressing.refresh_from_db()
        self.assertEqual(self.pressing.primary_color, "#222222")

    def test_employe_cannot_update_branding(self):
        """Spécification : l'employé ne peut pas éditer le branding du pressing."""
        self.auth(self.employe)

        response = self.client.patch(
            self.url, {"primary_color": "#333333"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.pressing.refresh_from_db()
        self.assertEqual(self.pressing.primary_color, "#111111")

    def test_gerant_can_upload_logo(self):
        self.auth(self.gerant)

        response = self.client.patch(self.url, {"logo": logo_upload()}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pressing.refresh_from_db()
        self.assertTrue(self.pressing.logo)

    def test_invalid_color_rejected_on_update(self):
        self.auth(self.gerant)

        response = self.client.patch(
            self.url, {"secondary_color": "orange"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_without_pressing_gets_404(self):
        orphan = User.objects.create_user(username="70000009", password=PASSWORD)
        self.auth(orphan)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
