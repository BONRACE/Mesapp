"""Validation des images téléversées : taille du fichier et dimensions (évite les « bombes de décompression »)."""
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_image_upload(f):
    max_bytes = getattr(settings, "MAX_IMAGE_UPLOAD_BYTES", 3 * 1024 * 1024)
    if f.size > max_bytes:
        raise ValidationError(f"Image trop lourde ({f.size // 1024} Ko) : {max_bytes // (1024 * 1024)} Mo maximum.")
    img = getattr(f, "image", None)
    side = getattr(settings, "MAX_IMAGE_PIXELS_SIDE", 6000)
    if img is not None and (img.width > side or img.height > side):
        raise ValidationError(f"Image trop grande : {side} pixels maximum de chaque côté.")


def harden_image_fields(form, *names):
    """Ajoute validate_image_upload aux champs image du formulaire (s'ils existent)."""
    for name in names:
        field = form.fields.get(name)
        if field is not None and validate_image_upload not in field.validators:
            field.validators.append(validate_image_upload)
