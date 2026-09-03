"""Tests des utilitaires de normalisation téléphone (Issue #5)."""
from django.test import SimpleTestCase

from apps.clients.services import clean_phone, normalize_phone
from rest_framework.exceptions import ValidationError


class NormalizePhoneTests(SimpleTestCase):
    def test_strips_spaces(self):
        self.assertEqual(normalize_phone("70 12 34 56"), "70123456")

    def test_strips_international_prefix(self):
        self.assertEqual(normalize_phone("+226 70 12 34 56"), "22670123456")

    def test_strips_dashes_and_dots(self):
        self.assertEqual(normalize_phone("70-12-34.56"), "70123456")

    def test_empty_and_none(self):
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")


class CleanPhoneTests(SimpleTestCase):
    def test_valid_local_number(self):
        self.assertEqual(clean_phone("70 12 34 56"), "70123456")

    def test_valid_international_number(self):
        self.assertEqual(clean_phone("+226 70 12 34 56"), "22670123456")

    def test_too_short_rejected(self):
        with self.assertRaises(ValidationError):
            clean_phone("123")

    def test_too_long_rejected(self):
        # 16 chiffres — au-delà de la limite E.164.
        with self.assertRaises(ValidationError):
            clean_phone("1234 5678 9012 3456")

    def test_letters_rejected(self):
        with self.assertRaises(ValidationError):
            clean_phone("ABCD--12")
