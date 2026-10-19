from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.decorators import spectateur_requis
from apps.core.pdf import PdfIndisponible, rendre_pdf
from apps.core.qr import qr_svg_data_uri
from apps.events.models import Evenement, TypeTicket
from apps.payments.providers import moyens_pour_pays
from apps.payments.services import PanierItem, creer_commande, lancer_paiement

from .forms import AchatForm, ChoixMoyenForm
from .models import Commande, Ticket


@spectateur_requis
def mes_tickets(request):
    """Dashboard spectateur : tickets détenus, commandes passées et à venir."""
    aujourdhui = timezone.localdate()
    tickets = Ticket.objects.filter(titulaire=request.user, commande__statut="paye").select_related(
        "type_ticket__evenement__organisateur"
    )
    a_venir = [t for t in tickets if t.evenement.date_fin >= aujourdhui]
    passes = [t for t in tickets if t.evenement.date_fin < aujourdhui]
    commandes = Commande.objects.filter(acheteur=request.user).prefetch_related("tickets")
    return render(request, "tickets/mes_tickets.html", {
        "a_venir": a_venir,
        "passes": passes,
        "commandes": commandes,
    })


@spectateur_requis
def ticket_detail(request, reference):
    ticket = get_object_or_404(Ticket.objects.select_related("type_ticket__evenement__organisateur", "titulaire", "commande"), reference=reference)
    # Accès : titulaire, acheteur (réservation pour un ami) ou organisateur de l'événement.
    autorise = request.user in {ticket.titulaire, ticket.commande.acheteur} or request.user == ticket.evenement.organisateur
    if not autorise:
        raise Http404("Ticket introuvable.")
    return render(request, "tickets/ticket.html", {
        "ticket": ticket,
        "qr": qr_svg_data_uri(ticket.reference),
    })


@spectateur_requis
def ticket_pdf(request, reference):
    ticket = get_object_or_404(Ticket.objects.select_related("type_ticket__evenement__organisateur", "titulaire", "commande"), reference=reference)
    autorise = request.user in {ticket.titulaire, ticket.commande.acheteur} or request.user == ticket.evenement.organisateur
    if not autorise:
        raise Http404("Ticket introuvable.")
    try:
        return rendre_pdf("tickets/ticket_pdf.html", {"ticket": ticket, "qr": qr_svg_data_uri(ticket.reference)}, f"ticket-{ticket.reference}.pdf")
    except PdfIndisponible as exc:
        messages.error(request, str(exc))
        return redirect("tickets:ticket", reference=reference)


@spectateur_requis
@require_http_methods(["GET", "POST"])
def acheter(request, slug):
    evenement = get_object_or_404(Evenement, slug=slug, statut=Evenement.Statut.PUBLIE)
    if request.user.est_organisateur and evenement.organisateur_id == request.user.id:
        messages.error(request, "Vous ne pouvez pas acheter de tickets pour vos propres événements.")
        return redirect(evenement.get_absolute_url())
    form = AchatForm(request.POST or None, evenement=evenement, initial={"type_ticket": None})
    if request.method == "POST" and form.is_valid():
        tt = form.cleaned_data["type_ticket"]
        benef = None
        if form.cleaned_data["pour_un_ami"]:
            benef = {
                "prenom": form.cleaned_data["ami_prenom"],
                "nom": form.cleaned_data["ami_nom"],
                "contact": form.cleaned_data["ami_contact"],
                "sexe": form.cleaned_data["ami_sexe"],
            }
        try:
            commande = creer_commande(request.user, [PanierItem(tt, form.cleaned_data["quantite"], benef)], moyen="")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            return redirect("tickets:paiement", reference=commande.reference)
    return render(request, "tickets/acheter.html", {"evenement": evenement, "form": form})


@spectateur_requis
@require_http_methods(["GET", "POST"])
def paiement(request, reference):
    commande = get_object_or_404(Commande, reference=reference, acheteur=request.user)
    if commande.est_payee:
        messages.info(request, "Cette commande est déjà payée.")
        return redirect("tickets:mes_tickets")
    moyens = moyens_pour_pays(request.user.pays)
    form = ChoixMoyenForm(request.POST or None, initial={"telephone_payeur": request.user.telephone_complet})
    if request.method == "POST" and form.is_valid():
        try:
            lancer_paiement(commande, form.cleaned_data["moyen"], form.cleaned_data["telephone_payeur"])
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("tickets:paiement", reference=commande.reference)
        commande.refresh_from_db()
        if commande.est_payee:
            messages.success(request, "Paiement validé ! Vos tickets sont émis et le reçu part par e-mail.")
            return redirect("tickets:mes_tickets")
        messages.error(request, "Le paiement a échoué. Réessayez avec un autre moyen.")
        return redirect("tickets:paiement", reference=commande.reference)
    return render(request, "tickets/paiement.html", {"commande": commande, "moyens": moyens, "form": form})
