from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from orders.models import Order
from products.models import Product


class Eligibility(models.TextChoices):
    """Where a viewer stands with reviewing one product."""

    SIGNED_OUT = "signed_out", "Signed out"
    ALREADY_REVIEWED = "already_reviewed", "Already reviewed"
    CAN_REVIEW = "can_review", "Can review"
    AWAITING_DELIVERY = "awaiting_delivery", "Awaiting delivery"
    NOT_A_BUYER = "not_a_buyer", "Not a buyer"


class ReviewManager(models.Manager):
    def eligibility(self, user, product):
        """The user's one ``Eligibility`` state for reviewing ``product``.

        Past the signed-out and already-reviewed checks, it's decided by
        the user's own orders containing the product: a Delivered one can
        review, a Placed or Shipped one is awaiting delivery, and a
        Cancelled one counts for nothing. Availability is ignored, and
        staff get no exemption. Only creation asks; later status changes
        never touch an existing review.
        """
        if not user.is_authenticated:
            return Eligibility.SIGNED_OUT
        if self.filter(user=user, product=product).exists():
            return Eligibility.ALREADY_REVIEWED
        statuses = set(
            Order.objects.filter(user=user, items__product=product).values_list(
                "status", flat=True
            )
        )
        if Order.Status.DELIVERED in statuses:
            return Eligibility.CAN_REVIEW
        if statuses & {Order.Status.PLACED, Order.Status.SHIPPED}:
            return Eligibility.AWAITING_DELIVERY
        return Eligibility.NOT_A_BUYER

    def ensure_may_submit(self, user, product):
        """Return the user's eligibility, or raise ``PermissionDenied``.

        Only a delivered buyer may submit, plus someone who already has, so
        their duplicate can be answered with their review instead of a 403.
        """
        eligibility = self.eligibility(user, product)
        if eligibility not in (Eligibility.CAN_REVIEW, Eligibility.ALREADY_REVIEWED):
            raise PermissionDenied
        return eligibility

    def submit(self, user, product, rating, comment):
        """Create ``user``'s review of ``product``; return ``(review, created)``.

        Eligibility is re-checked here, whatever the page showed: anyone
        but a delivered buyer gets ``PermissionDenied``. A user who has
        already reviewed the product gets their existing review back
        untouched with ``created=False``, so a double-click or a stale
        second tab can never overwrite it. That holds even when a
        concurrent request wins the race to insert: the unique constraint
        catches it here, and the ``IntegrityError`` never reaches the view.
        """
        if self.ensure_may_submit(user, product) == Eligibility.ALREADY_REVIEWED:
            return self.get(user=user, product=product), False
        try:
            with transaction.atomic():
                review = self.create(
                    user=user, product=product, rating=rating, comment=comment
                )
        except IntegrityError:
            return self.get(user=user, product=product), False
        return review, True

    def section(self, user, product):
        """Everything the product page's reviews section renders.

        The viewer's own review is pulled out for the pinned slot; the
        list is everyone else's, newest first.
        """
        reviews = self.filter(product=product).select_related("user")
        own_review = None
        if user.is_authenticated:
            own_review = reviews.filter(user=user).first()
            reviews = reviews.exclude(user=user)
        return {
            "product": product,
            "review_summary": self.summary(product),
            "eligibility": self.eligibility(user, product),
            "own_review": own_review,
            "other_reviews": reviews,
        }

    def summary(self, product):
        """The product's average rating and review count, in one query.

        With no reviews, the average is ``None``, not zero: there is no
        rating to show.
        """
        return self.filter(product=product).aggregate(
            average=models.Avg("rating"), count=models.Count("pk")
        )


class Review(models.Model):
    """One customer's rating and comment on one product they received."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(max_length=2000)
    # Plain fields (not auto_now_add/auto_now) so the seed can backdate
    # reviews. A new review's updated_at matches created_at exactly (see
    # save()), so it doesn't read as edited.
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(blank=True)
    edited_by_staff = models.BooleanField(default=False)

    objects = ReviewManager()

    class Meta:
        # Newest first by creation, so an edit never moves a review.
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_review_user_product"
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_1_to_5",
            ),
        ]

    def __str__(self):
        return f"{self.rating}★ {self.product.name} by {self.user.username}"

    def save(self, *args, **kwargs):
        if self.updated_at is None:
            self.updated_at = self.created_at
        super().save(*args, **kwargs)

    @property
    def is_edited(self):
        """Changed since it was posted."""
        return self.updated_at > self.created_at
