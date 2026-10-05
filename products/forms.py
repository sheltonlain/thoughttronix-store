"""Back-office forms for the catalog models.

ModelForms inherit the models' own rules (name required, slug unique);
the explicit ``price`` declaration adds the one rule the model doesn't
carry — the price must be positive. ``clean_image`` rejects unusable
uploads, each with a plain-language reason. Widgets get their DaisyUI
classes in one shared ``__init__`` loop, as on ``CheckoutForm``.
"""

from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import filesizeformat

from .images import (
    ACCEPTED_FORMATS,
    MAX_MEGAPIXELS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    MIN_HEIGHT,
    MIN_WIDTH,
)
from .models import Category, Product, Tag

# Plain-language names for the formats staff are likely to try.
FORMAT_NAMES = {"WEBP": "WebP", "MPO": "JPEG"}


class ProductImageInput(forms.ClearableFileInput):
    """A file input with a DaisyUI-styled "remove image" checkbox."""

    template_name = "products/widgets/image_input.html"
    clear_checkbox_label = "Remove the current image"


class StyledModelForm(forms.ModelForm):
    """Base form that dresses every widget in DaisyUI classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "toggle toggle-primary"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "textarea w-full"
                widget.attrs.setdefault("rows", 6)
            elif isinstance(widget, forms.SelectMultiple):
                widget.attrs["class"] = "select h-auto w-full"
                widget.attrs.setdefault("size", 8)
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = "file-input w-full"
            else:
                widget.attrs["class"] = "input w-full"


class ProductForm(StyledModelForm):
    price = forms.DecimalField(
        label="Price (USD)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "tagline",
            "description",
            "image",
            "price",
            "category",
            "tags",
            "is_available",
        ]
        widgets = {
            "image": ProductImageInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
        }
        help_texts = {
            "image": (
                f"JPEG, PNG, or WebP, up to {MAX_UPLOAD_MB} MB, at least "
                f"{MIN_WIDTH} × {MIN_HEIGHT} pixels. Without one, the "
                "category's placeholder is shown."
            ),
        }
        error_messages = {
            "image": {
                "invalid_image": (
                    "We couldn't read this file as an image. It may be "
                    "damaged, or not a picture at all — try saving it again "
                    "as a JPEG, PNG, or WebP."
                ),
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Judge uploads by content, not name: drop the extension check.
        self.fields["image"].validators = []

    def clean_image(self):
        """Reject uploads that can't be shown well, saying why in plain words.

        Django's ImageField has already confirmed Pillow can open the file
        (whatever its extension); ``image.image`` is that Pillow image.
        """
        image = self.cleaned_data.get("image")
        if not isinstance(image, UploadedFile):
            return image  # no new upload: unchanged, cleared, or none

        if image.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(
                f"This file is {filesizeformat(image.size)}. The limit is "
                f"{MAX_UPLOAD_MB} MB — try exporting a smaller version."
            )

        kind = image.image.format
        if kind not in ACCEPTED_FORMATS:
            name = FORMAT_NAMES.get(kind, kind)
            raise forms.ValidationError(
                f"We accept JPEG, PNG, or WebP images. This file is a {name}."
            )

        width, height = image.image.size
        megapixels = width * height / 1_000_000
        if megapixels > MAX_MEGAPIXELS:
            raise forms.ValidationError(
                f"This image is {width:,} × {height:,} pixels "
                f"({megapixels:.1f} megapixels). The limit is {MAX_MEGAPIXELS} "
                "megapixels — please resize it and try again."
            )
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            raise forms.ValidationError(
                f"This image is {width} × {height} pixels. It needs to be at "
                f"least {MIN_WIDTH} × {MIN_HEIGHT} pixels to look sharp on the "
                "product page."
            )

        # The extension is ignored — name the upload by its real format so
        # the model field's extension check agrees with what Pillow found.
        image.name = f"upload.{ACCEPTED_FORMATS[kind]}"
        return image

    def save(self, commit=True):
        image = self.cleaned_data.get("image")
        if isinstance(image, UploadedFile):
            self.instance.set_image(image)
        return super().save(commit)


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class TagForm(StyledModelForm):
    class Meta:
        model = Tag
        fields = ["name", "slug"]
