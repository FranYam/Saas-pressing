# Backlog de Développement — SaaS Pressing Multi-Tenant

Ce document contient un plan de développement étape par étape, découpé sous forme de tickets/issues actionnables pour suivre et construire l'application SaaS de gestion de pressing. Ce backlog est structuré pour s'aligner sur l'architecture technique modulaire proposée (Django + DRF au backend, PWA au frontend, base PostgreSQL Neon) tout en assurant l'isolation stricte des données (multi-tenant).

---

## Sommaire des Épisodes de Développement
* **Phase 1 : Socle Technique & Isolation Multi-Tenant (Core)**
  * Issue #1 : Initialisation du Projet & Configuration Multi-Environnement
  * Issue #2 : Système d'Isolation Multi-Tenant (Core & Mixins)
* **Phase 2 : Authentification & Gestion des Comptes (Accounts & Tenants)**
  * Issue #3 : Création des Établissements (Tenants) & Customisation Visuelle
  * Issue #4 : Gestion des Utilisateurs, Rôles et Authentification
* **Phase 5 : Gestion des Clients (Clients App)**
  * Issue #5 : Module de Gestion des Clients & Recherche par Téléphone
* **Phase 6 : Gestion des Commandes & Cycle de Vie (Orders App)**
  * Issue #6 : Module d'Enregistrement des Commandes et Articles
  * Issue #7 : Cycle de Vie de la Commande & Génération de Ticket Unique
* **Phase 7 : Gestion des Paiements & Créances (Payments App)**
  * Issue #8 : Enregistrement des Règlements (Espèces, Crédit) & Calculs de Solde
  * Issue #9 : Intégration Passerelle Mobile Money (Orange Money / Moov Money)
* **Phase 8 : Notifications & Services Tiers (Notifications)**
  * Issue #10 : Système de Notifications SMS Automatiques et Relances
* **Phase 9 : Logistique, Livraison & Commande en Ligne (Optional/MVP extended)**
  * Issue #11 : Demande de Collecte/Livraison en Ligne & Attribution Coursier
* **Phase 10 : Pilotage & Dashboard (Dashboard & Analytics)**
  * Issue #12 : Tableau de Bord Gérant & Consolidation des Données du Jour

---

## Phase 1 : Socle Technique & Isolation Multi-Tenant (Core)

### Issue #1 : Initialisation du Projet & Configuration Multi-Environnement
* **Domaine** : DevOps, Base de données
* **Description** : Mettre en place le dépôt, configurer Django avec le support de variables d'environnement distantes via `django-environ`, et brancher la base de données PostgreSQL (Neon).
* **Spécifications Techniques** :
  * **Database** : PostgreSQL (Neon) avec support du pooler PgBouncer dans `DATABASE_URL` [23]. Configuration de `dev.py` pour pointer vers une branche de dev Neon gratuite [23].
  * **Backend** : Django + DRF, structure modulaire par domaine d'application [21]. Fichier `.env` pour stocker les variables d'environnement de manière sécurisée [23].
* **Tâches à réaliser** :
  1. Initialiser le projet Django avec la structure suivante :
     ```text
     config/
       settings/
         base.py
         dev.py
         prod.py
     ```
  2. Installer `django-environ`, `psycopg2-binary`, `django-cors-headers`, `djangorestframework` et `drf-spectacular` [15, 23, 24].
  3. Configurer `config/settings/base.py` pour lire la configuration de la base de données via `environ.Env()`.
  4. Configurer `drf-spectacular` pour générer automatiquement la documentation OpenAPI [24].
* **Critères d'acceptation** :
  * Les commandes `python manage.py migrate` s'exécutent avec succès sur la base de données de développement (Neon branch) [23].
  * L'URL `/api/schema/swagger-ui/` est accessible et affiche une documentation vierge.

---

