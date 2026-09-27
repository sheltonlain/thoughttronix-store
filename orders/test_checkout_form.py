"""CheckoutForm tests — coverage priority 2 in the PRD.

Each declarative rule rejects bad input with a field-specific error;
a fully valid form passes. No database required, except where the
address book supplies initial values.
"""

import pytest

from .forms import CheckoutForm

VALID_DATA = {
    "email": "casey@example.com",
    "shipping_name": "Casey Monroe",
    "shipping_street": "12 Cortex Lane",
    "shipping_line2": "Unit 7",
    "shipping_city": "Canyon",
    "shipping_state": "TX",
    "shipping_zip": "79015",
    "billing_name": "Casey Monroe",
    "billing_street": "12 Cortex Lane",
    "billing_line2": "",
    "billing_city": "Canyon",
    "billing_state": "TX",
    "billing_zip": "79015-1234",
    "card_number": "4242 4242 4242 4242",
    "card_expiry": "12/39",
    "card_cvv": "123",
}


def form_with(**overrides):
    return CheckoutForm(data={**VALID_DATA, **overrides})


def test_a_fully_valid_form_passes():
    assert form_with().is_valid()


def test_line2_is_optional_but_everything_else_is_required():
    required = [name for name in VALID_DATA if not name.endswith("_line2")]
    for name in required:
        form = form_with(**{name: ""})
        assert not form.is_valid()
        assert form.errors[name] == ["This field is required."]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("shipping_state", "XX"),  # not one of the 50 states + DC
        ("billing_state", "Texas"),
        ("shipping_zip", "790"),
        ("billing_zip", "79015-12"),
        ("card_number", "4242 4242 4242 4241"),  # fails Luhn
        ("card_expiry", "01/20"),  # long expired
        ("card_expiry", "13/30"),  # no thirteenth month
        ("card_cvv", "12"),
        ("card_cvv", "abcd"),
    ],
)
def test_each_rule_rejects_bad_input_on_its_own_field(field, value):
    form = form_with(**{field: value})

    assert not form.is_valid()
    assert field in form.errors
    assert len(form.errors) == 1  # the error lands beside its field, alone


def test_the_form_declares_no_imperative_validation():
    """The showcase contract: declarative rules only, per the PRD."""
    assert "clean" not in CheckoutForm.__dict__
    assert not any(name.startswith("clean_") for name in CheckoutForm.__dict__)


# --- "Same as shipping" ------------------------------------------------------

BILLING_BLANK = {name: "" for name in VALID_DATA if name.startswith("billing_")}


def test_same_as_shipping_copies_shipping_into_billing():
    form = form_with(**BILLING_BLANK, use_shipping_for_billing="on")

    assert form.is_valid()
    assert form.cleaned_data["billing_street"] == "12 Cortex Lane"
    assert form.cleaned_data["billing_line2"] == "Unit 7"
    assert form.cleaned_data["billing_zip"] == "79015"


def test_same_as_shipping_still_validates_the_address():
    form = form_with(**BILLING_BLANK, use_shipping_for_billing="on", shipping_zip="790")

    assert not form.is_valid()
    assert "shipping_zip" in form.errors


def test_without_same_as_shipping_billing_is_required():
    form = form_with(**BILLING_BLANK)

    assert not form.is_valid()
    assert form.errors["billing_street"] == ["This field is required."]


def test_the_option_checkboxes_are_optional_and_off_when_absent():
    form = form_with()

    assert form.is_valid()
    assert form.cleaned_data["save_shipping"] is False
    assert form.cleaned_data["save_billing"] is False
    assert form.cleaned_data["use_shipping_for_billing"] is False


def test_the_nickname_is_optional_and_kept():
    form = form_with(save_shipping="on", save_shipping_label="Studio")

    assert form.is_valid()
    assert form.cleaned_data["save_shipping_label"] == "Studio"
    assert form.cleaned_data["save_billing_label"] == ""


def test_the_nickname_fits_the_address_label():
    form = form_with(save_shipping_label="x" * 51)

    assert not form.is_valid()
    assert "save_shipping_label" in form.errors


def test_the_option_checkboxes_stay_out_of_the_address_sections():
    names = [bound.name for bound in CheckoutForm().billing_fields()]

    assert names == [
        "billing_name",
        "billing_street",
        "billing_line2",
        "billing_city",
        "billing_state",
        "billing_zip",
    ]


# --- Initial values ----------------------------------------------------------


def test_initial_for_a_new_customer_ticks_the_save_boxes(customer):
    initial = CheckoutForm.initial_for(customer)

    assert initial == {"save_shipping": True, "save_billing": True}


def test_initial_for_fills_in_the_defaults(customer, address):
    customer.fill_empty_defaults(address)

    initial = CheckoutForm.initial_for(customer)

    assert initial["shipping_street"] == "214 Synapse Street"
    assert initial["billing_city"] == "Canyon"
    assert initial["save_shipping"] is False
    assert initial["save_billing"] is False
