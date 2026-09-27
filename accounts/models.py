from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Case, Value, When

from .validators import US_STATES, zip_validator


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary and nothing else: customers are
    plain users, employees are ``is_staff``, the admin is ``is_superuser``.
    """

    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001

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
        """
        parts = {part: data[f"{prefix}_{part}"] for part in Address.PARTS}
        address = self.filter(user=user, **parts).first()
        if address is None:
            address = self.create(user=user, **parts)
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
