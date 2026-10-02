from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Ticket, Retrait, calculer_solde
from .utils import generate_qr_bytes, build_ticket_pdf
from .payment_constants import moyens_paiement_pour


@login_required
def spectateur_dashboard(request):
    aujourdhui = timezone.now().date()
    tickets = list(Ticket.objects.filter(spectateur=request.user).select_related(
        "ticket_type", "ticket_type__event").order_by("-ticket_type__event__date_debut"))

    a_venir = sorted([t for t in tickets if t.event.date_fin >= aujourdhui],
                      key=lambda t: t.event.date_debut)
    ticket_en_cours = a_venir[0] if a_venir else None

    historique = [t for t in tickets if t.id != (ticket_en_cours.id if ticket_en_cours else None)]

    context = {
        "ticket_en_cours": ticket_en_cours,
        "historique": historique,
        "total": len(tickets),
    }
    return render(request, "tickets/spectateur_dashboard.html", context)


@login_required
def detail(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, spectateur=request.user)
    return render(request, "tickets/ticket_detail.html", {"ticket": ticket})


@login_required
def qr_image(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, spectateur=request.user)
    return HttpResponse(generate_qr_bytes(ticket.qr_payload), content_type="image/png")


@login_required
def ticket_pdf(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, spectateur=request.user)
    pdf_bytes = build_ticket_pdf(ticket)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="billet-{ticket.code}.pdf"'
    return response


@login_required
def retraits(request):
    if not request.user.is_organisateur:
        messages.error(request, "Cette page est réservée aux organisateurs.")
        return redirect("dashboard_redirect")

    solde = calculer_solde(request.user)
    moyens = moyens_paiement_pour(request.user.pays)
    historique = Retrait.objects.filter(organisateur=request.user)

    if request.method == "POST":
        moyen = request.POST.get("moyen_paiement")
        destination = request.POST.get("destination", "").strip()
        try:
            montant = Decimal(request.POST.get("montant", "0"))
        except Exception:
            montant = Decimal("0")

        codes_valides = {code for code, _, _ in moyens}
        if montant <= 0:
            messages.error(request, "Le montant doit être supérieur à zéro.")
        elif montant > solde:
            messages.error(request, "Le montant dépasse ton solde disponible.")
        elif moyen not in codes_valides:
            messages.error(request, "Moyen de paiement invalide pour ton pays.")
        else:
            Retrait.objects.create(
                organisateur=request.user, montant=montant,
                moyen_paiement=moyen, destination=destination,
                statut=Retrait.Statut.REUSSI,
            )
            messages.success(request, f"Retrait de {montant:.0f} FCFA envoyé avec succès ✅")
            return redirect("tickets:retraits")

    context = {
        "solde": solde,
        "moyens": moyens,
        "historique": historique,
        "commission_pourcentage": settings.PLATFORM_COMMISSION_PERCENT,
    }
    return render(request, "tickets/retraits.html", context)
