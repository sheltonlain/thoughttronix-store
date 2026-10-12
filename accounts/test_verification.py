"""Signing up with an email, verifying it from the emailed link, the
sign-in rule for unverified accounts, and resending the link."""

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


def test_bad_link_page_links_to_resend(client, db):
    response = client.get(reverse("accounts:verify_email", args=["OTk5OTk", "x-y"]))

    assert reverse("accounts:resend_verification") in response.content.decode()


# --- Signing in -----------------------------------------------------------------


@pytest.fixture
def unverified_user(db):
    return get_user_model().objects.create_user(
        username="unverified", password=PASSWORD, email="unverified@example.com"
    )


def sign_in(client, username, password=PASSWORD):
    return client.post(
        reverse("accounts:login"), {"username": username, "password": password}
    )


@pytest.mark.parametrize(
    ("fixture", "username", "password"),
    [
        ("verified_customer", "verified", "verified123"),
        ("customer", "customer", "customer123"),
    ],
    ids=["verified", "blank-email"],
)
def test_verified_and_blank_email_users_sign_in(
    client, request, fixture, username, password
):
    user = request.getfixturevalue(fixture)

    response = sign_in(client, username, password)

    assert response.status_code == HTTPStatus.FOUND
    assert client.session["_auth_user_id"] == str(user.pk)


def test_unverified_user_is_refused_with_link_to_resend(client, unverified_user):
    response = sign_in(client, "unverified")

    assert response.status_code == HTTPStatus.OK
    assert "_auth_user_id" not in client.session
    form = response.context["form"]
    assert form.has_error("__all__", code="unverified")
    page = response.content.decode()
    assert "verify your email" in page
    assert f'href="{reverse("accounts:resend_verification")}"' in page


def test_unverified_user_with_wrong_password_sees_only_invalid_login(
    client, unverified_user
):
    response = sign_in(client, "unverified", "not-the-password")

    form = response.context["form"]
    assert form.has_error("__all__", code="invalid_login")
    assert not form.has_error("__all__", code="unverified")
    assert "verify your email" not in response.content.decode()
    assert "_auth_user_id" not in client.session


def test_verifying_never_reactivates_a_deactivated_account(client, db):
    sign_up(client)
    user = fresh_user()
    user.is_active = False
    user.save(update_fields=["is_active"])

    client.get(verify_link(mail.outbox[0]))
    response = sign_in(client, "fresh-thinker")

    user.refresh_from_db()
    assert user.email_verified_at is not None
    assert not user.is_active
    assert response.context["form"].has_error("__all__", code="invalid_login")
    assert "_auth_user_id" not in client.session


# --- Resending ------------------------------------------------------------------


def resend(client, email):
    return client.post(
        reverse("accounts:resend_verification"), {"email": email}, follow=True
    )


def test_resend_page_returns_200(client, db):
    response = client.get(reverse("accounts:resend_verification"))

    assert response.status_code == HTTPStatus.OK


def test_resend_sends_a_working_link_to_an_unverified_account(client, unverified_user):
    resend(client, "UNVERIFIED@Example.com")

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["unverified@example.com"]
    client.get(verify_link(mail.outbox[0]))
    unverified_user.refresh_from_db()
    assert unverified_user.email_verified_at is not None


@pytest.mark.parametrize(
    "email", ["verified@example.com", "nobody@example.com"], ids=["verified", "unknown"]
)
def test_resend_sends_nothing_for_verified_or_unknown(client, verified_customer, email):
    resend(client, email)

    assert mail.outbox == []


def test_resend_replies_the_same_in_every_case(
    client, unverified_user, verified_customer
):
    replies = [
        resend(client, email)
        for email in [
            "unverified@example.com",
            "verified@example.com",
            "nobody@example.com",
        ]
    ]

    assert len({reply.redirect_chain[-1][0] for reply in replies}) == 1
    assert replies[0].redirect_chain[-1][0] == reverse("accounts:login")
    # The masked CSRF token (in the form and the body's HTMX headers)
    # differs on every render; nothing else may.
    csrf = re.compile(r'(csrfmiddlewaretoken" value=|"X-CSRFToken": )"[^"]+"')
    pages = {csrf.sub("", reply.content.decode()) for reply in replies}
    assert len(pages) == 1
    assert "we&#x27;ve sent it a new verification link" in pages.pop()


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
