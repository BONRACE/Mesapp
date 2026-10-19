"""Rendu PDF (WeasyPrint) des tickets et cartes de visite.

WeasyPrint nécessite Pango (voir README). Si la bibliothèque système manque,
on renvoie une erreur explicite plutôt qu'un crash.
"""
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string


class PdfIndisponible(RuntimeError):
    pass


def rendre_pdf(template, contexte, nom_fichier):
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise PdfIndisponible(
            "La génération PDF requiert WeasyPrint et ses dépendances système (Pango)."
        ) from exc
    html = render_to_string(template, contexte)
    pdf = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    reponse = HttpResponse(pdf, content_type="application/pdf")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    return reponse
