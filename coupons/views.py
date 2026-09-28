"""The Coupons tab of the back office — Marketing's own screens.

Every view gates on ``CouponManagerRequiredMixin`` (staff plus the
``manage_coupons`` permission); URLs use pks. The ``section`` context
entry drives the active tab in the staff shell.
"""

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.mixins import CouponManagerRequiredMixin

from .forms import CouponForm
from .models import Coupon


class ManageCouponListView(CouponManagerRequiredMixin, ListView):
    """Coupons with their status, filterable via ``?status=``.

    Archived coupons stay out of the way unless their tab is picked.
    """

    template_name = "coupons/manage_coupons.html"
    context_object_name = "coupons"
    paginate_by = 20
    extra_context = {"section": "coupons"}

    def get_queryset(self):
        # Explicit order: Meta.ordering doesn't apply to GROUP BY queries.
        coupons = (
            Coupon.objects.with_use_count()
            .prefetch_related("products")
            .order_by(*Coupon._meta.ordering)
        )
        status = self.request.GET.get("status", "")
        if status in Coupon.Status.values:
            return coupons.with_status(status)
        return coupons.unarchived()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Coupon.Status.choices
        context["active_status"] = self.request.GET.get("status", "")
        return context


class CouponFormMixin(CouponManagerRequiredMixin, SuccessMessageMixin):
    model = Coupon
    form_class = CouponForm
    template_name = "coupons/manage_coupon_form.html"
    success_url = reverse_lazy("coupons:manage_coupons")
    extra_context = {"section": "coupons"}

    def get_success_message(self, cleaned_data):
        return f"“{self.object.code}” {self.verb}."


class ManageCouponCreateView(CouponFormMixin, CreateView):
    verb = "created"


class ManageCouponUpdateView(CouponFormMixin, UpdateView):
    verb = "saved"


class ManageCouponDeleteView(CouponManagerRequiredMixin, DeleteView):
    """Only a coupon nobody has used can go; a used one is archived instead."""

    model = Coupon
    context_object_name = "coupon"
    template_name = "coupons/manage_coupon_confirm_delete.html"
    success_url = reverse_lazy("coupons:manage_coupons")
    extra_context = {"section": "coupons"}

    def form_valid(self, form):
        if self.object.is_locked:
            messages.error(
                self.request,
                f"“{self.object.code}” has been used, so it can't be deleted. "
                "Archive it instead.",
            )
            return redirect("coupons:manage_coupon_update", pk=self.object.pk)
        messages.success(self.request, f"“{self.object.code}” deleted.")
        return super().form_valid(form)


class ManageCouponArchiveView(CouponManagerRequiredMixin, View):
    """POST-only: retire a coupon, switching it off and freeing its code."""

    def post(self, request, pk):
        coupon = get_object_or_404(Coupon, pk=pk)
        coupon.is_archived = True
        coupon.is_active = False
        coupon.save(update_fields=["is_archived", "is_active"])
        messages.success(request, f"“{coupon.code}” archived. Its code is free.")
        return redirect("coupons:manage_coupons")


class ManageCouponRestoreView(CouponManagerRequiredMixin, View):
    """POST-only: bring an archived coupon back — still switched off, so it
    never goes live by surprise. Refused if its code has been reused."""

    def post(self, request, pk):
        coupon = get_object_or_404(Coupon, pk=pk)
        coupon.is_archived = False
        try:
            coupon.validate_constraints()
        except ValidationError:
            messages.error(
                request,
                f"{coupon.code} is already in use by another coupon — "
                "archive or rename that one first.",
            )
            return redirect(reverse("coupons:manage_coupons") + "?status=ARCHIVED")
        coupon.save(update_fields=["is_archived"])
        messages.success(
            request, f"“{coupon.code}” restored. Switch it on when it's ready."
        )
        return redirect("coupons:manage_coupon_update", pk=coupon.pk)
