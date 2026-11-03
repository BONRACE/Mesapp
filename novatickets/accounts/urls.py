from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.NovaLoginView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("inscription/", views.register_choice, name="register"),
    path("inscription/spectateur/", views.register_spectateur, name="register_spectateur"),
    path("inscription/organisateur/", views.register_organisateur, name="register_organisateur"),
    path("profil/", views.profile, name="profile"),

    # Mot de passe oublié : e-mail avec un lien à usage unique (valable 1 h) -> nouveau mot de passe.
    path("mot-de-passe/oublie/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html", email_template_name="accounts/password_reset_email.txt",
        html_email_template_name="accounts/password_reset_email.html", subject_template_name="accounts/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done")), name="password_reset"),
    path("mot-de-passe/envoye/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("mot-de-passe/reinitialiser/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html", success_url=reverse_lazy("accounts:password_reset_complete")),
        name="password_reset_confirm"),
    path("mot-de-passe/termine/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
