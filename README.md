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

## Endpoints disponibles

| Méthode | Endpoint | Accès | Description |
|---|---|---|---|
| POST | `/api/v1/tenants/register/` | Public | Inscrit un pressing + son gérant (atomique), retourne JWT |
| GET | `/api/v1/tenants/profile/` | Authentifié | Branding du pressing (theming PWA) |
| PATCH | `/api/v1/tenants/profile/` | Gérant | Customisation logo / couleurs |
| POST | `/api/v1/accounts/login/` | Public | JWT (téléphone + mot de passe), claims `role`/`pressing_id` |
| POST | `/api/v1/accounts/login/refresh/` · `/verify/` | Public | Cycle de vie des tokens |
| GET | `/api/v1/accounts/me/` | Authentifié | Profil de l'utilisateur connecté |
| CRUD | `/api/v1/accounts/employees/` | Gérant | Équipe du pressing (DELETE = désactivation) |
| CRUD | `/api/v1/clients/` | Authentifié | Répertoire clients du pressing (`?search=` par préfixe téléphone ou nom) |
| GET/POST | `/api/v1/orders/` | Authentifié | Commandes + articles imbriqués (`?status=`, `?client=`, total calculé serveur) |
| PATCH | `/api/v1/orders/{id}/update_status/` | Authentifié | Cycle `RECU→EN_TRAITEMENT→PRET→LIVRE` validé (reçu texte inclus) |

Documentation interactive : <http://127.0.0.1:8000/api/schema/swagger-ui/>

## Avancement du backlog

| Issue | Contenu | Statut |
|---|---|---|
| #1 | Initialisation & configuration multi-environnement | ✅ |
| #2 | Isolation multi-tenant (core : mixin + permission) | ✅ |
| — | Fondation modèles `Pressing` + `User` (JWT opérationnel) | ✅ |
| #3 | Tenants : inscription + customisation visuelle | ✅ |
| #4 | Accounts : JWT claims, /me/, gestion équipe (RBAC) | ✅ |
| #5 | Clients : répertoire & recherche par téléphone | ✅ |
| #6 | Orders : commande + articles, création transactionnelle | ✅ |
| #7 | Orders : ticket unique TX-YYMM-NNN + cycle de vie validé | ✅ |
| #8-#12 | Payments, Gateway, SMS, Delivery, Dashboard | ⏳ prochaine : #8 |

## Variables d'environnement

Voir [`.env.example`](.env.example). En production, `DJANGO_SECRET_KEY`,
`DATABASE_URL` (Neon avec `-pooler`) et `ALLOWED_HOSTS` sont obligatoires.
