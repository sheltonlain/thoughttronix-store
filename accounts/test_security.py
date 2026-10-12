"""The account security center: the hub, its navbar link, password change
and its security alert, and the grandfathering of emails that existed
before verification."""

from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from django.core import mail
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.urls import reverse
from django.utils import timezone

NEW_PASSWORD = "lucid-dream-4417"

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


def test_security_hub_links_to_password_change(client, customer):
    client.force_login(customer)

    page = client.get(reverse("accounts:security")).content.decode()

    assert reverse("accounts:password_change") in page


# --- Password change ----------------------------------------------------------


def change_password(client, old, new1=NEW_PASSWORD, new2=None, **kwargs):
    return client.post(
        reverse("accounts:password_change"),
        {
            "old_password": old,
            "new_password1": new1,
            "new_password2": new1 if new2 is None else new2,
        },
        **kwargs,
    )


def test_password_change_requires_login(client, db):
    url = reverse("accounts:password_change")

    response = client.get(url)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"{reverse('accounts:login')}?next={url}"


@pytest.mark.parametrize(
    ("old", "new1", "new2", "field"),
    [
        ("wrong-password", NEW_PASSWORD, NEW_PASSWORD, "old_password"),
        ("verified123", NEW_PASSWORD, "something-else-88", "new_password2"),
        ("verified123", "12345678", "12345678", "new_password2"),  # validators
    ],
    ids=["wrong-current", "mismatch", "fails-validators"],
)
def test_password_change_rejects_bad_input(
    client, verified_customer, old, new1, new2, field
):
    client.force_login(verified_customer)

    response = change_password(client, old, new1, new2)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors[field]
    verified_customer.refresh_from_db()
    assert verified_customer.check_password("verified123")
    assert mail.outbox == []


def test_password_change_returns_to_hub_still_signed_in(client, verified_customer):
    client.force_login(verified_customer)

    response = change_password(client, "verified123", follow=True)

    assert response.redirect_chain[-1][0] == reverse("accounts:security")
    assert "Password changed" in response.content.decode()
    assert response.context["user"].is_authenticated
    verified_customer.refresh_from_db()
    assert verified_customer.check_password(NEW_PASSWORD)


def test_password_change_signs_out_other_sessions(client, verified_customer):
    other_device = Client()
    other_device.force_login(verified_customer)
    client.force_login(verified_customer)

    change_password(client, "verified123")

    response = other_device.get(reverse("accounts:security"))
    assert response.status_code == HTTPStatus.FOUND
    assert response.url.startswith(reverse("accounts:login"))


def test_password_change_alerts_verified_address(
    client, verified_customer, monkeypatch
):
    changed_at = datetime(2026, 10, 11, 14, 30, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: changed_at)
    client.force_login(verified_customer)

    change_password(client, "verified123")

    assert len(mail.outbox) == 1
    alert = mail.outbox[0]
    assert alert.to == ["verified@example.com"]
    assert "password was changed" in alert.subject
    assert "Your password was changed" in alert.body
    assert "11 October 2026, 14:30" in alert.body
    assert "If this wasn't you, reset your password" in alert.body


def test_password_change_without_email_sends_nothing(client, customer):
    client.force_login(customer)

    response = change_password(client, "customer123")

    assert response.status_code == HTTPStatus.FOUND
    customer.refresh_from_db()
    assert customer.check_password(NEW_PASSWORD)
    assert mail.outbox == []


def test_security_alert_skips_unverified_email(customer):
    customer.email = "unverified@example.com"

    assert customer.send_security_alert("Your password was changed") is False
    assert mail.outbox == []


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
