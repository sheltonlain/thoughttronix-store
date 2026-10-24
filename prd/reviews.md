# PRD: The ThoughtTronix Store — Customer Reviews

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

---

## Problem Statement

Customers deciding whether to buy a ThoughtTronix product have only our word to go on: the tagline, the description, and whatever the legal team let through. They can't see what people who actually own the product think of it. That's a problem when the product has side effects, or when it was recalled following the incidents.

Customers who *have* bought something have nowhere to say how it went. Staff have no way to deal with a review that's abusive, off-topic, or wrong, because reviews don't exist yet.

## Solution

Every product's detail page gets a **Reviews** section: a summary of the average star rating and review count, followed by the reviews themselves. A customer who has received the product (a delivered order containing it) can leave one review: a 1–5 star rating and a written comment. They can later edit or delete it. Everything happens in place, with no full page reload, and the customer's own review always sits in a fixed spot at the top of the section, so they never lose their place.

Eligibility belongs to the account that bought the product. A SoulSear owner can review their SoulSear; their next of kin cannot.

People who can't review see a short message explaining why: sign in, wait for delivery, or "only customers who've received this product can review it."

Staff can edit or delete any review inline on the product page, and a new back-office **Reviews** tab lists every review for moderation, with a star-rating filter and in-place delete. When staff edit a customer's words, the review is marked "Edited by staff," so readers always know.

## User Stories

**Visitor (not signed in)**

1. As a visitor, I can read a product's reviews and see its average rating and review count, so that I can learn what owners think before I buy.
2. As a visitor, I see a "Sign in to review" link in the reviews section that brings me back to the same product after signing in, so that I know reviews are possible and don't lose my place.

**Customer (signed in)**

