"""Critère d'acceptation Issue #1 : la documentation OpenAPI est servie."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class APIDocsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_swagger_ui_accessible(self):
        response = self.client.get(reverse("swagger-ui"))
        self.assertEqual(response.status_code, 200)

    def test_schema_generated(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, 200)
