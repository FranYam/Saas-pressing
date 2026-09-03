"""Modèles orders — implémentés aux Issues #6-#7.

Commande : UUID, ticket_number unique, FK client, statut
(RECU / EN_TRAITEMENT / PRET / LIVRE), canal, dates, total, FK pressing.
ArticleCommande : FK commande, type_vetement, quantité, prix unitaire.
"""
