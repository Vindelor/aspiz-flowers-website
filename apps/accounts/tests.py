"""
Login / registration regression tests.

Run (inside the web container):

    docker compose exec web python manage.py test apps.accounts -v 2

The Django test runner creates a throw-away database called ``test_<DB_NAME>``,
so the MySQL user needs rights on it.  One-time grant (run on the db container):

    GRANT ALL ON `test\\_%`.* TO 'shopuser'@'%';

No real WhatsApp message is ever sent: ``send_otp_sms`` is mocked and the
6-digit code is read from the mock call.
"""
from datetime import timedelta, timezone as dt_timezone
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.products.models import Category, Product

from .forms import RegisterForm
from .models import LoginCode, User
from .sms import SmsSendError

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
PHONE_LOCAL = "0555 123 45 67"
PHONE_E164 = "905551234567"


def _fake_sms():
    """Patch the sender; returns the patcher (use as context manager)."""
    return mock.patch("apps.accounts.views.sms.send_otp_sms", return_value=True)


class AuthFlowBase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    # -- helpers ---------------------------------------------------------
    def register(self, phone=PHONE_LOCAL, name="Ayşe Yılmaz", client=None, **extra):
        c = client or self.client
        return c.post(
            reverse("accounts:register"),
            {"full_name": name, "phone": phone, "terms": "on", **extra},
            **AJAX,
        )

    def request_login_code(self, phone=PHONE_LOCAL, client=None, **extra):
        c = client or self.client
        return c.post(reverse("accounts:login"), {"phone": phone, **extra}, **AJAX)

    def verify(self, code, client=None, **extra):
        c = client or self.client
        return c.post(reverse("accounts:login_verify"), {"code": code, **extra}, **AJAX)

    def make_active_user(self, phone=PHONE_E164, **kw):
        return User.objects.create(
            username=kw.pop("username", "uye" + phone[-10:]),
            phone=phone,
            first_name="Test",
            is_active=True,
            **kw,
        )


