from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import EventForm, TicketFormSet
from .models import Event


def organizer_required(view):
    @login_required
    def wrapper(request, *a, **kw):
        if not request.user.is_organisateur:
            raise PermissionDenied
        return view(request, *a, **kw)
    wrapper.__name__ = view.__name__
    return wrapper


def detail(request, slug):
    event = get_object_or_404(Event.objects.prefetch_related("ticket_types"), slug=slug)
    is_owner = request.user.is_authenticated and event.organizer_id == request.user.id
    if not event.is_published and not is_owner:
        raise PermissionDenied
    return render(request, "events/detail.html", {
        "event": event,
        "is_owner": is_owner,
        "is_organizer": request.user.is_authenticated and request.user.is_organisateur,
    })


@organizer_required
def create(request):
    form = EventForm(request.POST or None, request.FILES or None)
    formset = TicketFormSet(request.POST or None, instance=Event())
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()
            formset.instance = event
            formset.save()
        messages.success(request, "Événement créé. Publiez-le quand vous êtes prêt.")
        return redirect("core:organizer_dashboard")
    return render(request, "events/form.html", {"form": form, "formset": formset, "editing": False})


@organizer_required
def edit(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    form = EventForm(request.POST or None, request.FILES or None, instance=event)
    formset = TicketFormSet(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            form.save()
            formset.save()
        messages.success(request, "Événement mis à jour.")
        return redirect("core:organizer_dashboard")
    return render(request, "events/form.html", {"form": form, "formset": formset, "editing": True, "event": event})


@organizer_required
@require_POST
def toggle_publish(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    if event.is_published:
        event.status = Event.DRAFT
        messages.info(request, "Événement repassé en brouillon.")
    else:
        if not event.ticket_types.exists():
            messages.error(request, "Ajoutez au moins un type de ticket avant de publier.")
            return redirect("core:organizer_dashboard")
        event.status = Event.PUBLISHED
        messages.success(request, "Événement publié : il est visible par tous.")
    event.save(update_fields=["status"])
    return redirect("core:organizer_dashboard")


@organizer_required
@require_POST
def delete(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user)
    if event.orders.filter(status="paid").exists():
        messages.error(request, "Impossible de supprimer un événement avec des ventes.")
    else:
        event.delete()
        messages.success(request, "Événement supprimé.")
    return redirect("core:organizer_dashboard")
