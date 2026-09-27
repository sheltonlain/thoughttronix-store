from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        *DjangoUserAdmin.fieldsets,
        (
            "ThoughtTronix",
            {
                "fields": (
                    "job_title",
                    "default_shipping_address",
                    "default_billing_address",
                )
            },
        ),
    )
    # Read-only: an editable dropdown would offer every customer's addresses.
    readonly_fields = ("default_shipping_address", "default_billing_address")
    list_display = ("username", "email", "job_title", "is_staff")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Look, don't touch: address books belong to their customers.

    Delete stays allowed — admin checks it on cascaded rows, so blocking it
    would also block deleting a user who has saved addresses.
    """

    list_display = ("__str__", "user", "created_at")
    list_select_related = ("user",)
    search_fields = ("user__username", "label", "name", "street", "city", "zip")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
