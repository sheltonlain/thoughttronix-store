"""The review form, shared by create (and, later, edit).

The ModelForm inherits the model's rules: ``comment`` is required, at most
2,000 characters, and stripped (Django's ``CharField`` strips by default),
so a whitespace-only comment fails as blank. ``rating`` is redeclared as a
choice of five stars so it can render as DaisyUI's ``rating`` component;
there's no default, so a missing rating is an ordinary field error.
"""

from django import forms

from .models import Review

STAR_CHOICES = [(n, f"{n} star{'' if n == 1 else 's'}") for n in range(1, 6)]


class StarRatingInput(forms.RadioSelect):
    """Five ``mask-star`` radios, each labelled ("3 stars") for screen readers."""

    template_name = "reviews/widgets/star_rating.html"

    def __init__(self, attrs=None):
        super().__init__({"class": "mask mask-star-2 bg-warning", **(attrs or {})})


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Your rating",
        choices=STAR_CHOICES,
        coerce=int,
        widget=StarRatingInput,
        error_messages={"required": "Choose a star rating."},
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {"comment": "Your review"}
        widgets = {
            "comment": forms.Textarea(
                attrs={"class": "textarea w-full", "rows": 4, "maxlength": 2000}
            )
        }
        error_messages = {"comment": {"required": "Write a few words about it."}}
