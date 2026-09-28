"""The coupon form Marketing fills in.

A ModelForm, so the model's own rules apply: the code's format, a percent
of at most 100, an end after the start, one unarchived coupon per code.
Once a coupon has been used its deal — code, type, value, products — is
disabled; Django then ignores anything posted for those fields.
"""

from django import forms

from products.forms import StyledModelForm

from .models import Coupon

LOCKED_FIELDS = ["code", "discount_type", "value", "products"]


class CouponForm(StyledModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "value",
            "products",
            "min_subtotal",
            "starts_at",
            "expires_at",
            "max_uses_per_customer",
            "max_uses",
            "is_active",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["products"].queryset = self.fields["products"].queryset.order_by(
            "name"
        )
        if self.instance.pk and self.instance.is_locked:
            for name in LOCKED_FIELDS:
                self.fields[name].disabled = True
