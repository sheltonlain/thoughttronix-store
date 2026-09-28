"""The Coupons tab: Marketing-only access, the status list, CRUD, locking.

Coupons sit behind ``is_staff`` *and* the ``coupons.manage_coupons``
permission — other staff get 403 and never see the tab.
"""

from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from coupons.models import Coupon
from orders.services import place_order
from orders.test_checkout_form import VALID_DATA

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)


def local(moment):
    """A datetime as a ``datetime-local`` input submits it."""
    return timezone.localtime(moment).strftime("%Y-%m-%dT%H:%M")


def coupon_data(**overrides):
    now = timezone.now()
    data = {
        "code": "WELCOME20",
        "discount_type": "FIXED",
        "value": "20.00",
        "is_active": "on",
        "starts_at": local(now - DAY),
        "expires_at": local(now + 30 * DAY),
        "max_uses_per_customer": "1",
        "max_uses": "",
        "min_subtotal": "100.00",
    }
    data.update(overrides)
    return data


def page_urls(coupon):
    """The GET-able coupon pages."""
    return [
        reverse("coupons:manage_coupons"),
        reverse("coupons:manage_coupon_create"),
        reverse("coupons:manage_coupon_update", kwargs={"pk": coupon.pk}),
        reverse("coupons:manage_coupon_delete", kwargs={"pk": coupon.pk}),
    ]


def manage_urls(coupon):
    """Every coupon URL, POST-only actions included, for the denial sweeps."""
    return [
        *page_urls(coupon),
        reverse("coupons:manage_coupon_archive", kwargs={"pk": coupon.pk}),
        reverse("coupons:manage_coupon_restore", kwargs={"pk": coupon.pk}),
    ]


@pytest.fixture
def coupon(make_coupon):
    return make_coupon()


@pytest.fixture
def used_coupon(coupon, cart, cart_item):
    """SERAPHINE50 after one order: 50% off $699.98 is $349.99 discounted."""
    place_order(cart, cart.user, dict(VALID_DATA), coupon_code=coupon.code)
    return coupon


# --- Access control ----------------------------------------------------------


def test_anonymous_users_are_sent_to_login(client, coupon):
    for url in manage_urls(coupon):
        response = client.get(url)

        assert response.status_code == HTTPStatus.FOUND, url
        assert reverse("accounts:login") in response.url


def test_customers_get_403(client, customer, coupon):
    client.force_login(customer)

    for url in manage_urls(coupon):
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN, url


def test_staff_without_the_permission_get_403(client, staff_user, coupon):
    client.force_login(staff_user)

    for url in manage_urls(coupon):
        assert client.get(url).status_code == HTTPStatus.FORBIDDEN, url


def test_marketing_get_200(client, marketing_user, coupon):
    client.force_login(marketing_user)

    for url in page_urls(coupon):
        response = client.get(url)

        assert response.status_code == HTTPStatus.OK, url
        assert "{#" not in response.content.decode(), url


def test_superusers_have_the_permission_implicitly(client, coupon):
    admin = get_user_model().objects.create_superuser(
        username="admin", password="admin123"
    )
    client.force_login(admin)

    assert client.get(reverse("coupons:manage_coupons")).status_code == HTTPStatus.OK


def test_the_coupons_tab_shows_for_marketing_only(client, marketing_user, staff_user):
    tab = reverse("coupons:manage_coupons")

    client.force_login(marketing_user)
    assert tab in client.get(reverse("products:manage_products")).content.decode()

    client.force_login(staff_user)
    assert tab not in client.get(reverse("products:manage_products")).content.decode()


# --- The coupon list ---------------------------------------------------------