### Issue #2 : Système d'Isolation Multi-Tenant (Core & Mixins)
* **Domaine** : Backend (Core / Sécurité), Base de données
* **Description** : Concevoir la brique centrale d'isolation de données. Chaque pressing (tenant) doit voir uniquement ses propres ressources [16, 22].
* **Spécifications Techniques** :
  * **Database** : Préparer l'approche multi-tenant single-database. Chaque modèle métier (Client, Commande, Paiement, Coursier, User) contiendra une clé étrangère (`FK`) vers l'entité `Pressing` [22].
  * **Backend** : 
    * Créer l'application Django `core/`.
    * Implémenter un `TenantScopedQuerysetMixin` dans `core/mixins.py` pour filtrer automatiquement les querysets sur `request.user.pressing` [22].
    * Implémenter une permission personnalisée `IsSameTenant` dans `core/permissions.py` qui vérifie que l'objet demandé appartient bien au pressing de l'utilisateur connecté [22].
* **Tâches à réaliser** :
  1. Créer le module `core/` sans modèle de données direct, mais avec `mixins.py` et `permissions.py`.
  2. Implémenter le `TenantScopedQuerysetMixin` :
     ```python
     # core/mixins.py
     class TenantScopedQuerysetMixin:
         def get_queryset(self):
             # Filtre automatiquement selon le pressing de l'utilisateur connecté
             return super().get_queryset().filter(pressing=self.request.user.pressing)
     ```
  3. Implémenter `IsSameTenant` pour sécuriser les requêtes individuelles (GET detail, PUT, DELETE) [22] :
     ```python
     # core/permissions.py
     from rest_framework import permissions

     class IsSameTenant(permissions.BasePermission):
         def has_object_permission(self, request, view, obj):
             return obj.pressing == request.user.pressing
     ```
* **Critères d'acceptation** :
  * Les tests unitaires valident que le mixin de filtrage restreint correctement les résultats au pressing de l'utilisateur connecté [22, 23].

---

## Phase 2 : Authentification & Gestion des Comptes (Accounts & Tenants)

### Issue #3 : Création des Établissements (Tenants) & Customisation Visuelle
* **Domaine** : Database, API REST, UI/PWA
* **Description** : Permettre l'enregistrement des pressings lors de l'inscription, incluant la configuration de leur marque (logo, couleurs) [6].
* **Spécifications Techniques** :
  * **Database** : Modèle `Pressing` [17] :
    * `id` (UUID), `nom` (VARCHAR), `adresse` (TEXT), `telephone` (VARCHAR), `proprietaire` (VARCHAR), `logo` (IMAGE/URL), `couleur_primaire` (VARCHAR), `couleur_secondaire` (VARCHAR) [17].
  * **Backend** : Application `tenants/` [21]. Créer `models.py`, `serializers.py`, `views.py`, et `urls.py`. Point de terminaison public d'inscription `/api/v1/tenants/register/` permettant de créer simultanément le pressing et son utilisateur gérant.
  * **UI / PWA** : Écran d'inscription simple en français permettant de renseigner le nom du pressing, télécharger un logo et sélectionner des couleurs primaires/secondaires [12, 14]. Stockage local des paramètres visuels pour les appliquer à l'interface [12].
* **Tâches à réaliser** :
  1. Développer le modèle `Pressing` dans `tenants/models.py`.
  2. Créer un sérialiseur `PressingSerializer` gérant les champs requis (dont logo et codes hexadécimaux de couleur) [17].
  3. Mettre en place la logique d'application dynamique du thème UI dans la PWA (variables CSS basées sur les couleurs récupérées de l'API) [12].
* **Critères d'acceptation** :
  * L'inscription d'un pressing renvoie un statut HTTP 201 avec les détails de l'établissement.
  * L'interface PWA change ses couleurs de marque dynamiquement selon les couleurs définies dans le modèle du pressing connecté [12].

---

