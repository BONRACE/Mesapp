from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("categories", views.WasteCategoryViewSet, basename="category")
router.register("points", views.CollectionPointViewSet, basename="collection-point")
router.register("pickups", views.PickupViewSet, basename="pickup")
urlpatterns = router.urls
