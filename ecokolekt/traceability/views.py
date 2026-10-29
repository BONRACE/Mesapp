from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BatchEventForm, allowed_event_types
from .models import WasteBatch
from .services import batch_from_token, qr_png, record_event, verify_chain


@login_required
def batch_list(request):
    batches = (
        WasteBatch.objects.filter(Q(producer=request.user) | Q(holder=request.user))
        .select_related("category")
        .distinct()
    )
    return render(request, "traceability/batch_list.html", {"batches": batches})


@login_required
def batch_detail(request, pk):
    batch = get_object_or_404(WasteBatch.objects.select_related("category", "producer"), pk=pk)
    if request.user not in (batch.producer, batch.holder) and not request.user.is_staff:
        raise Http404
    return render(request, "traceability/batch_detail.html", {
        "batch": batch,
        "events": batch.events.select_related("actor"),
        "chain_ok": verify_chain(batch),
        "form": BatchEventForm(user=request.user),
        "can_record": bool(allowed_event_types(request.user)),
    })


@login_required
def batch_qr(request, pk):
    batch = get_object_or_404(WasteBatch, pk=pk)
    if request.user not in (batch.producer, batch.holder):
        raise Http404
    return HttpResponse(qr_png(batch), content_type="image/png")


def scan(request, token):
    """Page publique issue du QR : provenance lisible sans données personnelles."""
    batch = batch_from_token(token)
    if batch is None:
        raise Http404
    if request.method == "POST" and request.user.is_authenticated:
        return _record_from_scan(request, batch, token)
    return render(request, "traceability/scan.html", {
        "batch": batch,
        "events": batch.events.all(),
        "chain_ok": verify_chain(batch),
        "form": BatchEventForm(user=request.user),
    })


def _record_from_scan(request, batch, token):
    form = BatchEventForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "Action non autorisée pour votre rôle.")
        return redirect("traceability:scan", token=token)
    record_event(
        batch, request.user, form.cleaned_data["event_type"],
        latitude=form.cleaned_data.get("latitude"),
        longitude=form.cleaned_data.get("longitude"),
        note=form.cleaned_data["note"],
    )
    messages.success(request, "Événement enregistré dans la chaîne de traçabilité.")
    return redirect("traceability:scan", token=token)


@login_required
@require_POST
def batch_event(request, pk):
    batch = get_object_or_404(WasteBatch, pk=pk)
    form = BatchEventForm(request.POST, user=request.user)
    if form.is_valid():
        record_event(
            batch, request.user, form.cleaned_data["event_type"],
            latitude=form.cleaned_data.get("latitude"),
            longitude=form.cleaned_data.get("longitude"),
            note=form.cleaned_data["note"],
        )
        messages.success(request, "Événement enregistré.")
    else:
        messages.error(request, "Action non autorisée pour votre rôle.")
    return redirect("traceability:detail", pk=batch.pk)