class RegistrationTests(AuthFlowBase):
    def test_happy_path_register_then_verify_logs_in(self):
        with _fake_sms() as send:
            r = self.register()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["step"], "verify")
        user = User.objects.get(phone=PHONE_E164)
        self.assertFalse(user.is_active, "must stay inactive until the code is verified")
        self.assertEqual((user.first_name, user.last_name), ("Ayşe", "Yılmaz"))
        self.assertFalse(user.has_usable_password())
        code = send.call_args.args[1]

        r = self.verify(code)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["success"])
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_phone_is_stored_normalised_for_every_typing_style(self):
        for i, typed in enumerate(["0555 123 45 67", "+90 555 123 45 67", "5551234567", "905551234567"]):
            cache.clear()
            User.objects.all().delete()
            with _fake_sms():
                r = self.register(phone=typed, client=Client())
            self.assertEqual(r.status_code, 200, (typed, r.content))
            self.assertEqual(User.objects.get().phone, PHONE_E164, typed)

    def test_invalid_and_foreign_numbers_rejected(self):
        for bad in ["1111111111", "abc", "+1 202 555 0143", "0555 123", ""]:
            cache.clear()
            with _fake_sms() as send:
                r = self.register(phone=bad)
            self.assertEqual(r.status_code, 400, bad)
            self.assertIn("phone", r.json()["errors"], bad)
            send.assert_not_called()
        self.assertFalse(User.objects.exists())

    def test_terms_required(self):
        with _fake_sms():
            r = self.client.post(
                reverse("accounts:register"),
                {"full_name": "A B", "phone": PHONE_LOCAL},
                **AJAX,
            )
        self.assertEqual(r.status_code, 400)
        self.assertIn("terms", r.json()["errors"])

    def test_cannot_register_active_number_in_any_stored_format(self):
        for stored in ["905551234567", "05551234567", "5551234567"]:
            cache.clear()
            User.objects.all().delete()
            self.make_active_user(phone=stored)
            with _fake_sms() as send:
                r = self.register(phone="+90 555 123 45 67")
            self.assertEqual(r.status_code, 400, stored)
            self.assertIn("phone", r.json()["errors"], stored)
            send.assert_not_called()

    def test_retry_after_unverified_registration_replaces_stale_row(self):
        with _fake_sms():
            self.register()
        first = User.objects.get(phone=PHONE_E164)
        cache.delete(f"otp_cooldown:{PHONE_E164}")  # skip the 60 s wait
        with _fake_sms() as send:
            r = self.register(name="Ayşe Yılmaz")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(User.objects.filter(phone=PHONE_E164).count(), 1)
        self.assertNotEqual(User.objects.get(phone=PHONE_E164).pk, first.pk)
        self.assertEqual(self.verify(send.call_args.args[1]).status_code, 200)

    def test_legacy_email_login_code_table_is_gone(self):
        """
        accounts_emaillogincode (retired e-mail login) kept a real FOREIGN KEY
        to accounts_user; deleting a never-verified user that still had a row
        there raised IntegrityError 1451 -> HTTP 500 on re-registration.
        Migration 0008 drops the table, so nothing can block that delete.
        """
        self.assertNotIn("accounts_emaillogincode", connection.introspection.table_names())
        with _fake_sms():
            self.register()
        cache.delete(f"otp_cooldown:{PHONE_E164}")
        with _fake_sms():
            r = self.register()
        self.assertEqual(r.status_code, 200, r.content)

    def test_sms_failure_leaves_no_dangling_account_and_refunds_limits(self):
        with mock.patch("apps.accounts.views.sms.send_otp_sms", side_effect=SmsSendError("boom")):
            r = self.register()
        self.assertEqual(r.status_code, 503)
        self.assertFalse(User.objects.filter(phone=PHONE_E164).exists())
        # the customer must be able to try again immediately
        with _fake_sms():
            r = self.register()
        self.assertEqual(r.status_code, 200, r.content)

    def test_admin_disabled_account_cannot_be_reregistered(self):
        u = self.make_active_user()
        u.is_active = False
        u.last_login = timezone.now()
        u.save()
        with _fake_sms() as send:
            r = self.register()
        self.assertEqual(r.status_code, 400)
        send.assert_not_called()
        self.assertTrue(User.objects.filter(pk=u.pk).exists())


