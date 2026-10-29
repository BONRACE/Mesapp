from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from operations.models import WasteCategory

from .forms import ListingForm, OrderForm
from .models import Listing, Order
from .services import OutOfStock, cancel_order, create_order


@login_required
def listing_list(request):
    listings = Listing.objects.filter(status=Listing.Status.ACTIVE).select_related("category", "seller")
    category = request.GET.get("categorie")
    query = request.GET.get("q", "").strip()
    if category:
        listings = listings.filter(category__code=category)
    if query:
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query))
    return render(request, "marketplace/listing_list.html", {
        "listings": listings,
        "categories": WasteCategory.objects.all(),
        "current_category": category,
        "query": query,
    })


@login_required
def listing_detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related("category", "seller", "site"), pk=pk)
    return render(request, "marketplace/listing_detail.html", {
        "listing": listing,
        "order_form": OrderForm(),
    })


@role_required("recycler")
def listing_create(request):
    form = ListingForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.seller = request.user
        listing.save()
        messages.success(request, "Offre publiée sur le marché.")
        return redirect("marketplace:mine")
    return render(request, "marketplace/listing_form.html", {"form": form})


@role_required("recycler")
def my_listings(request):
    listings = Listing.objects.filter(seller=request.user).select_related("category")
    return render(request, "marketplace/my_listings.html", {"listings": listings})


@role_required("recycler")
@require_POST
def listing_toggle(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if listing.status == Listing.Status.ACTIVE:
        listing.status = Listing.Status.PAUSED
    elif listing.status == Listing.Status.PAUSED:
        listing.status = Listing.Status.ACTIVE
    listing.save(update_fields=["status"])
    return redirect("marketplace:mine")


@login_required
@require_POST
def order_create(request, pk):
    form = OrderForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Quantité invalide.")
        return redirect("marketplace:detail", pk=pk)
    try:
        order = create_order(request.user, pk, form.cleaned_data["quantity_kg"])
    except Listing.DoesNotExist:
        messages.error(request, "Cette offre n'est plus disponible.")
        return redirect("marketplace:list")
    except OutOfStock as exc:
        messages.error(request, str(exc))
        return redirect("marketplace:detail", pk=pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("marketplace:detail", pk=pk)
    messages.success(request, "Commande enregistrée. Le paiement en ligne sera disponible prochainement.")
    return redirect("marketplace:orders")


@login_required
def order_list(request):
    purchases = Order.objects.filter(buyer=request.user).select_related("listing")
    sales = Order.objects.filter(listing__seller=request.user, status=Order.Status.PAID).select_related("listing", "buyer")
    return render(request, "marketplace/order_list.html", {"purchases": purchases, "sales": sales})


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, buyer=request.user)
    cancel_order(order)
    messages.success(request, "Commande annulée. Stock remis en vente.")
    return redirect("marketplace:orders")
