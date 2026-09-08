"""Seed du catalogue standard pour les pressings existants avant l'app catalog."""
from django.db import migrations


def seed(apps, schema_editor):
    Pressing = apps.get_model("tenants", "Pressing")
    Tarif = apps.get_model("catalog", "Tarif")

    DEFAULTS = [
        ("Chemise", "Vêtements", "500"),
        ("Pantalon", "Vêtements", "750"),
        ("Robe", "Vêtements", "1000"),
        ("Costume", "Vêtements", "3000"),
        ("Boubou", "Traditionnel", "2000"),
        ("Drap", "Linge de maison", "1500"),
        ("Rideau", "Linge de maison", "2000"),
    ]

    for pressing in Pressing.objects.all():
        if not Tarif.objects.filter(pressing=pressing).exists():
            Tarif.objects.bulk_create(
                [
                    Tarif(pressing=pressing, name=name, category=category, price=price)
                    for name, category, price in DEFAULTS
                ]
            )


def unseed(apps, schema_editor):
    Tarif = apps.get_model("catalog", "Tarif")
    Tarif.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
