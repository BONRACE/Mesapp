"""Traçabilité : jetons QR signés, chaîne de hachage des événements, création de lots."""
import hashlib
import io
import secrets

import qrcode
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from .models import BatchStatus, EventType, TrackingEvent, WasteBatch

GENESIS_HASH = "0" * 64

EVENT_STATUS = {
    EventType.PICKED_UP: BatchStatus.COLLECTED,
    EventType.RECEIVED: BatchStatus.AT_CENTER,
    EventType.PROCESSED: BatchStatus.PROCESSED,
    EventType.SOLD: BatchStatus.SOLD,
}


def _new_code():
    return f"EK-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


def _digest(batch_id, previous_hash, event_type, actor_id, occurred_at, note):
    payload = "|".join([str(batch_id), previous_hash, event_type, str(actor_id or ""),
                        occurred_at.isoformat(), note])
    return hashlib.sha256(payload.encode()).hexdigest()


def sign_batch_token(batch):
    """Jeton signé (HMAC) embarqué dans le QR. Falsifier l'UUID invalide la signature."""
    return signing.dumps({"b": str(batch.id)}, salt=settings.QR_SIGNING_SALT, compress=True)


def batch_from_token(token):
    try:
        data = signing.loads(token, salt=settings.QR_SIGNING_SALT)
    except signing.BadSignature:
        return None
    return WasteBatch.objects.filter(pk=data.get("b")).first()


def scan_url(batch):
    return settings.SITE_BASE_URL.rstrip("/") + reverse(
        "traceability:scan", kwargs={"token": sign_batch_token(batch)}
    )


def qr_png(batch):
    buffer = io.BytesIO()
    qrcode.make(scan_url(batch)).save(buffer, format="PNG")
    return buffer.getvalue()


def append_event(batch, event_type, actor=None, latitude=None, longitude=None, note=""):
    last = batch.events.order_by("-occurred_at", "-id").first()
    previous = last.hash if last else GENESIS_HASH
    occurred = timezone.now()
    digest = _digest(batch.id, previous, event_type, actor and actor.pk, occurred, note)
    return TrackingEvent.objects.create(
        batch=batch, actor=actor, event_type=event_type,
        latitude=latitude, longitude=longitude, note=note,
        occurred_at=occurred, previous_hash=previous, hash=digest,
    )


def verify_chain(batch):
    """Recalcule toute la chaîne : retourne False si un événement a été altéré ou supprimé."""
    previous = GENESIS_HASH
    for event in batch.events.order_by("occurred_at", "id"):
        expected = _digest(batch.id, previous, event.event_type, event.actor_id,
                           event.occurred_at, event.note)
        if event.previous_hash != previous or event.hash != expected:
            return False
        previous = event.hash
    return True


def create_batch_from_pickup(pickup, actor):
    site = pickup.site
    batch = WasteBatch.objects.create(
        code=_new_code(),
        producer=pickup.producer,
        pickup=pickup,
        category=pickup.category,
        weight_kg=pickup.actual_kg,
        holder=actor,
        status=BatchStatus.COLLECTED,
    )
    append_event(batch, EventType.CREATED, actor, site.latitude, site.longitude, f"Enlèvement #{pickup.pk}")
    append_event(batch, EventType.PICKED_UP, actor, site.latitude, site.longitude)
    return batch


def record_event(batch, actor, event_type, latitude=None, longitude=None, note=""):
    """Ajoute un événement et met à jour le statut ou le détenteur du lot."""
    event = append_event(batch, event_type, actor, latitude, longitude, note)
    if event_type in EVENT_STATUS:
        batch.status = EVENT_STATUS[event_type]
    if event_type in (EventType.TRANSFERRED, EventType.RECEIVED):
        batch.holder = actor
    batch.save(update_fields=["status", "holder"])
    return event
