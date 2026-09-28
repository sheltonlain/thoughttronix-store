"""Promotional coupons — codes Marketing writes and retires themselves.

A coupon is one deal: a percent or a fixed amount, off the whole order or
off hand-picked products, usable between two moments. Its rules live here,
on the model and its queryset: ``Coupon.objects.for_code()`` finds a
coupon from what a customer typed, and ``evaluate()`` prices a cart with
it. Both the checkout's Apply preview and ``place_order`` call
``evaluate()``, so the price the customer sees is the price they pay.

Every refusal is a ``CouponError`` whose text is the message to show the
customer — a specific reason, never an error page.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from django.utils.formats import date_format

from orders.models import Order
from products.models import Product

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

code_validator = RegexValidator(
    r"^[A-Za-z0-9-]+$", "Use only letters, digits and hyphens."
)


class CouponError(ValueError):
    """A code the customer can't use; its text is the message to show them.

    A ``ValueError``, so ``place_order`` keeps its documented contract.
    """


def _money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


@dataclass(frozen=True)
class Evaluation:
    """A cart priced with a coupon.

    ``line_discounts`` maps each cart line's product pk to its share of
    the discount — zero for lines the coupon doesn't cover. The shares
    always add up to ``discount`` exactly.
    """

    coupon: "Coupon"
    subtotal: Decimal
    discount: Decimal
    line_discounts: dict[int, Decimal]

    @property
    def total(self) -> Decimal:
        return self.subtotal - self.discount


class CouponQuerySet(models.QuerySet):
    def unarchived(self):
        return self.filter(is_archived=False)

    def with_use_count(self):
        """Annotate each coupon's uses, so a list reads them in one query."""
        return self.annotate(
            annotated_use_count=Count(
                "orders", filter=~Q(orders__status=Order.Status.CANCELLED)
            )
        )

    def with_status(self, status: str):
        """Coupons showing ``status`` — the same precedence as ``Coupon.status``."""
        if status == Coupon.Status.ARCHIVED:
            return self.filter(is_archived=True)
        now = timezone.now()
        coupons = self.unarchived()
        if status == Coupon.Status.EXPIRED:
            return coupons.filter(expires_at__lte=now)
        coupons = coupons.filter(expires_at__gt=now)
        if status == Coupon.Status.SCHEDULED:
            return coupons.filter(starts_at__gt=now)
        coupons = coupons.filter(starts_at__lte=now)
        if status == Coupon.Status.SWITCHED_OFF:
            return coupons.filter(is_active=False)
        coupons = coupons.filter(is_active=True)
        if "annotated_use_count" not in coupons.query.annotations:
            coupons = coupons.with_use_count()
        used_up = Q(max_uses__isnull=False, annotated_use_count__gte=F("max_uses"))
        if status == Coupon.Status.USED_UP:
            return coupons.filter(used_up)
        return coupons.exclude(used_up)

    def for_code(self, code: str) -> "Coupon":
        """The coupon a customer means by ``code``, ignoring case and spaces.

        Raises ``CouponError`` for a code that never existed, and reads an
        archived-only code as expired — which, to the customer, it is.
        """
        normalized = code.strip().upper()
        coupon = self.unarchived().filter(code=normalized).first()
        if coupon is not None:
            return coupon
        if normalized and self.filter(code=normalized).exists():
            raise CouponError(f"The code {normalized} has expired.")
        raise CouponError(
            "We don't recognize that code. Check the spelling and try again."
        )


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Percent off"
        FIXED = "FIXED", "Fixed amount off"

    class Status(models.TextChoices):
        LIVE = "LIVE", "Live"
        SCHEDULED = "SCHEDULED", "Scheduled"
        EXPIRED = "EXPIRED", "Expired"
        SWITCHED_OFF = "SWITCHED_OFF", "Switched off"
        USED_UP = "USED_UP", "Used up"
        ARCHIVED = "ARCHIVED", "Archived"

    code = models.CharField(
        max_length=30,
        validators=[MinLengthValidator(3), code_validator],
        help_text="What customers type. Letters, digits and hyphens; "
        "capitals don't matter.",
    )
    discount_type = models.CharField(
        max_length=7, choices=DiscountType.choices, default=DiscountType.PERCENT
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(CENT)],
        help_text="A percent (up to 100) or a dollar amount, per the type. "
        "A dollar amount comes off once per order.",
    )
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name="coupons",
        help_text="Leave empty to discount the whole order.",
    )
    min_subtotal = models.DecimalField(
        "Minimum spend",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(CENT)],
        help_text="Optional. Counts only the products the coupon covers.",
    )
    starts_at = models.DateTimeField("Starts", default=timezone.now)
    expires_at = models.DateTimeField("Expires")
    max_uses_per_customer = models.PositiveIntegerField(
        "Uses per customer",
        null=True,
        blank=True,
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Leave empty for unlimited.",
    )
    max_uses = models.PositiveIntegerField(
        "Total uses",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Leave empty for unlimited.",
    )
    is_active = models.BooleanField(
        "Active",
        default=True,
        help_text="Switch off to stop a code at once, whatever its dates.",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CouponQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at", "code"]
        permissions = [("manage_coupons", "Can manage coupons")]
        constraints = [
            # Archiving frees a code, so "SUMMER" can run again next year.
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_archived=False),
                name="unique_unarchived_coupon_code",
                violation_error_message="That code is already in use by "
                "another coupon.",
            )
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        self.code = self.code.strip().upper()
        # The constraint below is the backstop; checking here names the
        # field. (Forms skip a conditional constraint whose condition
        # field, ``is_archived``, isn't on the form.)
        if (
            not self.is_archived
            and Coupon.objects.unarchived()
            .filter(code=self.code)
            .exclude(pk=self.pk)
            .exists()
        ):
            raise ValidationError(
                {"code": f"{self.code} is already in use by another coupon."}
            )
        if (
            self.discount_type == self.DiscountType.PERCENT
            and self.value is not None
            and self.value > 100
        ):
            raise ValidationError(
                {"value": "A percent discount can't be more than 100%."}
            )
        if self.starts_at and self.expires_at and self.expires_at <= self.starts_at:
            raise ValidationError({"expires_at": "The end must be after the start."})

    # --- Usage ---------------------------------------------------------------

    @property
    def use_count(self) -> int:
        """Orders that spent a use; a cancelled order gives its use back."""
        annotated = self.__dict__.get("annotated_use_count")
        if annotated is not None:
            return annotated
        return self._spent_orders().count()

    def total_discounted(self) -> Decimal:
        return self._spent_orders().aggregate(total=Sum("discount"))["total"] or ZERO

    @property
    def is_locked(self) -> bool:
        """Once any order carries this coupon, its deal can't change."""
        return self.orders.exists()

    def _spent_orders(self):
        return self.orders.exclude(status=Order.Status.CANCELLED)

    # --- For the back office -------------------------------------------------

    @property
    def status(self) -> str:
        now = timezone.now()
        if self.is_archived:
            return self.Status.ARCHIVED
        if now >= self.expires_at:
            return self.Status.EXPIRED
        if now < self.starts_at:
            return self.Status.SCHEDULED
        if not self.is_active:
            return self.Status.SWITCHED_OFF
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return self.Status.USED_UP
        return self.Status.LIVE

    def get_status_display(self) -> str:
        return self.Status(self.status).label

    @property
    def summary(self) -> str:
        """The deal in plain words, e.g. "50% off 3 products"."""
        if self.discount_type == self.DiscountType.PERCENT:
            amount = f"{self.value.normalize():f}%"
        else:
            amount = _money(self.value)
        count = len(self.products.all())  # uses a prefetch when there is one
        if count:
            target = f"{count} product{'s' if count != 1 else ''}"
        else:
            target = "your order"
        text = f"{amount} off {target}"
        if self.min_subtotal:
            text += f", min. spend {_money(self.min_subtotal)}"
        return text

    # --- Pricing a cart ------------------------------------------------------

    def evaluate(self, cart, user) -> Evaluation:
        """Price ``cart`` with this coupon for ``user``, or raise ``CouponError``.

        Checks, in order: the dates, the switch, the total cap, the
        customer's own limit, whether anything in the cart is covered, and
        the minimum spend (over covered products only).
        """
        self._check_usable_by(user)
        lines = list(cart.lines())
        covered_ids = {product.pk for product in self.products.all()}
        covered = [
            (line.product_id, line.line_total)
            for line in lines
            if not covered_ids or line.product_id in covered_ids
        ]
        if not covered:
            raise CouponError(f"{self.code} doesn't apply to anything in your cart.")
        covered_subtotal = sum((total for _, total in covered), ZERO)
        if self.min_subtotal and covered_subtotal < self.min_subtotal:
            short = self.min_subtotal - covered_subtotal
            raise CouponError(f"Spend {_money(short)} more to use {self.code}.")

        shares = self.split_discount(covered)
        return Evaluation(
            coupon=self,
            subtotal=sum((line.line_total for line in lines), ZERO),
            discount=sum(shares.values(), ZERO),
            line_discounts={
                line.product_id: shares.get(line.product_id, ZERO) for line in lines
            },
        )

    def split_discount(self, lines: list[tuple[int, Decimal]]) -> dict[int, Decimal]:
        """Each covered line's share of the discount, keyed by product pk.

        ``lines`` are ``(product_pk, line_total)`` pairs, all covered.
        Percent: each line's percent, rounded half-up to the cent. Fixed:
        the amount (capped at the lines' total, so nothing goes below
        zero) split by line value, the last line absorbing rounding so
        the shares add up exactly. Pure arithmetic — no checks — which is
        why the seed can reuse it for historical orders.
        """
        if self.discount_type == self.DiscountType.PERCENT:
            rate = self.value / 100
            return {
                pk: (total * rate).quantize(CENT, ROUND_HALF_UP) for pk, total in lines
            }

        covered_subtotal = sum((total for _, total in lines), ZERO)
        amount = min(self.value, covered_subtotal)
        shares = {}
        for pk, total in lines[:-1]:
            share = amount * total / covered_subtotal
            shares[pk] = share.quantize(CENT, ROUND_HALF_UP)
        last_pk = lines[-1][0]
        shares[last_pk] = amount - sum(shares.values(), ZERO)
        return shares

    def _check_usable_by(self, user):
        now = timezone.now()
        if now >= self.expires_at:
            raise CouponError(f"The code {self.code} has expired.")
        if now < self.starts_at:
            starts = date_format(timezone.localtime(self.starts_at), "F j")
            raise CouponError(
                f"The code {self.code} isn't active yet — it starts {starts}."
            )
        if not self.is_active:
            raise CouponError(f"The code {self.code} is no longer available.")
        if self.max_uses is not None and self.use_count >= self.max_uses:
            raise CouponError(f"The code {self.code} has reached its limit.")
        if self.max_uses_per_customer is not None:
            used = self._spent_orders().filter(user=user).count()
            if used >= self.max_uses_per_customer:
                raise CouponError(f"You've already used the code {self.code}.")