3. As a customer who has a delivered order containing a product, I see a review form at the top of that product's reviews section, so that I can share my experience.
4. As a customer, I pick my rating by clicking one of five stars, so that rating feels like a star rating rather than a number field.
5. As a customer, I must choose a rating and write a non-blank comment of up to 2,000 characters; if I don't, errors appear beside the fields and everything I entered is preserved, so that I can fix mistakes without retyping.
6. As a customer, submitting my review shows it in place at the top of the reviews section, along with the updated average and count, without a full page reload, so that I don't lose my place.
7. As a customer, I can leave only one review per product; if I submit the form a second time (a double-click or a stale second tab), nothing is overwritten and I see my existing review with a note that I've already reviewed this product, so that a stale form can never change my review.
8. As a customer, I can edit my review in place: the form replaces my review card, Save puts the updated card back, and Cancel restores it unchanged, all without a page reload or the page moving, so that editing is quick and I keep my place.
9. As a customer, I can delete my review after confirming, and the section updates in place (the form returns, since I'm still eligible), so that I can take back what I said.
10. As a customer, I can never edit or delete another customer's review; no button or URL lets me, so that reviews can be trusted.
11. As a customer whose order containing the product has not been delivered yet, I see "You can review this once your order is delivered," so that I know the form will appear and the feature isn't broken.
12. As a customer who has never bought the product, I see "Only customers who've received this product can review it," so that I understand why there's no form.
13. As a customer, I can review a product even if it's currently unavailable, as long as I received it, so that past buyers of discontinued or recalled products can still speak.
14. As a customer, my review stays mine even if my order's status later changes, so that a back-office status edit never silently erases what I wrote.
15. As a customer, my review shows my first name and last initial (or my username if I have no first name), never my full name, so that my identity stays reasonably private.
16. As a customer, every review shows a "Verified purchase" badge, so that I know reviews come only from real buyers.
17. As a customer, a review that has been changed since it was posted shows "Edited," and one last changed by staff shows "Edited by staff," so that I know whose words I'm reading.
18. As a customer, if the review I'm editing or deleting was already removed (for example by staff in another tab), the section refreshes to the current state, with a note that the review no longer exists when I was editing, so that I'm never stuck on a dead form.

**SoulSear owners and their families**

19. As a SoulSear owner with a delivered order, I can review my SoulSear like any other product, so that Defense customers have a voice too.
20. As the next of kin of a SoulSear owner, I cannot review the SoulSear from my own account, because eligibility belongs to the account that bought the product.

**Staff and admins**

21. As a staff member, I see Edit and Delete on every review on every product page, and they work in place exactly as they do for authors, so that I can moderate where I see a problem.
22. As a staff member, I cannot write a review for a product I haven't received; I see the same "only customers who've received this product" message as anyone else, so that staff status doesn't bypass the purchase rule.
23. As a staff member, when I edit a customer's review it is marked "Edited by staff"; if the author edits it again afterward, that mark clears, so that readers know whose words they are reading.
24. As a staff member, I can open a **Reviews** tab in the back office that lists every review, newest first, with its product (linked to the product page), author, stars, a comment excerpt, and date, so that I can moderate without browsing product by product.
25. As a staff member, I can filter the Reviews tab by star rating, so that I can find, for example, every 1-star review in one click.
26. As a staff member, I can delete a review from the Reviews tab after confirming, and the list updates in place, so that I can clear spam quickly.
27. As a staff member, an empty Reviews tab (or an empty filter result) shows a designed empty state, so that it never looks broken.
28. As a superuser, I can inspect reviews in the Django admin, so that I can diagnose customer issues.

**Developers and reviewers**

29. As a developer or reviewer, after running `seed` I can sign in as the demo `customer` and see every reviews state: a product I've reviewed (DreamWeaver), delivered products I can still review (MindSync, SyncRest), and products awaiting delivery (Seraphine Mini, Veil), so that the feature can be demonstrated without setup.
30. As a developer or reviewer, seeded products show reviews from background customers, including one marked "Edited by staff," so that the list, summary, and labels can be demonstrated.

## Implementation Decisions

**New app**

- A new `reviews` Django app owns the feature: model, manager, forms, views, URLs, templates, admin, and tests. URLs are mounted under `/reviews/` with the `reviews` namespace; templates live in the project-level `templates/reviews/` directory, with HTMX partials underscore-prefixed in `partials/` per FRONTEND.md.
- Dependencies point one way: `reviews` imports from `products`, `orders`, and `accounts`. The only reverse touchpoints are the product detail view (which adds the reviews context) and the detail template (which includes the reviews section partial), the same way they include the wishlist button. The back-office tab rail gains a Reviews tab.

**Model**

- `Review`: foreign keys to the user and the product (both cascade: deleting a product or user deletes their reviews), `rating`, `comment`, `created_at`, `updated_at`, and an `edited_by_staff` boolean.
- `rating` is a small positive integer, 1–5, with min/max validators *and* a database check constraint, so invalid ratings can't be stored by any path.
- `comment` is a required text field, maximum 2,000 characters; leading and trailing whitespace is stripped, so whitespace-only comments are rejected.
- A `UniqueConstraint` on user–product enforces one review per customer per product.
- Default ordering is newest `created_at` first. Edits never change a review's position.

**Logic in the model and manager, not the views**

- An eligibility method on the review manager takes a user and a product and returns one named state: *signed out*, *already reviewed*, *can review*, *awaiting delivery*, or *not a buyer*. *Can review* means the user has an order with status Delivered containing the product (through order items). *Awaiting delivery* means they have a Placed or Shipped order containing it. Cancelled orders never count. Product availability is ignored. Staff get no exemption.
- Eligibility is checked only when a review is created. Later order status changes (which the back office allows in any direction) never touch existing reviews.
- A create method on the manager re-checks eligibility and creates the review. If a review already exists for the pair, including when a concurrent insert hits the unique constraint, it returns the existing review and signals that it was a duplicate. The `IntegrityError` never reaches the view.
- A `revise(rating, comment, by)` method on `Review` applies an edit and sets `edited_by_staff` to whether `by` is someone other than the author. An author's own edit clears the flag.
- A permission method on `Review` answers whether a given user may change it: the author, or any staff member. A matching queryset method returns the reviews a user may change (their own, or all of them for staff). Edit and delete lookups go through it.
- A `public_name` method on the `User` model returns first name plus last initial ("Casey M."), falling back to the username when the first name is blank. The product page and the back-office list both use it.
- A summary (average rating and count) for a product comes from a single aggregate query.

**Form and star widget**

- A model form owns rating and comment validation. Errors appear beside their fields and entered values are preserved, matching checkout.
- The rating uses a radio-select widget with a custom widget template rendering DaisyUI's `rating` component (five `mask-star` radios, each with an `aria-label` such as "3 stars"). There's no default selection; a missing rating is a normal field error. The same component, read-only, displays stars on review cards and in the summary.

**Product detail page**

- `ProductDetailView` adds the reviews context: the summary, the viewer's eligibility state, the viewer's own review (if any), and the other reviews.
- The reviews section is a single partial containing:
  - **Summary:** average stars and count, or "No reviews yet."
  - **Pinned slot:** depending on eligibility, the create form, the viewer's own review card, or a message: "Sign in to review" (a link to sign-in with `next` set to the product URL), "You can review this once your order is delivered," or "Only customers who've received this product can review it" (also shown to staff who haven't bought the product).
  - **List:** everyone else's reviews, newest first by creation time, with no pagination.
- Each review card shows read-only stars, the author's public name, the date, the comment (auto-escaped, line breaks preserved), a "Verified purchase" badge, and "Edited" (when `updated_at` is later than `created_at`) or "Edited by staff." Edit and Delete buttons appear only for users permitted to change that review.
- The reviews section adds no `btn-primary`: Add to cart remains the page's single primary action. Review submit, Edit, Save, Cancel, and Delete use outline or ghost styles.

**Endpoints and HTMX swaps**

- Every endpoint requires sign-in and stays thin: it calls the manager or model methods and renders a partial.
- **Create** (POST, keyed by product): re-checks eligibility on the server. On success, or on a duplicate, it re-renders the whole reviews section; a duplicate shows an "already reviewed" note in the pinned slot. On invalid input it re-renders the section with the form and its errors. An ineligible user gets a 403.
- **Edit form** (GET, keyed by review): swaps only that review's card for the edit form.
- **Cancel edit** (GET, keyed by review): swaps the form back to the unchanged card.
- **Save edit** (POST, keyed by review): validates, calls `revise`, and re-renders the whole section, since the summary may change. On invalid input it re-renders only the card-sized form with errors.
- **Delete** (POST, keyed by review): guarded by HTMX's `hx-confirm` (an HTMX attribute, not custom JavaScript), deletes the review, and re-renders the whole section.
- Re-rendering the whole section on every save-type action keeps the summary, empty state, pinned slot, and list consistent from one partial, with no out-of-band swaps. Because the list's order never changes on edit, the page doesn't jump.
- **Reviews that are missing or not yours:** edit, save, and delete look the review up through the "reviews this user may change" queryset first.
  - Found there: proceed.
  - Exists but belongs to someone else: **404**.
  - Doesn't exist at all: return 200 with a freshly rendered section. Delete treats this as already done (idempotent); edit and save add a "That review no longer exists" note. Reviews are public, so confirming that a pk is gone leaks nothing.
- No `django.contrib.messages` for any review action. Inline swaps carry their own feedback, per the PRD messages convention.

**Back office**

- A new **Reviews** tab in the staff shell, visible to and gated on all staff (`StaffRequiredMixin`). No new permission: the requirement gives every staff member and admin moderation rights.
- The list shows every review newest first: product name linking to the public product page, author's public name, stars, a comment excerpt, date, and edited status, plus a `?rating=` querystring filter using the same pattern as Orders' `?status=` filter.
- Each row has an HTMX Delete (with `hx-confirm`) that re-renders the list contents partial, so the empty state appears automatically. Deleting a review that's already gone just re-renders.
- No back-office edit screen. Editing happens inline on the product page, so there's one edit form in the codebase.
- A designed empty state covers both "no reviews yet" and "no reviews match this filter."

**Admin**

- `Review` is registered in the Django admin with list display, search, and a rating filter.

**Seed**

- The wipe step clears reviews. A new step after orders creates reviews:
  - Background customers' reviews are generated only from their **delivered** order lines, with a seeded RNG so every run is identical, and with ratings and comments drawn from a fixed pool of in-world review text.
  - The demo `customer` gets one review, on DreamWeaver. MindSync and SyncRest stay unreviewed so the create form shows; Seraphine Mini and Veil show "awaiting delivery."
  - One background review is marked edited by staff.
- No Defense or SoulSear orders are added. The seed's existing reasoning holds (a single SoulSear sale would flatten the dashboard's revenue chart). The SoulSear rule is proven in tests instead.
- The summary line reports the number of seeded reviews.

