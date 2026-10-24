"""Review views — thin per the architecture convention.

Every endpoint renders a partial (never ``base.html``). Create re-renders
the whole reviews section, so the summary, pinned slot, and list stay
consistent from one template with no out-of-band swaps.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views import View

from products.models import Product

from .forms import ReviewForm
from .models import Eligibility, Review

SECTION_TEMPLATE = "reviews/partials/_reviews_section.html"


def section_context(user, product, form=None, **extra):
    """The reviews section's context, with a blank form unless given one.

    Shared by the product page and the endpoints that re-render the section.
    """
    context = Review.objects.section(user, product)
    context["review_form"] = form or ReviewForm()
    context.update(extra)
    return context


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
            return render(
                request,
                SECTION_TEMPLATE,
                section_context(request.user, product, duplicate=True),
            )
        form = ReviewForm(request.POST)
        if not form.is_valid():
            return render(
                request, SECTION_TEMPLATE, section_context(request.user, product, form)
            )
        _, created = Review.objects.submit(request.user, product, **form.cleaned_data)
        return render(
            request,
            SECTION_TEMPLATE,
            section_context(request.user, product, duplicate=not created),
        )
