from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Tokens for email verification links.

    The hash covers the email, the pending email, and the verification
    time, so a link dies once it's used (``email_verified_at`` changes) or
    once a newer email change replaces it (``pending_email`` changes).
    Links last ``EMAIL_VERIFICATION_TIMEOUT``, not the reset timeout.
    """

    key_salt = "accounts.tokens.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        verified_at = (
            ""
            if user.email_verified_at is None
            else user.email_verified_at.replace(microsecond=0, tzinfo=None)
        )
        return f"{user.pk}{user.email}{user.pending_email}{verified_at}{timestamp}"

    def check_token(self, user, token):
        # Django's version hardcodes PASSWORD_RESET_TIMEOUT, so the
        # signature and expiry checks are repeated here with our own.
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        if self._num_seconds(self._now()) - ts > settings.EMAIL_VERIFICATION_TIMEOUT:
            return False
        return any(
            constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret), token
            )
            for secret in [self.secret, *self.secret_fallbacks]
        )


email_verification_token = EmailVerificationTokenGenerator()
