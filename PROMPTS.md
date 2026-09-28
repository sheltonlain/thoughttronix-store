# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-09-28 — Promotional coupon codes: design interview, tests first, build, and ship

The session began on 2026-09-27 and ran into 2026-09-28.

### Prompts

1. `/grill-me` with: "We want to implement promotional coupon codes to the
   ThoughtTronix store. The customer will have the option to type in a
   coupon code when they check out, and they will see the price of their
   cart drop. The code will expire when the promotion ends. If a customer
   types in an expired code, they should see a message saying that the
   code is expired. We do not want them to see a broken page,a server
   error, a blank page, or an opportunity for the customer to contact
   Legal. Our marketing department should have the power to write the
   coupon codes themselves and set when they retire without having to
   file a support ticket. The coupon system must support both order-wide
   discounts and discounts limited to specific products, such as 50% off
   Seraphine for a limited time."
2. (Q1, who manages coupons) "Can we go with option A and implement the
   permission check for marketing that you mentioned we could add later?"
3. (Q1b, how Marketing is identified) "Yes, go with A"
4. (Q2, discount kinds) "Go with c"
5. (Q3, fixed amount per order or per unit) "a"
6. (Q4, choosing covered products) "a"
7. (Q5, a coupon's lifetime) "c"
8. (Q6, usage limits) "c"
9. (Q7, how a code is applied) "b"
10. (Q8, a code gone bad before "Place order") "a"
11. (Q9, what an order records) "b"
12. (Q10, code uniqueness and reuse) "c"
13. (Q11, editing after use) "b"
14. (Q12, minimum spend) "b"
15. (Q13, where the code lives) "b"
16. (Q14, the Coupons tab) "Let's go with your recommendation of b with
    the usage summary"
17. (Q15, demo seed data) "c"
18. "First, I want us to add some tests for the new code that we will be
    implementing"
19. "Implement the code we discussed"
20. "How can i manually verify the features in the browser?"
21. "commit and push the feature"
22. "merge it into main and push"
23. "delete the feature branch"
24. "In the checkout screen, can you make the words \"Have a coupon code?\"
    written in blue so they stand out more?"
25. "Can you make the apply button appear blue as well?"
26. "commit and push the changes with a message saying what changed"
27. "Add our session log to PROMPTS.md"

### Summary

- **Outcome:**
  - **Design interview (15 questions + one follow-up).** Before asking
    anything, the codebase was read: `place_order`'s dormant
    `coupon_code` seam and the Top Products query were found there.
    Settled:
    - **Access:** a Coupons tab gated on `is_staff` plus a
      `coupons.manage_coupons` permission granted per user (no Groups).
    - **Discounts:** percent or fixed; a fixed amount comes off once per
      order; a hand-picked product list, where empty means order-wide;
      an optional minimum spend over covered products.
    - **Lifetime and limits:** an Active switch, a start, and a required
      end; per-customer (default 1) and total use limits.
    - **Codes:** unique among unarchived coupons, so archiving frees a
      code; a used coupon's terms are locked.
    - **Checkout:** an HTMX Apply preview, and a code gone bad before
      "Place order" blocks the order.
    - **Orders and dashboard:** the discount is snapshotted on the order
      and split across its lines; Top Products subtracts it.
    - **Structure and seed:** a new `coupons` app with its rules on the
      model; seed coupons in every state, plus historical orders that
      used one.
  - **Tests first:** 79 tests (counting parametrized cases) across three
    new files
    (`coupons/test_models.py`, `coupons/test_backoffice.py`,
    `orders/test_coupon_checkout.py`) and one dashboard test. They pinned
    the interface names, the message wording, and the cent-exact
    arithmetic. The old "seam is accepted and ignored" test was removed.
  - **Build:**
    - **`coupons` app:** `Coupon.objects.for_code()`,
      `coupon.evaluate()`, `split_discount()`, status and summary, plus
      the Coupons tab with list, filters, create, edit, archive, restore
      and delete.
    - **Checkout:** `CouponManagerRequiredMixin`; `place_order` locks and
      re-checks the coupon; an Apply endpoint with an order-summary
      partial and an out-of-band total on the Place-order button.
    - **Pages and data:** coupon lines on the order pages; migrations
      `coupons/0001` and `orders/0003`; the seed gains a `marketing`
      login, five coupons, and 10 SPRING-SALE orders (one per customer).
    - **Docs:** README and CLAUDE.md updated.
    - **Checks:** suite green at 318 passed and ruff clean. The seed was
      run twice against a scratch database: the output was identical
      and every coupon landed in its intended state.
  - **Shipped:** committed as `e0e12dd` on a `feature/coupons` branch,
    pushed, fast-forwarded into `main`, pushed, and the branch deleted
    locally and on GitHub. A follow-up made "Have a coupon code?" blue
    and semibold (`text-primary`) and the Apply button `btn-primary`,
    committed as `9de13fc` and pushed to `main`.
- **Deviations:**
  - **Q1:** took option A but also asked for the Marketing permission
    check that had been offered only as a later add-on, which needed a
    follow-up question (Q1b).
  - **Q2:** chose both discount types (C) over the recommended
    percent-only (A), which opened Q3 (per order vs per unit).
  - **Q10:** chose "archiving frees a code" (C) over the recommended
    "unique forever" (A), which reshaped the uniqueness rule, the
    expired message for archived codes, and restore.
  - **Every other answer took the recommendation.**
  - **Asked for tests before implementation** rather than taking the
    offered next step of writing `prd/coupons.md` and `plans/coupons.md`.
    Those docs were never written.
  - **Asked how to verify the feature in the browser;** a five-part
    walkthrough was given.
  - **Asked to merge into `main`** after the first push went to a
    feature branch.
- **Sideways:**
  - **Suite couldn't run until the build.** While only the tests
    existed, their import errors made a plain `pytest` stop at
    collection. This was flagged, with `--continue-on-collection-errors`
    as the workaround.
  - **Two test-writing slips.** One expected discount was written as
    $174.99 when half-up rounding gives $175.00; it was fixed before any
    run. A test file's import order was fixed by ruff.
  - **Duplicate code hit the database.** Duplicate codes reached the
    database as an IntegrityError: a ModelForm skips a conditional
    unique constraint when the condition's field (`is_archived`) isn't
    on the form. The fix was a check in `Coupon.clean()`, with the
    constraint kept as the backstop.
  - **Coupon list pagination warned "unordered".** `Meta.ordering`
    doesn't apply to the list's GROUP BY query; fixed with an explicit
    `order_by`.
  - **A checkout test failed on escaping.** It looked for "don't
    recognize", but Django renders the apostrophe as `&#x27;`. The test
    assertion was changed (not the message).
  - **Ruff DJ012.** It asked for `save()` before `clean()`.
  - **Design adjustments made while building, and reported:**
    `Order.subtotal` became a computed property rather than a stored
    field; archiving also switches a coupon off; restoring leaves it
    off.
  - **Rules the tests pinned without discussion:** half-up rounding; a
    cancelled order gives its use back; "expired" wins over "switched
    off"; `CouponError` subclasses `ValueError`; the exact message
    wording. They were flagged to the user and not revisited.
  - **Not verified in a browser.** The HTMX out-of-band total and the
    `form="checkout-form"` hidden input were never checked in one (a
    manual test plan was given instead). The coupon row lock is
    untested, because SQLite ignores `select_for_update`.
  - **Pre-existing, not fixed.** While checking the seed,
    `total_revenue()` returned long decimals on SQLite (e.g.
    `57391.8500000000`). This predates the feature.

## 2026-09-26 — Saved addresses: manual test plan, shipping, and checkout nicknames (cont.)

Continues the session logged in the entry below, after that entry's log
had already been written.

### Prompts

1. "How do I verify this feature manually in the browser?"
2. "commit these changes"
3. "merge it into main"
4. "push it and delete the branch"
5. "When adding a new address in checkout, I'd like there to be an option
   to add a nickname to the address at that time"
6. "commit and push it"
7. "update PROMPTS.md with this session"

### Summary

- **Outcome:**
  - **Manual test plan:** a browser walkthrough in four parts (returning
    customer, brand-new customer, cross-customer 404s, admin), each step
    with an expected result.
  - **Saved-addresses feature shipped:** committed as `19c2763` on a
    `saved-addresses` branch, fast-forwarded into `main`, pushed to
    `origin/main`, and the branch deleted.
  - **Checkout nicknames:** ticking "Save to my address book" now reveals
    an optional **Nickname (optional)** field for that section. Two new
    optional `CheckoutForm` fields, `save_shipping_label` and
    `save_billing_label` (`max_length=50`, matching `Address.label`), live
    in a new `_save_to_book.html` partial. It shows and hides with
    Tailwind's `group-has-[:checked]:block`, which is CSS `:has()` with no
    JavaScript, and stays visible whenever the field has an error.
    `Address.objects.save_from_checkout` reads the nickname from checkout
    data, so `place_order` only needed a docstring change. 239 passed
    (+9), ruff clean, Tailwind force-rebuilt. Committed as `99be4df`
    through the same branch, fast-forward, push and delete sequence.
- **Deviations:**
  - The nickname request reverses grill-me Q9, where labels were kept
    off checkout. That decision was made to avoid a *required* label's
    conditional validation. An *optional* nickname avoids it, so I
    implemented it without re-asking and explained the difference.
  - One behavior I chose myself and flagged for the user: a nickname
    typed for an address already in the book labels it only if it has
    no label, and never renames one. No answer yet.
  - For "commit these changes" I branched first rather than committing
    straight to `main`, where the user's earlier commits went. The user
    then asked for the merge and push, and I reused that flow for the
    nickname commit.
- **Sideways:** My first check that the new `group-has-[:checked]:block`
  rule had compiled returned nothing, which looked like a build failure.
  The grep pattern escaped the selector wrong. A looser search found
  `.group-has-\[\:checked\]\:block` in `assets/css/tailwind.css`. This is
  the same mistake as in the 2026-09-20 hot-pink entry.

## 2026-09-26 — Saved addresses: grilled design, then address book + checkout reuse

### Prompts

1. `/grill-me` "Customers should be able to save shipping and billing
   addresses to their account and reuse them at checkout." — the skill
   interviews one decision at a time, beginner-level, with options and a
   recommendation for each.
2. Fifteen answers, one per question, each taking the recommended option:
   - Q1 what a saved address is → **a**, one address book usable for either
     purpose
   - Q2 which app → **a**, `accounts/` (and move `US_STATES`/`zip_validator`
     there)
   - Q3 how addresses get saved → **c**, both an address book page and a
     checkout checkbox
   - Q4 who saves at checkout → **c**, `place_order` flags + an `Address`
     manager method
   - Q5 duplicates → **b**, skip exact matches
   - Q6 picking at checkout → **b**, HTMX dropdown that fills in the fields
   - Q7 defaults → **c**, two nullable FKs on `User`
   - Q8 auto-default → **b**, fill empty defaults, never overwrite
   - Q9 identifying addresses → **c**, optional label with fallback
   - Q10 address book CRUD → **a**, full-page generic views like the back
     office
   - Q11 save checkbox initial state → **c**, ticked only when the book is
     empty
   - Q12 navigation → **a**, navbar "Addresses" link
   - Q13 staff visibility → **b**, Django admin only
   - Q14 seed → **b**, "Home" and "Work" for the demo customer
   - Q15 tests → **b**, full coverage in files following the existing layout
3. "You can add the 'billing same as shipping' checkbox as long as it works
   with the code. Go ahead and add what we've talked about to PROMPTS.md,
   but no need to write the other documentation at the moment. Implement
   the changes we discussed."
4. (Rejected my edit to `accounts/admin.py` and the `makemigrations` run.)
   "Can you please explain that code more so I can consider implementing
   it?"
5. "go with option 1 and continue"

### Summary

- **Outcome:** Customers can save addresses and reuse them at checkout.
  - **Model (`accounts/`):** `Address` (owner, optional `label`, the six
    address parts, `created_at`), and `User.default_shipping_address` /
    `default_billing_address` (nullable FKs, `SET_NULL`). Migration
    `accounts/0002_user_addresses.py`, applied. `US_STATES` and
    `zip_validator` moved to `accounts/validators.py`, so the address book
    and checkout share one set of rules. Manager method
    `Address.objects.save_from_checkout` reuses an identical address instead
    of duplicating it. `User.fill_empty_defaults` fills an empty default
    slot and never overwrites one. `address_book(user)` lists defaults
    first, then newest.
  - **Address book (`/accounts/addresses/`):** list with a designed empty
    state, plus add, edit, delete (confirm page), and POST-only
    set-default-shipping and set-default-billing. Every view goes through
    `OwnAddressesMixin`, so another user's address is a 404. "Addresses"
    link in the navbar.
  - **Checkout:** a "Use a saved address" HTMX dropdown per section (hidden
    when the book is empty) swaps in `_address_fields.html` already filled
    in. The page starts filled from the defaults. "Save to my address book"
    checkboxes start ticked only while the book is empty.
    `place_order(..., save_shipping=, save_billing=)` saves addresses
    inside its existing transaction.
  - **"Same as shipping address"** (added in prompt 3, beyond the grilled
    scope): an HTMX toggle swaps the billing card to a note. On submit,
    `CheckoutForm.__init__` copies the shipping values into the billing
    fields before validation, so the form still has no `clean()` and the
    existing "no imperative validation" test still passes.
  - **Admin:** `Address` is view-only in Django admin; the user page shows
    the two defaults read-only.
  - **Seed:** `customer` gets "Home" (both defaults) and "Work", and their
    four orders now ship to Home. The RNG draw still happens, so the rest of
    the demo world is unchanged.
  - **Tests:** suite went from 167 to 230 passed, ruff clean. Tailwind was
    rebuilt with `--force` and the new classes confirmed in the compiled
    CSS.
- **Deviations:** Every grill-me recommendation was taken as offered. The
  user reversed my out-of-scope call on "billing same as shipping" and asked
  for it, on condition it fit the code. They also asked to skip the
  PRD/plan documents I offered. In prompt 4 they stopped an edit to ask what
  it did. After the explanation (three options) they chose option 1, the
  one I suggested.
- **Sideways:**
  - My first `AddressAdmin` made addresses fully read-only, including
    delete. I then realized admin checks delete permission on cascaded rows,
    so no customer with a saved address could have been deleted from admin.
    My fix was rejected pending the explanation above, then approved.
  - One multi-file test edit went through a bash heredoc and failed on a
    quoting error. Nothing had been written, as `git status` confirmed, and
    I redid the edits directly.
  - The local database was migrated but not re-seeded. `seed` is
    destructive, so that is left for the user to run.

## 2026-09-20 — Featured badge: theme accent replaced with literal hot pink (cont.)

Continues the two entries below, each of which had already been logged.

### Prompts

1. "The badge is not really showing up as pink. It should be a hot pink
   color. Please make the changes to do so."
2. "update PROMPTS.md with this session"

### Summary

- **Outcome:** Replaced `badge-accent` with explicit color utilities in both
  templates: `badge border-[#ff69b4] bg-[#ff69b4] text-[#1a1a1a]` in
  `templates/products/catalog.html` and `templates/products/detail.html`.
  Diagnosis: `badge-accent` had compiled correctly all along, but resolves
  to the `night` theme's accent, `oklch(72.36% 0.176 350.048)` ≈ `#f471b5`
  — pink by hue but dusty and desaturated against the dark background.
  The color is now literal hot pink, `#ff69b4`, independent of the theme
  palette. The border is overridden too, since DaisyUI's `.badge` draws one
  from the theme that would otherwise ring the hot pink in the old color.
  Text is near-black, not white: on `#ff69b4` white is ~2.6:1 contrast and
  fails WCAG AA, while `#1a1a1a` is ~6.4:1. Force-rebuilt and confirmed all
  three rules in `assets/css/tailwind.css`. 167 passed, ruff clean.
- **Deviations:** Second override of my styling choice on the same badge.
  The previous entry recorded that I had substituted `badge-accent` for a
  literal pink and flagged that it might not be the pink they meant — it was
  not, and the user came back to say so. Lesson recorded: when a user names
  a specific color, match the color literally rather than routing it
  through the nearest design-system token. Also noted to the user, no answer
  yet: hardcoding a hex departs from the "Tailwind + DaisyUI classes only"
  convention in CLAUDE.md; offered to define a named custom color in
  `assets/css/source.css` instead.
- **Sideways:** My first verification greps for the compiled rules returned
  "No matches found," which briefly looked like the arbitrary-value classes
  had failed to compile. They had not — CSS escapes `#` and `[` in
  selectors, so the emitted text is `.bg-\[\#ff69b4\]`, and the unescaped
  patterns could never match. Re-checked against the escaped form and all
  three rules were present. Nearly chased a build problem that did not
  exist.

## 2026-09-20 — Featured badge restyled: pink with a star (cont.)

Continues the session logged in the entry below, after that entry's log had
already been written.

### Prompts

1. "Can you change the featured badge to be pink with a star next to the
   word 'Featured'?"
2. "update PROMPTS.md with this session"

### Summary

- **Outcome:** Changed the badge in both templates from
  `badge badge-primary` reading "Featured" to `badge badge-accent` reading
  "★ Featured" — `templates/products/catalog.html` and
  `templates/products/detail.html`. DaisyUI has no `badge-pink`; the `night`
  theme's accent is `oklch(72.36% 0.176 350.048)`, hue 350, which is pink,
  so the pink comes from the theme's own palette rather than a hardcoded
  `bg-pink-500`. The star is the Unicode `★` — the project allows no
  JavaScript and carries no icon library. Suite still 167 passed, ruff
  clean; the tests match on the word "Featured" so the star did not
  affect them.
- **Deviations:** The user changed the badge styling I had chosen
  (`badge-primary`, no icon) to pink with a star. I substituted
  `badge-accent` for a literal pink utility class and flagged that
  substitution, offering explicit Tailwind pink classes if the theme accent
  is not the pink they meant — no answer yet at time of writing.
- **Sideways:** `tailwind build` reported "All 1 stylesheet(s) are up to
  date" and skipped rescanning, which would have shipped the brand-new
  `badge-accent` class missing from the compiled CSS, rendering the badge
  without its color. Caught before finishing; re-ran with `--force` and
  confirmed `badge-accent` is present in `assets/css/tailwind.css`. Worth
  remembering: that command's freshness check does not notice new utility
  classes appearing in templates.

## 2026-09-20 — Featured products: `is_featured` field and its badge

### Prompts

1. "Add an is_featured field to Product. It is a boolean and defaults to
   not-featured, so existing products stay unfeatured."
2. "Add a featured badge." — with the detail: a featured product shows a
   "Featured" badge in two places, the catalog listing and the product
   detail page; both places must show it.
3. "Write a short sentence that explains what code was changed to add the
   featured badge"
4. "Make the sentence more simplistic and written in plain English."
5. "Which template files were changed?"
6. The PROMPTS.md session-log prompt quoted at the top of this file.

### Summary

- **Outcome:** Added `is_featured = models.BooleanField(default=False)` to
  `Product` (`products/models.py`) with migration
  `products/migrations/0003_product_is_featured.py`, applied — existing rows
  default to unfeatured. Rendered a `badge badge-primary` "Featured" behind
  an `{% if product.is_featured %}` guard in two templates:
  `templates/products/catalog.html` (the card's badge row, beside the
  category badge) and `templates/products/detail.html` (the status row,
  which became `flex flex-wrap gap-2` so the badge sits next to the
  stock badge). Added a `featured_product` fixture to `conftest.py` and
  three tests in `products/tests.py` — catalog badge, detail badge, and an
  unfeatured product showing no badge. Suite green at 167 passed, ruff clean.
- **Deviations:** After the first prompt I offered a `featured()` queryset
  method, a back-office form checkbox, and a featured row on the catalog;
  the user took none of them and scoped prompt 2 to the badge alone. The
  one-sentence explanation was asked for, then rejected as too technical and
  redone in plain English; a follow-up then asked which template files had
  changed. Nothing was overridden on the implementation itself.
- **Sideways:** Nothing. No failed tests, no wrong turns, no rework of code.
  One thing is still unwired and was flagged to the user rather than
  fixed: nothing in the UI sets `is_featured` — the back-office product
  form has no checkbox for it, so the flag is currently settable only from
  the shell or Django admin.
