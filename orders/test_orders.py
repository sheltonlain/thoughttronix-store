"""Order model behavior, the checkout flow, and owner-only access."""

import datetime
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address

from .models import CartItem, Order
from .services import place_order
from .test_checkout_form import VALID_DATA


@pytest.fixture
def order(cart, cart_item):
    return place_order(cart, cart.user, dict(VALID_DATA))


@pytest.fixture
def other_customer(db):
    return get_user_model().objects.create_user(username="other", password="x")


# --- Model behavior ----------------------------------------------------------


def test_order_number_format(order):
    assert order.number == f"TT-{order.created_at.year}-{order.pk:05d}"
    assert str(order) == order.number


def test_orders_come_most_recent_first(customer, order):
    older = Order.objects.create(
        user=customer,
        total=Decimal("9.00"),
        email="casey@example.com",
        shipping_name="Casey Monroe",
        shipping_street="12 Cortex Lane",
        shipping_city="Canyon",
        shipping_state="TX",
        shipping_zip="79015",
        billing_name="Casey Monroe",
        billing_street="12 Cortex Lane",
        billing_city="Canyon",
        billing_state="TX",
        billing_zip="79015",
        card_last4="4242",
        created_at=timezone.now() - datetime.timedelta(days=30),
    )

    assert list(Order.objects.all()) == [order, older]


def test_order_item_str(order):
    assert str(order.items.get()) == "2 × Seraphine Home Hub"


# --- The checkout page -------------------------------------------------------


def test_checkout_requires_login(client, db):
    response = client.get(reverse("orders:checkout"))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_an_empty_cart_is_sent_back_to_the_cart_page(client, customer):
    client.force_login(customer)

    response = client.get(reverse("orders:checkout"))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("orders:cart")


def test_an_unavailable_line_is_sent_back_to_the_cart_page(
    client, customer, cart, cart_item, unavailable_product
):
    cart.items.create(product=unavailable_product)
    client.force_login(customer)

    response = client.get(reverse("orders:checkout"))

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("orders:cart")


def test_checkout_page_shows_the_form_and_the_cart(client, customer, cart_item):
    client.force_login(customer)

    response = client.get(reverse("orders:checkout"))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "Shipping address" in page
    assert "Billing address" in page
    assert "Seraphine Home Hub" in page
    assert "699.98" in page


def test_a_valid_checkout_places_the_order(client, customer, cart_item):
    client.force_login(customer)

    response = client.post(reverse("orders:checkout"), VALID_DATA)

    order = Order.objects.get()
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("orders:confirmation", kwargs={"pk": order.pk})
    assert not CartItem.objects.exists()


def test_an_invalid_checkout_preserves_input_and_places_nothing(
    client, customer, cart_item
):
    bad = {**VALID_DATA, "card_number": "4242 4242 4242 4241"}
    client.force_login(customer)

    response = client.post(reverse("orders:checkout"), bad)

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "Enter a valid card number." in page
    assert "12 Cortex Lane" in page  # everything typed is preserved
    assert not Order.objects.exists()
    assert CartItem.objects.exists()


def test_confirmation_shows_the_order_number(client, customer, order):
    client.force_login(customer)

    response = client.get(reverse("orders:confirmation", kwargs={"pk": order.pk}))

    assert response.status_code == HTTPStatus.OK
    assert order.number in response.content.decode()


# --- Checkout and the address book -------------------------------------------


def test_checkout_fills_in_the_default_addresses(client, customer, cart_item, address):
    customer.fill_empty_defaults(address)
    client.force_login(customer)

    response = client.get(reverse("orders:checkout"))

    form = response.context["form"]
    assert form["shipping_street"].value() == "214 Synapse Street"
    assert form["billing_zip"].value() == "79015"
    assert response.context["shipping_selected"] == address.pk


def test_checkout_offers_saved_addresses(client, customer, cart_item, address):
    client.force_login(customer)

    page = client.get(reverse("orders:checkout")).content.decode()

    assert "Use a saved address" in page
    assert str(address) in page


def test_checkout_hides_the_picker_with_an_empty_book(client, customer, cart_item):
    client.force_login(customer)

    page = client.get(reverse("orders:checkout")).content.decode()

    assert "Use a saved address" not in page


def test_save_boxes_start_ticked_only_with_an_empty_book(client, customer, cart_item):
    client.force_login(customer)

    empty = client.get(reverse("orders:checkout")).context["form"]
    assert empty["save_shipping"].value() is True

    Address.objects.create(
        user=customer,
        name="Casey Monroe",
        street="1 Neural Plaza",
        city="Amarillo",
        state="TX",
        zip="79101",
    )
    filled = client.get(reverse("orders:checkout")).context["form"]
    assert filled["save_shipping"].value() is False
    assert filled["save_billing"].value() is False


