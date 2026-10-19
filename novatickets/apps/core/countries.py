"""Référentiel des pays du monde : nom français, indicatif et drapeau.

Le drapeau n'est pas stocké : il est calculé à partir du code ISO 3166-1 alpha-2
en convertissant chaque lettre en « Regional Indicator Symbol » Unicode. Cela
évite d'embarquer 200 images et fonctionne partout (navbar, <option>, PDF).
"""

# (code ISO, nom français, indicatif téléphonique, longueur min, longueur max)
# Les longueurs concernent le numéro national, sans l'indicatif ni le 0 initial.
_RAW = [
    ("AF", "Afghanistan", "93", 9, 9), ("ZA", "Afrique du Sud", "27", 9, 9),
    ("AL", "Albanie", "355", 8, 9), ("DZ", "Algérie", "213", 9, 9),
    ("DE", "Allemagne", "49", 10, 11), ("AD", "Andorre", "376", 6, 9),
    ("AO", "Angola", "244", 9, 9), ("AG", "Antigua-et-Barbuda", "1268", 7, 7),
    ("SA", "Arabie saoudite", "966", 9, 9), ("AR", "Argentine", "54", 10, 11),
    ("AM", "Arménie", "374", 8, 8), ("AW", "Aruba", "297", 7, 7),
    ("AU", "Australie", "61", 9, 9), ("AT", "Autriche", "43", 10, 13),
    ("AZ", "Azerbaïdjan", "994", 9, 9), ("BS", "Bahamas", "1242", 7, 7),
    ("BH", "Bahreïn", "973", 8, 8), ("BD", "Bangladesh", "880", 10, 10),
    ("BB", "Barbade", "1246", 7, 7), ("BE", "Belgique", "32", 9, 9),
    ("BZ", "Belize", "501", 7, 7), ("BJ", "Bénin", "229", 10, 10),
    ("BT", "Bhoutan", "975", 8, 8), ("BY", "Biélorussie", "375", 9, 9),
    ("BO", "Bolivie", "591", 8, 8), ("BA", "Bosnie-Herzégovine", "387", 8, 9),
    ("BW", "Botswana", "267", 7, 8), ("BR", "Brésil", "55", 10, 11),
    ("BN", "Brunei", "673", 7, 7), ("BG", "Bulgarie", "359", 8, 9),
    ("BF", "Burkina Faso", "226", 8, 8), ("BI", "Burundi", "257", 8, 8),
    ("KH", "Cambodge", "855", 8, 9), ("CM", "Cameroun", "237", 9, 9),
    ("CA", "Canada", "1", 10, 10), ("CV", "Cap-Vert", "238", 7, 7),
    ("CL", "Chili", "56", 9, 9), ("CN", "Chine", "86", 11, 11),
    ("CY", "Chypre", "357", 8, 8), ("CO", "Colombie", "57", 10, 10),
    ("KM", "Comores", "269", 7, 7), ("CG", "Congo-Brazzaville", "242", 9, 9),
    ("CD", "Congo (RDC)", "243", 9, 9), ("KP", "Corée du Nord", "850", 8, 10),
    ("KR", "Corée du Sud", "82", 9, 10), ("CR", "Costa Rica", "506", 8, 8),
    ("CI", "Côte d'Ivoire", "225", 10, 10), ("HR", "Croatie", "385", 8, 9),
    ("CU", "Cuba", "53", 8, 8), ("CW", "Curaçao", "599", 7, 8),
    ("DK", "Danemark", "45", 8, 8), ("DJ", "Djibouti", "253", 8, 8),
    ("DM", "Dominique", "1767", 7, 7), ("EG", "Égypte", "20", 10, 10),
    ("AE", "Émirats arabes unis", "971", 9, 9), ("EC", "Équateur", "593", 9, 9),
    ("ER", "Érythrée", "291", 7, 7), ("ES", "Espagne", "34", 9, 9),
    ("EE", "Estonie", "372", 7, 8), ("SZ", "Eswatini", "268", 8, 8),
    ("US", "États-Unis", "1", 10, 10), ("ET", "Éthiopie", "251", 9, 9),
    ("FJ", "Fidji", "679", 7, 7), ("FI", "Finlande", "358", 9, 10),
    ("FR", "France", "33", 9, 9), ("GA", "Gabon", "241", 8, 9),
    ("GM", "Gambie", "220", 7, 7), ("GE", "Géorgie", "995", 9, 9),
    ("GH", "Ghana", "233", 9, 9), ("GI", "Gibraltar", "350", 8, 8),
    ("GR", "Grèce", "30", 10, 10), ("GD", "Grenade", "1473", 7, 7),
    ("GL", "Groenland", "299", 6, 6), ("GP", "Guadeloupe", "590", 9, 9),
    ("GT", "Guatemala", "502", 8, 8), ("GN", "Guinée", "224", 9, 9),
    ("GQ", "Guinée équatoriale", "240", 9, 9), ("GW", "Guinée-Bissau", "245", 7, 9),
    ("GY", "Guyana", "592", 7, 7), ("GF", "Guyane française", "594", 9, 9),
    ("HT", "Haïti", "509", 8, 8), ("HN", "Honduras", "504", 8, 8),
    ("HK", "Hong Kong", "852", 8, 8), ("HU", "Hongrie", "36", 9, 9),
    ("MH", "Îles Marshall", "692", 7, 7), ("SB", "Îles Salomon", "677", 7, 7),
    ("IN", "Inde", "91", 10, 10), ("ID", "Indonésie", "62", 9, 12),
    ("IQ", "Irak", "964", 10, 10), ("IR", "Iran", "98", 10, 10),
    ("IE", "Irlande", "353", 9, 9), ("IS", "Islande", "354", 7, 7),
    ("IL", "Israël", "972", 9, 9), ("IT", "Italie", "39", 9, 11),
    ("JM", "Jamaïque", "1876", 7, 7), ("JP", "Japon", "81", 10, 10),
    ("JO", "Jordanie", "962", 9, 9), ("KZ", "Kazakhstan", "7", 10, 10),
    ("KE", "Kenya", "254", 9, 9), ("KG", "Kirghizistan", "996", 9, 9),
    ("KI", "Kiribati", "686", 5, 8), ("KW", "Koweït", "965", 8, 8),
    ("LA", "Laos", "856", 8, 10), ("LS", "Lesotho", "266", 8, 8),
    ("LV", "Lettonie", "371", 8, 8), ("LB", "Liban", "961", 7, 8),
    ("LR", "Libéria", "231", 7, 9), ("LY", "Libye", "218", 9, 9),
    ("LI", "Liechtenstein", "423", 7, 7), ("LT", "Lituanie", "370", 8, 8),
    ("LU", "Luxembourg", "352", 9, 9), ("MO", "Macao", "853", 8, 8),
    ("MK", "Macédoine du Nord", "389", 8, 8), ("MG", "Madagascar", "261", 9, 9),
    ("MY", "Malaisie", "60", 9, 10), ("MW", "Malawi", "265", 9, 9),
    ("MV", "Maldives", "960", 7, 7), ("ML", "Mali", "223", 8, 8),
    ("MT", "Malte", "356", 8, 8), ("MA", "Maroc", "212", 9, 9),
    ("MQ", "Martinique", "596", 9, 9), ("MU", "Maurice", "230", 7, 8),
    ("MR", "Mauritanie", "222", 8, 8), ("YT", "Mayotte", "262", 9, 9),
    ("MX", "Mexique", "52", 10, 10), ("FM", "Micronésie", "691", 7, 7),
    ("MD", "Moldavie", "373", 8, 8), ("MC", "Monaco", "377", 8, 9),
    ("MN", "Mongolie", "976", 8, 8), ("ME", "Monténégro", "382", 8, 8),
    ("MZ", "Mozambique", "258", 9, 9), ("MM", "Myanmar", "95", 8, 10),
    ("NA", "Namibie", "264", 9, 9), ("NR", "Nauru", "674", 7, 7),
    ("NP", "Népal", "977", 10, 10), ("NI", "Nicaragua", "505", 8, 8),
    ("NE", "Niger", "227", 8, 8), ("NG", "Nigeria", "234", 10, 10),
    ("NO", "Norvège", "47", 8, 8), ("NC", "Nouvelle-Calédonie", "687", 6, 6),
    ("NZ", "Nouvelle-Zélande", "64", 8, 10), ("OM", "Oman", "968", 8, 8),
    ("UG", "Ouganda", "256", 9, 9), ("UZ", "Ouzbékistan", "998", 9, 9),
    ("PK", "Pakistan", "92", 10, 10), ("PW", "Palaos", "680", 7, 7),
    ("PS", "Palestine", "970", 9, 9), ("PA", "Panama", "507", 7, 8),
    ("PG", "Papouasie-Nouvelle-Guinée", "675", 8, 8), ("PY", "Paraguay", "595", 9, 9),
    ("NL", "Pays-Bas", "31", 9, 9), ("PE", "Pérou", "51", 9, 9),
    ("PH", "Philippines", "63", 10, 10), ("PL", "Pologne", "48", 9, 9),
    ("PF", "Polynésie française", "689", 8, 8), ("PR", "Porto Rico", "1787", 7, 7),
    ("PT", "Portugal", "351", 9, 9), ("QA", "Qatar", "974", 8, 8),
    ("CF", "République centrafricaine", "236", 8, 8), ("DO", "République dominicaine", "1809", 7, 7),
    ("RE", "La Réunion", "262", 9, 9), ("RO", "Roumanie", "40", 9, 9),
    ("GB", "Royaume-Uni", "44", 10, 10), ("RU", "Russie", "7", 10, 10),
    ("RW", "Rwanda", "250", 9, 9), ("KN", "Saint-Kitts-et-Nevis", "1869", 7, 7),
    ("SM", "Saint-Marin", "378", 8, 10), ("VC", "Saint-Vincent-et-les-Grenadines", "1784", 7, 7),
    ("LC", "Sainte-Lucie", "1758", 7, 7), ("SV", "Salvador", "503", 8, 8),
    ("WS", "Samoa", "685", 5, 7), ("ST", "Sao Tomé-et-Principe", "239", 7, 7),
    ("SN", "Sénégal", "221", 9, 9), ("RS", "Serbie", "381", 8, 9),
    ("SC", "Seychelles", "248", 7, 7), ("SL", "Sierra Leone", "232", 8, 8),
    ("SG", "Singapour", "65", 8, 8), ("SK", "Slovaquie", "421", 9, 9),
    ("SI", "Slovénie", "386", 8, 8), ("SO", "Somalie", "252", 7, 9),
    ("SD", "Soudan", "249", 9, 9), ("SS", "Soudan du Sud", "211", 9, 9),
    ("LK", "Sri Lanka", "94", 9, 9), ("SE", "Suède", "46", 9, 9),
    ("CH", "Suisse", "41", 9, 9), ("SR", "Suriname", "597", 6, 7),
    ("SY", "Syrie", "963", 9, 9), ("TJ", "Tadjikistan", "992", 9, 9),
    ("TW", "Taïwan", "886", 9, 9), ("TZ", "Tanzanie", "255", 9, 9),
    ("TD", "Tchad", "235", 8, 8), ("CZ", "Tchéquie", "420", 9, 9),
    ("TH", "Thaïlande", "66", 9, 9), ("TL", "Timor oriental", "670", 7, 8),
    ("TG", "Togo", "228", 8, 8), ("TO", "Tonga", "676", 5, 7),
    ("TT", "Trinité-et-Tobago", "1868", 7, 7), ("TN", "Tunisie", "216", 8, 8),
    ("TM", "Turkménistan", "993", 8, 8), ("TR", "Turquie", "90", 10, 10),
    ("TV", "Tuvalu", "688", 5, 7), ("UA", "Ukraine", "380", 9, 9),
    ("UY", "Uruguay", "598", 8, 8), ("VU", "Vanuatu", "678", 5, 7),
    ("VA", "Vatican", "379", 8, 10), ("VE", "Venezuela", "58", 10, 10),
    ("VN", "Vietnam", "84", 9, 10), ("YE", "Yémen", "967", 9, 9),
    ("ZM", "Zambie", "260", 9, 9), ("ZW", "Zimbabwe", "263", 9, 9),
]

