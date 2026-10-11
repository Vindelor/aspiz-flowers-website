from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user model extending Django's built-in auth, so we can safely
    add store-specific fields later (phone, wholesale tier, etc.) without
    a painful migration to swap AUTH_USER_MODEL after the fact.
    """
    # Login/registration are phone-only now (no email step anywhere in the
    # customer-facing flow) — phone is the real identity, so it carries the
    # unique constraint email used to have. The email field is kept only
    # because AbstractUser defines it; it's left blank and unused by every
    # form/view, so no code should read or write it going forward.
    email = models.EmailField("email address", blank=True)
    phone = models.CharField("Telefon", max_length=20, unique=True)
    address = models.TextField("Adres", blank=True)

    def __str__(self):
        return self.get_full_name() or self.username


class LoginCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_codes")
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() < self.expires_at and self.attempts < 5
