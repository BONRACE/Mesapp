from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import organizer_required

from .catalog import channels_for_country
from .forms import PayoutMethodForm
from .models import PayoutMethod


def _set_default(method):
    """Un seul moyen par défaut par organisateur."""
    with transaction.atomic():
        PayoutMethod.objects.filter(organizer=method.organizer).exclude(pk=method.pk).update(is_default=False)
        if not method.is_default:
            method.is_default = True
            method.save(update_fields=["is_default"])


@organizer_required
def method_list(request):
    return render(request, "payouts/list.html", {
        "methods": request.user.payout_methods.all(),
        "channels": channels_for_country(request.user.country).values(),
    })


def _save(request, instance=None):
    form = PayoutMethodForm(request.POST or None, instance=instance, organizer=request.user)
    if request.method == "POST" and form.is_valid():
        method = form.save(commit=False)
        method.organizer = request.user
        method.save()
        if form.cleaned_data.get("is_default") or request.user.payout_methods.count() == 1:
            _set_default(method)
        messages.success(request, "Moyen de retrait enregistré.")
        return redirect("payouts:list"), form
    return None, form


@organizer_required
def method_create(request):
    resp, form = _save(request)
    return resp or render(request, "payouts/form.html", {"form": form, "title": "Ajouter un moyen de retrait"})


@organizer_required
def method_edit(request, pk):
    method = get_object_or_404(PayoutMethod, pk=pk, organizer=request.user)
    resp, form = _save(request, method)
    return resp or render(request, "payouts/form.html", {"form": form, "title": "Modifier le moyen de retrait", "method": method})


@organizer_required
@require_POST
def method_default(request, pk):
    _set_default(get_object_or_404(PayoutMethod, pk=pk, organizer=request.user))
    messages.success(request, "Moyen par défaut mis à jour.")
    return redirect("payouts:list")


@organizer_required
@require_POST
def method_delete(request, pk):
    method = get_object_or_404(PayoutMethod, pk=pk, organizer=request.user)
    was_default = method.is_default
    method.delete()                       # l'historique des retraits garde son instantané (libellé + compte masqué)
    if was_default:
        nxt = request.user.payout_methods.first()
        if nxt:
            _set_default(nxt)
    messages.success(request, "Moyen de retrait supprimé.")
    return redirect("payouts:list")
