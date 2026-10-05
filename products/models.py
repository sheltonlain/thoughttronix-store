from django.core.files.base import ContentFile
from django.db import models, transaction
from django.templatetags.static import static
from django.urls import reverse

from .images import encode_product_image

# Categories with a dedicated placeholder illustration; anything else
# falls back to default.svg. Placeholders are static files chosen by
# category, shown for any product without a usable uploaded image.
PLACEHOLDER_CATEGORIES = {
    "home-assistants",
    "neural-implants",
    "neural-wearables",
    "accessories",
    "defense",
    "legacy-products",
}


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("products:category", kwargs={"slug": self.slug})

    @property
    def placeholder_image(self):
        """Static path of the placeholder image shown for this category's products."""
        if self.slug in PLACEHOLDER_CATEGORIES:
            return f"images/placeholders/{self.slug}.svg"
        return "images/placeholders/default.svg"


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)

    def search(self, text):
        """Simple icontains search over name and description."""
        return self.filter(
            models.Q(name__icontains=text) | models.Q(description__icontains=text)
        )


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    tagline = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")
    image = models.ImageField(upload_to="products/", blank=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Save, then delete the previous image file if it was replaced or cleared."""
        previous = ""
        if self.pk:
            previous = (
                Product.objects.filter(pk=self.pk)
                .values_list("image", flat=True)
                .first()
                or ""
            )
        super().save(*args, **kwargs)
        if previous and previous != self.image.name:
            self._delete_image_file_on_commit(previous)

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"slug": self.slug})

    def delete(self, *args, **kwargs):
        name = self.image.name
        result = super().delete(*args, **kwargs)
        if name:
            self._delete_image_file_on_commit(name)
        return result

    def _delete_image_file_on_commit(self, name):
        """Delete a stored image once the transaction commits, if no product
        still references it. A rolled-back save keeps its file."""
        storage = self.image.storage

        def delete_if_unreferenced():
            if not Product.objects.filter(image=name).exists():
                storage.delete(name)

        transaction.on_commit(delete_if_unreferenced)

    def set_image(self, file):
        """Attach ``file`` as this product's image, resized and re-encoded
        as WebP. The file is written to storage on the next ``save()``."""
        self.image = ContentFile(encode_product_image(file), name=f"{self.slug}.webp")

    @property
    def has_display_image(self):
        """True when an uploaded image is set and its file is in storage."""
        return bool(self.image) and self.image.storage.exists(self.image.name)

    @property
    def display_image_url(self):
        """The uploaded image's URL, or the category placeholder's — never
        a missing file. Templates show product images only through this."""
        if self.has_display_image:
            return self.image.url
        return static(self.category.placeholder_image)

    @property
    def display_image_alt(self):
        """Alt text: descriptive for a real photo, empty for a decorative
        placeholder (the product name is already beside it)."""
        return f"{self.name} product photo" if self.has_display_image else ""
