"""Wishlist views — thin per the architecture convention.

Saving and unsaving are separate endpoints, never a toggle, so every
click does what its label said — even a double-click or a stale tab.
Each renders the button partial (never ``base.html``) in its new state.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import TemplateView

from products.models import Product

from .models import Wishlist, WishlistItem


class WishlistView(LoginRequiredMixin, TemplateView):
    """The customer's own Wishlist page."""

    template_name = "wishlist/wishlist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wishlist"] = Wishlist.for_user(self.request.user)
        return context


class WishlistButtonView(LoginRequiredMixin, View):
    """Base for the detail page's HTMX save/unsave: act, re-render the button.

    Any product can be saved — no ``available()`` filter, unlike the cart.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        in_wishlist = self.act(Wishlist.for_user(request.user), product)
        return render(
            request,
            "wishlist/partials/_wishlist_button.html",
            {"product": product, "in_wishlist": in_wishlist},
        )

    def act(self, wishlist, product):
        """Change the wishlist; return whether the product is now saved."""
        raise NotImplementedError


class AddToWishlistView(WishlistButtonView):
    def act(self, wishlist, product):
        wishlist.add(product)
        return True


class RemoveFromWishlistView(WishlistButtonView):
    def act(self, wishlist, product):
        wishlist.remove(product)
        return False


class RemoveWishlistItemView(LoginRequiredMixin, View):
    """HTMX: the Wishlist page's Remove; re-renders the whole contents.

    Items are always fetched through the owner's wishlist — never by bare pk.
    """

    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, pk=pk, wishlist__user=request.user)
        item.delete()
        return render(
            request,
            "wishlist/partials/_wishlist_contents.html",
            {"wishlist": item.wishlist},
        )
