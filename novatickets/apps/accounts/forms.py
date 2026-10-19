"""Formulaires d'inscription et de profil."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from apps.core.countries import PAYS_DEFAUT, choix_pays, get_pays

from .models import ProfilOrganisateur, Role, Sexe, User

CLASSE_CHAMP = (
    "w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 "
    "placeholder-slate-400 shadow-sm outline-none transition "
    "focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/15"
)
CLASSE_FICHIER = (
    "w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm "
    "text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-600 "
    "file:px-4 file:py-2 file:text-white hover:border-emerald-400"
)


def styler(champs, classe=CLASSE_CHAMP):
    for champ in champs.values():
        widget = champ.widget
        if isinstance(widget, forms.ClearableFileInput):
            widget.attrs.setdefault("class", CLASSE_FICHIER)
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "h-5 w-5 rounded border-slate-300 text-emerald-600")
        else:
            widget.attrs.setdefault("class", classe)


class ChampsTelephoneMixin(forms.Form):
    """Pays + téléphone obligatoires, validés selon l'indicatif du pays."""

    pays = forms.ChoiceField(label="Pays", initial=PAYS_DEFAUT)
    telephone = forms.CharField(
        label="Numéro de téléphone mobile",
        max_length=20,
        help_text="Sans l'indicatif ni le 0 initial.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pays"].choices = choix_pays()
        self.fields["pays"].widget.attrs.update({"data-selecteur-pays": "1"})
        self.fields["telephone"].widget.attrs.update(
            {
                "data-champ-telephone": "1",
                "inputmode": "numeric",
                "placeholder": "97 00 00 00",
                # Pas de bordure propre : le champ vit dans le groupe « indicatif + numéro ».
                "class": "w-full border-0 bg-transparent px-3 py-3 text-slate-900 outline-none focus:ring-0",
            }
        )

    def clean_telephone(self):
        """Valide la longueur du numéro selon le pays sélectionné."""
        brut = self.cleaned_data["telephone"]
        chiffres = "".join(c for c in brut if c.isdigit())
        code_pays = self.data.get("pays") or PAYS_DEFAUT
        pays = get_pays(code_pays)

        # On tolère la saisie de l'indicatif ou d'un 0 initial, puis on nettoie.
        if chiffres.startswith(pays.indicatif) and len(chiffres) > pays.longueur_max:
            chiffres = chiffres[len(pays.indicatif):]
        chiffres = chiffres.lstrip("0") or chiffres

        if not chiffres:
            raise forms.ValidationError("Le numéro de téléphone mobile est obligatoire.")
        if not (pays.longueur_min <= len(chiffres) <= pays.longueur_max):
            attendu = (
                f"{pays.longueur_min} chiffres"
                if pays.longueur_min == pays.longueur_max
                else f"entre {pays.longueur_min} et {pays.longueur_max} chiffres"
            )
            raise forms.ValidationError(
                f"Un numéro {pays.nom} ({pays.indicatif_affiche}) doit comporter {attendu}. "
                f"Vous en avez saisi {len(chiffres)}."
            )
        return chiffres


class BaseInscriptionForm(ChampsTelephoneMixin, UserCreationForm):
    """Champs partagés par les deux parcours d'inscription."""

    first_name = forms.CharField(label="Prénoms", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse e-mail")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "pays", "telephone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Mot de passe"
        self.fields["password2"].label = "Confirmez le mot de passe"
        styler(self.fields)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.email = self.cleaned_data["email"]
        # Le username reste technique : on le dérive de l'e-mail.
        base = utilisateur.email.split("@")[0][:140] or "membre"
        username, suffixe = base, 1
        while User.objects.filter(username=username).exists():
            suffixe += 1
            username = f"{base}{suffixe}"
        utilisateur.username = username
        utilisateur.pays = self.cleaned_data["pays"]
        utilisateur.indicatif = get_pays(self.cleaned_data["pays"]).indicatif_affiche
        utilisateur.telephone = self.cleaned_data["telephone"]
        utilisateur.role = self.role_cible
        if commit:
            utilisateur.save()
        return utilisateur


class InscriptionSpectateurForm(BaseInscriptionForm):
    """Spectateur : identité complète, sexe, profession, photo."""

    role_cible = Role.SPECTATEUR

    sexe = forms.ChoiceField(label="Sexe", choices=Sexe.choices)
    profession = forms.CharField(label="Profession", max_length=120)
    photo = forms.ImageField(label="Photo de profil", required=False)

    class Meta(BaseInscriptionForm.Meta):
        fields = [
            "first_name", "last_name", "email", "sexe", "profession",
            "pays", "telephone", "photo",
        ]

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.sexe = self.cleaned_data["sexe"]
        utilisateur.profession = self.cleaned_data["profession"]
        if self.cleaned_data.get("photo"):
            utilisateur.photo = self.cleaned_data["photo"]
        if commit:
            utilisateur.save()
        return utilisateur


class InscriptionOrganisateurForm(BaseInscriptionForm):
    """Organisateur : identité + structure (logo, signature)."""

    role_cible = Role.ORGANISATEUR

    structure = forms.CharField(label="Nom de la structure", max_length=150)
    description = forms.CharField(
        label="Présentation de la structure",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    logo = forms.ImageField(label="Logo de la structure", required=False)
    signature = forms.ImageField(label="Signature (image)", required=False)
    site_web = forms.URLField(label="Site web", required=False)

    class Meta(BaseInscriptionForm.Meta):
        fields = ["first_name", "last_name", "email", "pays", "telephone"]

    def save(self, commit=True):
        utilisateur = super().save(commit=commit)
        if commit:
            ProfilOrganisateur.objects.create(
                utilisateur=utilisateur,
                structure=self.cleaned_data["structure"],
                description=self.cleaned_data.get("description", ""),
                logo=self.cleaned_data.get("logo"),
                signature=self.cleaned_data.get("signature"),
                site_web=self.cleaned_data.get("site_web", ""),
            )
        return utilisateur


class ConnexionForm(AuthenticationForm):
    """Connexion par e-mail (ou identifiant) + mot de passe."""

    username = forms.CharField(label="Adresse e-mail")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].label = "Mot de passe"
        styler(self.fields)

    def clean_username(self):
        saisie = self.cleaned_data["username"].strip()
        # On accepte l'e-mail et on le traduit en username pour l'authentification.
        utilisateur = User.objects.filter(email__iexact=saisie).first()
        return utilisateur.username if utilisateur else saisie


class ProfilForm(ChampsTelephoneMixin, forms.ModelForm):
    """Édition du profil spectateur/organisateur."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "sexe", "profession", "photo", "pays", "telephone"]
        labels = {
            "first_name": "Prénoms",
            "last_name": "Nom",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pays"].initial = self.instance.pays
        styler(self.fields)

    def save(self, commit=True):
        utilisateur = super().save(commit=False)
        utilisateur.indicatif = get_pays(self.cleaned_data["pays"]).indicatif_affiche
        if commit:
            utilisateur.save()
        return utilisateur


class ProfilOrganisateurForm(forms.ModelForm):
    class Meta:
        model = ProfilOrganisateur
        fields = ["structure", "description", "logo", "signature", "site_web"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        styler(self.fields)
