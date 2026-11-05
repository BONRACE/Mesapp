"""En-têtes de sécurité complémentaires (ceux de Django : nosniff, X-Frame-Options, Referrer-Policy, HSTS)."""


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # La caméra n'est autorisée que pour notre propre origine (scanner de billets) ; tout le reste est coupé.
        response.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=(), usb=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # Politique de contenu : interdit les plugins, les <base> détournés, l'envoi de formulaires vers un autre site et
        # l'intégration dans un cadre ; n'autorise que nos propres scripts (+ scripts en ligne des gabarits) et les images
        # de notre domaine / data: (QR, aperçus). Drapeaux : CDN jsdelivr ; polices : Google Fonts.
        response.setdefault("Content-Security-Policy", (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:; "
            "connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"))
        # Pages d'un compte connecté : jamais conservées dans le cache d'un navigateur partagé / d'un proxy.
        if getattr(request, "user", None) is not None and request.user.is_authenticated and not request.path.startswith(("/static/", "/media/")):
            response.setdefault("Cache-Control", "private, no-store")
        return response
