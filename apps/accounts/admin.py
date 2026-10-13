from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from .models import User


class AdminUserChangeForm(BaseUserChangeForm):
    """
    Only overrides the on-screen labels for phone/address inside admin.
    The model's verbose_name ("Telefon"/"Adres") is left as-is because the
    site's own profile page (apps/accounts/forms.py ProfileForm) reads its
    field labels straight from the model, and that page must stay Turkish.
    """
    class Meta(BaseUserChangeForm.Meta):
        model = User
        labels = {"phone": "Phone", "address": "Address"}


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Store info", {"fields": ("phone", "address")}),
    )
    # No "email" column: customer accounts never have one anymore (phone is
    # the real identity — see apps/accounts/models.py), so the column would
    # always show blank.

    list_display = ("username", "phone", "first_name", "last_name", "is_active", "is_staff")
    list_filter = BaseUserAdmin.list_filter
    search_fields = ("username", "phone", "first_name", "last_name")
    # The default add form only asks for username + password, which left
    # `phone` blank; the second such user then crashed on the UNIQUE constraint.
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "phone", "password1", "password2"),
        }),
    )

