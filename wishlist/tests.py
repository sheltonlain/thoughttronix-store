from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from .models import Wishlist, WishlistItem


@pytest.fixture
def wishlist(customer):
    return Wishlist.for_user(customer)


def detail_url(product, query=""):
    return reverse("products:detail", kwargs={"slug": product.slug}) + query


# --- Model behavior ---------------------------------------------------------


def test_wishlist_str(wishlist):
    assert str(wishlist) == "Wishlist for customer"


def test_wishlist_item_str(wishlist, product):
    assert str(wishlist.add(product)) == "Seraphine Home Hub"


def test_for_user_creates_the_wishlist_once(customer):
    first = Wishlist.for_user(customer)
    second = Wishlist.for_user(customer)

    assert first == second
    assert Wishlist.objects.count() == 1


def test_one_wishlist_per_user(wishlist, customer):
    with pytest.raises(IntegrityError):
        Wishlist.objects.create(user=customer)


def test_add_saves_the_product(wishlist, product):
    wishlist.add(product)

    assert wishlist.contains(product)


def test_add_is_idempotent(wishlist, product):
    first = wishlist.add(product)
    second = wishlist.add(product)

    assert first == second
    assert wishlist.items.count() == 1


def test_wishlist_product_pair_is_unique(wishlist, product):
    wishlist.add(product)

    with pytest.raises(IntegrityError):
        WishlistItem.objects.create(wishlist=wishlist, product=product)


def test_remove_unsaves_the_product(wishlist, product):
    wishlist.add(product)

    wishlist.remove(product)

    assert not wishlist.contains(product)


def test_remove_is_idempotent(wishlist, product, accessory):
    wishlist.add(accessory)

    wishlist.remove(product)

    assert not wishlist.contains(product)
    assert list(wishlist.items.values_list("product", flat=True)) == [accessory.pk]


def test_contains_is_per_wishlist(wishlist, product):
    other = Wishlist.for_user(
        get_user_model().objects.create_user(username="other", password="x")
    )
    other.add(product)

    assert not wishlist.contains(product)


def test_items_are_newest_first(wishlist, product, accessory, featured_product):
    now = timezone.now()
    WishlistItem.objects.create(
        wishlist=wishlist, product=accessory, added_at=now - timedelta(days=2)
    )
    WishlistItem.objects.create(wishlist=wishlist, product=product, added_at=now)
    WishlistItem.objects.create(
        wishlist=wishlist, product=featured_product, added_at=now - timedelta(days=1)
    )

    assert [item.product for item in wishlist.items.all()] == [
        product,
        featured_product,
        accessory,
    ]


def test_deleting_a_product_removes_it_from_every_wishlist(wishlist, product):
    other = Wishlist.for_user(
        get_user_model().objects.create_user(username="other", password="x")
    )
    wishlist.add(product)
    other.add(product)

    product.delete()

    assert not WishlistItem.objects.exists()
    assert Wishlist.objects.count() == 2


def test_deleting_a_user_deletes_their_wishlist(wishlist, customer, product):
    wishlist.add(product)

    customer.delete()

    assert not Wishlist.objects.exists()
    assert not WishlistItem.objects.exists()


def test_admin_shows_wishlists_with_their_items(admin_client, wishlist, product):
    wishlist.add(product)

    changelist = admin_client.get(reverse("admin:wishlist_wishlist_changelist"))
    change = admin_client.get(
        reverse("admin:wishlist_wishlist_change", args=[wishlist.pk])
    )

    assert changelist.status_code == HTTPStatus.OK
    assert "customer" in changelist.content.decode()
    assert change.status_code == HTTPStatus.OK
    assert "Seraphine Home Hub" in change.content.decode()


# --- Add and remove endpoints (HTMX) -----------------------------------------


