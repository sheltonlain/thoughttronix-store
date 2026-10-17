"""The development console email backend prints links whole."""

import io
import re

from django.core import mail
from django.urls import reverse

from accounts.mail import ReadableConsoleEmailBackend
from config import settings as project_settings


def test_settings_use_the_readable_console_backend():
    # pytest-django swaps in locmem for tests, so read the settings module.
    assert project_settings.EMAIL_BACKEND == "accounts.mail.ReadableConsoleEmailBackend"


def test_reset_email_prints_the_link_on_one_line(client, verified_customer):
    client.post(reverse("accounts:password_reset"), {"email": verified_customer.email})
    message = mail.outbox[0]
    link = re.search(r"https?://\S+/accounts/reset/\S+/", message.body).group(0)
    stream = io.StringIO()

    ReadableConsoleEmailBackend(stream=stream).send_messages([message])

    printed = stream.getvalue()
    assert f"To: {verified_customer.email}" in printed
    assert f"Subject: {message.subject}" in printed
    assert link in printed.splitlines()
    assert "=\n" not in printed
