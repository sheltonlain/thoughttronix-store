# PRD: The ThoughtTronix Store — Wishlist

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

---

## Problem Statement

Customers browsing the ThoughtTronix catalog often find a product they want but aren't ready to buy — the price is a stretch this month, the product is currently unavailable, or they simply want to think it over (which, our analytics team reminds us, we can already tell they are doing). Today their only option is to put it in the cart, where it clutters checkout, or to remember it on their own, which they reliably do not.

There is no place in the store to say "save this for later." A customer who leaves without buying has no easy way back to the products they were considering.

## Solution

Every signed-in customer gets a single personal wishlist. On any product's detail page, a button saves the product to the wishlist or removes it — in place, without reloading the page — and the button always shows whether the product is currently saved.

A **Wishlist** page, linked from the navbar, lists everything the customer has saved, newest first. From there they can open a product, add it to their cart, or remove it from the wishlist, again without a page reload. A customer can only ever see and change their own wishlist.

Signed-out visitors still see the save button; it takes them to sign in and back to the product, where a short hint reminds them to click Save now that they're signed in.

## User Stories

**Visitor (not signed in)**

1. As a visitor, I can see a "Save to wishlist" button on a product's detail page, so that I know the store offers a wishlist.
2. As a visitor, clicking "Save to wishlist" takes me to sign in and then returns me to the same product page, so that I don't lose my place.
3. As a visitor who has just signed in from the save button, I see a hint beside the button telling me to click it to save the product, so that I understand the product was not saved automatically.

**Customer (signed in)**

4. As a customer, I can save a product to my wishlist from its detail page without a full page reload, so that saving doesn't interrupt my browsing.
5. As a customer, I can remove a product from my wishlist from its detail page without a full page reload, so that I can change my mind just as easily.
6. As a customer, the wishlist button on a product's detail page shows whether that product is already saved ("♡ Save to wishlist" vs. "♥ Saved · Remove"), so that I always know its status.
7. As a customer, clicking the button twice quickly, or clicking a stale button in a second tab, never does the opposite of what its label said, so that the button can be trusted.
8. As a customer, I can save a product even when it is currently unavailable, so that I can remember it for when it returns.
9. As a customer, I can open my Wishlist page from a link in the navbar, so that I can find my saved products at any time.
10. As a customer, my Wishlist page lists each saved product with its image, name, price, and a link to its detail page, newest saved first, so that I can review what I've saved.
11. As a customer, unavailable products on my Wishlist page are clearly marked Unavailable, so that I'm not misled about what I can buy.
12. As a customer, I can add a saved product to my cart directly from my Wishlist page — with the same button and behavior as the catalog — so that I can move from "later" to "now" in one click.
13. As a customer, a product I add to my cart from the Wishlist page stays on my wishlist, so that adding to the cart doesn't silently change my list.
14. As a customer, I can remove a product from my Wishlist page without a full page reload, so that I can tidy my list quickly.
15. As a customer, when my wishlist is empty I see a friendly empty state that points me back to the catalog, rather than a blank page.
16. As a customer, I can only ever see and change my own wishlist; no URL lets me view or alter another customer's, so that my saved products stay private.
17. As a customer, I have exactly one wishlist, which exists without my having to create it, so that there's nothing to set up.

**Staff and developers**

18. As a superuser, I can inspect wishlists and their items in the Django admin, the same way carts are inspectable, so that I can diagnose customer issues.
19. As a developer or reviewer, after running `seed` I can sign in as the demo `customer` and immediately see a populated wishlist — including an unavailable product and a product already in the cart — so that every state of the feature is demonstrable without setup.

## Implementation Decisions

**New app**

- A new `wishlist` Django app owns the feature: models, views, URLs, templates, admin, and tests. Its URLs are mounted under `/wishlist/` with the `wishlist` namespace; its templates live in the project-level `templates/wishlist/` directory, with HTMX partials underscore-prefixed in `partials/` per FRONTEND.md.

**Models — mirroring `Cart` / `CartItem`**

- `Wishlist`: one-to-one with the user (cascade on user deletion), created lazily on first touch through a `for_user(user)` class method, exactly as `Cart.for_user` works. "One wishlist per customer" is enforced by the one-to-one field.
- `WishlistItem`: foreign key to its wishlist and to a product (both cascade — deleting a product removes it from every wishlist), plus an `added_at` timestamp. A unique constraint on the wishlist–product pair prevents duplicates. Default ordering is newest `added_at` first.
- Logic lives on the model, not the views: `add(product)` (idempotent via get-or-create — adding a saved product is a no-op), `remove(product)` (idempotent — removing an unsaved product is a no-op), `contains(product)`, and `lines()` (items with their products and categories loaded for display, since the category drives the placeholder image).
- No restriction on product availability: any product the detail page shows can be saved. Unlike the cart, which refuses unavailable products because they can't be bought, a wishlist isn't a purchase.

**Endpoints — separate add and remove, never a toggle**