@pytest.mark.parametrize("name", ["wishlist:add", "wishlist:remove"])
def test_endpoints_require_login(client, product, name):
    response = client.post(reverse(name, kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url
    assert not Wishlist.objects.exists()


@pytest.mark.parametrize("name", ["wishlist:add", "wishlist:remove"])
def test_endpoints_reject_get(client, customer, product, name):
    client.force_login(customer)

    response = client.get(reverse(name, kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert not WishlistItem.objects.exists()


def test_add_returns_the_saved_button(client, customer, product):
    client.force_login(customer)

    response = client.post(reverse("wishlist:add", kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "♥ Saved · Remove" in page
    assert 'aria-pressed="true"' in page
    assert reverse("wishlist:remove", kwargs={"pk": product.pk}) in page
    assert customer.wishlist.contains(product)


def test_remove_returns_the_unsaved_button(client, customer, wishlist, product):
    wishlist.add(product)
    client.force_login(customer)

    response = client.post(reverse("wishlist:remove", kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "♡ Save to wishlist" in page
    assert 'aria-pressed="false"' in page
    assert reverse("wishlist:add", kwargs={"pk": product.pk}) in page
    assert not wishlist.contains(product)


def test_repeated_add_stays_saved(client, customer, product):
    """A double-click on Save never unsaves."""
    client.force_login(customer)
    client.post(reverse("wishlist:add", kwargs={"pk": product.pk}))

    response = client.post(reverse("wishlist:add", kwargs={"pk": product.pk}))

    assert 'aria-pressed="true"' in response.content.decode()
    assert customer.wishlist.items.count() == 1


def test_removing_an_unsaved_product_stays_unsaved(client, customer, product):
    """A stale Remove button in another tab never saves."""
    client.force_login(customer)

    response = client.post(reverse("wishlist:remove", kwargs={"pk": product.pk}))

    assert response.status_code == HTTPStatus.OK
    assert 'aria-pressed="false"' in response.content.decode()
    assert not WishlistItem.objects.exists()


@pytest.mark.parametrize("name", ["wishlist:add", "wishlist:remove"])
def test_button_guards_against_double_clicks(client, customer, product, name):
    """The swapped-in button ignores clicks while it settles, so a
    double-click's second click can't hit the new, opposite button."""
    client.force_login(customer)

    page = client.post(reverse(name, kwargs={"pk": product.pk})).content.decode()

    assert 'hx-swap="outerHTML settle:500ms"' in page
    assert 'hx-disabled-elt="this"' in page
    assert "[&.htmx-added]:pointer-events-none" in page


def test_unavailable_product_can_be_saved(client, customer, unavailable_product):
    client.force_login(customer)

    response = client.post(
        reverse("wishlist:add", kwargs={"pk": unavailable_product.pk})
    )

    assert response.status_code == HTTPStatus.OK
    assert customer.wishlist.contains(unavailable_product)


def test_add_unknown_product_404s(client, customer, db):
    client.force_login(customer)

    response = client.post(reverse("wishlist:add", kwargs={"pk": 9999}))

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- The product detail page -------------------------------------------------


def test_detail_shows_save_button_when_not_saved(client, customer, product):
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert "♡ Save to wishlist" in page
    assert 'aria-pressed="false"' in page
    assert reverse("wishlist:add", kwargs={"pk": product.pk}) in page


def test_detail_shows_saved_button_when_saved(client, customer, wishlist, product):
    wishlist.add(product)
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert "♥ Saved · Remove" in page
    assert 'aria-pressed="true"' in page
    assert reverse("wishlist:remove", kwargs={"pk": product.pk}) in page


def test_detail_shows_sign_in_link_to_visitors(client, product):
    page = client.get(detail_url(product)).content.decode()

    assert "♡ Save to wishlist" in page
    assert "aria-pressed" not in page
    assert "hx-post" not in page.split("wishlist-control", 1)[1]


def test_visitor_link_returns_to_the_product_flagged(client, product):
    page = client.get(detail_url(product, "?wishlist=1")).content.decode()

    # The return URL is rebuilt from the product, never the current query.
    login = reverse("accounts:login")
    assert f'{login}?next=/products/seraphine-home-hub/%3Fwishlist%3D1"' in page


def test_add_to_cart_is_the_only_primary_button(client, customer, product):
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert page.count("btn-primary") == 1


HINT = "click Save to keep this product"


def test_hint_shows_after_sign_in_on_an_unsaved_product(client, customer, product):
    client.force_login(customer)

    page = client.get(detail_url(product, "?wishlist=1")).content.decode()

    assert HINT in page


def test_hint_hidden_without_the_flag(client, customer, product):
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert HINT not in page


def test_hint_hidden_from_visitors(client, product):
    page = client.get(detail_url(product, "?wishlist=1")).content.decode()

    assert HINT not in page


def test_hint_hidden_when_already_saved(client, customer, wishlist, product):
    wishlist.add(product)
    client.force_login(customer)

    page = client.get(detail_url(product, "?wishlist=1")).content.decode()

    assert HINT not in page


def test_flagged_get_never_saves(client, customer, product):
    client.force_login(customer)

    client.get(detail_url(product, "?wishlist=1"))

    assert not Wishlist.objects.exists()
    assert not WishlistItem.objects.exists()


# --- The Wishlist page --------------------------------------------------------


def test_wishlist_page_lists_only_my_items_newest_first(
    client, customer, wishlist, product, accessory, featured_product
):
    now = timezone.now()
    WishlistItem.objects.create(
        wishlist=wishlist, product=accessory, added_at=now - timedelta(days=1)
    )
    WishlistItem.objects.create(wishlist=wishlist, product=product, added_at=now)
    stranger = get_user_model().objects.create_user(username="stranger", password="x")
    Wishlist.for_user(stranger).add(featured_product)
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert "Seraphine Home Hub" in page
    assert "Seraphine Wall Mount" in page
    assert page.index("Seraphine Home Hub") < page.index("Seraphine Wall Mount")
    assert "Cortex Crown" not in page


def test_removing_another_customers_item_404s(client, customer, wishlist, product):
    stranger = get_user_model().objects.create_user(username="stranger", password="x")
    their_item = Wishlist.for_user(stranger).add(product)
    wishlist.add(product)
    client.force_login(customer)

    response = client.post(
        reverse("wishlist:remove_item", kwargs={"pk": their_item.pk})
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert WishlistItem.objects.filter(pk=their_item.pk).exists()
    assert wishlist.contains(product)


def test_removing_the_last_item_shows_the_empty_state(
    client, customer, wishlist, product
):
    item = wishlist.add(product)
    client.force_login(customer)

    response = client.post(reverse("wishlist:remove_item", kwargs={"pk": item.pk}))

    assert response.status_code == HTTPStatus.OK
    page = response.content.decode()
    assert "<html" not in page
    assert "Your wishlist is empty" in page
    assert reverse("products:catalog") in page
    assert "Seraphine Home Hub" not in page
    assert not wishlist.contains(product)


def test_wishlist_page_requires_login(client, db):
    response = client.get(reverse("wishlist:wishlist"))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_wishlist_page_rows_show_image_link_and_price(
    client, customer, wishlist, product
):
    wishlist.add(product)
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert f'src="{product.display_image_url}"' in page
    assert f'href="{product.get_absolute_url()}"' in page
    assert "$349.99" in page
    assert reverse("orders:add", kwargs={"pk": product.pk}) in page
    assert "Unavailable" not in page


def test_wishlist_page_marks_unavailable_products(
    client, customer, wishlist, unavailable_product
):
    wishlist.add(unavailable_product)
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert "badge-warning" in page
    assert (
        '<button class="btn btn-outline btn-sm" disabled>Unavailable</button>' in page
    )
    assert reverse("orders:add", kwargs={"pk": unavailable_product.pk}) not in page


def test_wishlist_page_shows_cart_quantities(
    client, customer, wishlist, product, cart_item
):
    wishlist.add(product)
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert "In cart (2) — add another" in page


def test_adding_to_cart_leaves_the_product_saved(client, customer, wishlist, product):
    wishlist.add(product)
    client.force_login(customer)

    client.post(reverse("orders:add", kwargs={"pk": product.pk}))

    assert customer.cart.items.filter(product=product).exists()
    assert wishlist.contains(product)


def test_empty_wishlist_page_shows_the_empty_state(client, customer):
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert "Your wishlist is empty" in page
    assert reverse("products:catalog") in page


def test_wishlist_page_remove_buttons_target_the_contents(
    client, customer, wishlist, product
):
    item = wishlist.add(product)
    client.force_login(customer)

    page = client.get(reverse("wishlist:wishlist")).content.decode()

    assert 'id="wishlist-contents"' in page
    assert reverse("wishlist:remove_item", kwargs={"pk": item.pk}) in page
    assert 'hx-target="#wishlist-contents"' in page


def test_remove_item_requires_login(client, wishlist, product):
    item = wishlist.add(product)

    response = client.post(reverse("wishlist:remove_item", kwargs={"pk": item.pk}))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url
    assert wishlist.contains(product)


def test_remove_item_rejects_get(client, customer, wishlist, product):
    item = wishlist.add(product)
    client.force_login(customer)

    response = client.get(reverse("wishlist:remove_item", kwargs={"pk": item.pk}))

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert wishlist.contains(product)


def test_remove_item_rerenders_the_remaining_items(
    client, customer, wishlist, product, accessory
):
    item = wishlist.add(product)
    wishlist.add(accessory)
    client.force_login(customer)

    response = client.post(reverse("wishlist:remove_item", kwargs={"pk": item.pk}))

    page = response.content.decode()
    assert "<html" not in page
    assert "Seraphine Wall Mount" in page
    assert "Seraphine Home Hub" not in page
    assert "Your wishlist is empty" not in page
    assert not wishlist.contains(product)


# --- Navbar ------------------------------------------------------------------

NAV_LINK = 'href="/wishlist/" class="btn btn-ghost btn-sm">Wishlist</a>'


def test_navbar_shows_wishlist_link_to_customers(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert NAV_LINK in page


def test_navbar_hides_wishlist_link_from_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert NAV_LINK not in page