def test_list_shows_status_summary_and_usage(client, marketing_user, make_coupon):
    now = timezone.now()
    make_coupon(max_uses=100)
    make_coupon(code="SPRING-SALE", starts_at=now - 40 * DAY, expires_at=now - DAY)
    client.force_login(marketing_user)

    page = client.get(reverse("coupons:manage_coupons")).content.decode()

    assert "SERAPHINE50" in page
    assert "SPRING-SALE" in page
    assert "Live" in page
    assert "Expired" in page
    assert "50% off your order" in page
    assert "0 / 100" in page


def test_list_filters_by_status(client, marketing_user, make_coupon):
    now = timezone.now()
    make_coupon()
    make_coupon(code="SPRING-SALE", starts_at=now - 40 * DAY, expires_at=now - DAY)
    client.force_login(marketing_user)

    page = client.get(
        reverse("coupons:manage_coupons"), {"status": "EXPIRED"}
    ).content.decode()

    assert "SPRING-SALE" in page
    assert "SERAPHINE50" not in page


def test_archived_coupons_hide_until_asked_for(client, marketing_user, make_coupon):
    make_coupon(code="LAST-YEAR", is_archived=True)
    client.force_login(marketing_user)
    url = reverse("coupons:manage_coupons")

    assert "LAST-YEAR" not in client.get(url).content.decode()
    assert "LAST-YEAR" in client.get(url, {"status": "ARCHIVED"}).content.decode()


def test_unknown_status_filter_is_ignored(client, marketing_user, coupon):
    client.force_login(marketing_user)

    page = client.get(
        reverse("coupons:manage_coupons"), {"status": "TELEPORTED"}
    ).content.decode()

    assert "SERAPHINE50" in page


def test_list_has_a_designed_empty_state(client, marketing_user):
    client.force_login(marketing_user)

    page = client.get(reverse("coupons:manage_coupons")).content.decode()

    assert "No coupons yet" in page


def test_filtered_empty_state_offers_to_clear(client, marketing_user, coupon):
    client.force_login(marketing_user)

    page = client.get(
        reverse("coupons:manage_coupons"), {"status": "SCHEDULED"}
    ).content.decode()

    assert "No coupons with that status" in page


# --- Creating and editing ------------------------------------------------------


def test_marketing_can_create_an_order_wide_coupon(client, marketing_user):
    client.force_login(marketing_user)

    response = client.post(
        reverse("coupons:manage_coupon_create"), coupon_data(), follow=True
    )

    coupon = Coupon.objects.get(code="WELCOME20")
    assert coupon.discount_type == Coupon.DiscountType.FIXED
    assert coupon.value == Decimal("20.00")
    assert coupon.min_subtotal == Decimal("100.00")
    assert coupon.max_uses_per_customer == 1
    assert coupon.max_uses is None
    assert not coupon.products.exists()
    assert "created" in response.content.decode()


def test_marketing_can_limit_a_coupon_to_products(client, marketing_user, product):
    client.force_login(marketing_user)

    client.post(
        reverse("coupons:manage_coupon_create"),
        coupon_data(
            code="seraphine50",
            discount_type="PERCENT",
            value="50",
            products=[str(product.pk)],
        ),
    )

    coupon = Coupon.objects.get(code="SERAPHINE50")  # typed lowercase, stored upper
    assert list(coupon.products.all()) == [product]


def test_marketing_can_edit_an_unused_coupons_terms(client, marketing_user, coupon):
    client.force_login(marketing_user)

    client.post(
        reverse("coupons:manage_coupon_update", kwargs={"pk": coupon.pk}),
        coupon_data(code="SERAPHINE50", discount_type="PERCENT", value="40"),
    )

    coupon.refresh_from_db()
    assert coupon.value == Decimal("40")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"discount_type": "PERCENT", "value": "150"}, "100%"),
        ({"value": "0"}, "greater than or equal to 0.01"),
        ({"code": "SAVE 20!"}, "letters, digits and hyphens"),
        ({"code": "AB"}, "at least 3 characters"),
        ({"expires_at": local(timezone.now() - 2 * DAY)}, "after the start"),
        ({"expires_at": ""}, "This field is required."),
    ],
)
def test_bad_coupons_are_rejected(client, marketing_user, overrides, message):
    client.force_login(marketing_user)

    response = client.post(
        reverse("coupons:manage_coupon_create"), coupon_data(**overrides)
    )

    assert response.status_code == HTTPStatus.OK
    assert message in response.content.decode()
    assert not Coupon.objects.exists()