def test_checking_out_with_save_ticked_saves_the_address(client, customer, cart_item):
    client.force_login(customer)

    client.post(reverse("orders:checkout"), {**VALID_DATA, "save_shipping": "on"})

    saved = Address.objects.get()
    assert saved.user == customer
    assert saved.street == "12 Cortex Lane"
    customer.refresh_from_db()
    assert customer.default_shipping_address == saved


def test_checking_out_with_same_as_shipping(client, customer, cart_item):
    data = {
        name: value
        for name, value in VALID_DATA.items()
        if not name.startswith("billing_")
    }
    client.force_login(customer)

    client.post(reverse("orders:checkout"), {**data, "use_shipping_for_billing": "on"})

    order = Order.objects.get()
    assert order.billing_street == order.shipping_street == "12 Cortex Lane"
    assert order.billing_zip == order.shipping_zip == "79015"


def test_the_address_picker_fills_a_section(client, customer, address):
    client.force_login(customer)

    response = client.get(
        reverse("orders:checkout_address_fields", kwargs={"section": "billing"}),
        {"saved_address": address.pk},
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert 'id="billing-fields"' in page
    assert 'value="214 Synapse Street"' in page
    assert "<html" not in page  # a partial, never base.html


def test_the_address_picker_can_blank_a_section(client, customer, address):
    client.force_login(customer)

    response = client.get(
        reverse("orders:checkout_address_fields", kwargs={"section": "shipping"}),
        {"saved_address": ""},
    )

    page = response.content.decode()
    assert 'id="shipping-fields"' in page
    assert "214 Synapse Street" not in page


@pytest.mark.parametrize(
    ("section", "saved_address"),
    [("shipping", "abc"), ("payment", "")],
)
def test_the_address_picker_rejects_bad_input(client, customer, section, saved_address):
    client.force_login(customer)

    response = client.get(
        reverse("orders:checkout_address_fields", kwargs={"section": section}),
        {"saved_address": saved_address},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_address_picker_never_loads_anothers_address(
    client, customer, other_users_address
):
    client.force_login(customer)

    response = client.get(
        reverse("orders:checkout_address_fields", kwargs={"section": "shipping"}),
        {"saved_address": other_users_address.pk},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_address_picker_requires_login(client, address):
    response = client.get(
        reverse("orders:checkout_address_fields", kwargs={"section": "shipping"}),
        {"saved_address": address.pk},
    )

    assert response.status_code == HTTPStatus.FOUND


def test_ticking_same_as_shipping_collapses_billing(client, customer):
    client.force_login(customer)

    response = client.get(
        reverse("orders:checkout_billing_section"),
        {"use_shipping_for_billing": "on"},
    )

    page = response.content.decode()
    assert 'id="billing-body"' in page
    assert "bill the shipping address above" in page
    assert 'name="billing_street"' not in page


def test_unticking_same_as_shipping_restores_billing(client, customer, address):
    customer.fill_empty_defaults(address)
    client.force_login(customer)

    response = client.get(reverse("orders:checkout_billing_section"))

    page = response.content.decode()
    assert 'name="billing_street"' in page
    assert 'value="214 Synapse Street"' in page
    assert 'name="save_billing"' in page


# --- Order history and detail ------------------------------------------------


def test_history_requires_login(client, db):
    response = client.get(reverse("orders:history"))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_history_lists_the_customers_orders(client, customer, order):
    client.force_login(customer)

    response = client.get(reverse("orders:history"))

    assert response.status_code == HTTPStatus.OK
    assert order.number in response.content.decode()


def test_history_has_a_designed_empty_state(client, customer):
    client.force_login(customer)

    response = client.get(reverse("orders:history"))

    assert "No orders yet" in response.content.decode()


def test_detail_shows_purchase_time_prices(client, customer, order):
    order.items.get().product.__class__.objects.update(price=Decimal("999.00"))
    client.force_login(customer)

    response = client.get(reverse("orders:detail", kwargs={"pk": order.pk}))

    page = response.content.decode()
    assert "349.99" in page
    assert "card ending 4242" in page
    assert "12 Cortex Lane" in page


def test_customers_cannot_see_anothers_orders(client, other_customer, order):
    client.force_login(other_customer)

    assert (
        client.get(reverse("orders:detail", kwargs={"pk": order.pk})).status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.get(reverse("orders:confirmation", kwargs={"pk": order.pk})).status_code
        == HTTPStatus.NOT_FOUND
    )
    history = client.get(reverse("orders:history"))
    assert order.number not in history.content.decode()
