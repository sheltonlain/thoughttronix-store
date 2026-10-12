"""The account security center: the hub, its navbar link, password change
and its security alert, forgot password, and the grandfathering of emails
that existed before verification."""

import os
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
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


# --- Forgot password ------------------------------------------------------------


def request_reset(client, email):
    return client.post(reverse("accounts:password_reset"), {"email": email})


def reset_link(message):
    """The set-new-password path from a reset email."""
    return re.search(r"https?://[^/\s]+(/accounts/reset/\S+/)", message.body).group(1)


def set_new_password(client, link, new1=NEW_PASSWORD, new2=None):
    """Open the emailed link, then submit the new password on the page it
    lands on. (Django swaps the token into the session and redirects, so
    the token never sits in the form page's URL.)"""
    form_page = client.get(link, follow=True)
    return client.post(
        form_page.redirect_chain[-1][0],
        {"new_password1": new1, "new_password2": new1 if new2 is None else new2},
    )


def test_sign_in_page_links_to_password_reset(client, db):
    page = client.get(reverse("accounts:login")).content.decode()

    assert "Forgot password?" in page
    assert reverse("accounts:password_reset") in page


@pytest.mark.parametrize(
    "typed", ["verified@example.com", "VERIFIED@Example.COM"], ids=["exact", "caps"]
)
def test_password_reset_emails_a_verified_address(client, verified_customer, typed):
    response = request_reset(client, typed)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["verified@example.com"]
    assert "/accounts/reset/" in reset_link(message)
    assert "expires in one hour" in message.body


def make_unverified(user):
    user.email_verified_at = None
    user.save()


def make_inactive(user):
    user.is_active = False
    user.save()


def make_passwordless(user):
    user.set_unusable_password()
    user.save()


@pytest.mark.parametrize(
    ("change", "typed"),
    [
        (make_unverified, "verified@example.com"),
        (None, "nobody@example.com"),
        (make_inactive, "verified@example.com"),
        (make_passwordless, "verified@example.com"),
    ],
    ids=["unverified", "unknown", "inactive", "unusable-password"],
)
def test_password_reset_sends_nothing_without_a_match(
    client, verified_customer, change, typed
):
    if change:
        change(verified_customer)

    response = request_reset(client, typed)

    # The same redirect to the same page as a real match: nothing given away.
    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_done")
    assert mail.outbox == []


def test_password_reset_sets_new_password_and_alerts(client, verified_customer):
    request_reset(client, "verified@example.com")
    link = reset_link(mail.outbox[0])

    response = set_new_password(client, link)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("accounts:password_reset_complete")
    assert len(mail.outbox) == 2
    alert = mail.outbox[1]
    assert alert.to == ["verified@example.com"]
    assert "Your password was reset" in alert.body
    assert "If this wasn't you, reset your password" in alert.body

    signed_in = client.post(
        reverse("accounts:login"),
        {"username": "verified", "password": NEW_PASSWORD},
    )
    assert signed_in.status_code == HTTPStatus.FOUND
    assert client.get(reverse("accounts:security")).status_code == HTTPStatus.OK


def test_password_reset_enforces_password_validators(client, verified_customer):
    request_reset(client, "verified@example.com")

    response = set_new_password(client, reset_link(mail.outbox[0]), "12345678")

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["new_password2"]
    verified_customer.refresh_from_db()
    assert verified_customer.check_password("verified123")
    assert len(mail.outbox) == 1  # the reset link; no alert


def test_password_reset_link_works_only_once(client, verified_customer):
    request_reset(client, "verified@example.com")
    link = reset_link(mail.outbox[0])
    set_new_password(client, link)

    response = Client().get(link, follow=True)

    assert response.context["validlink"] is False
    assert "doesn't work" in response.content.decode()
    assert reverse("accounts:password_reset") in response.content.decode()


@pytest.mark.parametrize(
    ("elapsed", "valid"),
    [(timedelta(minutes=59), True), (timedelta(hours=1, seconds=1), False)],
    ids=["within-hour", "after-hour"],
)
def test_password_reset_link_expires_after_an_hour(
    client, verified_customer, monkeypatch, elapsed, valid
):
    sent_at = datetime(2026, 10, 11, 14, 0)
    monkeypatch.setattr(PasswordResetTokenGenerator, "_now", lambda self: sent_at)
    request_reset(client, "verified@example.com")
    link = reset_link(mail.outbox[0])

    monkeypatch.setattr(
        PasswordResetTokenGenerator, "_now", lambda self: sent_at + elapsed
    )
    response = client.get(link, follow=True)

    assert response.context["validlink"] is valid


def test_password_reset_timeout_defaults_to_an_hour(settings):
    assert settings.PASSWORD_RESET_TIMEOUT == 60 * 60


def test_password_reset_timeout_reads_from_env():
    script = (
        "import django; django.setup();"
        "from django.conf import settings;"
        "print(settings.PASSWORD_RESET_TIMEOUT)"
    )
    environment = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "PASSWORD_RESET_TIMEOUT": "120",
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "120"


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