- All wishlist views require sign-in and stay thin; they call model methods and render a partial.
- Detail-page add: a POST keyed by product pk adds the product and re-renders the wishlist button partial in its "saved" state.
- Detail-page remove: a POST keyed by product pk removes the product and re-renders the button partial in its "not saved" state.
- Separate add/remove endpoints (rather than one toggle) guarantee every click does what its label promised, even on double-clicks or stale tabs.
- Wishlist-page remove: a POST keyed by wishlist-item pk, looking the item up *through its owner* (the item's wishlist must belong to the requesting user — never a bare pk lookup), removes it and re-renders the whole wishlist-contents partial. This mirrors the cart's line-action views; re-rendering the contents means the empty state appears automatically when the last item goes. Another customer's item pk 404s.
- Wishlist page: a sign-in-required page rendering the current user's wishlist lines.

**Product detail page**

- `ProductDetailView` adds an `in_wishlist` flag to its context (one existence check for signed-in users; false for visitors).
- The wishlist button is a new self-contained partial included beside the existing Add to cart button. It has three states:
  - Signed in, not saved: "♡ Save to wishlist", `btn-outline btn-sm`, HTMX POST to add, outer-HTML swap, `aria-pressed="false"`.
  - Signed in, saved: "♥ Saved · Remove", `btn-outline btn-secondary btn-sm`, HTMX POST to remove, outer-HTML swap, `aria-pressed="true"`.
  - Signed out: a plain link (no HTMX) styled like the not-saved state, pointing to the sign-in page with `next` set to the product's URL plus a `wishlist=1` query flag.
- The cart's Add to cart remains the page's only `btn-primary`.
- When a signed-in customer views a product with `wishlist=1` in the querystring and the product is not yet saved, a small hint appears beneath the button prompting them to click Save. The flag is display-only — a GET never changes data — so a crafted link cannot alter anyone's wishlist. The hint is template logic only; the view does not change for it.

**Wishlist page**

- Lists saved products newest first, each row showing image (via the product's display-image properties), name linking to the detail page, price, and an Unavailable badge where applicable.
- Each row includes the existing add-to-cart partial unchanged, matching the catalog cards (the per-card primary button follows the catalog's precedent). The cart-quantities context it relies on is already provided site-wide by the orders context processor; unavailable products automatically show the cart partial's disabled "Unavailable" state.
- Each row has an HTMX Remove button targeting the wishlist-contents partial.
- A designed empty state links back to the catalog, per FRONTEND.md's rule that every list view has one.

**Navbar**

- Signed-in users get a plain "Wishlist" `btn-ghost btn-sm` link alongside Orders, Addresses, and Security. No count badge, so no new context processor and no out-of-band swaps in any wishlist response.

**Admin**

- `Wishlist` is registered in the Django admin with a tabular inline of its items, mirroring the cart's admin. There is no back-office (staff shell) tab for wishlists.

**Seed**

- The `seed` command gains a demo wishlist for the `customer` user: a short list of three or four product slugs including at least one unavailable product and one product also in the seeded cart, created in a dedicated step after the cart. The wipe step clears wishlists along with carts, and the summary line mentions the seeded wishlist.

**Testing**

- pytest with the shared project-level fixtures, no factory-boy, green at every phase boundary.
- Model: lazy creation, one wishlist per user, add idempotency, remove idempotency, `contains`, newest-first ordering, cascade on product deletion.
- Views: sign-in required on every endpoint; add and remove return the correct button state with `aria-pressed`; unavailable products can be saved; item removal through another user's item pk 404s; the wishlist page shows only the requester's items; empty state renders; the contents partial re-renders after removal.
- Detail page: the three button states; the `wishlist=1` hint appears only for signed-in users on an unsaved product and never mutates data.
- Seed: the demo customer's wishlist exists with the expected mix.

## Out of Scope

- Named wishlists, multiple wishlists per customer, and shared or public wishlists.
- Automatically saving the product after sign-in (would require a session-stored pending action; a GET-triggered save is unsafe).
- Carrying the `next` return URL through the signup → email verification → sign-in flow; a visitor who signs up from the save button lands on the default post-login page.
- Wishlist buttons on catalog and category cards — detail page only.
- A navbar wishlist count badge.
- Back-in-stock or price-drop notifications.
- "Move to cart" (removing from the wishlist on add-to-cart).
- A staff back-office view of customer wishlists, or wishlist data on the analytics dashboard.
- Restyling the catalog's per-card primary buttons to satisfy the one-primary-per-page rule strictly.

## Further Notes

- **Known limitation — expired session on HTMX POST.** If a customer's session expires while a page is open, `LoginRequiredMixin` answers the HTMX POST with a redirect to the login page; HTMX follows it and swaps the whole login page into the button's place. The cart's Add to cart button already behaves this way. Rather than fix it for the wishlist alone (creating inconsistency), this is recorded as a project-wide follow-up: an HTMX-aware login mixin that responds with an `HX-Redirect` header, applied to cart and wishlist views together.
- The design deliberately mirrors existing, reviewed patterns — `Cart.for_user`, the cart's unique line constraint, its owner-scoped line-action views, and the add-to-cart partial's signed-out link — so the wishlist introduces no new architectural ideas.
- Visual language stays Tailwind + DaisyUI (`night` theme); no JavaScript beyond HTMX.
