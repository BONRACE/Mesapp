# Moyens de paiement proposés à l'achat, selon le pays du spectateur.
# La zone UEMOA (Franc CFA ouest-africain) a accès au Mobile Money local ;
# le reste de l'Afrique a Orange Money / carte ; le reste du monde a carte / PayPal.

PAYS_UEMOA = {
    "Bénin", "Togo", "Côte d'Ivoire", "Sénégal", "Mali",
    "Burkina Faso", "Niger", "Guinée-Bissau",
}

PAYS_AFRIQUE_AUTRE = {
    "Nigeria", "Ghana", "Cameroun", "Gabon", "Congo-Brazzaville", "Congo (RDC)",
    "Kenya", "Tanzanie", "Ouganda", "Rwanda", "Afrique du Sud", "Maroc",
    "Algérie", "Tunisie", "Égypte", "Guinée", "Mauritanie", "Tchad",
    "République centrafricaine", "Madagascar", "Zambie", "Zimbabwe",
}

MOYENS_PAIEMENT_UEMOA = [
    ("mtn_momo", "MTN Mobile Money", "📱"),
    ("moov_money", "Moov Money", "📱"),
    ("orange_money", "Orange Money", "📱"),
    ("carte", "Carte bancaire (Visa / Mastercard)", "💳"),
]

MOYENS_PAIEMENT_AFRIQUE = [
    ("orange_money", "Orange Money", "📱"),
    ("mtn_momo", "MTN Mobile Money", "📱"),
    ("carte", "Carte bancaire (Visa / Mastercard)", "💳"),
]

MOYENS_PAIEMENT_INTERNATIONAL = [
    ("carte", "Carte bancaire (Visa / Mastercard)", "💳"),
    ("paypal", "PayPal", "🅿️"),
]


def moyens_paiement_pour(pays):
    """Retourne la liste des moyens de paiement (code, libellé, icône) adaptés au pays donné."""
    if pays in PAYS_UEMOA:
        return MOYENS_PAIEMENT_UEMOA
    if pays in PAYS_AFRIQUE_AUTRE:
        return MOYENS_PAIEMENT_AFRIQUE
    return MOYENS_PAIEMENT_INTERNATIONAL


MOYEN_PAIEMENT_LABELS = dict(
    (code, label) for code, label, _ in
    MOYENS_PAIEMENT_UEMOA + MOYENS_PAIEMENT_AFRIQUE + MOYENS_PAIEMENT_INTERNATIONAL
)