### Issue #4 : Gestion des Utilisateurs, Rôles et Authentification
* **Domaine** : Database, API REST, UI/PWA
* **Description** : Implémenter le système de connexion et la gestion des rôles ("Gérant" et "Employé") [8, 12].
* **Spécifications Techniques** :
  * **Database** : Modèle `User` héritant de `AbstractUser` [17] :
    * `telephone` (VARCHAR - identifiant unique pour simplifier l'accès mobile), `role` (CHOICES: 'GERANT', 'EMPLOYE'), `pressing` (FK vers Pressing, nullable uniquement pour les super-admins) [17].
  * **Backend** : Application `accounts/` séparée de `tenants/` [21]. Utiliser JWT (JSON Web Tokens) via `djangorestframework-simplejwt` pour sécuriser l'API REST.
  * **UI / PWA** : Formulaire de connexion sur smartphone (avec mémorisation de session locale) [14]. Contrôle d'affichage de l'interface en fonction du rôle (le menu financier/rapport n'est visible que pour le rôle Gérant) [12].
* **Tâches à réaliser** :
  1. Créer `accounts/models.py` avec le modèle `User` personnalisé.
  2. Configurer JWT dans `settings/base.py` pour utiliser le numéro de téléphone et le mot de passe pour l'authentification.
  3. Développer les endpoints `/api/v1/accounts/login/` et `/api/v1/accounts/employees/` (pour que le gérant puisse ajouter un employé au pressing connecté) [9].
  4. Mettre en place un middleware d'authentification ou configurer DRF pour exiger l'authentification par défaut sur tous les endpoints sauf l'inscription.
* **Critères d'acceptation** :
  * Un employé se connecte via son numéro de téléphone et son mot de passe.
  * Les requêtes API HTTP sans jeton d'authentification valide renvoient une erreur 401 Unauthorized.
  * Un employé connecté ne peut pas accéder aux endpoints financiers du gérant (contrôle basé sur le rôle DRF / permissions de groupe) [12].

---

## Phase 3 : Gestion des Clients (Clients App)

### Issue #5 : Module de Gestion des Clients & Recherche par Téléphone
* **Domaine** : Database, API REST, UI/PWA
* **Description** : Développer le répertoire client. L'enregistrement au comptoir nécessite une recherche rapide par numéro de téléphone [10].
* **Spécifications Techniques** :
  * **Database** : Modèle `Client` [17] :
    * `id` (UUID), `nom` (VARCHAR), `telephone` (VARCHAR), `pressing` (FK vers Pressing) [17]. Clé unique composite sur (telephone, pressing) pour qu'un client soit unique au sein d'un même pressing.
  * **Backend** : Application `clients/` [21]. Endpoint GET `/api/v1/clients/?search=<telephone>` héritant de `TenantScopedQuerysetMixin` [22].
  * **UI / PWA** : Formulaire de saisie d'un nouveau client et champ de recherche dynamique en haut de l'écran de caisse.
* **Tâches à réaliser** :
  1. Créer l'application `clients/` et définir le modèle `Client`.
  2. Implémenter le sérialiseur `ClientSerializer` et le viewset associé configuré avec `TenantScopedQuerysetMixin` [22].
  3. Ajouter un index d'indexation sur le champ `telephone` dans PostgreSQL pour accélérer les recherches.
  4. Coder la logique UI : lors de la saisie d'un numéro de téléphone, l'application recherche le client localement ou via l'API. S'il n'existe pas, un bouton de création rapide de fiche client apparaît [10].
* **Critères d'acceptation** :
  * La recherche par téléphone renvoie instantanément la fiche du client (temps de réponse API < 100ms).
  * L'isolation multi-tenant est respectée : le pressing A ne peut pas rechercher ni visualiser les clients du pressing B [20, 22].

---

## Phase 4 : Gestion des Commandes & Cycle de Vie (Orders App)

### Issue #6 : Module d'Enregistrement des Commandes et Articles
* **Domaine** : Database, API REST, UI/PWA
* **Description** : Implémenter la saisie d'une commande par un employé au comptoir avec sélection d'articles et de types de vêtements [9].
* **Spécifications Techniques** :
  * **Database** : Modèles `Commande` et `ArticleCommande` (relation One-to-Many) [17] :
    * `Commande` : `id` (UUID), `client` (FK Client), `pressing` (FK Pressing), `statut` (VARCHAR, defaut 'RECU'), `canal` (VARCHAR, 'COMPTOIR'/'EN_LIGNE'), `date_depot` (DATETIME), `date_retrait_prevue` (DATETIME), `montant_total` (DECIMAL) [17].
    * `ArticleCommande` : `id`, `commande` (FK Commande), `type_vetement` (VARCHAR, ex: Pantalon, Chemise), `quantite` (INTEGER), `prix_unitaire` (DECIMAL) [17].
  * **Backend** : Application `orders/` [21]. Sérialiseur imbriqué (`CommandeSerializer` gérant en écriture/lecture les `ArticleCommande`).
  * **UI / PWA** : Écran d'enregistrement d'une commande au comptoir. L'employé sélectionne le client, ajoute les articles (avec des boutons "+" et "-" simples), indique la date de retrait prévue et valide [5].
* **Tâches à réaliser** :
  1. Créer l'application `orders/` et déclarer les modèles `Commande` et `ArticleCommande`.
  2. Implémenter la logique de création transactionnelle dans le sérialiseur (redéfinir la méthode `create()` pour sauvegarder la commande et ses articles de manière atomique) :
     ```python
     @transaction.atomic
     def create(self, validated_data):
         # extraction et création des articles
     ```
  3. Concevoir l'interface de saisie d'articles optimisée pour écran mobile d'entrée de gamme [14].
* **Critères d'acceptation** :
  * L'enregistrement d'une commande complète s'effectue en moins de 5 interactions sur la PWA [14, 20].
  * Si la base de données échoue à créer un article, la commande globale n'est pas enregistrée (rollback transactionnel).

---

### Issue #7 : Cycle de Vie de la Commande & Génération de Ticket Unique
* **Domaine** : Logiciels (Services), API REST, UI/PWA
* **Description** : Gérer le cycle de statut d'une commande (`Reçu` ➔ `En traitement` ➔ `Prêt` ➔ `Livré`) et générer un numéro de ticket de commande unique et court pour le client [5, 9].
* **Spécifications Techniques** :
  * **Backend** :
    * Implémenter une fonction de génération de ticket (ex: Format court "TX-2608-001" réinitialisé mensuellement) dans un module `services.py` au sein de l'application `orders/` pour séparer la logique de la vue [21].
    * Endpoint PATCH `/api/v1/orders/<id>/update_status/` permettant de faire progresser le statut [9].
  * **UI / PWA** : 
    * Vue de liste des commandes en attente avec filtres par statut.
    * Affichage du reçu/ticket optimisé pour impression thermique (format 58mm ou 80mm) ou partage rapide (WhatsApp / SMS) [6].
* **Tâches à réaliser** :
  1. Écrire le générateur de ticket séquentiel dans `orders/services.py` [21].
  2. Ajouter des validations pour s'assurer que le cycle de statut est respecté (ex: on ne peut pas livrer une commande qui n'est pas marquée comme prête).
  3. Intégrer un template HTML/CSS épuré imprimable via l'API Web Print du navigateur mobile pour le ticket client [6].
* **Critères d'acceptation** :
  * Un numéro de ticket unique est généré automatiquement lors de la création d'une commande [9].
  * La modification du statut d'une commande met à jour instantanément la liste des commandes en attente sur l'écran de l'employé.

---

## Phase 5 : Gestion des Paiements & Créances (Payments App)

### Issue #8 : Enregistrement des Règlements (Espèces, Crédit) & Calculs de Solde
* **Domaine** : Database, Logiciels (Services), API REST, UI/PWA
* **Description** : Suivre les règlements financiers au comptoir. Gérer les encaissements totaux, partiels, ou les commandes à crédit, et calculer le solde des créances clients [6, 10].
* **Spécifications Techniques** :
  * **Database** : Modèle `Paiement` [17] :
    * `id` (UUID), `commande` (FK Commande), `montant` (DECIMAL), `mode` (CHOICES: 'ESPECES', 'MOBILE_MONEY', 'CREDIT'), `date` (DATETIME), `statut` (CHOICES: 'PAYE', 'PARTIEL', 'CREDIT') [17].
  * **Backend** : Application `payments/` [21]. 
    * Créer `payments/services.py` pour centraliser le calcul du montant total payé par commande et le solde restant dû par un client donné [21].
    * Le calcul du solde dû (créances) doit consolider l'historique de toutes les commandes du client [10].
  * **UI / PWA** : Écran d'encaissement lors de la saisie de commande. Affichage proéminent du "Reste à payer" et de l'historique des créances sur la fiche client [10].
* **Tâches à réaliser** :
  1. Développer l'application `payments/` avec le modèle `Paiement` [17, 21].
  2. Coder la méthode `get_client_balance(client_id)` dans `payments/services.py` [21].
  3. Mettre à jour l'état de la commande (`Commande.statut_paiement`) lors de chaque ajout de transaction sur celle-ci.
* **Critères d'acceptation** :
  * Une commande à crédit (montant payé = 0) est correctement identifiée et le montant s'ajoute immédiatement à la dette globale dans la fiche du client [10].
  * Le gérant peut lister à tout moment tous les clients ayant un solde de créance débiteur supérieur à 0 [11].

---

### Issue #9 : Intégration Passerelle Mobile Money (Orange Money / Moov Money)
* **Domaine** : API REST, Passerelles externes
* **Description** : Implémenter l'intégration avec les API locales d'Orange Money et Moov Money pour initier des demandes de paiement en ligne (Push USSD/STK Push) et recevoir les webhooks de confirmation [14, 15].
* **Spécifications Techniques** :
  * **Backend** : Créer l'application `payments_gateway/` séparée de `payments/` [21].
    * `payments_gateway/` gère les appels d'API fragiles vers les opérateurs burkinabés [15, 21].
    * Endpoint public non authentifié de réception de webhook : `/api/v1/payments-gateway/webhook/<operator>/` gérant la validation de signature pour éviter les fraudes.
    * Sur réception de la confirmation de l'opérateur, appeler la logique métier interne de `payments/services.py` pour enregistrer la transaction payée de manière sécurisée [14].
* **Tâches à réaliser** :
  1. Créer l'application `payments_gateway/` [21].
  2. Implémenter les clients d'API HTTP pour initier un paiement en ligne (Orange / Moov) à partir du numéro de téléphone du client [14, 15].
  3. Développer les vues de webhook pour intercepter le statut de paiement envoyé par les serveurs des opérateurs [14, 15].
* **Critères d'acceptation** :
  * Le déclenchement d'un paiement mobile money initie une requête vers la passerelle externe [14, 15].
  * L'appel réussi du webhook simulant un paiement valide marque automatiquement la commande associée comme "Payée" et met à jour l'historique des paiements de celle-ci.

---

## Phase 6 : Notifications & Services Tiers (Notifications)

### Issue #10 : Système de Notifications SMS Automatiques et Relances
* **Domaine** : Logiciels (Services), API REST
* **Description** : Envoyer un SMS automatique au client burkinabé lorsque son linge est prêt ou pour le relancer en cas d'oubli prolongé [4, 11].
* **Spécifications Techniques** :
  * **Backend** : Application `notifications/` [21].
    * Connexion à une passerelle SMS locale ou un agrégateur régional [15].
    * Préparer `notifications/tasks.py` avec Celery pour exécuter les envois de SMS en tâche de fond asynchrone sans bloquer la requête HTTP de mise à jour du statut de la commande [24].
    * Script de relance automatique (commande planifiée cron/beat) ciblant les vêtements prêts non retirés depuis plus de 7 jours [11].
* **Tâches à réaliser** :
  1. Créer l'application `notifications/` [21].
  2. Développer le client HTTP de la passerelle SMS d'envoi.
  3. Écrire le récepteur de signal Django (`post_save` sur le modèle `Commande`) : si le statut passe à `PRÊT`, une notification SMS est déclenchée [11, 20].
  4. Mettre en place la tâche planifiée pour relancer les clients ayant des vêtements oubliés [11].
* **Critères d'acceptation** :
  * Le passage d'une commande au statut « Prêt » génère et envoie effectivement une requête d'envoi de SMS avec le nom du pressing et le numéro de ticket court [11, 20].

---

## Phase 7 : Logistique, Livraison & Commande en Ligne (Optional/MVP extended)

### Issue #11 : Demande de Collecte/Livraison en Ligne & Attribution Coursier
* **Domaine** : Database, API REST, UI/PWA
* **Description** : Permettre aux clients finaux de demander une collecte de linge à domicile et aux gérants d'assigner un coursier pour le transport [6, 13].
* **Spécifications Techniques** :
  * **Database** : Modèle `Coursier` [17] :
    * `id` (UUID), `nom` (VARCHAR), `telephone` (VARCHAR), `pressing` (FK Pressing) [17].
  * **Backend** : 
    * Ajout des champs logistiques sur `Commande` : `adresse_collecte` (TEXT/GPS), `statut_livraison` (CHOICES: 'A_COLLECTER', 'COLLECTE', 'A_LIVRER', 'LIVRE'), `coursier_assigne` (FK Coursier) [17].
    * Vues dédiées pour les coursiers : GET `/api/v1/orders/my-deliveries/` qui filtre les commandes par `coursier_assigne=request.user` [8].
  * **UI / PWA** : 
    * Formulaire client de demande de collecte avec saisie d'adresse textuelle et optionnelle de coordonnées GPS (utilisation de l'API de géolocalisation HTML5 de l'appareil mobile) [13, 15].
    * Interface mobile allégée pour le coursier, listant uniquement ses livraisons du jour et lui permettant de marquer un colis comme "Livré" en une interaction [8, 14].
* **Tâches à réaliser** :
  1. Créer le modèle `Coursier` et migrer la base de données PostgreSQL [17].
  2. Implémenter les permissions spécifiques pour que le coursier ne puisse voir que les commandes qui lui sont assignées [8].
  3. Développer l'interface cartographique simplifiée ou de saisie d'adresse dans le parcours client en ligne [13, 15].
* **Critères d'acceptation** :
  * Une demande de collecte en ligne apparaît sur le tableau de bord du gérant qui peut lui affecter manuellement un coursier [7, 13].
  * Le coursier connecté sur son smartphone ne voit que les commandes qui lui sont affectées et peut modifier son état de livraison [8].

---

## Phase 8 : Pilotage & Dashboard (Dashboard & Analytics)

### Issue #12 : Tableau de Bord Gérant & Consolidation des Données du Jour
* **Domaine** : API REST, UI/PWA
* **Description** : Fournir une vue globale des performances de l'activité du jour, de la semaine ou du mois pour le gérant du pressing [6, 11].
* **Spécifications Techniques** :
  * **Backend** : Endpoint GET `/api/v1/dashboard/summary/` accessible uniquement aux utilisateurs ayant le rôle "Gérant" [12]. 
    * Requêtes d'agrégation SQL (Django `django.db.models.Sum`, `Count`) pour compiler : le chiffre d'affaires cumulé du jour, le nombre de commandes en cours, l'encours total des créances clients et la liste des commandes non réclamées depuis longtemps [6, 11].
  * **UI / PWA** : Page d'accueil pour le profil Gérant présentant des indicateurs clés (KPIs) graphiques clairs et textuels, optimisée pour un chargement rapide [11, 14].
* **Tâches à réaliser** :
  1. Développer l'API d'agrégation financière et opérationnelle dans l'application `dashboard/` (ou au sein d'un service dans `orders/services.py`).
  2. Sécuriser l'endpoint avec une permission DRF spécifique `IsGerant`.
  3. Concevoir l'interface de reporting sur la PWA avec un design épuré, réduisant le volume de données chargées pour économiser les données mobiles [14].
* **Critères d'acceptation** :
  * Le tableau de bord affiche en temps réel le chiffre d'affaires du jour consolidé à partir de tous les paiements enregistrés [11, 20].
  * Les statistiques financières ne sont jamais chargées ni accessibles par un utilisateur ayant uniquement le rôle Employé/Caissier [12].
