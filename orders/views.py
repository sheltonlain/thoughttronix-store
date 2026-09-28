"""Cart and checkout views — thin per the architecture convention.

The three HTMX interactions of the core live here: add-to-cart, quantity
change, and line removal. Each renders a partial (never ``base.html``);
the responses carry the navbar badge as an out-of-band swap via the
``oob_badge`` context flag. Checkout is conventional full-page work:
validate the form, hand everything to ``place_order``. Its HTMX helpers
fill in the form from the address book and re-price the order summary
with a coupon — what's submitted is always plain form fields.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from accounts.mixins import StaffRequiredMixin
from accounts.models import Address
from coupons.models import Coupon, CouponError
from products.models import Product

from .forms import CheckoutForm, OrderStatusForm
from .models import Cart, CartItem, Order
from .services import place_order


class CartView(LoginRequiredMixin, TemplateView):
    """The customer's cart page."""

    template_name = "orders/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart"] = Cart.for_user(self.request.user)
        return context


class AddToCartView(LoginRequiredMixin, View):
    """HTMX: add a product; the button swaps and the badge updates OOB.

    Looks the product up through ``available()``, so adding an
    unavailable product 404s — the same not-for-sale semantics as the
    public catalog.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.available(), pk=pk)
        item = Cart.for_user(request.user).add(product)
        return render(
            request,
            "orders/partials/_add_button.html",
            {"product": product, "in_cart": item.quantity, "oob_badge": True},
        )


class CartItemActionView(LoginRequiredMixin, View):
    """Base for HTMX line mutations: act, then re-render the cart contents.

    Items are always fetched through the owner's cart — never by bare pk.
    """

    def post(self, request, pk):
        item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
        self.act(item)
        return render(
            request,
            "orders/partials/_cart_contents.html",
            {"cart": item.cart, "oob_badge": True},
        )

    def act(self, item):
        raise NotImplementedError


class IncrementCartItemView(CartItemActionView):
    def act(self, item):
        item.increment()


class DecrementCartItemView(CartItemActionView):
    def act(self, item):
        item.decrement()


class RemoveCartItemView(CartItemActionView):
    def act(self, item):
        item.delete()


def order_summary(cart, user, code):
    """Context for the checkout's order-summary card, priced with ``code``.

    A code that can't be used leaves the price alone and explains why in
    ``coupon_error`` — the card always renders, never an error page.
    """
    subtotal = cart.total()
    context = {"cart": cart, "subtotal": subtotal, "total": subtotal}
    if code.strip():
        try:
            evaluation = Coupon.objects.for_code(code).evaluate(cart, user)
        except CouponError as error:
            context["coupon_error"] = str(error)
        else:
            context["evaluation"] = evaluation
            context["total"] = evaluation.total
    return context


class CheckoutView(LoginRequiredMixin, FormView):
    """The single checkout page: validate the form, hand off to the service.

    A cart that can't check out (empty, or holding a product that has
    since become unavailable) is sent back to the cart page to be fixed —
    ``place_order`` enforces the same rules transactionally as the
    backstop.
    """

    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        cart = Cart.for_user(request.user)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty — add something first.")
            return redirect("orders:cart")
        unavailable = [
            line.product.name for line in cart.lines() if not line.product.is_available
        ]
        if unavailable:
            messages.warning(
                request,
                f"No longer available: {', '.join(unavailable)}. "
                "Remove them from the cart to check out.",
            )
            return redirect("orders:cart")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {**super().get_initial(), **CheckoutForm.initial_for(self.request.user)}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        form = context["form"]
        code = (form["coupon_code"].value() or "") if form.is_bound else ""
        context.update(order_summary(Cart.for_user(user), user, code))
        context["saved_addresses"] = Address.objects.address_book(user)
        # Preselect the defaults only on a fresh page; a re-rendered POST
        # shows whatever the customer had typed instead.
        if not form.is_bound:
            context["shipping_selected"] = user.default_shipping_address_id
            context["billing_selected"] = user.default_billing_address_id
        return context

    def form_valid(self, form):
        cart = Cart.for_user(self.request.user)
        try:
            order = place_order(
                cart,
                self.request.user,
                form.cleaned_data,
                save_shipping=form.cleaned_data["save_shipping"],
                save_billing=form.cleaned_data["save_billing"],
                coupon_code=form.cleaned_data["coupon_code"],
            )
        except CouponError as error:
            # The code went bad after it was applied. Never charge a price
            # the customer didn't see: stop, and show them the real one.
            form.add_error(
                None,
                f"Your order wasn't placed. {error} Without it, your total is "
                f"${cart.total():,.2f} — place your order again, or try "
                "another code.",
            )
            return self.form_invalid(form)
        messages.success(self.request, f"Order {order.number} placed. Thank you!")
        return redirect(reverse("orders:confirmation", kwargs={"pk": order.pk}))


class CheckoutApplyCouponView(LoginRequiredMixin, View):
    """HTMX: re-price the order summary with a code, or say why not.

    Always the summary partial — a good code shows the drop and carries
    the code to "Place order"; any other input gets a message. A blank
    code removes the coupon. The Place-order button's total follows OOB.
    """

    def post(self, request):
        cart = Cart.for_user(request.user)
        code = request.POST.get("coupon_code", "")
        return render(
            request,
            "orders/partials/_order_summary.html",
            {**order_summary(cart, request.user, code), "oob_total": True},
        )


class CheckoutAddressFieldsView(LoginRequiredMixin, View):
    """HTMX: one checkout address section, filled from a saved address.

    ``?saved_address=<pk>`` picks the address; an empty value returns the
    section blank ("Enter a new address"). Addresses are only ever looked
    up through the customer's own book — anyone else's is a 404.
    """

    def get(self, request, section):
        if section not in ("shipping", "billing"):
            raise Http404
        pk = request.GET.get("saved_address", "")
        initial = {}
        if pk:
            if not pk.isdigit():
                raise Http404
            address = get_object_or_404(Address, pk=pk, user=request.user)
            initial = address.as_checkout_initial(section)
        form = CheckoutForm(initial=initial)
        return render(
            request,
            "orders/partials/_address_fields.html",
            {"section": section, "fields": form.address_fields(section)},
        )


class CheckoutBillingSectionView(LoginRequiredMixin, View):
    """HTMX: the billing card's body, swapped when "same as shipping" toggles.

    Ticked, billing collapses to a note (the form copies shipping into
    billing on submit); unticked, the picker and fields come back, filled
    from the default billing address.
    """

    def get(self, request):
        user = request.user
        return render(
            request,
            "orders/partials/_billing_body.html",
            {
                "form": CheckoutForm(initial=CheckoutForm.initial_for(user)),
                "same_as_shipping": bool(request.GET.get("use_shipping_for_billing")),
                "saved_addresses": Address.objects.address_book(user),
                "billing_selected": user.default_billing_address_id,
            },
        )


class OwnOrdersMixin(LoginRequiredMixin):
    """Orders are always fetched through the owner — never by bare pk."""

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderConfirmationView(OwnOrdersMixin, DetailView):
    template_name = "orders/confirmation.html"
    context_object_name = "order"


class OrderHistoryView(OwnOrdersMixin, ListView):
    """The customer's orders, most recent first per the model ordering."""

    template_name = "orders/order_history.html"
    context_object_name = "orders"


