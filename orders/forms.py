"""The checkout form — the codebase's showcase of declarative validation.

Every rule is visible at its field declaration, in the style of data
annotations: field types validate (``EmailField``), field arguments
validate (``required``, ``max_length``, ``ChoiceField``), and the
``validators=[...]`` list carries the rest. No ``clean_*`` methods
and no ``clean()`` — none of its current rules need imperative validation.

"Same as shipping" keeps that true: rather than making the billing fields
conditionally required, the form copies the shipping values into the
billing fields before validating, so the billing rules check a real
address either way.
"""

from django import forms
from django.core.validators import RegexValidator

from accounts.models import Address
from accounts.validators import US_STATES, zip_validator

from .models import Order
from .validators import validate_card_number, validate_expiry

cvv_validator = RegexValidator(r"^\d{3,4}$", "Enter the 3- or 4-digit CVV.")


class CheckoutForm(forms.Form):
    """One page, one POST: contact, shipping, billing, payment."""

    email = forms.EmailField(label="Email")

    shipping_name = forms.CharField(label="Full name", max_length=100)
    shipping_street = forms.CharField(label="Street address", max_length=200)
    shipping_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    shipping_city = forms.CharField(label="City", max_length=100)
    shipping_state = forms.ChoiceField(label="State", choices=US_STATES)
    shipping_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    billing_name = forms.CharField(label="Full name", max_length=100)
    billing_street = forms.CharField(label="Street address", max_length=200)
    billing_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    billing_city = forms.CharField(label="City", max_length=100)
    billing_state = forms.ChoiceField(label="State", choices=US_STATES)
    billing_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    card_number = forms.CharField(
        label="Card number", max_length=23, validators=[validate_card_number]
    )
    card_expiry = forms.CharField(
        label="Expiry (MM/YY)", max_length=5, validators=[validate_expiry]
    )
    card_cvv = forms.CharField(label="CVV", max_length=4, validators=[cvv_validator])

    # Address-book options. Their names deliberately avoid the
    # ``shipping_``/``billing_`` prefixes the field groups below match on.
    use_shipping_for_billing = forms.BooleanField(
        label="Same as shipping address", required=False
    )
    save_shipping = forms.BooleanField(label="Save to my address book", required=False)
    save_billing = forms.BooleanField(label="Save to my address book", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "checkbox checkbox-sm"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"
        if self.is_bound and self._billing_mirrors_shipping():
            data = self.data.copy()
            for part in Address.PARTS:
                data[f"billing_{part}"] = data.get(f"shipping_{part}", "")
            self.data = data

    def _billing_mirrors_shipping(self):
        name = "use_shipping_for_billing"
        widget = self.fields[name].widget
        return widget.value_from_datadict(self.data, self.files, self.add_prefix(name))

    @classmethod
    def initial_for(cls, user):
        """Starting values for ``user``: their default addresses, and the
        save checkboxes ticked only while their address book is empty."""
        initial = {}
        if user.default_shipping_address:
            initial.update(
                user.default_shipping_address.as_checkout_initial("shipping")
            )
        if user.default_billing_address:
            initial.update(user.default_billing_address.as_checkout_initial("billing"))
        book_is_empty = not user.addresses.exists()
        initial["save_shipping"] = book_is_empty
        initial["save_billing"] = book_is_empty
        return initial

    # Field groups for the template — the form owns its own structure.

    def address_fields(self, section):
        """One address section's fields; ``section`` is shipping or billing."""
        return [self[name] for name in self.fields if name.startswith(f"{section}_")]

    def shipping_fields(self):
        return self.address_fields("shipping")

    def billing_fields(self):
        return self.address_fields("billing")

    def card_fields(self):
        return [self[name] for name in self.fields if name.startswith("card_")]


class OrderStatusForm(forms.ModelForm):
    """The back-office status dropdown — any of the four states, anytime.

    Guarding the workflow (no un-cancelling, no re-shipping a delivered
    order) is deliberately left as a student exercise.
    """

    class Meta:
        model = Order
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "select"})}
