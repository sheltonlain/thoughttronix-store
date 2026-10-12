"""Changing the account's email: the request, its confirmation link, the
alert to the current address, and adding a first email to a blank-email
account."""

import re
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse

from accounts.tokens import EmailVerificationTokenGenerator


def request_change(client, email="new@example.com", password="verified123", **kw):
    return client.post(
        reverse("accounts:email_change"),
        {"email": email, "password": password},
        **kw,
    )


def confirm_link(message):
    """The confirmation path from an email-change email."""
    return re.search(
        r"https?://[^/\s]+(/accounts/security/email/confirm/\S+/)", message.body
    ).group(1)


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        username="other", password="x", email="taken@example.com"
    )


# --- The page -------------------------------------------------------------------


def test_email_change_requires_login(client, db):
    url = reverse("accounts:email_change")

    response = client.get(url)

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == f"{reverse('accounts:login')}?next={url}"


def test_security_hub_links_to_email_change(client, verified_customer):
    client.force_login(verified_customer)

    page = client.get(reverse("accounts:security")).content.decode()

    assert reverse("accounts:email_change") in page


# --- Bad requests ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "password", "field"),
    [
        ("new@example.com", "wrong-password", "password"),
        ("verified@example.com", "verified123", "email"),
        ("Verified@EXAMPLE.com", "verified123", "email"),
        ("taken@example.com", "verified123", "email"),
        ("TAKEN@Example.com", "verified123", "email"),
    ],
    ids=["wrong-password", "unchanged", "unchanged-caps", "taken", "taken-caps"],
)
def test_bad_request_saves_and_sends_nothing(
    client, verified_customer, other_user, email, password, field
):
    client.force_login(verified_customer)

    response = request_change(client, email, password)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors[field]
    verified_customer.refresh_from_db()
    assert verified_customer.pending_email == ""
    assert verified_customer.email == "verified@example.com"
    assert mail.outbox == []


# --- A good request -------------------------------------------------------------


def test_request_holds_pending_and_emails_both_addresses(client, verified_customer):
    client.force_login(verified_customer)

    response = request_change(client, follow=True)

    verified_customer.refresh_from_db()
    assert verified_customer.pending_email == "new@example.com"
    assert verified_customer.email == "verified@example.com"

    assert response.redirect_chain[-1][0] == reverse("accounts:security")
    page = response.content.decode()
    assert "Check your new inbox" in page
    assert "Change to" in page
    assert "pending" in page

    assert len(mail.outbox) == 2
    link_email, alert = mail.outbox
    assert link_email.to == ["new@example.com"]
    assert confirm_link(link_email).startswith("/accounts/security/email/confirm/")
    assert "expires in three days" in link_email.body
    assert alert.to == ["verified@example.com"]
    assert "An email change was requested" in alert.body
    assert "If this wasn't you, reset your password" in alert.body


def test_password_reset_still_goes_to_old_address_while_pending(
    client, verified_customer
):
    client.force_login(verified_customer)
    request_change(client)
    mail.outbox.clear()

    Client().post(reverse("accounts:password_reset"), {"email": "verified@example.com"})
    Client().post(reverse("accounts:password_reset"), {"email": "new@example.com"})

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["verified@example.com"]


# --- Confirming -----------------------------------------------------------------


def test_link_swaps_the_email_in_verified(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)
    old_verified_at = verified_customer.email_verified_at

    response = client.get(confirm_link(mail.outbox[0]), follow=True)

    assert response.redirect_chain[-1][0] == reverse("accounts:security")
    assert "Your email is now new@example.com" in response.content.decode()
    verified_customer.refresh_from_db()
    assert verified_customer.email == "new@example.com"
    assert verified_customer.pending_email == ""
    assert verified_customer.email_verified_at > old_verified_at


def test_link_works_without_being_signed_in(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)

    Client().get(confirm_link(mail.outbox[0]))

    verified_customer.refresh_from_db()
    assert verified_customer.email == "new@example.com"


def test_used_link_shows_error(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)
    link = confirm_link(mail.outbox[0])
    client.get(link)

    response = client.get(link)

    assert response.status_code == HTTPStatus.OK
    assert response.templates[0].name == "accounts/email_change_invalid.html"
    assert reverse("accounts:email_change") in response.content.decode()
    verified_customer.refresh_from_db()
    assert verified_customer.email == "new@example.com"


def test_second_request_supersedes_the_first(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client, "first@example.com")
    first_link = confirm_link(mail.outbox[0])
    request_change(client, "second@example.com")
    second_link = confirm_link(mail.outbox[2])

    response = client.get(first_link)

    assert response.templates[0].name == "accounts/email_change_invalid.html"
    verified_customer.refresh_from_db()
    assert verified_customer.email == "verified@example.com"
    assert verified_customer.pending_email == "second@example.com"

    client.get(second_link)
    verified_customer.refresh_from_db()
    assert verified_customer.email == "second@example.com"


def test_confirmation_refused_if_address_was_taken_meanwhile(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)
    link = confirm_link(mail.outbox[0])
    get_user_model().objects.create_user(username="quick", email="NEW@example.com")

    response = client.get(link, follow=True)

    assert response.redirect_chain[-1][0] == reverse("accounts:security")
    assert "now in use by another account" in response.content.decode()
    verified_customer.refresh_from_db()
    assert verified_customer.email == "verified@example.com"
    assert verified_customer.pending_email == ""


def tamper_token(link):
    return link[:-2] + ("0" if link[-2] != "0" else "1") + "/"


def test_tampered_link_shows_error(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)

    response = client.get(tamper_token(confirm_link(mail.outbox[0])))

    assert response.templates[0].name == "accounts/email_change_invalid.html"
    verified_customer.refresh_from_db()
    assert verified_customer.email == "verified@example.com"


@pytest.mark.parametrize(
    ("elapsed", "valid"),
    [(timedelta(days=2, hours=23), True), (timedelta(days=3, seconds=1), False)],
    ids=["within-three-days", "after-three-days"],
)
def test_link_expires_after_three_days(
    client, verified_customer, monkeypatch, elapsed, valid
):
    sent_at = datetime(2026, 10, 11, 14, 0)
    monkeypatch.setattr(EmailVerificationTokenGenerator, "_now", lambda self: sent_at)
    client.force_login(verified_customer)
    request_change(client)
    link = confirm_link(mail.outbox[0])

    monkeypatch.setattr(
        EmailVerificationTokenGenerator, "_now", lambda self: sent_at + elapsed
    )
    client.get(link)

    verified_customer.refresh_from_db()
    assert (verified_customer.email == "new@example.com") is valid


def test_change_link_cannot_be_spent_as_signup_verification(client, verified_customer):
    client.force_login(verified_customer)
    request_change(client)
    link = confirm_link(mail.outbox[0])
    signup_style = link.replace("/security/email/confirm/", "/verify/")

    client.get(signup_style)
    client.get(link)

    verified_customer.refresh_from_db()
    assert verified_customer.email == "new@example.com"


# --- Blank-email accounts ---------------------------------------------------------


def test_blank_email_user_adds_an_email_without_alert(client, customer):
    client.force_login(customer)
    hub = client.get(reverse("accounts:security")).content.decode()
    assert "Add an email" in hub

    request_change(client, password="customer123")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@example.com"]
    client.get(confirm_link(mail.outbox[0]))
    customer.refresh_from_db()
    assert customer.email == "new@example.com"
    assert customer.email_verified_at is not None
