from django.conf import settings
from django.db import models
from django.utils import timezone

from products.models import Product


class Wishlist(models.Model):
    """A customer's wishlist — one per user, created lazily on first touch.

    Unlike the cart, it takes any product, available or not: saving
    something for later isn't a purchase.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist",
    )

    def __str__(self):
        return f"Wishlist for {self.user.username}"

    @classmethod
    def for_user(cls, user):
        """Return the user's wishlist, creating it on first touch."""
        wishlist, _ = cls.objects.get_or_create(user=user)
        return wishlist

    def add(self, product):
        """Save a product; saving one already saved is a no-op."""
        item, _ = self.items.get_or_create(product=product)
        return item

    def remove(self, product):
        """Unsave a product; removing one that isn't saved is a no-op."""
        self.items.filter(product=product).delete()

    def contains(self, product):
        return self.items.filter(product=product).exists()

    def lines(self):
        """Saved items, newest first, with their products loaded for display."""
        # The category gives the image placeholder, so load it too.
        return self.items.select_related("product__category")


class WishlistItem(models.Model):
    """One saved product; the wishlist–product pair is unique."""

    wishlist = models.ForeignKey(
        Wishlist, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    # default (not auto_now_add) so the seed can backdate saves.
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # Newest first; pk breaks ties between saves in the same instant.
        ordering = ["-added_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"], name="unique_wishlist_product"
            )
        ]

    def __str__(self):
        return self.product.name
