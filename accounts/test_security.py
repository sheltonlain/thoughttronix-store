"""The account security center: the hub, its navbar link, and the
grandfathering of emails that existed before verification."""

from http import HTTPStatus

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

# --- The hub -----------------------------------------------------------------


def test_security_hub_requires_login(client, db):
    url = reverse("accounts:security")

    response = client.get(url)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"{reverse('accounts:login')}?next={url}"


def test_security_hub_shows_verified_email(client, verified_customer):
    client.force_login(verified_customer)

    response = client.get(reverse("accounts:security"))

    page = response.content.decode()
    assert response.status_code == HTTPStatus.OK
    assert "verified@example.com" in page
    assert "Verified" in page
    assert "No email on file" not in page


def test_security_hub_warns_when_no_email(client, customer):
    client.force_login(customer)

    page = client.get(reverse("accounts:security")).content.decode()

    assert "No email on file" in page
    assert "can't recover your account" in page
    assert "Verified" not in page


def test_security_hub_is_the_same_for_staff(client, staff_user):
    client.force_login(staff_user)

    response = client.get(reverse("accounts:security"))

    assert response.status_code == HTTPStatus.OK
    assert response.templates[0].name == "accounts/security.html"
    assert "No email on file" in response.content.decode()


# --- Navbar -------------------------------------------------------------------


def test_navbar_shows_security_to_signed_in_users(client, customer):
    client.force_login(customer)

    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:security") in page


def test_navbar_hides_security_from_visitors(client, db):
    page = client.get(reverse("products:catalog")).content.decode()

    assert reverse("accounts:security") not in page


# --- Grandfathering migration -------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_grandfathering_verifies_existing_emails_only():
    before = [("accounts", "0003_user_email_verification")]
    after = [("accounts", "0004_grandfather_verified_emails")]
    executor = MigrationExecutor(connection)
    executor.migrate(before)
    User = executor.loader.project_state(before).apps.get_model("accounts", "User")
    User.objects.create(username="had-email", email="had@example.com")
    User.objects.create(username="no-email", email="")

    executor = MigrationExecutor(connection)
    executor.migrate(after)

    User = executor.loader.project_state(after).apps.get_model("accounts", "User")
    had_email = User.objects.get(username="had-email")
    no_email = User.objects.get(username="no-email")
    assert had_email.email_verified_at is not None
    assert no_email.email_verified_at is None
    assert no_email.email == ""