**Testing**

- pytest with the shared project-level fixtures, no factory-boy, green at every phase boundary.
- **Model and manager:**
  - each eligibility state (signed out, not a buyer, awaiting delivery for both Placed and Shipped, cancelled order doesn't count, can review, already reviewed)
  - an unavailable product is reviewable by a delivered buyer
  - staff get no exemption
  - a later status change leaves the review in place
  - unique constraint
  - rating check constraint
  - duplicate create returns the existing review without modifying it
  - `revise` sets and clears `edited_by_staff`
  - permission method and queryset for author, other customer, and staff
  - summary aggregate
  - cascade on product and user deletion
  - `public_name` with and without a first name
- **SoulSear:** a delivered buyer of SoulSear Mark II can review it; a different user (the "next of kin") cannot, even though they share an address with the buyer.
- **Views:**
  - sign-in required on every endpoint
  - create succeeds and re-renders the section; invalid input shows field errors and preserves input; an ineligible user is refused
  - edit and cancel swap the card
  - save re-renders the section and sets "Edited" or "Edited by staff"
  - delete re-renders the section
  - another user's review 404s for edit, save, and delete
  - staff can edit and delete any review
  - missing reviews behave as specified
- **Detail page:** every pinned-slot state; summary and empty state; Edit and Delete appear only when permitted; still exactly one `btn-primary`.
- **Back office:** staff-only gating; list contents and ordering; rating filter; HTMX delete; both empty states; the tab appears in the rail.
- **Seed:** reviews exist; every seeded review's author had a delivered order containing its product; the demo customer's expected review state per product; exactly one staff-edited review.

## Out of Scope

- Average stars or review counts on catalog and category cards: detail page only.
- Pagination or "load more" for reviews.
- A back-office edit screen for reviews (editing is inline on the product page).
- Review analytics on the staff dashboard.
- Revoking or hiding reviews automatically when an order is cancelled or moved out of Delivered (staff can delete such reviews by hand).
- A "next of kin," household, or shared-account model.
- Staff replies to reviews, helpful/unhelpful voting, review photos, and reporting or flagging by customers.
- Notifying customers when staff edit or delete their review.
- A global HTMX configuration for swapping 4xx responses.
- Half-star ratings.

## Further Notes

- **Known limitation: expired session on HTMX POST.** As with the cart and wishlist, if a session expires while the page is open, the login redirect is swapped into the target element. This stays covered by the existing project-wide follow-up (an HTMX-aware login mixin that responds with `HX-Redirect`) rather than being fixed here alone.
- The design mirrors existing, reviewed patterns:
  - owner-scoped lookups from cart lines and wishlist items
  - the whole-contents re-render from the wishlist page
  - the signed-out `next` link from the wishlist button
  - the querystring status filter from back-office Orders
  - the custom widget template precedent from the product image input
- Eligibility is computed from data that already exists (orders and their items); no fields are added to orders or products.
- Visual language stays Tailwind + DaisyUI (`night` theme), with no JavaScript beyond HTMX.
