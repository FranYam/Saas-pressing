"""Tests de l'authentification JWT — l'utilisateur se connecte avec son
numéro de téléphone (username) et son mot de passe.

Identifiants générés à l'exécution (apps/core/tests/utils.py) : le dépôt
ne contient aucune chaîne littérale ressemblant à un mot de passe.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.tests.utils import fake_password
from apps.tenants.models import Pressing

PASSWORD = fake_password()


class JWTAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.user = User.objects.create_user(
            username="70123456",
            password=PASSWORD,
            role=User.Role.GERANT,
            pressing=self.pressing,
        )
        self.login_url = reverse("accounts:token_obtain_pair")
        self.refresh_url = reverse("accounts:token_refresh")

    def credentials(self):
        return {"username": self.user.username, "password": PASSWORD}

    def test_login_returns_token_pair(self):
        response = self.client.post(self.login_url, self.credentials(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password_denied(self):
        wrong = {"username": self.user.username, "password": fake_password()}
        response = self.client.post(self.login_url, wrong, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_returns_new_access_token(self):
        tokens = self.client.post(self.login_url, self.credentials(), format="json").data

        response = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