def test_a_code_in_use_is_rejected(client, marketing_user, coupon):
    client.force_login(marketing_user)

    response = client.post(
        reverse("coupons:manage_coupon_create"), coupon_data(code="seraphine50")
    )

    assert "already in use" in response.content.decode()
    assert Coupon.objects.count() == 1


def test_an_archived_coupons_code_can_be_reused(client, marketing_user, make_coupon):
    make_coupon(code="SUMMER", is_archived=True)
    client.force_login(marketing_user)

    client.post(reverse("coupons:manage_coupon_create"), coupon_data(code="SUMMER"))

    assert Coupon.objects.filter(code="SUMMER", is_archived=False).exists()


# --- Locked once used ----------------------------------------------------------


def test_a_used_coupons_terms_are_locked(client, marketing_user, used_coupon):
    client.force_login(marketing_user)
    later = timezone.now() + 60 * DAY

    client.post(
        reverse("coupons:manage_coupon_update", kwargs={"pk": used_coupon.pk}),
        coupon_data(
            code="CHEAPER",
            discount_type="FIXED",
            value="5.00",
            expires_at=local(later),
            max_uses="500",
        ),
    )

    used_coupon.refresh_from_db()
    # The deal is frozen...
    assert used_coupon.code == "SERAPHINE50"
    assert used_coupon.discount_type == Coupon.DiscountType.PERCENT
    assert used_coupon.value == Decimal("50")
    # ...but its dates and limits stay Marketing's to change.
    assert local(used_coupon.expires_at) == local(later)
    assert used_coupon.max_uses == 500


def test_the_edit_page_explains_the_lock_and_shows_usage(
    client, marketing_user, used_coupon
):
    client.force_login(marketing_user)

    page = client.get(
        reverse("coupons:manage_coupon_update", kwargs={"pk": used_coupon.pk})
    ).content.decode()

    assert "Used by 1 order" in page
    assert "349.99" in page


def test_an_unused_coupon_can_be_deleted(client, marketing_user, coupon):
    client.force_login(marketing_user)

    response = client.post(
        reverse("coupons:manage_coupon_delete", kwargs={"pk": coupon.pk})
    )

    assert response.url == reverse("coupons:manage_coupons")
    assert not Coupon.objects.exists()


def test_a_used_coupon_cannot_be_deleted(client, marketing_user, used_coupon):
    client.force_login(marketing_user)

    client.post(reverse("coupons:manage_coupon_delete", kwargs={"pk": used_coupon.pk}))

    assert Coupon.objects.filter(pk=used_coupon.pk).exists()


# --- Archiving -----------------------------------------------------------------


def test_marketing_can_archive_and_restore(client, marketing_user, coupon):
    client.force_login(marketing_user)

    client.post(reverse("coupons:manage_coupon_archive", kwargs={"pk": coupon.pk}))
    coupon.refresh_from_db()
    assert coupon.is_archived

    client.post(reverse("coupons:manage_coupon_restore", kwargs={"pk": coupon.pk}))
    coupon.refresh_from_db()
    assert not coupon.is_archived


def test_restoring_is_refused_when_the_code_was_taken(
    client, marketing_user, make_coupon
):
    old = make_coupon(is_archived=True)
    make_coupon()
    client.force_login(marketing_user)

    response = client.post(
        reverse("coupons:manage_coupon_restore", kwargs={"pk": old.pk}), follow=True
    )

    old.refresh_from_db()
    assert old.is_archived
    assert "already in use" in response.content.decode()
