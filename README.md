# SaaS Pressing — API Backend

API REST **multi-tenant** de gestion de pressings pour le marché du Burkina Faso :
commandes au comptoir, paiements & créances, notifications SMS, livraison.

> Références projet : [`docs/structure-projet-pressing-saas.md`](docs/structure-projet-pressing-saas.md)
> (architecture cible) et [`docs/backlog-developpement.md`](docs/backlog-developpement.md)
> (workflow de développement par issues).

## Stack

| Composant | Choix |
|---|---|
| Framework | Django 5 + Django REST Framework |
| Base de données | PostgreSQL (Neon, pooler PgBouncer via `DATABASE_URL`) — SQLite en fallback dev local |
| Authentification | JWT (`djangorestframework-simplejwt`), login par numéro de téléphone |
| Documentation | OpenAPI automatique (`drf-spectacular`) |
| Isolation tenant | FK `pressing` sur chaque entité + `TenantScopedQuerysetMixin` + `IsSameTenant` |
| Tâches de fond | `notifications/tasks.py` prêt pour Celery + Redis (Issue #10) |

## Démarrage rapide (dev)

```bash
py -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash) — .venv\Scripts\activate en cmd
pip install -r requirements/dev.txt
cp .env.example .env                 # rien à changer pour du local SQLite
python manage.py migrate
python manage.py runserver
```

Documentation Swagger : <http://127.0.0.1:8000/api/schema/swagger-ui/>

## Tests

```bash
python manage.py test
```

## Structure du projet

```
config/               settings découpés (base / dev / prod), urls, wsgi/asgi
apps/
  core/               mixins & permissions multi-tenant, pagination, exceptions, modèles abstraits
  tenants/            Pressing (établissement, branding logo/couleurs)
  accounts/           User (gérant/employé), rôles, JWT
  clients/            répertoire clients, recherche par téléphone     (Issue #5)
  orders/             Commande + articles, cycle de vie, tickets      (Issues #6-#7)
  payments/           Paiement, créances, soldes                      (Issue #8)
  payments_gateway/   intégration Orange/Moov Money, webhooks         (Issue #9)
  notifications/      SMS automatiques, relances                      (Issue #10)
  deliveries/         coursiers, collecte/livraison                   (Issue #11)
requirements/         base.txt / dev.txt / prod.txt
docs/                 architecture, backlog, schéma OpenAPI
```

## Avancement du backlog

| Issue | Contenu | Statut |
|---|---|---|
| #1 | Initialisation & configuration multi-environnement | ✅ |
| #2 | Isolation multi-tenant (core : mixin + permission) | ✅ |
| — | Fondation modèles `Pressing` + `User` (JWT opérationnel) | ✅ |
| #3 | Tenants : inscription + customisation visuelle | ⏳ prochaine |
| #4 | Accounts : gestion employés, RBAC complet | ⏳ |
| #5-#12 | Clients, Orders, Payments, Gateway, SMS, Delivery, Dashboard | ⏳ |

## Variables d'environnement

Voir [`.env.example`](.env.example). En production, `DJANGO_SECRET_KEY`,
`DATABASE_URL` (Neon avec `-pooler`) et `ALLOWED_HOSTS` sont obligatoires.
