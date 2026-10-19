from decimal import Decimal

from rest_framework import serializers

from accounts.serializers import LatLngMixin, point_from
from waste.serializers import WasteCategorySerializer

from .models import Listing, Order


def display_name(user) -> str:
    recycler = getattr(user, "recycler", None)
    if recycler and recycler.company_name:
        return recycler.company_name
    return user.full_name or "Vendeur"


class ListingSerializer(LatLngMixin, serializers.ModelSerializer):
    category_detail = WasteCategorySerializer(source="category", read_only=True)
    seller_name = serializers.SerializerMethodField()
    seller_role = serializers.CharField(source="seller.role", read_only=True)
    is_mine = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Listing
        fields = (
            "id", "title", "description", "category", "category_detail", "grade", "quantity_kg", "unit_price",
            "min_order_kg", "address", "latitude", "longitude", "lat", "lng", "distance_m", "photo", "is_active",
            "in_stock", "seller_name", "seller_role", "is_mine", "created_at",
        )
        read_only_fields = ("created_at",)
        extra_kwargs = {"latitude": {"write_only": True}, "longitude": {"write_only": True}}

    def get_seller_name(self, o):
        return display_name(o.seller)

    def get_is_mine(self, o):
        req = self.context.get("request")
        return bool(req and req.user.is_authenticated and req.user.id == o.seller_id)

    def get_lat(self, o):
        return o.location.y if o.location else None

    def get_lng(self, o):
        return o.location.x if o.location else None

    def get_distance_m(self, o):
        d = getattr(o, "distance", None)
        return int(d.m) if d is not None else None

    def validate_category(self, c):
        if not c.is_recyclable:
            raise serializers.ValidationError("Cette catégorie n'est pas revendable sur le marché.")
        return c

    def validate_quantity_kg(self, v):
        if v <= 0:
            raise serializers.ValidationError("La quantité doit être positive.")
        return v

    def validate_unit_price(self, v):
        if v < 1:
            raise serializers.ValidationError("Le prix doit être d'au moins 1 FCFA/kg.")
        return v

    def _apply_point(self, data):
        pt = point_from(data)
        data.pop("latitude", None), data.pop("longitude", None)
        if pt is not None:
            data["location"] = pt

    def create(self, validated):
        self._apply_point(validated)
        return Listing.objects.create(seller=self.context["request"].user, **validated)

    def update(self, instance, validated):
        self._apply_point(validated)
        return super().update(instance, validated)


class OrderSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    category_name = serializers.CharField(source="listing.category.name", read_only=True)
    category_color = serializers.CharField(source="listing.category.color", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    buyer_name = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    seller_net = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField(help_text="buyer | seller | admin")

    class Meta:
        model = Order
        fields = (
            "id", "listing", "listing_title", "category_name", "category_color", "quantity_kg", "unit_price",
            "total", "commission", "seller_net", "status", "status_label", "delivery_address", "notes",
            "buyer_name", "seller_name", "role", "created_at", "paid_at", "shipped_at", "delivered_at",
        )
        read_only_fields = fields

    def get_buyer_name(self, o):
        return display_name(o.buyer)

    def get_seller_name(self, o):
        return display_name(o.seller)

    def _uid(self):
        req = self.context.get("request")
        return req.user.id if req else None

    def get_role(self, o):
        uid = self._uid()
        return "buyer" if o.buyer_id == uid else "seller" if o.seller_id == uid else "admin"

    def get_seller_net(self, o):
        return o.seller_net if o.seller_id == self._uid() else None


class OrderCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField()
    quantity_kg = serializers.DecimalField(max_digits=9, decimal_places=2, min_value=Decimal("0.1"))
    delivery_address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    notes = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
