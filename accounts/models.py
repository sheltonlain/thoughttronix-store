from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models
from django.db.models import Case, Q, Value, When
from django.db.models.functions import Lower
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token
from .validators import US_STATES, zip_validator


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001

    # Null means "not verified"; a timestamp records when it was. Separate
    # from ``is_active``, which only ever means "deactivated by staff".
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # A requested new address, held here until its link is clicked.
    pending_email = models.EmailField(blank=True, default="")

    # A foreign key holds one value, so "one default of each" needs no
    # further enforcement; deleting the address clears the slot.
    default_shipping_address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    default_billing_address = models.ForeignKey(
        "Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            # Two accounts never share an email, whatever its capitalization.
            # Blank stays allowed, and blanks don't collide with each other.
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="accounts_user_email_ci_unique",
                violation_error_message="That email address is already in use.",
            ),
        ]

    def set_default_address(self, kind, address):
        """Make ``address`` the default for ``kind`` ("shipping" or "billing")."""
        field = f"default_{kind}_address"
        setattr(self, field, address)
        self.save(update_fields=[field])

    def fill_empty_defaults(self, address):
        """Make ``address`` the default wherever no default is set yet.

        Never replaces a default the customer already has — a one-off gift
        address can't take over their home address.
        """
        empty = [
            field
            for field in ("default_shipping_address", "default_billing_address")
            if getattr(self, f"{field}_id") is None
        ]
        for field in empty:
            setattr(self, field, address)
        if empty:
            self.save(update_fields=empty)

    # --- Account security ------------------------------------------------------

    @property
    def verified_email(self):
        """The address alerts and recovery may use: the email, once
        verified. Blank when there is none or it isn't verified yet."""
        return self.email if self.email and self.email_verified_at else ""

    def _verification_link(self, request, url_name):
        """An absolute, single-use verification link to ``url_name``.

        ``request`` supplies the scheme and host.
        """
        path = reverse(
            url_name,
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(self.pk)),
                "token": email_verification_token.make_token(self),
            },
        )
        return request.build_absolute_uri(path)

    def send_verification_email(self, request):
        """Email a single-use link that verifies the account's email."""
        body = render_to_string(
            "accounts/email/verify_email.txt",
            {
                "user": self,
                "link": self._verification_link(request, "accounts:verify_email"),
            },
        )
        send_mail("Verify your ThoughtTronix email", body, None, [self.email])

    def verify_email(self, token):
        """Mark the email verified if ``token`` is a live link for it.

        Returns whether it worked. Verifying changes the token's hash, so
        the same link never works twice. An email that's already verified
        is refused, so an email-change link can't be spent here.
        ``is_active`` is left alone.
        """
        if (
            not self.email
            or self.email_verified_at
            or not email_verification_token.check_token(self, token)
        ):
            return False
        self.email_verified_at = timezone.now()
        self.save(update_fields=["email_verified_at"])
        return True

    def request_email_change(self, new_email, request):
        """Hold ``new_email`` as pending and email it a confirmation link.

        The current email stays in force until the link is clicked. A newer
        request replaces this one, and changing ``pending_email`` kills
        this link. The current verified address, if any, is alerted.
        """
        self.pending_email = new_email
        self.save(update_fields=["pending_email"])
        body = render_to_string(
            "accounts/email/confirm_email_change.txt",
            {
                "user": self,
                "link": self._verification_link(
                    request, "accounts:email_change_confirm"
                ),
            },
        )
        send_mail("Confirm your new ThoughtTronix email", body, None, [new_email])
        self.send_security_alert("An email change was requested")

    def confirm_email_change(self, token):
        """Swap the pending email in, verified, if ``token`` is a live link.

        Returns whether the link was good. Raises ``ValidationError`` if
        another account took the address since it was requested; the
        pending change is dropped and the email left as it was.
        """
        if not self.pending_email or not email_verification_token.check_token(
            self, token
        ):
            return False
        taken = (
            User.objects.filter(email__iexact=self.pending_email)
            .exclude(pk=self.pk)
            .exists()
        )
        if taken:
            self.pending_email = ""
            self.save(update_fields=["pending_email"])
            raise ValidationError(
                "That email address is now in use by another account, so "
                "your email wasn't changed.",
                code="taken",
            )
        self.email, self.pending_email = self.pending_email, ""
        self.email_verified_at = timezone.now()
        self.save(update_fields=["email", "pending_email", "email_verified_at"])
        return True

    def send_security_alert(self, action):
        """Email the verified address that ``action`` just happened.

        ``action`` reads as a sentence fragment, like "Your password was
        changed". Nothing is sent without a verified address. Returns
        whether an alert went out.
        """
        if not self.verified_email:
            return False
        body = render_to_string(
            "accounts/email/security_alert.txt",
            {"user": self, "action": action, "when": timezone.now()},
        )
        send_mail(
            f"Security alert: {action}",
            body,
            None,  # DEFAULT_FROM_EMAIL
            [self.verified_email],
        )
        return True


