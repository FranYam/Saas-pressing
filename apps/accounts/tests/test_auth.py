"""Tests de l'authentification JWT — l'utilisateur se connecte avec son
numéro de téléphone (username) et son mot de passe.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tenants.models import Pressing


class JWTAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.pressing = Pressing.objects.create(name="Pressing A")
        self.user = User.objects.create_user(
            username="70123456",
            password="secret123",
            role=User.Role.GERANT,
            pressing=self.pressing,
        )
        self.login_url = reverse("accounts:token_obtain_pair")
        self.refresh_url = reverse("accounts:token_refresh")

    def test_login_returns_token_pair(self):
        response = self.client.post(
            self.login_url,
            {"username": "70123456", "password": "secret123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_wrong_password_denied(self):
        response = self.client.post(
            self.login_url,
            {"username": "70123456", "password": "mauvais-mot-de-passe"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token_returns_new_access_token(self):
        tokens = self.client.post(
            self.login_url,
            {"username": "70123456", "password": "secret123"},
            format="json",
        ).data

        response = self.client.post(
            self.refresh_url, {"refresh": tokens["refresh"]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
