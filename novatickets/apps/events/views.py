from django.contrib import messages
from django.http import Http404
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.decorators import organisateur_requis
from apps.accounts.models import Role
from apps.tickets.models import Ticket

from .forms import EvenementForm, TypeTicketFormSet
from .models import Evenement


def liste_publique(request):
    """Vitrine des événements publiés, à venir en premier."""
    aujourdhui = timezone.localdate()
    q = request.GET.get("q", "").strip()
    qs = Evenement.objects.filter(statut=Evenement.Statut.PUBLIE, date_fin__gte=aujourdhui)
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(ville__icontains=q) | Q(lieu__icontains=q))
    return render(request, "events/liste.html", {"evenements": qs.select_related("organisateur"), "q": q})


def detail(request, slug):
    evenement = get_object_or_404(
        Evenement.objects.select_related("organisateur__profil_organisateur"),
        slug=slug,
    )
    # Un brouillon n'est visible que de son organisateur.
    if evenement.statut != Evenement.Statut.PUBLIE:
        if not (request.user.is_authenticated and request.user == evenement.organisateur):
            raise Http404("Événement introuvable.")
    types = evenement.types_tickets.all()
    peut_acheter = request.user.is_authenticated and not (
        request.user.est_organisateur and evenement.organisateur_id == request.user.id
    )
    return render(request, "events/detail.html", {
        "evenement": evenement,
        "types": types,
        "peut_acheter": peut_acheter and evenement.achats_ouverts,
        "est_proprietaire": request.user.is_authenticated and request.user == evenement.organisateur,
    })


@organisateur_requis
def dashboard(request):
    mes = Evenement.objects.filter(organisateur=request.user)
    tickets = Ticket.objects.filter(type_ticket__evenement__organisateur=request.user, commande__statut="paye")
    stats = {
        "evenements_actifs": mes.filter(statut=Evenement.Statut.PUBLIE, date_fin__gte=timezone.localdate()).count(),
        "tickets_vendus": tickets.count(),
        "ventes_brutes": tickets.aggregate(s=Sum("prix_unitaire"))["s"] or 0,
        "revenus_nets": request.user.total_revenus_nets,
        "solde": request.user.solde_disponible,
    }
    evenements = mes.annotate(nb_types=Count("types_tickets")).order_by("-cree_le")[:8]
    return render(request, "events/dashboard_organisateur.html", {"stats": stats, "evenements": evenements})


@organisateur_requis
def mes_evenements(request):
    return render(request, "events/mes_evenements.html", {"evenements": Evenement.objects.filter(organisateur=request.user)})


def _formset(request, instance=None):
    return TypeTicketFormSet(request.POST or None, instance=instance, prefix="types")


@organisateur_requis
@require_http_methods(["GET", "POST"])
def creer(request):
    form = EvenementForm(request.POST or None, request.FILES or None)
    formset = _formset(request)
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            evenement = form.save(commit=False)
            evenement.organisateur = request.user
            evenement.statut = Evenement.Statut.BROUILLON
            try:
                evenement.clean()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                evenement.save()
                formset.instance = evenement
                formset.save()
                if "publier" in request.POST:
                    evenement.statut = Evenement.Statut.PUBLIE
                    evenement.save(update_fields=["statut"])
                    messages.success(request, f"« {evenement.nom} » est publié.")
                else:
                    messages.success(request, "Événement enregistré en brouillon.")
                return redirect("events:mes_evenements")
    return render(request, "events/formulaire.html", {"form": form, "formset": formset, "titre": "Créer un événement"})


@organisateur_requis
@require_http_methods(["GET", "POST"])
def modifier(request, pk):
    evenement = get_object_or_404(Evenement, pk=pk, organisateur=request.user)
    form = EvenementForm(request.POST or None, request.FILES or None, instance=evenement)
    formset = _formset(request, instance=evenement)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        evenement = form.save()
        formset.save()
        messages.success(request, "Événement mis à jour.")
        return redirect("events:mes_evenements")
    return render(request, "events/formulaire.html", {"form": form, "formset": formset, "titre": "Modifier l'événement", "evenement": evenement})


@organisateur_requis
@require_POST
def publier(request, pk):
    evenement = get_object_or_404(Evenement, pk=pk, organisateur=request.user)
    if not evenement.types_tickets.exists():
        messages.error(request, "Ajoutez au moins un type de ticket avant de publier.")
        return redirect("events:mes_evenements")
    evenement.statut = (
        Evenement.Statut.BROUILLON if evenement.statut == Evenement.Statut.PUBLIE else Evenement.Statut.PUBLIE
    )
    evenement.save(update_fields=["statut"])
    messages.success(request, f"« {evenement.nom} » est maintenant {evenement.get_statut_display().lower()}.")
    return redirect("events:mes_evenements")