class OrderDetailView(OwnOrdersMixin, DetailView):
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("items")


# --- The back office --------------------------------------------------------
#
# Staff-only order oversight: every customer's orders, filterable by
# status, with the status dropdown on the detail page. The ``section``
# context entry drives the active tab in the staff shell.


class ManageOrderListView(StaffRequiredMixin, ListView):
    """All orders, most recent first, filterable via ``?status=``."""

    template_name = "orders/manage_orders.html"
    context_object_name = "orders"
    paginate_by = 20
    extra_context = {"section": "orders"}

    def get_queryset(self):
        orders = Order.objects.select_related("user")
        status = self.request.GET.get("status", "")
        if status in Order.Status.values:
            orders = orders.filter(status=status)
        return orders

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["active_status"] = self.request.GET.get("status", "")
        return context


class ManageOrderDetailView(StaffRequiredMixin, DetailView):
    """Any order's detail, with the status form alongside."""

    template_name = "orders/manage_order_detail.html"
    context_object_name = "order"
    queryset = Order.objects.select_related("user").prefetch_related("items")
    extra_context = {"section": "orders"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_form"] = OrderStatusForm(instance=self.object)
        return context


class UpdateOrderStatusView(StaffRequiredMixin, View):
    """POST-only: set an order's status from the back-office dropdown."""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"{order.number} is now {order.get_status_display().lower()}.",
            )
        else:
            messages.error(request, "That isn't a status an order can have.")
        return redirect("orders:manage_order_detail", pk=order.pk)
