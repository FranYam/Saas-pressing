"""Tâches Celery d'envoi SMS — implémentées à l'Issue #10.

Prêt pour le branchement Celery + Redis : les envois partent en tâche de fond
pour ne jamais bloquer la requête HTTP de mise à jour de statut, et un cron
beat relance les clients dont le linge est prêt non retiré depuis 7 jours.
"""
