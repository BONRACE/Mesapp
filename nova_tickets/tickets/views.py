from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from .models import Ticket
from .utils import generate_qr_bytes, build_ticket_pdf


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
