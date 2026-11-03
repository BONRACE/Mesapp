"""Stockage statique avec « cache busting » : chaque fichier est servi avec ?v=<date de modification>.

Évite qu'un navigateur garde une ancienne version de app.css (barre de navigation sans style, etc.)
après une mise à jour du projet.
"""
import os

from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class VersionedStaticStorage(StaticFilesStorage):
    def url(self, name):
        url = super().url(name)
        path = finders.find(name)
        if path and os.path.isfile(path):
            url += ("&" if "?" in url else "?") + "v=%d" % int(os.path.getmtime(path))
        return url
