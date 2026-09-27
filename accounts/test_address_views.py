"""The address book pages: CRUD, defaults, and owner-only access."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from accounts.models import Address

NEW_ADDRESS = {
    "label": "Work",
    "name": "Casey Monroe",
    "street": "1 Neural Plaza",
    "line2": "Suite 400",
    "city": "Amarillo",
    "state": "TX",
    "zip": "79101",
}


def test_address_book_requires_login(client, db):
    response = client.get(reverse("accounts:addresses"))

    assert response.status_code == HTTPStatus.FOUND
    assert reverse("accounts:login") in response.url


def test_address_book_has_a_designed_empty_state(client, customer):
    client.force_login(customer)

    page = client.get(reverse("accounts:addresses")).content.decode()

    assert "No saved addresses yet" in page
    assert reverse("accounts:address_add") in page


def test_address_book_lists_addresses_with_default_badges(client, customer, address):
    customer.fill_empty_defaults(address)
    client.force_login(customer)

    page = client.get(reverse("accounts:addresses")).content.decode()

    assert "214 Synapse Street" in page
    assert "Default shipping" in page
    assert "Default billing" in page


def test_navbar_links_to_the_address_book(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:addresses") in page


def test_adding_an_address(client, customer):
    client.force_login(customer)

    response = client.post(reverse("accounts:address_add"), NEW_ADDRESS)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:addresses")
    saved = Address.objects.get()
    assert saved.user == customer
    assert saved.label == "Work"


def test_the_first_address_added_becomes_the_default(client, customer):
    client.force_login(customer)

    client.post(reverse("accounts:address_add"), NEW_ADDRESS)

    customer.refresh_from_db()
    saved = Address.objects.get()
    assert customer.default_shipping_address == saved
    assert customer.default_billing_address == saved


def test_adding_an_address_keeps_an_existing_default(client, customer, address):
    customer.fill_empty_defaults(address)
    client.force_login(customer)

    client.post(reverse("accounts:address_add"), NEW_ADDRESS)

    customer.refresh_from_db()
    assert customer.default_shipping_address == address


def test_the_address_form_uses_the_checkout_rules(client, customer):
    client.force_login(customer)

    response = client.post(
        reverse("accounts:address_add"), {**NEW_ADDRESS, "zip": "790", "state": "XX"}
    )

    assert response.status_code == HTTPStatus.OK
    errors = response.context["form"].errors
    assert errors["zip"] == ["Enter a ZIP code like 79016 or 79016-1234."]
    assert "state" in errors
    assert not Address.objects.exists()


def test_the_label_is_optional(client, customer):
    client.force_login(customer)

    client.post(reverse("accounts:address_add"), {**NEW_ADDRESS, "label": ""})

    assert Address.objects.get().label == ""


def test_editing_an_address(client, customer, address):
    client.force_login(customer)

    response = client.post(
        reverse("accounts:address_edit", kwargs={"pk": address.pk}),
        {**NEW_ADDRESS, "street": "215 Synapse Street"},
    )

    assert response.status_code == HTTPStatus.FOUND
    address.refresh_from_db()
    assert address.street == "215 Synapse Street"


def test_deleting_an_address(client, customer, address):
    client.force_login(customer)
    url = reverse("accounts:address_delete", kwargs={"pk": address.pk})

    assert "Delete" in client.get(url).content.decode()
    response = client.post(url)

    assert response.status_code == HTTPStatus.FOUND
    assert not Address.objects.exists()


@pytest.mark.parametrize("kind", ["shipping", "billing"])
def test_setting_a_default(client, customer, address, kind):
    client.force_login(customer)

    response = client.post(
        reverse(f"accounts:address_default_{kind}", kwargs={"pk": address.pk})
    )

    assert response.status_code == HTTPStatus.FOUND
    customer.refresh_from_db()
    assert getattr(customer, f"default_{kind}_address") == address


def test_setting_a_default_is_post_only(client, customer, address):
    client.force_login(customer)

    response = client.get(
        reverse("accounts:address_default_shipping", kwargs={"pk": address.pk})
    )

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("accounts:address_edit", "get"),
        ("accounts:address_edit", "post"),
        ("accounts:address_delete", "get"),
        ("accounts:address_delete", "post"),
        ("accounts:address_default_shipping", "post"),
        ("accounts:address_default_billing", "post"),
    ],
)
def test_customers_cannot_touch_anothers_address(
    client, customer, other_users_address, name, method
):
    client.force_login(customer)
    url = reverse(name, kwargs={"pk": other_users_address.pk})

    response = getattr(client, method)(url, NEW_ADDRESS if method == "post" else None)

    assert response.status_code == HTTPStatus.NOT_FOUND
    other_users_address.refresh_from_db()
    assert other_users_address.street == "9 Axon Avenue"
    customer.refresh_from_db()
    assert customer.default_shipping_address is None


def test_anothers_address_is_not_listed(client, customer, other_users_address):
    client.force_login(customer)

    page = client.get(reverse("accounts:addresses")).content.decode()

    assert "9 Axon Avenue" not in page
