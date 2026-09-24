from django.shortcuts import render, redirect
from django.utils import timezone
from events.models import Event


def home(request):
    aujourdhui = timezone.now().date()
    events = Event.objects.filter(statut=Event.Statut.PUBLIE,
                                   date_fin__gte=aujourdhui)[:6]
    return render(request, "home.html", {"events": events})


def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_organisateur:
        return redirect("events:organisateur_dashboard")
    return redirect("tickets:spectateur_dashboard")
