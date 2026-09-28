"""Coupon rules: finding a code, what it's worth, and when it says no.

Every refusal a customer can meet is a ``CouponError`` carrying the
message checkout shows, so each message is pinned here — a friendly,
specific message (never an error page) is the feature.

Worked numbers come from the shared fixtures: ``cart_item`` is
2 × Seraphine Home Hub at $349.99 ($699.98); ``mount_line`` adds
1 × Seraphine Wall Mount at $49.00 ($748.98 in all).
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.utils import timezone

from coupons.models import Coupon, CouponError
from orders.models import Cart, Order
from orders.services import place_order
from orders.test_checkout_form import VALID_DATA

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)


@pytest.fixture
def mount_line(cart, cart_item, accessory):
    """A second line, after the hub: 1 × Seraphine Wall Mount at $49.00."""
    return cart.items.create(product=accessory, quantity=1)


@pytest.fixture
def stranger(db):
    return get_user_model().objects.create_user(username="stranger", password="x")


def use(coupon, user, product):
    """Place an order for one ``product`` with ``coupon`` — spending a use."""
    cart = Cart.for_user(user)
    cart.add(product)
    return place_order(cart, user, dict(VALID_DATA), coupon_code=coupon.code)


# --- The permission ----------------------------------------------------------


def test_the_manage_permission_exists():
    assert Permission.objects.filter(
        codename="manage_coupons", content_type__app_label="coupons"
    ).exists()


# --- Finding a code ----------------------------------------------------------


def test_codes_are_stored_in_uppercase(make_coupon):
    coupon = make_coupon(code="summer-26")

    coupon.refresh_from_db()
    assert coupon.code == "SUMMER-26"


def test_for_code_ignores_case_and_spaces(make_coupon):
    coupon = make_coupon()

    assert Coupon.objects.for_code("  seraphine50 ") == coupon


def test_an_unknown_code_is_not_recognized():
    with pytest.raises(CouponError, match="don't recognize"):
        Coupon.objects.for_code("THOUGHTS10")


def test_an_archived_code_reads_as_expired(make_coupon):
    make_coupon(is_archived=True)

    with pytest.raises(CouponError, match="has expired"):
        Coupon.objects.for_code("SERAPHINE50")


def test_a_live_coupon_wins_over_an_archived_namesake(make_coupon):
    make_coupon(is_archived=True, value=Decimal("10"))
    current = make_coupon(value=Decimal("20"))

    assert Coupon.objects.for_code("SERAPHINE50") == current


def test_coupon_error_is_a_value_error():
    """``place_order`` documents that it raises ValueError; coupons keep it."""
    assert issubclass(CouponError, ValueError)


# --- Code uniqueness ---------------------------------------------------------


def test_two_unarchived_coupons_cannot_share_a_code(make_coupon):
    make_coupon()

    with pytest.raises(IntegrityError), transaction.atomic():
        make_coupon()


def test_archiving_frees_a_code(make_coupon):
    make_coupon(is_archived=True)
    make_coupon()

    assert Coupon.objects.filter(code="SERAPHINE50").count() == 2


# --- What a coupon is worth --------------------------------------------------


def test_percent_off_the_order(make_coupon, cart, cart_item):
    result = make_coupon().evaluate(cart, cart.user)

    assert result.subtotal == Decimal("699.98")
    assert result.discount == Decimal("349.99")
    assert result.total == Decimal("349.99")


def test_percent_rounds_to_the_cent(make_coupon, cart, cart_item):
    result = make_coupon(value=Decimal("15")).evaluate(cart, cart.user)

    assert result.discount == Decimal("105.00")  # 104.997
    assert result.total == Decimal("594.98")


def test_fixed_amount_off_the_order(make_coupon, cart, cart_item):
    coupon = make_coupon(
        discount_type=Coupon.DiscountType.FIXED, value=Decimal("20.00")
    )

    result = coupon.evaluate(cart, cart.user)

    assert result.discount == Decimal("20.00")
    assert result.total == Decimal("679.98")


def test_a_discount_never_goes_below_zero(make_coupon, cart, cart_item):
    coupon = make_coupon(
        discount_type=Coupon.DiscountType.FIXED, value=Decimal("1000.00")
    )

    result = coupon.evaluate(cart, cart.user)

    assert result.discount == Decimal("699.98")
    assert result.total == Decimal("0.00")


def test_a_product_limited_coupon_discounts_only_those_products(
    make_coupon, cart, mount_line, product, accessory
):
    result = make_coupon(products=[product]).evaluate(cart, cart.user)

    assert result.subtotal == Decimal("748.98")
    assert result.discount == Decimal("349.99")
    assert result.total == Decimal("398.99")
    assert result.line_discounts == {
        product.pk: Decimal("349.99"),
        accessory.pk: Decimal("0.00"),
    }


def test_a_fixed_amount_comes_off_once_not_per_unit(
    make_coupon, cart, cart_item, product
):
    coupon = make_coupon(
        products=[product],
        discount_type=Coupon.DiscountType.FIXED,
        value=Decimal("20.00"),
    )

    assert coupon.evaluate(cart, cart.user).discount == Decimal("20.00")


def test_a_fixed_amount_is_split_by_line_value(
    make_coupon, cart, mount_line, product, accessory
):
    """$20 over $699.98 + $49.00: the hub's share rounds, the last line
    absorbs the leftover cent so the shares add up exactly."""
    coupon = make_coupon(
        discount_type=Coupon.DiscountType.FIXED, value=Decimal("20.00")
    )

    result = coupon.evaluate(cart, cart.user)

    assert result.line_discounts == {
        product.pk: Decimal("18.69"),
        accessory.pk: Decimal("1.31"),
    }


def test_line_discounts_add_up_to_the_discount(make_coupon, cart, mount_line):
    result = make_coupon(value=Decimal("15")).evaluate(cart, cart.user)

    assert sum(result.line_discounts.values()) == result.discount


# --- Refusals: each with its own message --------------------------------------


def test_an_expired_code_says_so(make_coupon, cart, cart_item):
    now = timezone.now()
    coupon = make_coupon(starts_at=now - 30 * DAY, expires_at=now - DAY)

    with pytest.raises(CouponError, match="has expired"):
        coupon.evaluate(cart, cart.user)


def test_a_scheduled_code_is_not_active_yet(make_coupon, cart, cart_item):
    now = timezone.now()
    coupon = make_coupon(starts_at=now + DAY, expires_at=now + 10 * DAY)

    with pytest.raises(CouponError, match="isn't active yet"):
        coupon.evaluate(cart, cart.user)


def test_a_switched_off_code_is_no_longer_available(make_coupon, cart, cart_item):
    coupon = make_coupon(is_active=False)

    with pytest.raises(CouponError, match="no longer available"):
        coupon.evaluate(cart, cart.user)


def test_a_code_for_other_products_does_not_apply(
    make_coupon, cart, cart_item, accessory
):
    coupon = make_coupon(products=[accessory])

    with pytest.raises(CouponError, match="doesn't apply to anything in your cart"):
        coupon.evaluate(cart, cart.user)


def test_below_the_minimum_says_how_much_more(make_coupon, cart, cart_item):
    coupon = make_coupon(min_subtotal=Decimal("800.00"))

    with pytest.raises(CouponError, match=r"Spend \$100\.02 more to use SERAPHINE50"):
        coupon.evaluate(cart, cart.user)


def test_the_minimum_counts_only_eligible_products(
    make_coupon, cart, mount_line, product
):
    """The cart is $748.98, but only the $699.98 of hubs counts."""
    coupon = make_coupon(products=[product], min_subtotal=Decimal("700.00"))

    with pytest.raises(CouponError, match=r"Spend \$0\.02 more"):
        coupon.evaluate(cart, cart.user)


# --- Usage limits --------------------------------------------------------------


def test_a_customer_can_use_a_code_once_by_default(make_coupon, customer, product):
    coupon = make_coupon()
    use(coupon, customer, product)
    cart = Cart.for_user(customer)
    cart.add(product)

    with pytest.raises(CouponError, match="already used"):
        coupon.evaluate(cart, customer)


def test_the_per_customer_limit_can_be_lifted(make_coupon, customer, product):
    coupon = make_coupon(max_uses_per_customer=None)

    use(coupon, customer, product)
    use(coupon, customer, product)

    assert coupon.orders.count() == 2


def test_the_total_cap_stops_everyone(make_coupon, customer, stranger, product):
    coupon = make_coupon(max_uses=1)
    use(coupon, stranger, product)
    cart = Cart.for_user(customer)
    cart.add(product)

    with pytest.raises(CouponError, match="reached its limit"):
        coupon.evaluate(cart, customer)


def test_a_cancelled_order_gives_its_use_back(make_coupon, customer, product):
    coupon = make_coupon()
    order = use(coupon, customer, product)
    order.status = Order.Status.CANCELLED
    order.save()
    cart = Cart.for_user(customer)
    cart.add(product)

    # 174.995 — half-cents round up, like a till.
    assert coupon.evaluate(cart, customer).discount == Decimal("175.00")


# --- Status and summary, for the back office -----------------------------------


def test_status_follows_the_switch_the_dates_and_the_archive(make_coupon):
    now = timezone.now()

    assert make_coupon(code="LIVE").status == Coupon.Status.LIVE
    assert (
        make_coupon(code="SOON", starts_at=now + DAY, expires_at=now + 9 * DAY).status
        == Coupon.Status.SCHEDULED
    )
    assert (
        make_coupon(code="GONE", starts_at=now - 9 * DAY, expires_at=now - DAY).status
        == Coupon.Status.EXPIRED
    )
    assert make_coupon(code="OFF", is_active=False).status == Coupon.Status.SWITCHED_OFF
    assert make_coupon(code="OLD", is_archived=True).status == Coupon.Status.ARCHIVED


def test_status_is_used_up_at_the_total_cap(make_coupon, customer, product):
    coupon = make_coupon(max_uses=1)
    use(coupon, customer, product)

    assert coupon.status == Coupon.Status.USED_UP


def test_a_coupon_is_locked_once_used(make_coupon, customer, product):
    coupon = make_coupon()
    assert not coupon.is_locked

    use(coupon, customer, product)

    assert coupon.is_locked


def test_summary_reads_in_plain_words(make_coupon, product, accessory):
    assert make_coupon(code="A", value=Decimal("15")).summary == "15% off your order"
    assert make_coupon(code="B", products=[product]).summary == "50% off 1 product"
    assert (
        make_coupon(code="C", products=[product, accessory]).summary
        == "50% off 2 products"
    )
    assert (
        make_coupon(
            code="D",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("20.00"),
            min_subtotal=Decimal("100.00"),
        ).summary
        == "$20.00 off your order, min. spend $100.00"
    )
