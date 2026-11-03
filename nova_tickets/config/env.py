"""Lecture du fichier .env (sans dépendance externe).

Format : une variable par ligne, `NOM=valeur`. Les lignes vides et celles qui commencent par # sont ignorées ;
les guillemets autour de la valeur sont facultatifs. Une variable déjà définie dans l'environnement du système
(serveur, Docker…) l'emporte toujours sur le fichier.
"""
import os
from pathlib import Path


def load_env(path):
    path = Path(path)
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:                      # commentaire en fin de ligne : NOM=valeur  # commentaire
            value = value.split(" #", 1)[0].strip()
        os.environ.setdefault(key.strip(), value)


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "oui", "on"}


def env_int(name, default=0):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]
