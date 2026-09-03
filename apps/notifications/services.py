"""Wrapper autour de la passerelle SMS (agrégateur local/régional) — Issue #10.

Les vues et tâches ne parlent jamais directement à l'API de l'agrégateur :
elles passent par ce module, seul endroit à modifier si l'agrégateur change.
"""