# Pays mis en avant en tête de liste (marché principal de NovaTickets).
PAYS_PRIORITAIRES = ["BJ", "TG", "CI", "SN", "BF", "NE", "ML", "GH", "NG", "CM"]

PAYS_DEFAUT = "BJ"


def drapeau(code_iso):
    """Renvoie l'emoji drapeau correspondant à un code ISO alpha-2."""
    code = (code_iso or "").upper()
    if len(code) != 2 or not code.isalpha():
        return "🏳️"
    return "".join(chr(0x1F1E6 + ord(lettre) - ord("A")) for lettre in code)


class Pays:
    """Petit objet valeur décrivant un pays."""

    __slots__ = ("code", "nom", "indicatif", "longueur_min", "longueur_max")

    def __init__(self, code, nom, indicatif, longueur_min, longueur_max):
        self.code = code
        self.nom = nom
        self.indicatif = indicatif
        self.longueur_min = longueur_min
        self.longueur_max = longueur_max

    @property
    def drapeau(self):
        return drapeau(self.code)

    @property
    def indicatif_affiche(self):
        return f"+{self.indicatif}"

    @property
    def libelle(self):
        return f"{self.drapeau}  {self.nom} ({self.indicatif_affiche})"

    def __str__(self):
        return self.nom


PAYS = {code: Pays(code, nom, ind, mn, mx) for code, nom, ind, mn, mx in _RAW}


def get_pays(code):
    """Récupère un pays, ou le pays par défaut si le code est inconnu."""
    return PAYS.get((code or "").upper()) or PAYS[PAYS_DEFAUT]


def liste_pays_triee():
    """Pays prioritaires d'abord, puis tous les autres par ordre alphabétique."""
    prioritaires = [PAYS[c] for c in PAYS_PRIORITAIRES if c in PAYS]
    autres = sorted(
        (p for p in PAYS.values() if p.code not in PAYS_PRIORITAIRES),
        key=lambda p: p.nom,
    )
    return prioritaires + autres


def choix_pays():
    """Choices Django pour un champ pays (drapeau + nom + indicatif)."""
    return [(p.code, p.libelle) for p in liste_pays_triee()]


def indicatifs_json():
    """Dictionnaire {code: {indicatif, drapeau, min, max}} injecté dans le JS
    des formulaires pour afficher le drapeau/indicatif en direct."""
    return {
        p.code: {
            "indicatif": p.indicatif_affiche,
            "drapeau": p.drapeau,
            "min": p.longueur_min,
            "max": p.longueur_max,
            "nom": p.nom,
        }
        for p in PAYS.values()
    }