class LoginTests(AuthFlowBase):
    def test_happy_path_for_every_phone_typing_style(self):
        user = self.make_active_user()
        for typed in ["0555 123 45 67", "+90 555 123 45 67", "5551234567", "905551234567"]:
            cache.clear()
            c = Client()
            with _fake_sms() as send:
                r = self.request_login_code(phone=typed, client=c)
            self.assertEqual(r.status_code, 200, (typed, r.content))
            r = self.verify(send.call_args.args[1], client=c)
            self.assertEqual(r.status_code, 200, (typed, r.content))
            self.assertEqual(int(c.session["_auth_user_id"]), user.pk)

    def test_legacy_zero_prefixed_account_can_log_in(self):
        user = self.make_active_user(phone="05551234567")
        with _fake_sms() as send:
            r = self.request_login_code(phone="+90 555 123 45 67")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.verify(send.call_args.args[1]).status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_unknown_number(self):
        with _fake_sms() as send:
            r = self.request_login_code()
        self.assertEqual(r.status_code, 400)
        send.assert_not_called()

    def test_pending_registration_gets_helpful_message(self):
        with _fake_sms():
            self.register()
        cache.clear()
        with _fake_sms() as send:
            r = self.request_login_code()
        self.assertEqual(r.status_code, 400)
        self.assertIn("Kayıt Ol", r.json()["errors"]["__all__"][0])
        send.assert_not_called()

    def test_staff_and_superuser_cannot_use_otp_login(self):
        for flag in ("is_staff", "is_superuser"):
            cache.clear()
            User.objects.all().delete()
            self.make_active_user(**{flag: True})
            with _fake_sms() as send:
                r = self.request_login_code()
            self.assertEqual(r.status_code, 400, flag)
            send.assert_not_called()

    def test_wrong_code_then_correct_code(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        code = send.call_args.args[1]
        wrong = "000000" if code != "000000" else "111111"
        r = self.verify(wrong)
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.verify(code).status_code, 200)

    def test_five_wrong_codes_burn_the_code(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        code = send.call_args.args[1]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(wrong).status_code, 400)
        r = self.verify(code)  # even the right one is refused now (burnt code / IP lock)
        self.assertIn(r.status_code, (400, 429))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_code_cannot_be_reused(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        code = send.call_args.args[1]
        self.assertEqual(self.verify(code).status_code, 200)
        other = Client()
        other.session  # noqa - force session creation
        r = self.verify(code, client=other)
        self.assertEqual(r.status_code, 400)

    def test_expired_code(self):
        user = self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        code = send.call_args.args[1]
        LoginCode.objects.filter(user=user).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.verify(code).status_code, 400)

    def test_new_code_invalidates_previous_one(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        old = send.call_args.args[1]
        cache.delete(f"otp_cooldown:{PHONE_E164}")
        with _fake_sms() as send:
            self.request_login_code()
        new = send.call_args.args[1]
        if old != new:
            self.assertEqual(self.verify(old).status_code, 400)
        self.assertEqual(self.verify(new).status_code, 200)

    def test_sixty_second_cooldown(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.assertEqual(self.request_login_code().status_code, 200)
            r = self.request_login_code()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(send.call_count, 1)

    def test_sms_failure_gives_503_and_allows_immediate_retry(self):
        self.make_active_user()
        with mock.patch("apps.accounts.views.sms.send_otp_sms", side_effect=SmsSendError("boom")):
            r = self.request_login_code()
        self.assertEqual(r.status_code, 503)
        self.assertFalse(LoginCode.objects.exists())
        with _fake_sms():
            self.assertEqual(self.request_login_code().status_code, 200)

    def test_hourly_per_phone_limit_is_really_one_hour(self):
        """5 sends per number per hour — the window must not shrink to the cache default (5 min)."""
        from apps.accounts import ratelimit as rl

        key = f"otp_phone:{PHONE_E164}"
        for _ in range(3):
            rl._bump(key, 3600)
        remaining = self._ttl_seconds(key)
        self.assertGreater(remaining, 3000, f"counter TTL collapsed to {remaining}s")

    def test_global_daily_budget_counter_keeps_24h_window(self):
        from apps.accounts import ratelimit as rl

        for _ in range(3):
            rl._bump("otp_global_daily", 24 * 3600)
        self.assertGreater(self._ttl_seconds("otp_global_daily"), 80000)

    def test_unbump_does_not_reset_window(self):
        from apps.accounts import ratelimit as rl

        key = f"otp_ip:1.2.3.4"
        rl._bump(key, 3600)
        rl._bump(key, 3600)
        rl._unbump(key)
        self.assertGreater(self._ttl_seconds(key), 3000)
        self.assertEqual(cache.get(key)[0], 1)

    def _ttl_seconds(self, key):
        from django.conf import settings

        if "db" not in settings.CACHES["default"]["BACKEND"]:
            self.skipTest("TTL probe only implemented for DatabaseCache")
        full = cache.make_key(key)
        with connection.cursor() as cur:
            cur.execute("SELECT expires FROM django_cache WHERE cache_key = %s", [full])
            expires = cur.fetchone()[0]
        if timezone.is_naive(expires):
            expires = timezone.make_aware(expires, dt_timezone.utc)
        return (expires - timezone.now()).total_seconds()

    def test_guest_cart_is_merged_on_login(self):
        user = self.make_active_user()
        cat = Category.objects.create(name="Gül", slug="gul")
        prod = Product.objects.create(name="Kırmızı Gül", slug="kirmizi-gul", sku="GUL-1", category=cat, stock_quantity=50)
        guest = Cart.objects.create(session_key=self.client.session.session_key or self._ensure_session())
        CartItem.objects.create(cart=guest, product=prod, quantity=2)

        with _fake_sms() as send:
            self.request_login_code()
        self.assertEqual(self.verify(send.call_args.args[1]).status_code, 200)
        cart = Cart.objects.get(user=user)
        self.assertEqual(cart.items.get().quantity, 2)

    def _ensure_session(self):
        s = self.client.session
        s.save()
        return s.session_key

    def test_next_url_is_honoured_and_open_redirect_blocked(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code(next="/orders/checkout/")
        r = self.verify(send.call_args.args[1])
        self.assertEqual(r.json()["redirect_url"], "/orders/checkout/")

        cache.clear()
        c = Client()
        with _fake_sms() as send:
            self.request_login_code(client=c, next="https://evil.example/phish")
        r = self.verify(send.call_args.args[1], client=c)
        self.assertEqual(r.json()["redirect_url"], reverse("core:home"))

    def test_next_survives_full_page_flow_via_login_required(self):
        self.make_active_user()
        r = self.client.get(reverse("orders:checkout"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])
        with _fake_sms() as send:
            r = self.client.post(r["Location"].split("?")[0], {"phone": PHONE_LOCAL, "next": "/orders/checkout/"})
        self.assertRedirects(r, reverse("accounts:login_verify_page"), fetch_redirect_response=False)
        r = self.client.post(reverse("accounts:login_verify"), {"code": send.call_args.args[1]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/orders/checkout/")

    def test_full_page_flow_wrong_code_returns_to_code_page_not_phone_page(self):
        """A typo must not force the user to wait 60 s for a brand-new code."""
        self.make_active_user()
        with _fake_sms() as send:
            self.client.post(reverse("accounts:login"), {"phone": PHONE_LOCAL})
        code = send.call_args.args[1]
        wrong = "000000" if code != "000000" else "111111"
        r = self.client.post(reverse("accounts:login_verify"), {"code": wrong})
        self.assertRedirects(r, reverse("accounts:login_verify_page"), fetch_redirect_response=False)
        # and the page still shows the code form
        page = self.client.get(reverse("accounts:login_verify_page"))
        self.assertContains(page, 'name="code"')

    def test_code_accepts_non_latin_digits_and_spaces(self):
        self.make_active_user()
        with _fake_sms() as send:
            self.request_login_code()
        code = send.call_args.args[1]
        arabic = code.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
        self.assertEqual(self.verify(arabic).status_code, 200)

    def test_logout_is_post_only(self):
        user = self.make_active_user()
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        r = self.client.post(reverse("accounts:logout"))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_is_redirected_away_from_login_and_register(self):
        self.client.force_login(self.make_active_user())
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 302)
        self.assertEqual(self.client.get(reverse("accounts:register")).status_code, 302)

    def test_verify_without_session_is_rejected(self):
        r = self.verify("123456")
        self.assertEqual(r.status_code, 400)

    def test_malformed_code_is_rejected(self):
        self.make_active_user()
        with _fake_sms():
            self.request_login_code()
        for bad in ["12345", "1234567", "abcdef", ""]:
            self.assertEqual(self.verify(bad).status_code, 400, bad)


class CartInteractionTests(AuthFlowBase):
    def _product(self):
        cat = Category.objects.create(name="Gül", slug="gul")
        return Product.objects.create(name="Kırmızı Gül", slug="kirmizi-gul", sku="GUL-1", category=cat, stock_quantity=50)

    def test_login_survives_duplicate_user_carts(self):
        """Two simultaneous first requests can create two carts for one user; that used to 500 every page."""
        user = self.make_active_user()
        Cart.objects.create(user=user)
        Cart.objects.create(user=user)
        with _fake_sms() as send:
            self.request_login_code()
        r = self.verify(send.call_args.args[1])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_duplicate_guest_carts_do_not_break_pages(self):
        self.client.get(reverse("core:home"))
        s = self.client.session
        s["touch"] = 1
        s.save()
        key = s.session_key
        Cart.objects.create(session_key=key)
        Cart.objects.create(session_key=key)
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_guest_items_are_added_to_existing_account_cart_quantity(self):
        user = self.make_active_user()
        prod = self._product()
        mine = Cart.objects.create(user=user)
        CartItem.objects.create(cart=mine, product=prod, quantity=3)
        s = self.client.session
        s["touch"] = 1
        s.save()
        guest = Cart.objects.create(session_key=s.session_key)
        CartItem.objects.create(cart=guest, product=prod, quantity=4)
        with _fake_sms() as send:
            self.request_login_code()
        self.assertEqual(self.verify(send.call_args.args[1]).status_code, 200)
        self.assertEqual(CartItem.objects.get(cart=mine, product=prod).quantity, 7)
        self.assertFalse(Cart.objects.filter(pk=guest.pk).exists())


class CsrfTests(AuthFlowBase):
    def test_modal_forms_work_with_csrf_enforced(self):
        """Same thing the browser does: GET a page, read the token, POST via fetch-style request."""
        import re as _re

        c = Client(enforce_csrf_checks=True)
        html = c.get(reverse("core:home")).content.decode()
        token = _re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
        with _fake_sms():
            r = c.post(
                reverse("accounts:register"),
                {"full_name": "A B", "phone": PHONE_LOCAL, "terms": "on", "csrfmiddlewaretoken": token},
                **AJAX,
            )
        self.assertEqual(r.status_code, 200, r.content)
        r = c.post(reverse("accounts:register"), {"full_name": "A B", "phone": PHONE_LOCAL, "terms": "on"}, **AJAX)
        self.assertEqual(r.status_code, 403)


class ProfileTests(AuthFlowBase):
    def test_phone_cannot_be_changed_from_profile(self):
        user = self.make_active_user()
        self.client.force_login(user)
        r = self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Yeni", "last_name": "Ad", "phone": "905559999999", "address": "x"},
        )
        self.assertEqual(r.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.phone, PHONE_E164)
        self.assertEqual(user.first_name, "Yeni")

    def test_profile_requires_login(self):
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])


class PagesRenderTests(AuthFlowBase):
    def test_standalone_pages_render(self):
        for name in ("accounts:login", "accounts:register"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_modal_present_for_guests_only(self):
        self.assertContains(self.client.get(reverse("core:home")), "data-login-modal")
        self.client.force_login(self.make_active_user())
        self.assertNotContains(self.client.get(reverse("core:home")), "data-login-modal")

    def test_admin_can_create_user_with_phone(self):
        admin = User.objects.create_superuser(username="boss", phone="905550000001", password="Str0ng-pass!x")
        self.client.force_login(admin)
        r = self.client.get(reverse("admin:accounts_user_add"))
        self.assertEqual(r.status_code, 200)

    def test_two_superusers_can_exist(self):
        User.objects.create_superuser(username="a", phone="905550000001", password="Str0ng-pass!x")
        User.objects.create_superuser(username="b", phone="905550000002", password="Str0ng-pass!x")


class RegisterFormUnitTests(TestCase):
    def test_username_is_unique_when_two_numbers_share_last_ten_digits(self):
        User.objects.create(username="uye5551234567", phone="905551234567")
        f = RegisterForm({"full_name": "A B", "phone": "+49 555 123 45 67", "terms": "on"})
        # not a TR number -> invalid, but username helper must still not collide
        from .forms import _unique_username_from_phone

        self.assertNotEqual(_unique_username_from_phone("905551234567"), "uye5551234567")
        self.assertFalse(f.is_valid())
