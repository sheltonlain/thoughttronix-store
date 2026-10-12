"""Signing up with an email, and verifying it from the emailed link."""

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from http import HTTPStatus

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from accounts.tokens import EmailVerificationTokenGenerator

PASSWORD = "neural-implant-9000"


def sign_up(client, email="fresh@example.com", **kwargs):
    return client.post(
        reverse("accounts:signup"),
        {
            "username": "fresh-thinker",
            "email": email,
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
        **kwargs,
    )


def verify_link(message):
    """The verification path from a verification email."""
    return re.search(r"https?://[^/\s]+(/accounts/verify/\S+/)", message.body).group(1)


def fresh_user():
    return get_user_model().objects.get(username="fresh-thinker")


# --- Signup -------------------------------------------------------------------


def test_signup_requires_an_email(client, db):
    response = sign_up(client, email="")

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["email"]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()
    assert mail.outbox == []


@pytest.mark.parametrize(
    "typed", ["verified@example.com", "Verified@EXAMPLE.com"], ids=["exact", "caps"]
)
def test_signup_rejects_an_email_already_in_use(client, verified_customer, typed):
    response = sign_up(client, email=typed)

    assert response.status_code == HTTPStatus.OK
    assert response.context["form"].errors["email"] == [
        "That email address is already in use."
    ]
    assert not get_user_model().objects.filter(username="fresh-thinker").exists()
    assert mail.outbox == []


def test_signup_creates_unverified_account_and_sends_link(client, db):
    response = sign_up(client, follow=True)

    user = fresh_user()
    assert user.email == "fresh@example.com"
    assert user.email_verified_at is None
    assert user.is_active

    assert response.redirect_chain[-1][0] == reverse("accounts:signup_sent")
    assert "Check your inbox" in response.content.decode()
    assert not response.context["user"].is_authenticated

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["fresh@example.com"]
    assert verify_link(message).startswith("/accounts/verify/")
    assert "expires in three days" in message.body


# --- The database constraint ----------------------------------------------------


def test_database_rejects_same_email_in_other_capitalization(verified_customer):
    with pytest.raises(IntegrityError), transaction.atomic():
        get_user_model().objects.create_user(
            username="lookalike", email="VERIFIED@example.com"
        )


def test_blank_emails_still_coexist(db):
    User = get_user_model()

    User.objects.create_user(username="no-email-1", email="")
    User.objects.create_user(username="no-email-2", email="")

    assert User.objects.filter(email="").count() == 2


# --- Verifying ----------------------------------------------------------------


def test_link_verifies_and_sends_to_sign_in(client, db):
    sign_up(client)

    response = client.get(verify_link(mail.outbox[0]), follow=True)

    assert response.redirect_chain[-1][0] == reverse("accounts:login")
    assert "Email verified" in response.content.decode()
    assert not response.context["user"].is_authenticated
    user = fresh_user()
    assert user.email_verified_at is not None
    assert user.is_active


def test_used_link_shows_error_and_changes_nothing(client, db):
    sign_up(client)
    link = verify_link(mail.outbox[0])
    client.get(link)
    verified_at = fresh_user().email_verified_at

    response = Client().get(link)

    assert response.status_code == HTTPStatus.OK
    assert response.templates[0].name == "accounts/verify_email_invalid.html"
    assert "doesn't work" in response.content.decode()
    assert fresh_user().email_verified_at == verified_at


def tamper_token(link):
    return link[:-2] + ("0" if link[-2] != "0" else "1") + "/"


def tamper_uid(link):
    return re.sub(r"/verify/[^/]+/", "/verify/OTk5OTk/", link)


def garble_uid(link):
    return re.sub(r"/verify/[^/]+/", "/verify/not-base64!/", link)


@pytest.mark.parametrize(
    "tamper", [tamper_token, tamper_uid, garble_uid], ids=["token", "uid", "garbage"]
)
def test_tampered_link_shows_error_and_changes_nothing(client, db, tamper):
    sign_up(client)

    response = client.get(tamper(verify_link(mail.outbox[0])))

    assert response.status_code == HTTPStatus.OK
    assert response.templates[0].name == "accounts/verify_email_invalid.html"
    assert fresh_user().email_verified_at is None


@pytest.mark.parametrize(
    ("elapsed", "valid"),
    [(timedelta(days=2, hours=23), True), (timedelta(days=3, seconds=1), False)],
    ids=["within-three-days", "after-three-days"],
)
def test_link_expires_after_three_days(client, db, monkeypatch, elapsed, valid):
    sent_at = datetime(2026, 10, 11, 14, 0)
    monkeypatch.setattr(EmailVerificationTokenGenerator, "_now", lambda self: sent_at)
    sign_up(client)
    link = verify_link(mail.outbox[0])

    monkeypatch.setattr(
        EmailVerificationTokenGenerator, "_now", lambda self: sent_at + elapsed
    )
    response = client.get(link)

    assert (fresh_user().email_verified_at is not None) is valid
    if not valid:
        assert response.templates[0].name == "accounts/verify_email_invalid.html"


# --- The timeout setting --------------------------------------------------------


def test_verification_timeout_defaults_to_three_days(settings):
    assert settings.EMAIL_VERIFICATION_TIMEOUT == 3 * 24 * 60 * 60


def test_verification_timeout_reads_from_env():
    script = (
        "import django; django.setup();"
        "from django.conf import settings;"
        "print(settings.EMAIL_VERIFICATION_TIMEOUT)"
    )
    environment = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "EMAIL_VERIFICATION_TIMEOUT": "120",
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "120"
