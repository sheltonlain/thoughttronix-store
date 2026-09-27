"""place_order tests — coverage priority 3 in the PRD.

Denormalization, cart emptying, atomicity, unavailable rejection, the
card_last4-only rule, and saving addresses to the address book.
"""

from decimal import Decimal

import pytest

from accounts.models import Address
from products.models import Product

from .models import CartItem, Order, OrderItem
from .services import place_order
from .test_checkout_form import VALID_DATA


@pytest.fixture
def checkout_data():
    return dict(VALID_DATA)


def test_creates_an_order_with_denormalized_snapshot(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.user == cart.user
    assert order.total == Decimal("699.98")
    assert order.status == Order.Status.PLACED
    item = order.items.get()
    assert item.product_name == "Seraphine Home Hub"
    assert item.unit_price == Decimal("349.99")
    assert item.quantity == 2
    assert item.line_total == Decimal("699.98")


def test_order_history_survives_catalog_changes(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    product = cart_item.product
    product.name = "Seraphine Home Hub II"
    product.price = Decimal("999.00")
    product.save()

    item = order.items.get()
    assert item.product_name == "Seraphine Home Hub"
    assert item.unit_price == Decimal("349.99")


def test_addresses_and_email_are_copied_onto_the_order(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.email == "casey@example.com"
    assert order.shipping_street == "12 Cortex Lane"
    assert order.shipping_line2 == "Unit 7"
    assert order.shipping_state == "TX"
    assert order.billing_zip == "79015-1234"


def test_only_the_last_four_card_digits_are_stored(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data)

    assert order.card_last4 == "4242"
    stored = [field.name for field in Order._meta.get_fields()]
    assert "card_number" not in stored
    assert "card_cvv" not in stored
    assert "card_expiry" not in stored


def test_the_cart_is_emptied(cart, cart_item, checkout_data):
    place_order(cart, cart.user, checkout_data)

    assert not cart.items.exists()
    assert cart.total() == Decimal("0.00")


def test_an_empty_cart_is_rejected(cart, checkout_data):
    with pytest.raises(ValueError):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()


def test_an_unavailable_product_is_rejected(
    cart, cart_item, unavailable_product, checkout_data
):
    cart.items.create(product=unavailable_product)

    with pytest.raises(ValueError, match="EchoPatch"):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()
    assert cart.items.count() == 2  # the cart is untouched


def test_a_failure_midway_leaves_no_partial_order(
    cart, cart_item, category, checkout_data, monkeypatch
):
    """All-or-nothing: if any line fails, no order and no emptied cart."""
    cart.add(
        Product.objects.create(
            name="Charging Pillow",
            slug="charging-pillow",
            price=Decimal("69.00"),
            category=category,
        )
    )

    original = OrderItem.objects.create
    calls = {"count": 0}

    def create_then_explode(**kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("boom")
        return original(**kwargs)

    monkeypatch.setattr(OrderItem.objects, "create", create_then_explode)

    with pytest.raises(RuntimeError):
        place_order(cart, cart.user, checkout_data)

    assert not Order.objects.exists()
    assert not OrderItem.objects.exists()
    assert CartItem.objects.count() == 2


def test_the_coupon_seam_is_accepted_and_ignored(cart, cart_item, checkout_data):
    order = place_order(cart, cart.user, checkout_data, coupon_code="THOUGHTS10")

    assert order.total == Decimal("699.98")


# --- Saving to the address book ----------------------------------------------


def test_nothing_is_saved_to_the_address_book_by_default(
    cart, cart_item, checkout_data
):
    place_order(cart, cart.user, checkout_data)

    assert not Address.objects.exists()


def test_save_shipping_saves_the_shipping_address(cart, cart_item, checkout_data):
    place_order(cart, cart.user, checkout_data, save_shipping=True)

    saved = Address.objects.get()
    assert saved.user == cart.user
    assert saved.street == "12 Cortex Lane"
    assert saved.zip == "79015"


def test_save_billing_saves_the_billing_address(cart, cart_item, checkout_data):
    place_order(cart, cart.user, checkout_data, save_billing=True)

    assert Address.objects.get().zip == "79015-1234"


def test_saving_both_when_identical_saves_one_address(cart, cart_item, checkout_data):
    for part in Address.PARTS:
        checkout_data[f"billing_{part}"] = checkout_data[f"shipping_{part}"]

    place_order(cart, cart.user, checkout_data, save_shipping=True, save_billing=True)

    assert Address.objects.count() == 1


def test_the_first_saved_address_becomes_the_default(cart, cart_item, checkout_data):
    place_order(cart, cart.user, checkout_data, save_shipping=True)

    user = cart.user
    user.refresh_from_db()
    assert user.default_shipping_address == Address.objects.get()


def test_a_rejected_order_saves_no_address(cart, checkout_data):
    with pytest.raises(ValueError):
        place_order(cart, cart.user, checkout_data, save_shipping=True)

    assert not Address.objects.exists()


def test_a_failed_address_save_places_no_order(
    cart, cart_item, checkout_data, monkeypatch
):
    """All-or-nothing covers the address book too."""

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(Address.objects, "save_from_checkout", explode)

    with pytest.raises(RuntimeError):
        place_order(cart, cart.user, checkout_data, save_shipping=True)

    assert not Order.objects.exists()
    assert CartItem.objects.count() == 1
