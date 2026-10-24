# Plan: Customer Reviews

> Source PRD: `prd/reviews.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: a new `reviews` app owns the model, manager, forms, views,
  URLs, admin, and tests. Templates live in `templates/reviews/`, with HTMX
  partials underscore-prefixed in `templates/reviews/partials/` per
  FRONTEND.md. Dependencies point one way: `reviews` imports from
  `products`, `orders`, and `accounts`. The only reverse touchpoints are
  `ProductDetailView` (which adds the reviews context), the detail template
  (which includes the reviews-section partial, like the wishlist button),
  and the back-office tab rail.
- **URLs** (all named under the `reviews:` namespace). The app is mounted
  at the root, like `orders` and `coupons`, so its back-office page can sit
  at `/backoffice/reviews/` beside the other tabs. Customer-facing
  endpoints carry a `reviews/` prefix in the app's own `urls.py`. This
  departs from the PRD's literal "mounted under `/reviews/`", and the user
  approved it. Back-office URLs use pks; HTMX endpoints are keyed by pk.
  - `reviews/product/<int:pk>/create/`: create, keyed by product pk (HTMX
    POST)
  - `reviews/<int:pk>/edit/`: GET swaps the card for the edit form; POST
    saves the edit
  - `reviews/<int:pk>/card/`: cancel edit, which swaps the unchanged card
    back (HTMX GET)
  - `reviews/<int:pk>/delete/`: delete from the product page (HTMX POST)
  - `backoffice/reviews/`: the back-office Reviews tab, with a `?rating=`
    filter
  - `backoffice/reviews/<int:pk>/delete/`: delete from the back-office list
    (HTMX POST)
- **Models**:
  - `Review`: FK to `accounts.User` and FK to `products.Product` (both
    cascade), `rating` (small positive integer with 1–5 min/max validators
    *and* a database check constraint), `comment` (required, max 2,000
    characters, whitespace stripped), `created_at`, `updated_at`, and an
    `edited_by_staff` boolean. A `UniqueConstraint` covers user–product.
    Default ordering is `-created_at`, so edits never move a review.
  - `User.public_name()` on `accounts.User`: first name plus last initial
    ("Casey M."), falling back to the username.
  - No fields are added to orders or products. Eligibility is derived from
    existing `Order` / `OrderItem` data.
- **Logic location**: the review manager owns eligibility (one named state:
  *signed out*, *already reviewed*, *can review*, *awaiting delivery*, *not
  a buyer*), the product summary (one aggregate query), and the
  duplicate-safe create. `Review` owns `revise(rating, comment, by)` and
  the "may this user change it" check, and a matching queryset method
  returns the reviews a user may change. Views stay thin.
- **Eligibility rules**: *can review* means a Delivered order containing
  the product. *Awaiting delivery* means a Placed or Shipped order
  containing it. Cancelled orders never count, availability is ignored,
  and staff get no exemption. Eligibility is checked only at creation;
  later order status changes never touch a review.
- **Auth**: every review endpoint uses `LoginRequiredMixin`. Edit, save,
  and delete look the review up through the "reviews this user may change"
  queryset. Someone else's review gets a 404. A review that no longer
  exists gets a freshly rendered section with a 200. The back-office tab
  uses `StaffRequiredMixin`, with no new permission.
- **Responses**: create, save, and delete re-render the whole reviews
  section. Edit and cancel swap one card. There are no out-of-band swaps
  and no `django.contrib.messages`; inline swaps carry their own notes.
  Deletes use `hx-confirm`.
- **Frontend**: Tailwind + DaisyUI (`night` theme), no JavaScript beyond
  HTMX. Stars use DaisyUI's `rating` component (`mask-star` radios with
  `aria-label`s), through a custom radio-select widget template for input
  and the same markup read-only for display. On the detail page, Add to
  cart stays the only `btn-primary`; every review button is outline or
  ghost.
- **Testing**: pytest with the shared project-level fixtures in
  `conftest.py`, per `docs/TESTING.md`, and no factory-boy. The suite is
  green at every phase boundary.
- **Known limitation, not fixed here**: an expired session on an HTMX POST
  swaps the login page into the target, as with the cart and wishlist.
  This stays on the project-wide follow-up (an HTMX-aware login mixin that
  answers with `HX-Redirect`).

---

## Phase 1: Read-only reviews section and seeded reviews

**User stories**: 1, 2, 11, 12, 15, 16, 17 (label display), 20, 22, 28,
29, 30

### What to build

Everything a reader sees, built on seeded data so it can be demoed right
away. Create the `reviews` app with the `Review` model, its constraints,
and its migration. Add the manager's eligibility state and product
summary, plus `User.public_name`. Register `Review` in the Django admin
with list display, search, and a rating filter. Mount the app's URLs (no
endpoints yet, apart from what the section needs to render).

`ProductDetailView` adds the reviews context: the summary, the viewer's
eligibility state, the viewer's own review (if any), and the other
reviews. The detail template includes a single reviews-section partial:

- **Summary**: read-only average stars and the review count, or "No
  reviews yet."
- **Pinned slot**:
  - *already reviewed*: the viewer's own review card
  - *signed out*: a "Sign in to review" link with `next` set to the product
    URL
  - *awaiting delivery*: "You can review this once your order is delivered"
  - *not a buyer* (including staff who haven't bought the product): "Only
    customers who've received this product can review it"
  - *can review*: a placeholder until Phase 2 adds the form
- **List**: everyone else's reviews, newest first by creation time, with no
  pagination.

Each review card shows read-only stars, the author's public name, the
date, the comment (auto-escaped, with line breaks preserved), a "Verified
purchase" badge, and either "Edited" (when `updated_at` is later than
`created_at`) or "Edited by staff."

The `seed` command clears reviews in its wipe step. A new step after
orders does three things:

- generates background customers' reviews from their **delivered** order
  lines only, using a seeded RNG and a fixed pool of in-world ratings and
  comments
- gives the demo `customer` one review, on DreamWeaver
- marks one background review as edited by staff

The summary line reports the number of seeded reviews.

### Acceptance criteria

- [x] Each eligibility state is returned correctly (tested): signed out,
      not a buyer, awaiting delivery for both Placed and Shipped, a
      cancelled order doesn't count, can review, and already reviewed.
- [x] An unavailable product is reviewable by a delivered buyer, and staff
      get no exemption (tested).
- [x] Moving a delivered order to another status leaves an existing review
      in place (tested).
- [x] The unique constraint and the rating check constraint reject bad rows
      at the database level (tested).
- [x] The summary aggregate returns the right average and count, including
      for a product with no reviews (tested).
- [x] Deleting a product or a user deletes their reviews (tested).
- [x] `public_name` returns "First L." and falls back to the username
      (tested).
- [x] SoulSear: a delivered buyer of SoulSear Mark II is eligible, and a
      different user at the same address is not (tested).
- [x] The detail page renders every pinned-slot message, the viewer's own
      card, the summary, and "No reviews yet" (tested).
- [x] Cards show the public name, "Verified purchase", and the "Edited" /
      "Edited by staff" labels correctly (tested).
- [x] The "Sign in to review" link's `next` returns to the product
      (tested).
- [x] Add to cart remains the detail page's only `btn-primary` (tested).
- [x] After `seed`, reviews exist. Every seeded author had a delivered
      order containing the product. Exactly one review is staff-edited.
      The demo `customer` has reviewed DreamWeaver, can review MindSync and
      SyncRest, and is awaiting delivery on Seraphine Mini and Veil
      (tested).
- [x] Re-running `seed` stays idempotent, and the summary line mentions
      reviews.
- [x] Superusers can inspect reviews in the Django admin.

---

## Phase 2: Writing a review

**User stories**: 3, 4, 5, 6, 7, 13, 19

### What to build

The create path, end to end. A model form owns rating and comment
validation: a required rating, and a non-blank comment of up to 2,000
characters after stripping. Its rating field uses a radio-select widget
with a custom widget template that renders DaisyUI's `rating` component:
five `mask-star` radios, each with an `aria-label` such as "3 stars", and
no default selection.

In the *can review* state, the pinned slot shows this form, using outline
or ghost buttons only. It submits by HTMX POST to the create endpoint and
targets the whole reviews section.

The manager's create method re-checks eligibility and creates the review.
If a review already exists for the pair, including when a concurrent
insert hits the unique constraint, it returns the existing review
unchanged and signals a duplicate. The `IntegrityError` never reaches the
view. The thin create view handles each outcome:

- **success**: re-renders the section, with the new card in the pinned
  slot and the updated summary
- **duplicate**: re-renders the section with the existing card and an
  "already reviewed" note
- **invalid input**: re-renders the section with the form, its field
  errors, and the entered values
- **ineligible user**: 403

### Acceptance criteria

- [x] The create endpoint requires sign-in and rejects GET (tested).
- [x] A delivered buyer's valid submission creates the review and
      re-renders the section with their card pinned and the summary
      updated (tested).
- [x] A missing rating and a blank or whitespace-only comment show errors
      beside their fields with the entered values preserved, and a comment
      over 2,000 characters is rejected (tested).
- [x] A duplicate submission leaves the existing review untouched and shows
      the "already reviewed" note (tested at the manager and view levels).
- [x] Signed-in users who are not buyers, are awaiting delivery, or are
      staff who haven't bought the product all get a 403 and create
      nothing (tested).
- [x] A delivered buyer can review an unavailable product, and a SoulSear
      Mark II buyer can review it through the endpoint (tested).
- [x] The star widget renders five labelled radios with none checked
      (tested).
- [x] Add to cart remains the detail page's only `btn-primary`.
- [x] As the seeded `customer`, MindSync's form submits in place without a
      page reload.

---

## Phase 3: Editing and deleting reviews (authors and staff)

**User stories**: 8, 9, 10, 14, 17, 18, 21, 23

### What to build

In-place edit and delete for anyone permitted to change a review: its
author, or any staff member. `Review` gains the permission method, the
matching queryset method (own reviews, or every review for staff), and
`revise(rating, comment, by)`. `revise` sets `edited_by_staff` when `by`
is not the author and clears it when the author edits.

Cards show Edit and Delete only to permitted users, which means staff see
them on every card on every product page. The endpoints are:

- **Edit form** (GET): swaps only that card for the review form, prefilled.
- **Cancel** (GET): swaps the form back to the unchanged card.
- **Save** (POST): validates and calls `revise`, then re-renders the whole
  section, since the summary may change. On invalid input it re-renders
  only the card-sized form with errors.
- **Delete** (POST, behind `hx-confirm`): deletes the review and
  re-renders the whole section. When the author deletes their own review,
  the create form returns to the pinned slot, since they are still
  eligible.

Every lookup goes through the "may change" queryset first:

- **found there**: proceed
- **exists but belongs to someone else**: 404
- **doesn't exist at all**: 200 with a freshly rendered section. Delete
  treats this as already done; edit and save add a "That review no longer
  exists" note.

### Acceptance criteria

- [ ] The edit, cancel, save, and delete endpoints require sign-in, and
      save and delete reject GET (tested).
- [ ] The permission method and the queryset answer correctly for the
      author, another customer, and staff (tested).
- [ ] `revise` sets `edited_by_staff` for a staff edit and clears it on a
      later author edit (tested).
- [ ] Edit swaps in a prefilled form and cancel restores the unchanged
      card (tested).
- [ ] Save re-renders the section showing "Edited" after an author edit
      and "Edited by staff" after a staff edit, and the list order is
      unchanged (tested).
- [ ] An invalid save re-renders only the form with errors and changes
      nothing (tested).
- [ ] Delete re-renders the section, and the author sees the create form
      again (tested).
- [ ] Another customer's review 404s for edit, cancel, save, and delete,
      and is left untouched (tested).
- [ ] Staff can edit and delete any review (tested).
- [ ] A review that no longer exists re-renders the section, with the "no
      longer exists" note for edit and save, and with no error for delete
      (tested).
- [ ] Edit and Delete appear only on cards the viewer may change (tested).
- [ ] Add to cart remains the detail page's only `btn-primary` (tested).
- [ ] In the browser, editing and cancelling don't move the page, and
      Delete asks for confirmation first.

---

## Phase 4: Back-office Reviews tab

**User stories**: 24, 25, 26, 27

### What to build

A **Reviews** tab in the staff shell's rail, visible to all staff, at
`/backoffice/reviews/`, gated by `StaffRequiredMixin`, with
`section = "reviews"`. The page renders a list-contents partial of every
review, newest first. Each row shows:

- the product name, linking to the public product page
- the author's public name
- read-only stars
- a comment excerpt
- the date
- the edited status

A `?rating=` querystring filter follows the Orders tab's `?status=`
pattern. Each row has an HTMX Delete (behind `hx-confirm`) that posts to
the back-office delete endpoint. The endpoint re-renders the list-contents
partial with the active filter preserved, so the empty state appears
automatically. Deleting a review that's already gone just re-renders.

A designed empty state covers both "no reviews yet" and "no reviews match
this filter." The back office has no edit screen; editing stays inline on
the product page.

### Acceptance criteria

- [ ] The tab and its delete endpoint are staff-only: visitors are sent to
      sign in and customers are refused (tested).
- [ ] The tab appears in the back-office rail for staff and is active on
      this page (tested).
- [ ] The list shows every review newest first, with the product link,
      public name, stars, excerpt, and date (tested).
- [ ] `?rating=N` shows only N-star reviews, and an invalid value falls
      back to all reviews (tested).
- [ ] HTMX delete removes the review and re-renders the list with the
      filter kept, and deleting a missing review just re-renders (tested).
- [ ] Both empty states render: no reviews at all, and no match for the
      filter (tested).
- [ ] After `seed`, filtering to 1-star reviews and deleting one works in
      the browser without a page reload.
