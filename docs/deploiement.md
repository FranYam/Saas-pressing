# Guide de déploiement — Neon (base) + Render (API) + R2 (médias)

Stratégie évolutive pensée pour démarrer **à 0 €** et monter en puissance
**sans réécrire une ligne de code** — seules les variables d'environnement
changent entre les phases.

```
┌─────────────┐   DATABASE_URL    ┌──────────────────────┐
│  Neon (BD)  │◄──────────────────│  Render (API Django) │◄── PWA / apps
└─────────────┘                   └──────────┬───────────┘
                                             │ S3_* (optionnel)
                                  ┌──────────▼───────────┐
                                  │ Cloudflare R2 (médias)│ ← logos persistants
                                  └──────────────────────┘
```

| Phase | Coût | Composants | Pour quand ? |
|---|---|---|---|
| **Pilote** | 0 €/mois | Neon free + Render free + R2 (10 Go offerts) | Démo, premiers pressings pilotes |
| **Production** | ~4-7 €/mois | Render Starter *ou* VPS (Neon + R2 inchangés) | Premiers clients payants |

> 🔁 **Important** : vos **données ne disparaissent jamais** au redéploiement
> (elles vivent sur Neon), et avec R2 les **logos uploadés** survivent aussi.
> Au stade pilote, la seule contrainte est la mise en veille de l'offre
> gratuite (~30-60 s de réveil après 15 min sans trafic).

---

## Étape 0 — Prérequis

