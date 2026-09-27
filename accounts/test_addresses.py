"""Address model and manager: labels, defaults, and checkout saving."""

from accounts.models import Address
from orders.test_checkout_form import VALID_DATA


def make_address(user, **overrides):
    fields = {
        "name": "Casey Monroe",
        "street": "77 Cortex Lane",
        "city": "Amarillo",
        "state": "TX",
        "zip": "79101",
        **overrides,
    }
    return Address.objects.create(user=user, **fields)


# --- Display -----------------------------------------------------------------


def test_str_leads_with_the_label(address):
    assert str(address) == "Home — 214 Synapse Street, Canyon, TX"


def test_str_falls_back_to_the_name_without_a_label(customer):
    address = make_address(customer)

    assert address.label == ""
    assert str(address) == "Casey Monroe — 77 Cortex Lane, Amarillo, TX"


def test_as_checkout_initial_maps_onto_one_section(address):
    initial = address.as_checkout_initial("billing")

    assert initial == {
        "billing_name": "Casey Monroe",
        "billing_street": "214 Synapse Street",
        "billing_line2": "",
        "billing_city": "Canyon",
        "billing_state": "TX",
        "billing_zip": "79015",
    }


# --- Defaults ----------------------------------------------------------------


def test_fill_empty_defaults_fills_both_empty_slots(customer, address):
    customer.fill_empty_defaults(address)

    customer.refresh_from_db()
    assert customer.default_shipping_address == address
    assert customer.default_billing_address == address


def test_fill_empty_defaults_never_overwrites_a_default(customer, address):
    customer.fill_empty_defaults(address)
    gift = make_address(customer, name="Grandma")

    customer.fill_empty_defaults(gift)

    customer.refresh_from_db()
    assert customer.default_shipping_address == address
    assert customer.default_billing_address == address


def test_fill_empty_defaults_fills_only_the_empty_slot(customer, address):
    work = make_address(customer, label="Work")
    customer.set_default_address("shipping", work)

    customer.fill_empty_defaults(address)

    customer.refresh_from_db()
    assert customer.default_shipping_address == work
    assert customer.default_billing_address == address


def test_deleting_a_default_address_clears_the_default(customer, address):
    customer.fill_empty_defaults(address)

    address.delete()

    customer.refresh_from_db()
    assert customer.default_shipping_address is None
    assert customer.default_billing_address is None


# --- The address book queryset -----------------------------------------------


def test_address_book_lists_defaults_first_then_newest(customer, address):
    older = make_address(customer, label="Older")
    newer = make_address(customer, label="Newer")
    customer.set_default_address("billing", older)

    book = list(Address.objects.address_book(customer))

    assert book == [older, newer, address]


def test_address_book_holds_only_the_users_own(customer, address, other_users_address):
    assert list(Address.objects.address_book(customer)) == [address]


# --- Saving from checkout ----------------------------------------------------


def test_save_from_checkout_creates_an_address(customer):
    saved = Address.objects.save_from_checkout(customer, VALID_DATA, "shipping")

    assert saved.user == customer
    assert saved.street == "12 Cortex Lane"
    assert saved.line2 == "Unit 7"
    assert saved.zip == "79015"
    assert saved.label == ""


def test_save_from_checkout_reuses_an_identical_address(customer):
    first = Address.objects.save_from_checkout(customer, VALID_DATA, "shipping")
    again = Address.objects.save_from_checkout(customer, VALID_DATA, "shipping")

    assert again == first
    assert Address.objects.count() == 1


def test_save_from_checkout_matches_regardless_of_label(customer):
    labeled = make_address(
        customer,
        label="Home",
        street="12 Cortex Lane",
        line2="Unit 7",
        city="Canyon",
        zip="79015",
    )

    saved = Address.objects.save_from_checkout(customer, VALID_DATA, "shipping")

    assert saved == labeled


def test_save_from_checkout_fills_empty_defaults(customer):
    saved = Address.objects.save_from_checkout(customer, VALID_DATA, "shipping")

    customer.refresh_from_db()
    assert customer.default_shipping_address == saved
    assert customer.default_billing_address == saved


def test_another_users_identical_address_is_not_reused(customer, other_users_address):
    data = {
        **VALID_DATA,
        "shipping_name": "Sam Stranger",
        "shipping_street": "9 Axon Avenue",
        "shipping_line2": "",
        "shipping_city": "Norman",
        "shipping_state": "OK",
        "shipping_zip": "73019",
    }

    saved = Address.objects.save_from_checkout(customer, data, "shipping")

    assert saved != other_users_address
    assert saved.user == customer
