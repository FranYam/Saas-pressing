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

## Déploiement

Guide complet (base **Neon** PostgreSQL + hébergement **Render** + médias
**Cloudflare R2**, stratégie pilote 0 € → production) :
[`docs/deploiement.md`](docs/deploiement.md).

CI : les tests tournent automatiquement à chaque push
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

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
| POST | `/api/tenants/register/` | Public | Inscrit un pressing + son gérant (atomique), retourne JWT |
| GET | `/api/tenants/profile/` | Authentifié | Branding du pressing (theming PWA) |
| PATCH | `/api/tenants/profile/` | Gérant | Customisation logo / couleurs |
| POST | `/api/accounts/login/` | Public | JWT (téléphone + mot de passe), claims `role`/`pressing_id` |
| POST | `/api/accounts/login/refresh/` · `/verify/` | Public | Cycle de vie des tokens |
| GET | `/api/accounts/me/` | Authentifié | Profil de l'utilisateur connecté |
| CRUD | `/api/accounts/employees/` | Gérant | Équipe du pressing (DELETE = désactivation) |
| CRUD | `/api/clients/` | Authentifié | Répertoire clients du pressing (`?search=` par préfixe téléphone ou nom) |
| GET/POST | `/api/orders/` | Authentifié | Commandes + articles imbriqués (`?status=`, `?client=`, total calculé serveur) |
| PATCH | `/api/orders/{id}/update_status/` | Authentifié | Cycle `RECU→EN_TRAITEMENT→PRET→LIVRE` validé (reçu texte inclus) |
| GET/POST | `/api/payments/` | Authentifié | Règlements (statut calculé serveur, immuables, `?commande=`) |
| GET | `/api/payments/client-balance/?client=` | Authentifié | Solde consolidé du client (dû, payé, reste, détail) |
| GET | `/api/payments/debtors/` | Gérant | Clients avec créance > 0 |
| POST | `/api/payments-gateway/initiate/` | Authentifié | Push Mobile Money (Orange/Moov) sur le reste à payer |
| POST | `/api/payments-gateway/webhook/{operator}/` | Public + HMAC-SHA256 | Confirmation opérateur (idempotente, montant vérifié) |
| GET | `/api/payments-gateway/requests/` | Authentifié | Suivi des demandes Mobile Money du pressing |
| — | `python manage.py send_reminders` | Cron / celery-beat | Relance SMS : linge prêt non retiré > 7 jours |
| CRUD | `/api/deliveries/couriers/` | Gérant (écriture) | Coursiers + compte de connexion (rôle COURSIER) |
| PATCH | `/api/orders/{id}/assign-courier/` | Gérant | Assigne un coursier à la commande |
| GET | `/api/orders/my-deliveries/` | Coursier | Uniquement SES livraisons assignées |
| PATCH | `/api/orders/{id}/update-delivery/` | Coursier assigné / gérant | Cycle `A_COLLECTER→COLLECTE→A_LIVRER→LIVRE` |
| GET | `/api/dashboard/summary/` | Gérant | KPIs temps réel : CA jour/mois, commandes, créances, non réclamés |

SMS automatiques : passage `PRET` → SMS au client (nom du pressing + ticket), journalisés dans `SmsNotification` (SIMULATED si passerelle non configurée, `tasks.py` prête pour Celery).

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
| #8 | Payments : règlements, soldes clients, créances (debtors) | ✅ |
| #9 | Passerelle Mobile Money (initiation + webhook signé) | ✅ |
| #10 | Notifications SMS (signal PRET, relances 7 jours, Celery-ready) | ✅ |
| #11 | Delivery : coursiers (rôle dédié), assignation, my-deliveries | ✅ |
| #12 | Dashboard gérant (agrégations SQL, IsGerant) | ✅ |

**🎉 Backlog complet : 12/12 issues livrées — 171 tests verts.**

## Portail client public

Le portail propose l'inscription et la connexion client, un catalogue tarifaire,
les demandes de collecte, ainsi qu'une consultation par ticket et numéro de
téléphone complet. Les routes publiques de connexion, inscription, collecte et
consultation sont limitées par des scopes DRF configurés dans
`REST_FRAMEWORK`.

En déploiement multi-instance, configurez un cache partagé pour que les limites
de requêtes soient communes à toutes les instances. Le lookup par ticket ne
retourne des commandes que si le numéro complet correspond.

## Variables d'environnement

Voir [`.env.example`](.env.example). En production, `DJANGO_SECRET_KEY`,
`DATABASE_URL` (Neon avec `-pooler`) et `ALLOWED_HOSTS` sont obligatoires.
