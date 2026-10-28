import phonenumbers
from django.contrib import admin, messages
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

    list_display = ("username", "phone", "phone_ok", "first_name", "last_name", "last_login", "is_active", "is_staff")
    actions = ["activate_users", "deactivate_users"]
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

    @admin.display(boolean=True, description="Geçerli TR telefon")
    def phone_ok(self, obj):
        """False for 'x12' placeholders, foreign or malformed numbers: such
        accounts can never receive the WhatsApp login code."""
        try:
            parsed = phonenumbers.parse((obj.phone or "").strip(), "TR")
        except phonenumbers.NumberParseException:
            return False
        return phonenumbers.is_valid_number(parsed) and phonenumbers.region_code_for_number(parsed) == "TR"

    @admin.action(description="Seçili kullanıcıları aktif et")
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} kullanıcı aktif edildi.", messages.SUCCESS)

    @admin.action(description="Seçili kullanıcıları pasif et")
    def deactivate_users(self, request, queryset):
        # Never let an admin lock themselves out by accident.
        updated = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{updated} kullanıcı pasif edildi.", messages.SUCCESS)