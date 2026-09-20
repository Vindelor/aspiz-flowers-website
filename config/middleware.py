from django.conf import settings
from django.utils import translation


class AdminLanguageMiddleware:
    """
    The shop's LANGUAGE_CODE is Turkish (customer-facing pages, order status
    labels, etc. all need to stay Turkish for shoppers). But the admin who
    updates daily flower photos wants the /admin/ panel itself in English.

    Django doesn't support "different language per URL prefix" out of the
    box, so this middleware activates the "en" locale only for requests
    under /admin/, and the site's normal language everywhere else. This
    affects Django's own built-in admin strings (Add, Change, Delete,
    filters, etc.) — it does NOT translate our own custom text (e.g. order
    status choices like "Kargoda"), since those are literal strings we
    wrote, not translation-marked strings. Those are handled separately in
    each admin.py where it made sense.
    """

    ADMIN_PREFIX = "/admin/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        target_language = "en" if request.path.startswith(self.ADMIN_PREFIX) else settings.LANGUAGE_CODE
        translation.activate(target_language)
        request.LANGUAGE_CODE = target_language
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        return response