class AddressQuerySet(models.QuerySet):
    def address_book(self, user):
        """The user's addresses: their defaults first, then newest first."""
        defaults = [
            pk
            for pk in (
                user.default_shipping_address_id,
                user.default_billing_address_id,
            )
            if pk is not None
        ]
        return (
            self.filter(user=user)
            .alias(
                is_default=Case(
                    When(pk__in=defaults, then=Value(True)),
                    default=Value(False),
                )
            )
            .order_by("-is_default", "-created_at", "-pk")
        )


class AddressManager(models.Manager.from_queryset(AddressQuerySet)):
    def save_from_checkout(self, user, data, prefix):
        """Save one checkout address section to the user's address book.

        ``data`` is checkout ``cleaned_data``; ``prefix`` is "shipping" or
        "billing". An identical address already in the book is reused
        rather than duplicated. Either way, it fills any empty default.

        The optional ``save_<prefix>_label`` nickname names a new address,
        or an existing one that has no label yet — it never renames one
        the customer already labeled.
        """
        parts = {part: data[f"{prefix}_{part}"] for part in Address.PARTS}
        label = data.get(f"save_{prefix}_label", "")
        address = self.filter(user=user, **parts).first()
        if address is None:
            address = self.create(user=user, label=label, **parts)
        elif label and not address.label:
            address.label = label
            address.save(update_fields=["label"])
        user.fill_empty_defaults(address)
        return address


class Address(models.Model):
    """A saved address in a customer's address book.

    One book serves both purposes: whether an address is for shipping or
    billing is decided at checkout, not stored here. Orders copy the
    address onto themselves, so editing or deleting one never touches
    order history.
    """

    # The address itself, named to line up with the checkout form's
    # ``shipping_<part>`` and ``billing_<part>`` fields.
    PARTS = ["name", "street", "line2", "city", "state", "zip"]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    label = models.CharField(
        "Label (optional)",
        max_length=50,
        blank=True,
        default="",
        help_text="A nickname like Home or Work.",
    )
    name = models.CharField("Full name", max_length=100)
    street = models.CharField("Street address", max_length=200)
    line2 = models.CharField("Apt, suite, etc. (optional)", max_length=200, blank=True)
    city = models.CharField("City", max_length=100)
    state = models.CharField("State", max_length=2, choices=US_STATES)
    zip = models.CharField("ZIP code", max_length=10, validators=[zip_validator])
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AddressManager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name_plural = "addresses"

    def __str__(self):
        where = f"{self.street}, {self.city}, {self.state}"
        return f"{self.label or self.name} — {where}"

    def as_checkout_initial(self, prefix):
        """This address as initial data for one checkout form section."""
        return {f"{prefix}_{part}": getattr(self, part) for part in self.PARTS}
