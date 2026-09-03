# Structure du projet — SaaS Pressing (Django REST Framework)

## Principe général

Une app Django **par domaine métier**, pas une seule grosse app "core". Chaque app a la même anatomie MVT/DRF : `models.py` → `serializers.py` → `views.py` → `urls.py`. C'est ce qui garde le code lisible et scalable même quand le projet grossit (facile d'ajouter l'appli mobile, l'espace fidélité, les stats avancées listés en "évolutions futures" sans tout casser).

```
pressing_saas/
├── manage.py
├── .env.example
├── requirements/
│   ├── base.txt              # django, djangorestframework, psycopg2-binary, django-environ...
│   ├── dev.txt                # + django-debug-toolbar, factory_boy
│   └── prod.txt               # + gunicorn, whitenoise, sentry-sdk
│
├── config/                    # anciennement "pressing_saas/" généré par défaut — renommé pour la clarté
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py            # settings communs
│   │   ├── dev.py             # DEBUG=True, sqlite ou Neon dev branch
│   │   └── prod.py            # DEBUG=False, Neon prod, sécurité, CORS strict
│   ├── urls.py                # inclut les urls.py de chaque app sous /api/v1/...
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── __init__.py
│   │
│   ├── core/                  # PAS de modèle métier ici — juste du partagé
│   │   ├── models.py          # ex: TimeStampedModel (abstract), UUIDModel
│   │   ├── permissions.py     # IsSameTenant, IsGerant, IsEmployee, IsCoursier
│   │   ├── pagination.py
│   │   ├── mixins.py          # TenantScopedQuerysetMixin
│   │   └── exceptions.py
│   │
│   ├── tenants/                # Entité "Pressing" (établissement) — coeur du multi-tenant
│   │   ├── models.py           # Pressing (nom, adresse, tel, logo, couleur_primaire, couleur_secondaire)
│   │   ├── serializers.py
│   │   ├── views.py            # inscription pressing, personnalisation logo/couleurs
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── tests/
│   │
│   ├── accounts/               # Utilisateur (gérant / employé), auth, rôles
│   │   ├── models.py           # User custom (AbstractUser) + role, pressing (FK)
│   │   ├── serializers.py      # login, création employé, JWT claims
│   │   ├── views.py
│   │   ├── permissions.py      # rôles spécifiques accounts si besoin
│   │   ├── urls.py
│   │   └── tests/
│   │
│   ├── clients/                 # Client final du pressing
│   │   ├── models.py            # Client (nom, tel, pressing FK)
│   │   ├── serializers.py
│   │   ├── views.py             # recherche par numéro de téléphone
│   │   ├── urls.py
│   │   └── tests/
│   │
│   ├── orders/                  # Commande + Article de commande (le coeur métier)
│   │   ├── models.py            # Commande, ArticleCommande
│   │   ├── serializers.py       # nested serializer articles dans commande
│   │   ├── views.py             # ViewSet avec transitions de statut Reçu→En traitement→Prêt→Livré
│   │   ├── services.py          # logique métier (génération n° ticket, calcul total) hors des views
│   │   ├── urls.py
│   │   └── tests/
│   │
│   ├── payments/                 # Paiement, créances, soldes
│   │   ├── models.py             # Paiement (commande FK, montant, mode, statut)
│   │   ├── serializers.py
│   │   ├── views.py              # enregistrement paiement partiel/total/crédit
│   │   ├── services.py           # calcul solde restant dû
│   │   ├── urls.py
│   │   └── tests/
│   │
│   ├── deliveries/                # Coursier + suivi collecte/livraison
│   │   ├── models.py              # Coursier, assignation à une Commande
│   │   ├── serializers.py
│   │   ├── views.py                # commandes assignées au coursier connecté
│   │   ├── urls.py
│   │   └── tests/
│   │
│   ├── payments_gateway/           # Intégration mobile money (Orange/Moov) — isolé du reste
│   │   ├── services.py             # appel API opérateur, initiation paiement
│   │   ├── webhooks.py             # réception confirmation
│   │   ├── urls.py
│   │   └── tests/
│   │
│   └── notifications/               # SMS (envoi "prêt", rappels)
│       ├── services.py              # wrapper autour de la passerelle SMS
│       ├── tasks.py                 # si Celery ajouté plus tard
│       └── tests/
│
├── static/
├── media/                         # logos des pressings
└── docs/
    └── api-schema.yml              # généré par drf-spectacular
```

## Pourquoi ce découpage

- **`core/`** évite de dupliquer les permissions et le mixin d'isolation tenant dans chaque app — un seul endroit à corriger si la règle multi-tenant change.
- **`tenants/` séparé de `accounts/`** : le Pressing (établissement) et l'Utilisateur (personne) sont deux entités distinctes avec des cycles de vie différents (un pressing existe même si tu changes ses employés).
- **`services.py`** dans les apps qui ont de la logique métier non triviale (calcul de solde, génération de ticket) : la vue reste fine (parsing requête + appel serializer + réponse), la logique métier est testable indépendamment de HTTP.
- **`payments_gateway/` séparé de `payments/`** : `payments/` gère la donnée (modèle Paiement), `payments_gateway/` gère l'intégration externe fragile (API Orange/Moov, webhooks). Si un opérateur change son API, tu ne touches qu'un seul module.
- Chaque app a son **`urls.py`** propre, monté dans `config/urls.py` avec un préfixe `/api/v1/<app>/` — ça prépare une v2 d'API sans casser l'existante (utile vu que la section 2.2 annonce des évolutions futures).

## Isolation multi-tenant (section 6.2)

Pas besoin de schémas Postgres séparés par pressing pour un MVP avec "un nombre limité de pressings pilotes" — trop lourd à maintenir. Utilise plutôt :

1. Chaque modèle métier (`Client`, `Commande`, `Paiement`, `Coursier`, `User`) a un **FK `pressing`**.
2. Un `TenantScopedQuerysetMixin` dans `core/mixins.py` que chaque `ViewSet` hérite, qui filtre automatiquement `queryset.filter(pressing=request.user.pressing)`.
3. Une permission `IsSameTenant` dans `core/permissions.py` qui vérifie qu'un objet demandé (get/update/delete) appartient bien au pressing de l'utilisateur connecté, avant même d'exécuter la vue.

Ça respecte le critère d'acceptation *"deux pressings distincts ne voient jamais les données l'un de l'autre"* avec un code simple à auditer (un seul endroit vérifie l'isolation, pas 10 vues qui filtrent chacune à leur façon).

## Config par environnement

`config/settings/base.py` lit tout depuis `.env` via `django-environ` — l'URL Neon (avec le pooler PgBouncer intégré) va directement dans `DATABASE_URL`, sans rien coder en dur. `dev.py` peut pointer vers une **branche Neon de dev** (Neon permet de créer des branches de la base gratuitement, pratique pour tester sans toucher aux données pilotes).

## Pour la suite (scalabilité, hors MVP)

- `notifications/tasks.py` est déjà prévu pour brancher Celery + Redis plus tard, si le volume de SMS grossit et que tu ne veux plus bloquer la requête HTTP le temps de l'envoi.
- `drf-spectacular` pour générer automatiquement la doc OpenAPI de l'API — utile le jour où tu factures l'accès API ou ajoutes l'app mobile native (section 2.2).
