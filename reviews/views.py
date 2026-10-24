"""Review views — thin per the architecture convention.

Every endpoint renders a partial (never ``base.html``). Create, save, and
delete re-render the whole reviews section, so the summary, pinned slot,
and list stay consistent from one template with no out-of-band swaps.
Edit and cancel swap a single card.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import StaffRequiredMixin
from products.models import Product

from .forms import ReviewForm
from .models import Eligibility, Review

SECTION_TEMPLATE = "reviews/partials/_reviews_section.html"
CARD_TEMPLATE = "reviews/partials/_review_card.html"
FORM_TEMPLATE = "reviews/partials/_review_form.html"


def section_context(user, product, form=None, **extra):
    """The reviews section's context, with a blank form unless given one.

    Shared by the product page and the endpoints that re-render the section.
    """
    context = Review.objects.section(user, product)
    context["review_form"] = form or ReviewForm()
    context.update(extra)
    return context


def render_section(request, product, form=None, **extra):
    """Render the whole reviews section, swapped in for whatever the
    request targeted (a card, when edit or cancel finds the review gone)."""
    response = render(
        request, SECTION_TEMPLATE, section_context(request.user, product, form, **extra)
    )
    response["HX-Retarget"] = "#reviews-section"
    response["HX-Reswap"] = "outerHTML"
    return response


class CreateReviewView(LoginRequiredMixin, View):
    """HTMX: post a review, then re-render the section.

    Eligibility is checked before the form, so an ineligible user gets a
    403 even with invalid input, and a duplicate shows the existing review
    with an "already reviewed" note whatever the stale form held. Invalid
    input re-renders with the bound form.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        eligibility = Review.objects.ensure_may_submit(request.user, product)
        if eligibility == Eligibility.ALREADY_REVIEWED:
            return render_section(request, product, duplicate=True)
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render_section(request, product, form)
        _, created = Review.objects.submit(request.user, product, **form.cleaned_data)
        return render_section(request, product, duplicate=not created)


def edit_form(review, data=None):
    """The form editing ``review``, with ids of its own so they never clash
    with the create form or another card's edit form on the page."""
    return ReviewForm(data, instance=review, auto_id=f"id_review_{review.pk}_%s")


class ChangeReviewMixin(LoginRequiredMixin):
    """Edit, cancel, and delete: find the review the user may change.

    The lookup goes through ``changeable_by`` first. Someone else's review
    is a 404. One that no longer exists returns ``None``, and the view
    answers with a fresh section: reviews are public, so confirming a pk
    is gone leaks nothing.
    """

    def get_review(self):
        pk = self.kwargs["pk"]
        review = (
            Review.objects.changeable_by(self.request.user)
            .select_related("user", "product")
            .filter(pk=pk)
            .first()
        )
        if review is None and Review.objects.filter(pk=pk).exists():
            raise Http404
        return review

    def render_gone(self, missing=False):
        """The fresh section for a review that no longer exists.

        Its product comes from the ``product`` pk every request sends,
        since the review that named it is gone.
        """
        params = (
            self.request.POST if self.request.method == "POST" else self.request.GET
        )
        try:
            product_pk = int(params.get("product", ""))
        except ValueError:
            raise Http404 from None
        product = get_object_or_404(Product, pk=product_pk)
        return render_section(self.request, product, missing=missing)


class EditReviewView(ChangeReviewMixin, View):
    """HTMX: GET swaps a card for its prefilled form; POST saves the edit.

    A valid save re-renders the whole section (the summary may change);
    invalid input re-renders only the card-sized form with its errors.
    """

    def get(self, request, pk):
        review = self.get_review()
        if review is None:
            return self.render_gone(missing=True)
        return render(
            request,
            FORM_TEMPLATE,
            {"form": edit_form(review), "editing": review},
        )

    def post(self, request, pk):
        review = self.get_review()
        if review is None:
            return self.render_gone(missing=True)
        form = edit_form(review, request.POST)
        if not form.is_valid():
            return render(request, FORM_TEMPLATE, {"form": form, "editing": review})
        review.revise(by=request.user, **form.cleaned_data)
        return render_section(request, review.product)


class ReviewCardView(ChangeReviewMixin, View):
    """HTMX: cancel an edit, swapping the unchanged card back in."""

    def get(self, request, pk):
        review = self.get_review()
        if review is None:
            return self.render_gone(missing=True)
        return render(request, CARD_TEMPLATE, {"review": review})


class DeleteReviewView(ChangeReviewMixin, View):
    """HTMX: delete a review (behind ``hx-confirm``) and re-render the section."""

    def post(self, request, pk):
        review = self.get_review()
        if review is None:
            return self.render_gone()
        product = review.product
        review.delete()
        return render_section(request, product)


# --- The back office --------------------------------------------------------
#
# Staff moderation: every review, filterable by star rating, with an
# in-place delete. There is no edit screen; editing stays inline on the
# product page.

MANAGE_CONTENTS_TEMPLATE = "reviews/partials/_manage_reviews_contents.html"


def active_rating(params):
    """The ``rating`` filter in ``params`` as 1–5, or None for anything else."""
    rating = params.get("rating", "")
    return int(rating) if rating in {"1", "2", "3", "4", "5"} else None


def manage_context(rating):
    return {
        "reviews": Review.objects.rated(rating).select_related("user", "product"),
        "active_rating": rating,
    }


class ManageReviewListView(StaffRequiredMixin, TemplateView):
    """Every review, newest first, filterable via ``?rating=``."""

    template_name = "reviews/manage_reviews.html"
    extra_context = {"section": "reviews", "ratings": range(5, 0, -1)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(manage_context(active_rating(self.request.GET)))
        return context


class ManageDeleteReviewView(StaffRequiredMixin, View):
    """HTMX: delete a review (behind ``hx-confirm``) and re-render the list.

    Idempotent: a review that's already gone (say, deleted in another tab)
    just re-renders the list.
    """

    def post(self, request, pk):
        Review.objects.filter(pk=pk).delete()
        return render(
            request,
            MANAGE_CONTENTS_TEMPLATE,
            manage_context(active_rating(request.POST)),
        )
