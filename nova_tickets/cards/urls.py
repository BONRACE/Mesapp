from django.urls import path

from . import views

app_name = "cards"

urlpatterns = [
    path("ma-carte/", views.edit, name="edit"),
    path("ma-carte/carte.pdf", views.my_card_pdf, name="pdf"),
    path("ma-carte/activer/", views.activate, name="activate"),
    path("<slug:slug>/", views.public, name="public"),
    path("<slug:slug>/contact.vcf", views.download_vcard, name="vcard"),
    path("<slug:slug>/qr.png", views.qr, name="qr"),
]
