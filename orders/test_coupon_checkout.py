"""Coupons at checkout: place_order's coupon seam, the Apply button, and
coupon lines on order pages.

The promise under test: the customer sees the price drop before paying,
pays exactly that, and a code that's gone bad produces a message — never
an error page, never an order at a price they didn't see.

``cart_item`` is 2 × Seraphine Home Hub at $349.99 ($699.98). SUMMER-15
takes 15% off: $105.00 off, $594.98 to pay.
"""

from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.urls import reverse
from django.utils import timezone

from coupons.models import CouponError

from .models import CartItem, Order
from .services import place_order
from .test_checkout_form import VALID_DATA

pytestmark = pytest.mark.django_db


@pytest.fixture
def summer(make_coupon):
    return make_coupon(code="SUMMER-15", value=Decimal("15"))


@pytest.fixture
def expired(make_coupon):
    now = timezone.now()
    return make_coupon(
        code="SPRING-SALE",
        starts_at=now - timedelta(days=40),
        expires_at=now - timedelta(days=1),
    )


@pytest.fixture
def discounted_order(summer, cart, cart_item):
    return place_order(cart, cart.user, dict(VALID_DATA), coupon_code="SUMMER-15")


def apply(client, code):
    return client.post(reverse("orders:checkout_apply_coupon"), {"coupon_code": code})


# --- place_order -------------------------------------------------------------


def test_place_order_applies_the_coupon(
    make_coupon, cart, cart_item, accessory, product
):
    cart.items.create(product=accessory, quantity=1)
    coupon = make_coupon(products=[product])

    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="seraphine50")

    assert order.subtotal == Decimal("748.98")
    assert order.discount == Decimal("349.99")
    assert order.total == Decimal("398.99")
    assert order.coupon == coupon
    assert order.coupon_code == "SERAPHINE50"
    hub, mount = order.items.all()
    assert hub.discount == Decimal("349.99")
    assert mount.discount == Decimal("0.00")


def test_without_a_code_nothing_is_discounted(cart, cart_item):
    order = place_order(cart, cart.user, dict(VALID_DATA), coupon_code="")

    assert order.discount == Decimal("0.00")
    assert order.subtotal == order.total == Decimal("699.98")
    assert order.coupon is None
    assert order.coupon_code == ""
    assert order.items.get().discount == Decimal("0.00")


def test_a_bad_code_places_nothing_and_keeps_the_cart(expired, cart, cart_item):
    with pytest.raises(CouponError, match="has expired"):
        place_order(cart, cart.user, dict(VALID_DATA), coupon_code="SPRING-SALE")

    assert not Order.objects.exists()
    assert CartItem.objects.count() == 1


def test_an_unknown_code_places_nothing(cart, cart_item):
    with pytest.raises(CouponError, match="don't recognize"):
        place_order(cart, cart.user, dict(VALID_DATA), coupon_code="THOUGHTS10")

    assert not Order.objects.exists()


def test_the_order_keeps_its_code_after_the_coupon_is_deleted(discounted_order):
    discounted_order.coupon.delete()

    discounted_order.refresh_from_db()
    assert discounted_order.coupon is None
    assert discounted_order.coupon_code == "SUMMER-15"
    assert discounted_order.discount == Decimal("105.00")


# --- The Apply button ----------------------------------------------------------


def test_apply_requires_login(client):
    response = apply(client, "SUMMER-15")

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_checkout_offers_the_apply_button(client, customer, cart_item):
    client.force_login(customer)

    page = client.get(reverse("orders:checkout")).content.decode()

    assert reverse("orders:checkout_apply_coupon") in page


def test_applying_a_good_code_shows_the_price_drop(client, customer, cart_item, summer):
    client.force_login(customer)

    response = apply(client, "summer-15")

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "SUMMER-15" in page
    assert "699.98" in page  # the subtotal
    assert "105.00" in page  # the discount
    assert "594.98" in page  # the new total
    assert 'value="SUMMER-15"' in page  # carried to "Place order"


def test_applying_an_expired_code_says_so(client, customer, cart_item, expired):
    client.force_login(customer)

    response = apply(client, "SPRING-SALE")

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "has expired" in page
    assert "699.98" in page  # the total is untouched
    assert 'value="SPRING-SALE"' not in page  # nothing carried forward


@pytest.mark.parametrize("code", ["THOUGHTS10", "X" * 500, "<script>alert(1)</script>"])
def test_any_junk_gets_a_message_not_an_error(client, customer, cart_item, code):
    client.force_login(customer)

    response = apply(client, code)

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "recognize that code" in page  # the apostrophe renders escaped
    assert "<script>alert(1)</script>" not in page


def test_applying_a_blank_code_removes_the_coupon(client, customer, cart_item):
    client.force_login(customer)

    response = apply(client, "")

    page = response.content.decode()
    assert "699.98" in page
    assert "recognize that code" not in page


def test_apply_renders_a_partial_and_places_nothing(
    client, customer, cart_item, summer
):
    client.force_login(customer)

    page = apply(client, "SUMMER-15").content.decode()

    assert "<html" not in page
    assert not Order.objects.exists()
    assert CartItem.objects.count() == 1


# --- Placing the order -----------------------------------------------------------


def test_checking_out_with_a_code_charges_the_discounted_total(
    client, customer, cart_item, summer
):
    client.force_login(customer)

    response = client.post(
        reverse("orders:checkout"), {**VALID_DATA, "coupon_code": "SUMMER-15"}
    )

    order = Order.objects.get()
    assert response.url == reverse("orders:confirmation", kwargs={"pk": order.pk})
    assert order.total == Decimal("594.98")


def test_a_code_gone_bad_at_checkout_keeps_the_page_and_places_nothing(
    client, customer, cart_item, expired
):
    """Applied while valid, expired before "Place order": show the page
    again with a message and the customer's entries — no order."""
    client.force_login(customer)

    response = client.post(
        reverse("orders:checkout"), {**VALID_DATA, "coupon_code": "SPRING-SALE"}
    )

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "has expired" in page
    assert "12 Cortex Lane" in page
    assert not Order.objects.exists()
    assert CartItem.objects.exists()


# --- Coupon lines on order pages ---------------------------------------------------


@pytest.mark.parametrize("url_name", ["orders:confirmation", "orders:detail"])
def test_customer_order_pages_show_the_coupon(
    client, customer, discounted_order, url_name
):
    client.force_login(customer)

    page = client.get(
        reverse(url_name, kwargs={"pk": discounted_order.pk})
    ).content.decode()

    assert "SUMMER-15" in page
    assert "699.98" in page
    assert "105.00" in page
    assert "594.98" in page


def test_back_office_order_detail_shows_the_coupon(
    client, staff_user, discounted_order
):
    client.force_login(staff_user)

    page = client.get(
        reverse("orders:manage_order_detail", kwargs={"pk": discounted_order.pk})
    ).content.decode()

    assert "SUMMER-15" in page
    assert "105.00" in page