- Un compte [GitHub](https://github.com) (déjà fait : dépôt `FranYam/Saas-pressing`)
- Un compte [Neon](https://neon.tech) — base PostgreSQL
- Un compte [Render](https://render.com) — hébergement de l'application
- Un compte [Cloudflare](https://dash.cloudflare.com) — stockage R2 des médias
- Dépôt à jour : `git push`

## Étape 1 — Créer la base PostgreSQL sur Neon

1. [neon.tech](https://neon.tech) → **Sign up** (avec GitHub).
2. **Create project** : `saas-pressing`, région **Frankfurt (eu-central-1)**.
3. Copier l'URL **« Pooled connection »** — celle avec **`-pooler`** dans
   le nom d'hôte :

   ```
   postgres://user:password@ep-xxxx-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```

   ⚠️ Prendre celle avec `-pooler` : les settings sont déjà configurés pour
   le pooler PgBouncer (`CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS`).

4. Générer la clé secrète Django :

   ```bash
   py -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

5. Créer le `.env` local (racine du projet — **gitignoré**, jamais commité) :

   ```bash
   cp .env.example .env
   ```

   ```ini
   DJANGO_SECRET_KEY=<la clé générée>
   DATABASE_URL=postgres://...-pooler...?sslmode=require
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

6. Valider en local sur la vraie base :

   ```bash
   python manage.py migrate      # crée le schéma sur Neon
   python manage.py test         # 171 tests rejoués sur PostgreSQL
   python manage.py runserver    # http://127.0.0.1:8000/api/schema/swagger-ui/
   ```

## Étape 2 — Créer le bucket R2 (médias persistants)

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **R2 Object Storage**
   → *Create bucket* : `saas-pressing-media`.
2. Dans le bucket → **Settings** → activer **Public Development URL**
   (`https://pub-xxxx.r2.dev`) — suffisant pour le pilote (domaine propre plus tard).
3. **Manage R2 API Tokens** → *Create API token* → permissions
   **Object Read & Write** sur ce bucket → noter **Access Key ID** et
   **Secret Access Key**.
4. L'URL endpoint du compte : `https://<account_id>.r2.cloudflarestorage.com`
   (visible dans la page des tokens).

Ces valeurs (bucket, endpoint, clés, domaine public) alimenteront les
variables `S3_*` ci-dessous. Tant qu'elles sont vides, le stockage reste
local — activer R2 n'est donc **pas bloquant** pour déployer.

## Étape 3 — Déployer l'application sur Render

1. [render.com](https://render.com) → **New + → Web Service** → connecter
   le dépôt `FranYam/Saas-pressing`.
2. Configuration :

   | Réglage | Valeur |
   |---|---|
   | Name / Region | `saas-pressing-api` / Frankfurt |
   | Branch | `main` |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements/prod.txt && python manage.py collectstatic --noinput && python manage.py migrate` |
   | Start Command | `gunicorn config.wsgi --workers 2 --timeout 120` |
   | Instance Type | Free (pilote) / Starter (production) |

3. Variables d'environnement (Render → Environment) :

   | Variable | Valeur |
   |---|---|
   | `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
   | `DJANGO_SECRET_KEY` | la même clé qu'en local |
   | `DATABASE_URL` | l'URL Neon `-pooler` |
   | `ALLOWED_HOSTS` | `saas-pressing-api.onrender.com` |
   | `CORS_ALLOWED_ORIGINS` | URL de la PWA (ou `http://localhost:5173` pour tester) |
   | `SECURE_SSL_REDIRECT` | `True` |
   | `S3_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` |
   | `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | clés du token R2 |
   | `S3_BUCKET_NAME` | `saas-pressing-media` |
   | `S3_CUSTOM_DOMAIN` | `pub-xxxx.r2.dev` |

4. **Create Web Service** → suivre les logs. Chaque `git push` sur `main`
   redéploie automatiquement — et la **CI GitHub Actions** (`.github/workflows/ci.yml`)
   fait tourner les 171 tests avant : un push rouge se voit immédiatement.

## Étape 4 — Vérifications post-déploiement

```bash
BASE=https://saas-pressing-api.onrender.com
curl -s -o /dev/null -w "%{http_code}\n" $BASE/api/schema/   # 200 attendu
```

- Swagger : `https://…/api/schema/swagger-ui/`
- Admin : `https://…/admin/` — créer le super-admin via l'onglet **Shell**
  de Render : `python manage.py createsuperuser`
- Inscrire un pressing de test : `POST /api/v1/tenants/register/`, puis
  vérifier dans l'admin que le logo atterrit bien sur R2 (URL `pub-xxxx.r2.dev/media/...`).

## Étape 5 — Brancher PWA et opérateurs

- La PWA appelle `https://saas-pressing-api.onrender.com/api/v1/...`
  (mettre à jour `CORS_ALLOWED_ORIGINS` avec l'URL définitive).
- Webhooks Mobile Money à déclarer auprès des opérateurs :
  - Orange : `https://…/api/v1/payments-gateway/webhook/orange/`
  - Moov : `https://…/api/v1/payments-gateway/webhook/moov/`
- Passerelle SMS : renseigner `SMS_API_URL`, `SMS_API_KEY`, `SMS_SENDER_ID`
  (tant que vides : SMS simulés et journalisés).

---

## Passer en production (~4-7 €/mois)

Quand les premiers pressings paient, **sans changer le code** :

- **Option Render Starter** : changer l'Instance Type → plus de mise en
  veille, tout le reste identique.
- **Option VPS** (Hetzner/OVH, ~4 €/mois) : toujours allumé, disque persistant
  (R2 devient optionnel) — déploiement Docker + gunicorn + Nginx, à préparer
  ensemble le moment venu.

## Et si 0,5 Go (Neon gratuit) ne suffit plus ?

À proportion de ce projet, 0,5 Go ≈ **400 000+ commandes** (les médias sont
sur R2, pas en base) : ~2 ans d'autonomie pour 10 pressings actifs. Surveiller
l'occupation dans le dashboard Neon (Storage) chaque mois.

Quand dépasser, par ordre de préférence :

1. **VPS unique (~4 €/mois, ex. Hetzner CX22)** : PostgreSQL **et** l'API sur
   la même machine — 40 Go SSD, toujours allumé, disque persistant (R2 devient
   optionnel). Migration des données : `pg_dump | psql` en une commande.
2. Neon Launch (10 Go) — simple mais ~19 $/mois : uniquement si vous voulez
   rester 100 % managé.
3. Supabase gratuit : même limite de 0,5 Go — aucun intérêt à migrer.

## Dépannage rapide

| Symptôme | Cause probable |
|---|---|
| `502 Bad Gateway` au 1er démarrage | build/migrations pas terminés — voir les logs |
| `ImproperlyConfigured: DJANGO_SECRET_KEY` | variable absente sur Render |
| `/admin/` en 400 | `ALLOWED_HOSTS` sans le domaine Render |
| `OperationalError` base | `DATABASE_URL` absente, sans `-pooler`, ou sans `?sslmode=require` |
| Requêtes PWA bloquées (CORS) | `CORS_ALLOWED_ORIGINS` sans l'URL de la PWA |
| Statiques manquants (CSS admin) | `collectstatic` absent du Build Command |
| Erreur au premier upload logo | une variable `S3_*` manquante ou token R2 sans droits écriture |
