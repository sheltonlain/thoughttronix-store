# Plan: Wishlist

> Source PRD: `prd/wishlist.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: a new `wishlist` app owns the models, views, URLs, admin,
  and tests. Templates live in `templates/wishlist/`, with HTMX partials
  underscore-prefixed in `templates/wishlist/partials/` per FRONTEND.md. It
  introduces no new architectural ideas; every piece mirrors a reviewed cart
  pattern.
- **URLs** (all named under the `wishlist:` namespace, mounted at
  `/wishlist/`, following the cart's path shapes):
  - `` (the root): the Wishlist page
  - `add/<int:pk>/`: detail-page add, keyed by product pk (HTMX POST)
  - `remove/<int:pk>/`: detail-page remove, keyed by product pk (HTMX POST)
  - `items/<int:pk>/remove/`: Wishlist-page remove, keyed by wishlist-item
    pk (HTMX POST)
- **Models**, mirroring `Cart` / `CartItem`:
  - `Wishlist`: one-to-one with `accounts.User` (cascade). It is created
    lazily through `Wishlist.for_user(user)`, exactly like `Cart.for_user`.
    The one-to-one field is what enforces one wishlist per customer.
  - `WishlistItem`: FK to `Wishlist` and FK to `products.Product` (both
    cascade), plus an `added_at` timestamp. A unique constraint covers the
    wishlist–product pair, and default ordering is `-added_at`.
  - Model methods: `add(product)` (idempotent get-or-create),
    `remove(product)` (idempotent), `contains(product)`, and `lines()`
    (items with product and category loaded).
- **Separate add and remove endpoints, never a toggle**: each click does
  what its label said, even on a double-click or a stale tab.
- **Availability**: no restriction. Any product the detail page shows can
  be saved, unlike the cart, which refuses unavailable products.
- **Auth**: every wishlist view uses `LoginRequiredMixin`. Item lookups
  always go through the owner (`wishlist__user=request.user`), never by
  bare pk, so another customer's item 404s.
- **Responses**: views stay thin. They call a model method and render a
  partial. Responses carry no out-of-band swaps, since there is no navbar
  count badge.
- **Frontend**: Tailwind + DaisyUI (`night` theme), no JavaScript beyond
  HTMX. On the detail page, Add to cart stays the only `btn-primary`.
- **Testing**: pytest with the shared project-level fixtures in
  `conftest.py`, per `docs/TESTING.md`, and no factory-boy. The suite is
  green at every phase boundary.
- **Known limitation, not fixed here**: an expired session on an HTMX POST
  swaps the login page into the target, just as the cart's button already
  does. This is recorded as a project-wide follow-up: an HTMX-aware login
  mixin that answers with `HX-Redirect`.

---

## Phase 1: Wishlist button on the detail page

**User stories**: 1, 2, 3, 4, 5, 6, 7, 8, 17, 18

### What to build

Everything a customer or visitor sees on a product's detail page. Create
the `wishlist` app, its two models and migration, and the model methods
`for_user`, `add`, `remove`, and `contains`. Register `Wishlist` in the
Django admin with a tabular inline of its items, mirroring the cart's admin.
Mount the app's URLs at `/wishlist/` with the detail-page add and remove
endpoints.

`ProductDetailView` adds an `in_wishlist` flag to its context: one
existence check for signed-in users, false for visitors. A self-contained
button partial sits beside Add to cart and has three states:

- **Signed in, not saved**: "♡ Save to wishlist", `btn-outline btn-sm`,
  HTMX POST to add, outer-HTML swap, `aria-pressed="false"`.
- **Signed in, saved**: "♥ Saved · Remove", `btn-outline btn-secondary
  btn-sm`, HTMX POST to remove, outer-HTML swap, `aria-pressed="true"`.
- **Signed out**: a plain link (no HTMX) styled like the not-saved state.
  It points to the sign-in page with `next` set to the product URL plus
  `?wishlist=1`.

The add endpoint returns the partial in its saved state, and the remove
endpoint returns it in its not-saved state. When a signed-in customer views
an unsaved product with `wishlist=1` in the querystring, a short hint
beneath the button prompts them to click Save. The hint is template logic
only. The flag is display-only, so the view does not change for it and a
GET never changes data.

### Acceptance criteria

- [ ] `Wishlist.for_user` creates a user's wishlist on first call and
      returns the same one afterward; one wishlist per user (tested).
- [ ] `add` is idempotent (saving twice leaves one item), `remove` is
      idempotent (removing an unsaved product is a no-op), and `contains`
      reports correctly (tested).
- [ ] Deleting a product removes it from every wishlist; deleting a user
      deletes their wishlist (tested).
- [ ] The add and remove endpoints require sign-in, reject GET, and return
      the button partial in the right state with the matching
      `aria-pressed` (tested).
- [ ] Repeating an add, or removing a product that isn't saved, never
      flips the state the opposite way (tested).
- [ ] An unavailable product can be saved (tested).
- [ ] The detail page renders each of the three button states correctly
      (tested).
- [ ] The signed-out link's `next` returns to the product with
      `wishlist=1` (tested).
- [ ] The hint appears only for a signed-in user on an unsaved product
      with `wishlist=1`, never for visitors or saved products, and the GET
      creates no wishlist items (tested).
- [ ] Add to cart remains the detail page's only `btn-primary`.
- [ ] Superusers can inspect wishlists and their items in the Django
      admin.

---

## Phase 2: The Wishlist page

**User stories**: 9, 10, 11, 12, 13, 14, 15, 16, 19

### What to build

The customer's own Wishlist page at `/wishlist/`, reached from a plain
"Wishlist" `btn-ghost btn-sm` navbar link shown to signed-in users
alongside Orders, Addresses, and Security. The page renders a contents
partial built from `lines()`, newest saved first. Each row shows:

- the product image (via the product's display-image properties)
- the name, linking to the detail page
- the price
- an Unavailable badge where it applies
- the existing add-to-cart partial, unchanged
- an HTMX Remove button

The add-to-cart partial gets its cart quantities from the orders context
processor that already runs site-wide. Unavailable products automatically
get the partial's disabled state. Adding to the cart leaves the product on
the wishlist.

Remove posts to the item endpoint, which looks the item up through its
owner and deletes it. It then re-renders the whole contents partial,
mirroring the cart's line-action views, so the designed empty state
appears when the last item goes. The empty state links back to the
catalog.

The `seed` command clears wishlists in its wipe step. A dedicated step
after the customer's cart saves three or four products for the demo
`customer`, including at least one unavailable product and one already in
the seeded cart. The seed summary line mentions the wishlist.

### Acceptance criteria

- [ ] The Wishlist page requires sign-in and lists only the requester's
      items, newest first (tested).
- [ ] Each row shows the image, linked name, and price; unavailable
      products show the Unavailable badge and the cart partial's disabled
      state (tested).
- [ ] Adding a saved product to the cart from the page leaves it on the
      wishlist (tested).
- [ ] An empty wishlist renders the empty state with a catalog link
      (tested).
- [ ] The item remove endpoint requires sign-in, removes the item, and
      re-renders the contents partial; removing the last item renders the
      empty state (tested).
- [ ] Another customer's item pk 404s and their item is left untouched
      (tested).
- [ ] The navbar shows the Wishlist link to signed-in users only, with no
      count badge.
- [ ] After `seed`, the demo `customer` has a wishlist that includes an
      unavailable product and a product in their cart (tested), and the
      summary line mentions it.
- [ ] Re-running `seed` stays idempotent.
