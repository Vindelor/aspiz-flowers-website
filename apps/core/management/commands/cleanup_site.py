from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import LoginCode
from apps.cart.models import Cart


class Command(BaseCommand):
    help = "Housekeeping: expired sessions, old guest carts, used/expired login codes. Run daily via cron."

    def add_arguments(self, parser):
        parser.add_argument("--cart-days", type=int, default=30)

    def handle(self, *args, **opts):
        call_command("clearsessions")
        cutoff = timezone.now() - timedelta(days=opts["cart_days"])
        carts, _ = Cart.objects.filter(user__isnull=True, updated_at__lt=cutoff).delete()
        codes, _ = LoginCode.objects.filter(expires_at__lt=timezone.now() - timedelta(days=1)).delete()
        self.stdout.write(f"Deleted {carts} guest-cart rows (incl. items), {codes} login codes.")