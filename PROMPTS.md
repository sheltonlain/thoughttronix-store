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

## 2026-10-24 — Customer reviews Phase 1: read-only section and seeded reviews, three behaviors built test-first

### Prompts

1. `/implement @prd/reviews.md @plans/reviews.md implement phase 1`
2. (TDD selection) "approved, go ahead"
3. (Cycle 1 test shown red) "Approved, make it pass"
4. "Move to cycle 2"
5. (Cycle 2 test shown red) "Approved, make it pass"
6. "Move to cycle 3"
7. (Cycle 3 test shown red) "Approved, make it pass"
8. "Yes, go ahead with the rest of phase 1"
9. "In step 3, wnen I look at DreamWeaver, my review apprears to be pinned
   at the top, but there are no other reviews, so it is hard to tell for
   sure. Additionally, since I have already received MindSync and SyncRest,
   I should I already be able to review the product. Finally, all of the
   warnings about reviews should appear next to a "Leave Your Review"
   button that is either clickable or grayed out based on the status of
   the order."
10. (Rejected a three-question prompt about the button) "Let's keep the
    form open as originally discussed in the PRD. Do not add the "Leave
    Your Review" button."
11. "It works now, go ahead and finish the phase"

### Summary

- **Outcome:**
  - **TDD selection:** three behaviors, approved as proposed:
    - `Review.objects.eligibility(user, product)` returns one named state
    - `Review.objects.summary(product)` returns the average and count
    - `User.public_name()` gives "Casey M." or the username
  - **Cycle 1:** a parametrized test over order status (Delivered → can
    review, Placed and Shipped → awaiting delivery, Cancelled → not a
    buyer). Red against a stub that always said "not a buyer", so the
    Cancelled case passed by accident, which I said at the time. Made
    green with one query over the user's own orders containing the
    product. The signed-out and already-reviewed states were added later
    with normal tests.
  - **Cycle 2:** red against a stub that returned an empty summary. The
    test fixed the empty case as `average: None`, not 0. A 1-star review
    on another product proves other products don't leak in. Made green
    with one `aggregate(Avg, Count)`.
  - **Cycle 3:** a stub `public_name()` that returned `""` came first, so
    the failure was an assertion, not an `AttributeError`. First name
    with no last name shows just the first name: my call, flagged.
  - **Rest of the phase (normal implementation):**
    - A new `reviews` app: the `Review` model with a rating check
      constraint and a unique user–product constraint, migration `0001`,
      and the admin with a rating filter and search. URLs are mounted at
      the root with no endpoints yet.
    - `Review.objects.section(user, product)` builds the whole section
      context, so Phases 2 and 3 can re-render it. `ProductDetailView`
      just adds it.
    - Partials `_reviews_section.html`, `_review_card.html`, and
      `_stars.html`. A `{% stars %}` tag rounds averages to whole stars
      (4.5 → 5, using `int(x + 0.5)`, since `round()` rounds to even).
    - The seed: a new `_create_reviews` step with its own RNG, a fixed
      comment pool, Casey's two-line DreamWeaver review, and one
      staff-edited review. The summary line counts reviews.
    - A `make_order` builder in `conftest.py`, the same shape as
      `make_coupon`.
  - **Tests:** 43 in `reviews/tests.py`, plus the `public_name` test in
    `accounts/tests.py` and `Review` in the seed idempotency test. Full
    suite green at 517 passed before the seed fix. The reviews and seed
    tests were re-run after it (93 passed). Ruff clean. All 15 Phase 1
    criteria are ticked in `plans/reviews.md`.
  - **Manual check:** the user followed the browser steps and confirmed
    the phase after the seed fix.
- **Deviations:**
  - **The button idea was dropped:** the user asked for a "Leave Your
    Review" button beside every message. That changes the PRD, so I
    asked three questions about it (when the form arrives, what a click
    does, what visitors see). The user rejected the prompt and kept the
    PRD's always-open form with no button.
  - **MindSync and SyncRest:** the user expected to be able to review
    them already. I explained that the placeholder is where Phase 2's
    form goes, and the phase boundary was kept.
  - **My choices, flagged to the user:**
    - `updated_at` is set from `created_at` in `save()`, not by
      `auto_now`, so the seed can backdate and a new review doesn't read
      as edited. Admin edits don't bump it.
    - The placeholder copy is "Reviewing opens soon."
    - The `btn-primary` test checks only the reviews section for
      visitors, because the navbar's Sign up is primary already.
- **Sideways:**
  - **Timestamp bug caught before testing:** both timestamps first
    defaulted to separate `timezone.now` calls. Every new review would
    have shown "Edited". I fixed it in `save()` and regenerated the
    uncommitted migration.
  - **Clumsy first summary test:** my first draft deleted the other
    product's review before asserting, which threw away the check it
    existed for. I caught it before running it and used a third product
    instead.
  - **Three test-assertion mistakes:** an apostrophe expected escaped in
    literal template text (twice), and a visitor `btn-primary` count
    that included the pre-existing navbar button.
  - **DreamWeaver had no other reviews:** found by the user in the
    browser. A throwaway-database script in the scratchpad showed that
    `dcole` and `snakamura` had received DreamWeaver, but the 3-in-5
    chance skipped both. The seed now always reviews delivered lines for
    the products Casey ordered (51 reviews, up from 44). The seed test
    checks each of those pages has other people's reviews. The tests
    missed this because they checked the rule, not the demo.
  - **Shell use:** a PowerShell match count and a `sed` to tick the plan
    ran without objection. `PROMPTS.md` was read and edited only with the
    file tools.

## 2026-10-18 — Customer reviews: broke the PRD into a four-phase plan

### Prompts

1. `/prd-to-plan @prd/reviews.md`
2. (Declined the two-question prompt on granularity and the back-office
   URL, choosing to clarify first) "1"
3. (Granularity, after the trade-offs were explained) "b, merge 3 and 4"
4. (Back-office URL) "a"
5. "Update PROMPTS.md with the standard prompt."

### Summary

- **Outcome:**
  - **Exploration:** before slicing, I read the integration points the PRD
    names:
    - `plans/wishlist.md` as the format model
    - `docs/ARCHITECTURE.md`, `docs/FRONTEND.md`, and `docs/TESTING.md`
    - `config/urls.py` and every app's URL patterns, including the Orders
      back-office paths
    - the back-office tab rail in `templates/backoffice/base.html`
    - `ProductDetailView`'s context
    - the seed's demo orders for DreamWeaver, MindSync, and SyncRest
  - **First breakdown (five phases):**
    - a read-only section plus seed
    - writing a review
    - editing and deleting your own review
    - staff moderation on the product page
    - the back-office Reviews tab
  - **Final breakdown (four phases):**
    - **Phase 1, read-only section and seeded reviews** (stories 1, 2, 11,
      12, 15–17, 20, 22, 28–30): the app, the model and its constraints,
      eligibility states, the summary, `public_name`, the admin, every
      pinned-slot message, the review cards, and the seed step.
    - **Phase 2, writing a review** (stories 3–7, 13, 19): the model form,
      the DaisyUI star widget, and the create endpoint with
      duplicate-safe create and a 403 for ineligible users.
    - **Phase 3, editing and deleting, for authors and staff** (stories
      8–10, 14, 17, 18, 21, 23): `revise`, the permission method and
      queryset, the edit, cancel, save, and delete endpoints, the 404 for
      someone else's review, and the "no longer exists" re-render.
    - **Phase 4, back-office Reviews tab** (stories 24–27): the staff list,
      the `?rating=` filter, HTMX delete, and both empty states.
  - **Plan:** written to `plans/reviews.md`, with architectural decisions,
    a description per phase, and acceptance criteria.
  - **Still to do:** nothing is committed, and no code has changed.
- **Deviations:**
  - **Clarified before answering:** the user declined the two-question
    prompt to ask about granularity first. I explained:
    - why staff moderation was thin (mostly one branch in the permission
      method)
    - why seeding sat in Phase 1 (otherwise the section is demoable only
      through tests)
  - **Granularity:** I recommended merging phases 3 and 4 so the
    permission method is written once. The user agreed.
  - **Back-office URL departs from the PRD:** the PRD says the app is
    "mounted under `/reviews/`". I recommended mounting it at the root,
    like `orders` and `coupons`, so the tab sits at `/backoffice/reviews/`
    with the other tabs. Customer endpoints keep a `reviews/` prefix. The
    user agreed, and the plan records the departure.
  - **My choices, not the PRD's, flagged to the user:**
    - the exact endpoint paths (edit GET and save POST share
      `reviews/<pk>/edit/`; cancel is `reviews/<pk>/card/`)
    - a placeholder in the *can review* slot until Phase 2
    - an invalid `?rating=` value falls back to all reviews
- **Sideways:**
  - **An assumption, not verified:** I said the invalid-`?rating=`
    fallback matches how the Orders filter treats a bad `?status=`, but I
    didn't read the Orders list view to confirm it. Check this when
    building Phase 4.
  - **No shell commands this session:** `PROMPTS.md` was read and edited
    with the file tools from the start.

## 2026-10-18 — Customer reviews: grilled the design and wrote the PRD

### Prompts

1. `/grill-me` with: "We need to add customer reviews to the ThoughtTronix
   store. The feature must include the following requirements: A customer
   can leave one review per product, and only for products they have
   purchased. SoulSear owners are eligible. Their next of kin are not. Each
   review will have a star-based rating (1-5) and a written comment.
   Customers can only edit or delete their own reviews, but staff and
   admins can edit or delete any review. Creating, editing, or deleting a
   review should update smoothly without reloading the full page or
   causing the customer to lose their place."
2. (Q1, what "next of kin are not" means) "Option 1, agreed"
3. (Q2, which order statuses count as purchased) "2"
4. (Q3, a review whose author later loses eligibility) "Option 1"
5. (Q4, which app) "Option 1"
6. (Q5, reviewing unavailable products) "Option 1"
7. (Q6, rating and comment validation) "2"
8. (Q7, where reviews appear and the summary) "Option 1"
9. (Q8, list order and pagination) "1"
10. (Q9, what each HTMX request swaps) "Option 1"
11. (Q10, where staff moderate) "2"
12. (Q11, what the back-office Reviews tab does) "Option 1"
13. (Q12, showing edits and staff edits) "Option 1"
14. (Q13, what non-eligible viewers see) "Option 1"
15. (Q14, a duplicate create) "Go with your recommendation"
16. (Q15, an HTMX action on a review that no longer exists) "Go with your
    recommendation"
17. (Q16, the reviewer's public name) "Your recommendation"
18. (Q17, the star picker) "1"
19. (Q18, seed data) "Option 1"
20. `/to-prd`
21. "Update PROMPTS.md with the standard prompt."
22. (Rejected a shell command) "What are my other options?"
23. "Option 1"

### Summary

- **Outcome:**
  - **Design interview (18 questions).** Before asking anything, the
    codebase was read: `Order`/`OrderItem` and the four order statuses,
    roles in `docs/ARCHITECTURE.md`, `StaffRequiredMixin`, the HTMX and
    template rules in `docs/FRONTEND.md`, `ProductDetailView` and its
    template, the wishlist PRD as the pattern to follow, and the seed's
    SoulSear products and demo orders. "Next of kin" exists nowhere in the
    code. Settled:
    - **Eligibility:** a Delivered order containing the product, checked
      once at creation. It belongs to the buying account (the SoulSear
      rule; no kin model). Availability is ignored, staff get no
      exemption, and later status changes never touch a review.
    - **Model:** a new `reviews` app. `Review` has a 1–5 rating (with a
      check constraint), a required comment of up to 2,000 characters,
      `created_at`, `updated_at`, and `edited_by_staff`, plus a unique
      user–product constraint. Logic lives in the manager (an eligibility
      state, an idempotent create) and the model (`revise`, a permission
      check). `User.public_name` shows "Casey M."
    - **Detail page:** one reviews-section partial with a summary, a slot
      pinned at the top (form, own review, or a message for the viewer's
      state), and the others newest first by creation, with no
      pagination. Create, save, and delete re-render the section; edit and
      cancel swap one card; delete uses `hx-confirm`. DaisyUI star radios.
      "Verified purchase", "Edited", and "Edited by staff" labels.
    - **Edge cases:** a duplicate create is a no-op that shows the
      existing review. Another user's review 404s. A review that's gone
      re-renders the section.
    - **Staff:** inline Edit and Delete on every review, plus a back-office
      Reviews tab for all staff with a `?rating=` filter and HTMX delete;
      no back-office edit screen.
    - **Seed:** reviews only from delivered order lines. Casey reviews
      DreamWeaver; one review is staff-edited. No SoulSear order (it would
      flatten the revenue chart); the SoulSear rule is proven in tests.
  - **PRD:** written to `prd/reviews.md` with 30 user stories.
  - **Still to do:** nothing is committed, and no code has changed.
- **Deviations:**
  - **Q2 overridden:** I recommended any non-cancelled order. The user
    chose delivered orders only, which made Q3 a real question and created
    the "awaiting delivery" state in Q13.
  - **Q6 overridden:** I recommended a 10-character minimum on comments.
    The user chose any non-blank comment up to 2,000 characters.
  - **Q10 overridden:** I recommended inline staff moderation only. The
    user added a back-office Reviews tab, which created Q11.
  - **Every other answer took the recommendation.**
  - **Defaults set without asking, and stated in the interview:** reviews
    cascade on product and user deletion, server-side permission checks,
    no `django.contrib.messages` for review actions, Django admin
    registration, all staff (not a permission subset) moderate.
  - **Filled in by `/to-prd`, flagged to the user:** an ineligible create
    POST gets a 403; an invalid edit re-renders only the card's form; the
    SoulSear test gives the "next of kin" the buyer's address; seeded
    comments come from a fixed pool of in-world text.
- **Sideways:**
  - **Q3 was found in the code:** `OrderStatusForm` allows any status at
    any time, so a delivered order can be moved back. That made "what
    happens to an existing review" concrete rather than hypothetical.
  - **Q15's recommendation was refined as I gave it:** I recommended
    Option 1 "but simplified" (delete is simply idempotent; only edit and
    save show the "no longer exists" note), not Option 1 exactly.
  - **Shell command rejected again:** to start this entry I ran a
    PowerShell command to count lines and print the end of `PROMPTS.md`,
    when the file tools would have done. The user rejected it and asked
    for other options, then chose reading and editing with the file
    tools. This is the third session in a row where this happened.

## 2026-10-18 — Wishlist Phase 2: the Wishlist page, three behaviors built test-first

### Prompts

1. `/tdd @prd/wishlist.md @plans/wishlist.md implement phase 2`
2. "What is your reasoning for selecting these three tests?"
3. "Approved, go ahead with all three"
4. (Cycle 1 test shown red) "Approved, make it pass"
5. "Move to cycle 2"
6. (Cycle 2 test shown red) "Approved, make it pass"
7. "Move to cycle 3"
8. (Cycle 3 test shown red) "Approved, make it pass"
9. "Yes, go ahead with the rest of phase 2"
10. "How can I manually verify this phase in the browser?"
11. "Add a PROMPTS.md entry for this session"
12. (Rejected a shell command) "What are my other options?"
13. "1"

### Summary

- **Outcome:**
  - **TDD selection:** three behaviors, approved after the user asked for
    the reasoning:
    - the Wishlist page lists only the requester's items, newest first
    - another customer's item pk 404s on remove and is left untouched
    - removing the last item re-renders the contents with the empty state
  - **Cycle 1:** red on `'Seraphine Home Hub' in page` against a stub page
    (URL `wishlist:wishlist`, `WishlistView`, empty `wishlist.html`). Made
    green with `Wishlist.lines()` (mirrors `Cart.lines()`), the view
    passing `Wishlist.for_user(request.user)`, and a bare
    `_wishlist_contents.html` loop. I said the scoping and order were
    really implemented but the rows only satisfied the test.
  - **Cycle 2:** red on `200 == 404` against a stub
    `RemoveWishlistItemView` at `wishlist:remove_item` that ignored the pk.
    Both customers saved the same product, so a product-based "fix" would
    also fail. Made green with
    `get_object_or_404(WishlistItem, pk=pk, wishlist__user=request.user)`.
    The view still didn't delete; I said so and left that for cycle 3.
  - **Cycle 3:** red because the response was still the item. Made green
    with `item.delete()` and a designed empty state ("Your wishlist is
    empty", a "Browse the catalog" link).
  - **Rest of the phase (normal implementation):**
    - Full rows: image, linked name, price, Unavailable badge, the
      unchanged add-to-cart partial, and an HTMX Remove targeting
      `#wishlist-contents`. `lines()` is evaluated once via `{% with %}`.
    - Navbar "Wishlist" `btn-ghost btn-sm` link after Orders, signed-in
      only, with no badge.
    - Seed: the wipe clears wishlists; `_create_customer_wishlist` saves
      MindSync Duo, EchoPatch (unavailable), Seraphine (in the cart), and
      MoodSet, backdated 1/6/13/30 days. The summary line mentions the
      wishlist.
  - **Tests:** 3 TDD tests plus 12 more in `wishlist/tests.py` (rows, the
    unavailable state, cart quantities, add to cart keeps the item, empty
    page, login and GET rejection on remove, partial re-render, navbar).
    The seed test in `products/tests.py` checks the demo wishlist, and the
    idempotency test now counts `WishlistItem`. Full suite green at 471
    passed, ruff clean.
  - **Manual check:** I gave browser steps for every acceptance criterion,
    including a DevTools `fetch` as `employee` to confirm another
    customer's item 404s.
  - **Still to do:** nothing is committed. I did not run `seed` against the
    local `db.sqlite3`. The user hadn't reported back on the browser steps
    by the end of the session.
- **Deviations:**
  - **Follow-up question:** the user asked why I picked the three tests.
    I said behavior 2 bent the skill's rule against behaviors an existing
    pattern has settled (the cart's owner-scoped lookup), and offered to
    drop it. The user kept all three.
  - **Flagged, not asked about:** the empty state's catalog link is
    `btn-primary` (as in the cart's), and its tagline is my own copy.
  - **Log request:** asked for with "Add a PROMPTS.md entry for this
    session" rather than the standard prompt. The entry follows the
    standard shape.
- **Sideways:**
  - **Full suite past the tool timeout:** the cycle 1 regression run took
    almost four minutes and finished in the background (457 passed). For
    cycles 2 and 3, which only touched wishlist code, I ran just
    `wishlist/tests.py` and said so.
  - **Formatting:** `ruff format` rewrapped a line in `wishlist/tests.py`
    after the full suite passed. It was a layout change only.
  - **Shell command rejected:** to start this entry I ran a PowerShell
    command to count lines and diff `PROMPTS.md`. The user rejected it
    and asked for other options, then chose reading and editing with the
    file tools.

## 2026-10-18 — Wishlist Phase 1: detail-page button, browser-verified, double-click fixed

### Prompts

1. "@prd/wishlist.md @plans/wishlist.md Implement phase 1"
2. "How can I manually verify this phase in the browser?"
3. "In 3. Save and remove without a reload (stories 4–6), Step 4 says that
   the hint should not appear when you load the page again. However, the
   hint did appear when I tried this step."
4. "It said Save to wishlist, so it works"
5. "When I double click the save button, the status toggles back and
   fourth."
6. "It works now, double-clicking stays saved"
7. "run the full test suite"
8. "Add our session to PROMPTS.md"

### Summary

- **Outcome:**
  - **New `wishlist` app:** `Wishlist`, one-to-one with the user and
    created lazily via `for_user`, with `add`, `remove`, and `contains`.
    `WishlistItem` has a unique wishlist–product constraint, cascades on
    product and user deletion, and is ordered newest first. The migration
    is `0001_initial`. The admin shows the items inline, plus an item
    count. URLs are mounted at `/wishlist/`.
  - **Endpoints:** `wishlist:add` and `wishlist:remove` are separate
    (never a toggle), keyed by product pk, POST-only, and require sign-in.
    Each re-renders the button partial in its new state. Unavailable
    products can be saved.
  - **Detail page:** `ProductDetailView` sets `in_wishlist` with one
    existence check that never creates a wishlist on a GET. The new
    `templates/wishlist/partials/_wishlist_button.html` has three states:
    not saved, saved, and a signed-out link whose `next` is rebuilt from
    the product URL plus `?wishlist=1`. The hint lives inside the swapped
    wrapper, so it disappears once Save is clicked.
  - **Choices beyond the plan, flagged to the user:**
    - `added_at` uses `default=timezone.now` rather than `auto_now_add`,
      so the Phase 2 seed can backdate saves.
    - Ordering is `["-added_at", "-pk"]`, so ties sort predictably.
  - **Tests:** `wishlist/tests.py` covers every Phase 1 acceptance
    criterion, plus an admin test and a double-click-guard test. The full
    suite is green at 456 passed, and ruff is clean.
  - **Still to do:** nothing is committed. `db.sqlite3` (tracked) changed
    when I ran `migrate`, and the user must decide whether to commit it.
    Browser checks for stale tabs, EchoPatch, and the admin had not been
    reported back by the end of the session.
- **Deviations:**
  - **Follow-up questions:** the user asked for a browser walkthrough,
    then reported two problems found while following it (both below).
  - **Nothing overridden:** no recommendation was rejected. I offered,
    but did not apply, the double-click guard for the cart's Add to cart
    button.
- **Sideways:**
  - **Bad walkthrough step:** step 4 of "Save and remove" said to check
    the hint "while the product is saved", but step 3 had just removed
    it, so the hint correctly appeared. I asked which button label showed.
    "Save to wishlist" confirmed the code was right and my instructions
    were wrong. I gave a corrected step (save first, then load
    `?wishlist=1`).
  - **Double-click toggled the state:** a real bug that the tests missed.
    The local server answered so fast that the second click of a
    double-click landed on the freshly swapped-in Remove button. Each
    click did what its label said at that moment, but the result defeated
    story 7. Fixed with `hx-disabled-elt="this"` plus
    `hx-swap="outerHTML settle:500ms"`, and a
    `[&.htmx-added]:pointer-events-none` class on the wrapper so the new
    button ignores clicks while it settles. I checked the vendored htmx
    2.0.6 and the compiled Tailwind output before reporting. The user
    confirmed the fix in the browser.
  - **A wrong test assertion:** the first version of the guard test
    expected `&amp;` in the class name. Django doesn't escape literal
    template text, so the assertion was corrected to a bare `&`.

## 2026-10-18 — Wishlist: broke the PRD into a two-phase plan

### Prompts

1. `/prd-to-plan @prd/wishlist.md`
2. "I think phases 3, 4, and 5 are too small. Can we fit 3 and 5 into
   phase 2 without making this phase too large. And is there somewhere we
   can fit phase 4?"
3. "yes, write the plan"
4. "Add our session to PROMPTS.md"
5. (Rejected a shell command) "What other options do we have?"
6. "option 1"

### Summary

- **Outcome:**
  - **Exploration:** before slicing, I read the cart code the PRD mirrors:
    `Cart.for_user`, the owner-scoped `CartItemActionView`, `orders/urls.py`
    for path shapes, the product detail template, the seed's
    `_create_customer_cart` step, and `plans/account-security.md` for the
    plan format.
  - **First breakdown (five phases):** detail-page save/remove, the
    Wishlist page and navbar link, Wishlist-page remove, the signed-out
    visitor flow, and the seeded demo wishlist.
  - **Final breakdown (two phases, one per page):**
    - **Phase 1, detail-page button** (stories 1–8, 17, 18): the
      `wishlist` app, both models and their methods, the admin, the add
      and remove endpoints, the `in_wishlist` flag, all three button
      states, and the `?wishlist=1` hint.
    - **Phase 2, the Wishlist page** (stories 9–16, 19): the page and
      navbar link, the newest-first list, the owner-scoped HTMX remove,
      the empty state, and the seeded demo wishlist.
  - **Plan:** written to `plans/wishlist.md`, with architectural
    decisions, a description per phase, and acceptance criteria.
  - **Still to do:** nothing is committed, and no code has changed. The
    existing uncommitted change to `REFLECTION.md` was left alone.
- **Deviations:**
  - **Granularity overridden:** I suggested folding phases 3 and 5 into
    Phase 2 and recommended keeping Phase 1 whole. The user found phases
    3, 4, and 5 all too small and asked where Phase 4 could go. I put the
    signed-out flow into Phase 1, since it is the third state of the same
    button partial, and folded 3 and 5 into Phase 2. The user approved.
  - **URL paths are my choice, not the PRD's:** the PRD fixes only the
    `/wishlist/` mount and the namespace. I chose `add/<pk>/`,
    `remove/<pk>/`, and `items/<pk>/remove/` to match the cart's paths,
    and flagged them to the user.
  - **Log request:** asked for with "Add our session to PROMPTS.md"
    rather than the standard prompt. The entry follows the standard shape.
- **Sideways:**
  - **Shell command rejected:** to start this entry I ran a PowerShell
    command to diff `PROMPTS.md` and count its lines. The user rejected
    it and asked for other options. I offered three: read and append with
    the file tools, take the format from the user, or draft the entry in
    chat. The user chose the file tools, which needed no shell.

## 2026-10-18 — Wishlist: grilled the design and wrote the PRD

### Prompts

1. `/grill-me` with: "We need to add a wishlist to the ThoughtTronix Store
   that will allow customers to save products for later in a wishlist. Each
   signed-in customer will have one wish list. We will not include named
   wishlists, multiple wishlists, or shared wishlists. Customers should be
   able to add or a remove a product from the product detail page without
   needing to reload the full page. The Add/Remove button must show the
   product's status in the wishlist. Customers will only be able to access
   their own wishlist."
2. (Q1, how the wishlist is stored) "Option A, mirror the cart"
3. (Q2, which app) "Option A, new wishlist app"
4. (Q3, what signed-out visitors see) "I like option A. Is there a way we
   can at least hint to the user that they will still need to add that
   item to the wishlist now that they've signed in?"
   — then: "Option A, and leave signup out of scope"
5. (Q4, toggle vs. separate endpoints) "Option B, separate add and remove
   endpoints"
6. (Q5, saving unavailable products) "a"
7. (Q6, the wishlist page) "b"
8. (Q7, Add to cart button style on the wishlist page) "Option A, match the
   catalog"
9. (Q8, Remove on the wishlist page) "Option A, mirror the cart line
   actions"
10. (Q9, navbar) "Option A, plain Wishlist link"
11. (Q10, catalog cards) "Option A, detail page only"
12. (Q11, seed data) "Option A, seed a demo wishlist"
13. (Q12, button labels and look) "a"
14. (Q13, expired session on an HTMX click) "Let's go with your
    recommendation"
15. `/to-prd`
16. "Add our session to PROMPTS.md"

### Summary

- **Outcome:**
  - **Design interview (13 questions).** Before asking anything, the
    codebase was read: `Cart`/`CartItem`, the HTMX add-to-cart partial and
    its signed-out login link, the owner-scoped cart line-action views, the
    site-wide `cart_quantities` context processor, Django admin, and the
    seed. Settled:
    - **Data:** a new `wishlist` app; `Wishlist` (one-to-one with the user,
      created lazily) and `WishlistItem` (product, `added_at`, unique per
      wishlist), mirroring the cart.
    - **Endpoints:** separate add and remove POSTs keyed by product for the
      detail page, never a toggle; a wishlist-page remove keyed by item and
      looked up through its owner, re-rendering the whole contents partial.
    - **Detail page:** "♡ Save to wishlist" / "♥ Saved · Remove", both
      outline, with `aria-pressed`. Signed-out visitors get a sign-in link
      whose `next` carries a display-only `?wishlist=1` hint flag.
    - **Wishlist page:** newest first, Unavailable badges, the cart's Add
      to cart partial unchanged, HTMX Remove, a designed empty state, and a
      plain navbar link.
    - **Rules:** unavailable products can be saved; the button is on the
      detail page only.
    - **Admin and seed:** a Django admin inline like `Cart`; a seeded
      wishlist for `customer` with an unavailable product and one already
      in the cart.
  - **PRD:** written to `prd/wishlist.md` with 19 user stories.
  - **Still to do:** nothing is committed, and no code has changed. The
    existing uncommitted change to `REFLECTION.md` was left alone.
- **Deviations:**
  - **Q3 follow-up:** the user took the recommendation but asked whether
    the visitor could be told the product still needs saving after
    sign-in. That became a three-option sub-question; the user took the
    recommended template-only hint, and agreed to leave the signup path
    out of scope.
  - **Q6 overridden:** I recommended a read-and-remove wishlist page and
    parked Add to cart as a follow-up. The user chose to include Add to
    cart on each row, which created Q7.
  - **Every other answer took the recommendation.**
- **Sideways:**
  - **Wrong claim about reuse:** in Q6 I said reusing `_add_button.html`
    on the wishlist page would need a style variant, because a page of
    `btn-primary` buttons breaks FRONTEND.md's one-primary rule. After the
    answer, I checked the code: `cart_quantities` is already provided on
    every page, and `catalog.html` already puts that same primary button on
    every card. I corrected the claim before asking Q7, and the user chose
    to match the catalog.
  - **Pre-existing flaw found, not fixed:** an HTMX POST after the session
    expires follows `LoginRequiredMixin`'s redirect and swaps the whole
    login page into the button. The cart's Add to cart already does this.
    It's recorded in the PRD as a known limitation and a project-wide
    follow-up.
  - **Log insert took two tries:** my first edit to this file failed
    because the text it matched against wasn't found, likely because of
    line endings. Anchoring on the heading line alone worked.

## 2026-10-17 — Readable console email backend for whole links

### Prompts

1. "Look at PROMPTS.md ## 2026-10-11 — Account security Phase 3: forgot
   password. The third prompt I gave stated that the password reset link
   does not work, and you had proposed a fix for this that I originally
   declined. I would like to implement that fix now."
2. "Update PROMPTS.md with the standard prompt"

### Summary

- **Outcome:**
  - **Backend:** `accounts/mail.py` adds `ReadableConsoleEmailBackend`, a
    subclass of Django's console backend. It prints From, To, Cc (when
    set), Subject, and the decoded `message.body`, instead of the raw MIME
    source. Long links no longer go out quoted-printable with a trailing
    `=`, so reset, verification, and email-change links copy whole from
    the terminal.
  - **Settings:** `EMAIL_BACKEND` in `config/settings.py` points at the
    new backend. Mail is still console-only, as the PRD says.
  - **Tests:** 2 new in `accounts/test_mail.py`:
    - the settings module names the new backend (pytest-django swaps in
      locmem, so the test reads `config.settings` directly)
    - a real reset email sent through the backend prints its link alone
      on one line, with no `=` line breaks

    Suite green at 420 passed, ruff clean.
  - **Still to do:** nothing is committed. The existing uncommitted
    change to `templates/base.html` was left alone.
- **Deviations:**
  - This reverses the Phase 3 decision to keep the stock console backend.
    The user asked for the fix they had declined then.
- **Sideways:**
  - The first ruff format check flagged `accounts/test_mail.py`. I
    reformatted it, which joined one wrapped line.
  - The full suite again ran past the two-minute tool timeout. It ran in
    the background and passed.

## 2026-10-11 — Account security Phase 6: email change

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 6"
2. (Rejected the first `CLAUDE.md` edit) "Can you shorten the summaryy down
   to one line? We do not want verbose explanations in our CLAUDE.md file."
3. "How can I manually verify this phase in the browser?"
4. "Update PROMPTS.md with the standard prompt"

### Summary

- **Outcome:**
  - **Model:** `User.request_email_change(new_email, request)` stores
    `pending_email`, emails a confirmation link to the new address, and
    sends the alert "An email change was requested" to the current
    verified address, if there is one.
    `User.confirm_email_change(token)` re-checks that no other account
    holds the address. It then moves `pending_email` into `email` and sets
    `email_verified_at`. If the address was taken, it raises
    `ValidationError` and clears the pending change. A shared
    `_verification_link` helper now builds both kinds of link.
  - **Form:** `ChangeEmailForm` asks for the new email and the current
    password. The password is checked the way Django's
    `PasswordChangeForm` checks it. The form rejects an unchanged address
    or one already in use, ignoring capitalization.
  - **Views and URLs:** `ChangeEmailView` (login required) is at
    `security/email/`. `ConfirmEmailChangeView` is at
    `security/email/confirm/<uidb64>/<token>/` and needs no sign-in.
    `LinkUserMixin` now holds the uid decoding that `VerifyEmailView` had
    inline, and both views use it.
  - **Templates:** `email_change.html` (title reads "Add an email" for
    blank-email accounts), `email_change_invalid.html`, and
    `email/confirm_email_change.txt`. The hub's Email card now shows the
    pending change and a "Change email" / "Add an email" button.
  - **Change to Phase 4 code:** `verify_email` now refuses an account
    whose email is already verified, so an email-change link can't be used
    up on the signup `/verify/` URL.
  - **Tests:** a new `accounts/test_email_change.py` with 19 tests:
    - login required, and the hub links to the change page
    - a wrong password, an unchanged address, or a taken address (exact
      and any capitalization) saves and sends nothing
    - a valid request sets the pending change and emails both addresses
    - password reset still goes to the old address while a change is
      pending
    - confirming swaps the address in, also when signed out
    - a used, replaced, or tampered link shows the error page
    - the link expires after three days (time controlled)
    - an address taken before confirming is refused
    - an email-change link can't be spent as signup verification
    - a blank-email account adds an email with no alert

    Suite green at 418 passed, ruff clean.
  - **Docs:** `CLAUDE.md`'s `accounts/` line is now one line. Phase 6's
    acceptance criteria are ticked in `plans/account-security.md`.
  - **Manual check:** I gave seven browser steps as `customer`. They use
    the seeded `mwren` account for the "taken" cases and the admin to clear
    an email and to take an address before confirming.
  - **Still to do:** nothing is committed. Reseed before committing.
- **Deviations:**
  - The user rejected my first, multi-line `CLAUDE.md` description of
    `accounts/` and asked for one line. My plan-ticking command was
    rejected along with it, and I redid it afterwards as a plain edit.
  - The user asked a follow-up about verifying the phase by hand.
- **Sideways:**
  - No test failures. `ruff format` reflowed only the new test file.
  - Two decisions were flagged to the user for review, not asked about:
    - clearing the pending change when the address is taken
    - leaving a true simultaneous-confirmation race to the database
      constraint, which would give a server error rather than a friendly
      message

## 2026-10-11 — Account security Phase 5: sign-in block and resend verification

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 5."
2. (Rejected a diagnostic command) "Explain what this does"
3. "Go ahead and run it"
4. (Rejected the first `docs/ARCHITECTURE.md` edit) "Can you shorten the
   summary for ARCHITECTURE.md? We do not want it to be extremely verbose."
5. "How can I manually verify this phase in the browser?"
6. "pdate PROMPTS.md with the standard prompt"

### Summary

- **Outcome:**
  - **Sign-in rule:** `SignInForm.confirm_login_allowed` refuses an account
    that has an email but no `email_verified_at`. Its error has the code
    `unverified` and a `format_html` link to the resend page. Django only
    calls the hook after the password checks out, so a wrong password
    still gets only the normal `invalid_login` error. Blank-email accounts
    still sign in.
  - **Resend:** `ResendVerificationForm.save(request)` finds an unverified
    account by email, case-insensitively, and calls the existing
    `User.send_verification_email`. `ResendVerificationView` (a
    `FormView`) at `verify/resend/` always redirects to sign-in with the
    same neutral flash message. Its template is `resend_verification.html`.
  - **Links to resend:** `verify_email_invalid.html` now has a "Send a new
    link" button, its only `btn-primary`, with sign-in demoted to
    `btn-ghost`. `signup_sent.html` links to resend too.
  - **Docs:** `docs/ARCHITECTURE.md` gained a short "Email verification"
    section: `email_verified_at` is the only flag, `is_active` means
    "deactivated by staff" only, and the sign-in rule.
  - **Tests:** added to `accounts/test_verification.py`:
    - verified and blank-email accounts sign in
    - an unverified account is refused, and the error links to resend
    - a wrong password shows only `invalid_login`
    - verifying a deactivated account leaves it inactive and unable to
      sign in
    - resend sends one working link to an unverified account (caps
      ignored) and nothing for verified or unknown addresses
    - resend's replies are identical with the CSRF token stripped
    - the bad-link page links to resend

    Suite green at 399 passed, ruff clean.
  - **Plan:** Phase 5's acceptance criteria are ticked in
    `plans/account-security.md`.
  - **Manual check:** I gave browser steps for each criterion:
    - signing up `tester5` and `tester6`
    - resend with an unverified, a verified, and an unknown address
    - clearing an email in the admin to test a blank-email sign-in
    - deactivating `tester6` before verifying it
  - **Still to do:** nothing is committed. Reseed before committing, and
    delete `tester5`/`tester6` in the admin if they're still there.
- **Deviations:**
  - The user rejected a diagnostic command until I explained it, then
    approved it.
  - The user rejected my first, longer `ARCHITECTURE.md` section, which
    covered tokens, timeouts, enumeration, and the admin path. The kept
    version is four lines.
  - The user asked a follow-up about verifying the phase by hand.
- **Sideways:**
  - The "replies the same" test first failed: 3 distinct pages. A
    throwaway diff test (copied into `accounts/`, then deleted) showed the
    only difference was the masked CSRF token, which also appears in
    `base.html`'s `hx-headers` on `<body>`. My regex only stripped the form
    field. Widening it fixed the test. No real leak.
  - `ruff format` reflowed the `format_html` string in `accounts/forms.py`
    after the suite had passed. The full suite was re-run afterwards.
  - The resend form doesn't skip inactive accounts, matching the PRD's
    wording. A deactivated, unverified account can still be sent a link,
    but verifying it doesn't reactivate it.

## 2026-10-11 — Account security Phase 4: signup with a verified email

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 4."
2. "How can I manually verify this phase in the browser?"
3. "Update PROMPTS.md with the standard prompt."

### Summary

- **Outcome:**
  - **Tokens:** `accounts/tokens.py` adds `EmailVerificationTokenGenerator`,
    a subclass of Django's `PasswordResetTokenGenerator`. Its hash covers
    `email`, `pending_email`, and `email_verified_at`, so a link dies once
    used. Django's `check_token` hardcodes `PASSWORD_RESET_TIMEOUT`, so the
    subclass overrides it to check `EMAIL_VERIFICATION_TIMEOUT` instead.
  - **Model:** `User.send_verification_email(request)` emails the link, and
    `User.verify_email(token)` sets `email_verified_at` if the token is live.
    Neither touches `is_active`. A `Meta` constraint makes `Lower("email")`
    unique for non-blank emails only. Migration
    `0005_user_email_ci_unique` adds it, and it was applied to
    `db.sqlite3`. Before adding it I checked the database: 15 users, no
    emails that clash when case is ignored, and 2 blank ones.
  - **Form:** `SignupForm` now requires an email, and `clean_email` rejects
    one already on an account, case-insensitively, with "That email
    address is already in use." The old "No email" docstring is replaced.
  - **Views and URLs:**
    - `SignupView` now sends the verification email and redirects to
      `signup/sent/`, a "Check your inbox" page. There's no auto-login.
    - `VerifyEmailView` at `verify/<uidb64>/<token>/` verifies the email
      and redirects to sign-in with "Email verified — you can now sign in."
      A bad link renders `verify_email_invalid.html`, which links to
      sign-in for now. Phase 5 will point it at resend.
  - **Templates:** `signup_sent.html`, `verify_email_invalid.html`, and the
    plain-text `email/verify_email.txt`.
  - **Settings:** `EMAIL_VERIFICATION_TIMEOUT` is read from `.env` with a
    three-day default. `.env.example` gained commented examples for it and
    for `PASSWORD_RESET_TIMEOUT`.
  - **Tests:** the two signup tests in `accounts/tests.py` now post an
    email and expect the "Check your inbox" redirect. The new
    `accounts/test_verification.py` covers:
    - a missing email
    - a duplicate email, exact and in different capitals
    - an unverified, active account and the one email it gets
    - the database constraint, and blank emails coexisting
    - a link verifying the account
    - used, tampered-token, unknown-uid, and garbage-uid links
    - expiry at just under and just over three days, with time controlled
      by monkeypatching `EmailVerificationTokenGenerator._now`
    - the default timeout, and an env override checked in a subprocess

    Suite green at 388 passed, ruff clean.
  - **Plan:** Phase 4's acceptance criteria are ticked in
    `plans/account-security.md`.
  - **Manual check:** I gave browser steps for each criterion:
    - signing up `tester1`–`tester3`
    - reading links from the console
    - checking the hub's Verified and Not verified badges
    - a temporary `.env` with `EMAIL_VERIFICATION_TIMEOUT=60` for expiry
    - the admin to test the constraint and blank emails coexisting
  - **Still to do:** nothing is committed. Reseed before committing, so
    test accounts don't end up in the tracked `db.sqlite3`.
- **Deviations:**
  - The user asked a follow-up about verifying the phase by hand.
  - No recommendations were overridden.
- **Sideways:**
  - `ruff format` reformatted `accounts/tokens.py` and `accounts/views.py`
    after the full suite had passed. The accounts tests were re-run
    (93 passed) to confirm.
  - Until Phase 5, unverified accounts can still sign in, which the plan
    allows. I flagged it.
  - Verification links wrap in the console with a trailing `=`, the same
    quoted-printable issue found in Phase 3. The manual steps say to rejoin
    them.
  - Like the reset expiry test, the expiry test patches Django's private
    `_now`.
  - The default-timeout test would fail if a local `.env` set
    `EMAIL_VERIFICATION_TIMEOUT`.

## 2026-10-11 — Account security Phase 3: forgot password

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 3"
2. "How can I manually verify this phase in the browser?"
3. "When I visit the password reset link from step 2, I land on a page
   saying that the link does not work because The reset link is invalid,
   has expired, or has already been used."
4. "No, update PROMPTS.md with the standard prompt."

### Summary

- **Outcome:**
  - **Forms:** `ResetPasswordForm` (Django's `PasswordResetForm`) narrows
    `get_users` to accounts with `email_verified_at` set. Django already
    matches case-insensitively and skips inactive accounts and unusable
    passwords. `SetNewPasswordForm` is Django's `SetPasswordForm` in
    DaisyUI. Both are in `accounts/forms.py`.
  - **Views and URLs:** thin subclasses of Django's four reset views at
    `password-reset/`, `password-reset/sent/`, `reset/<uidb64>/<token>/`,
    and `reset/done/`, named under `accounts:`. The confirm view sends
    "Your password was reset" through the Phase 2
    `User.send_security_alert`. The customer signs in themselves
    afterwards.
  - **Templates:** four DaisyUI pages in `templates/accounts/`, each
    with at most one `btn-primary`. The confirm page's invalid-link state
    links to a new request. The reset email body and subject are
    plain-text templates in `templates/accounts/email/`. The sign-in page
    gained a "Forgot password?" link.
  - **Settings:** `PASSWORD_RESET_TIMEOUT` is read from `.env` with a
    one-hour default.
  - **Tests:** 14 new in `accounts/test_security.py`:
    - the sign-in page link
    - exact and different-capitals verified emails each get a link
    - unverified, unknown, inactive, and unusable-password accounts get no
      mail and the same redirect, run as one parametrized test
    - the full reset, with the alert and signing in with the new password
    - the password validators
    - a link works only once
    - a link still works at 59 minutes and fails after one hour, with time
      controlled by monkeypatching `PasswordResetTokenGenerator._now`
    - the default timeout, and an env override checked in a subprocess

    Suite green at 373 passed, ruff clean.
  - **Plan:** Phase 3's acceptance criteria are ticked in
    `plans/account-security.md`.
  - **Manual check:** I gave browser steps for each criterion using the
    seeded accounts:
    - `customer` for the happy path
    - `mwren` for an unusable password
    - the admin to unverify and deactivate an account
    - a temporary `.env` with `PASSWORD_RESET_TIMEOUT=60` for expiry and
      the env override
  - **Still to do:** nothing is committed.
- **Deviations:**
  - The user asked a follow-up about verifying the phase by hand.
  - I offered a small development email backend that prints decoded
    bodies, so links copy whole from the terminal. The user declined, so
    the console backend stays as the PRD says. Links must be rejoined by
    hand when they wrap.
- **Sideways:**
  - The reset link copied from the terminal showed "This link doesn't
    work". I reproduced the raw email. The URL is about 80 characters long,
    so the email went out quoted-printable, and the console backend printed
    the link split across two lines with a trailing `=`. The copied link was
    therefore truncated. The token and code were fine. The workaround is to
    delete the `=` and join the two lines. The tests missed this because
    they read the decoded `message.body`. Phases 4 and 6 send links just as
    long, so the same thing will happen there.
  - Two tests are fragile, and I flagged both:
    - the expiry test patches Django's private
      `PasswordResetTokenGenerator._now`
    - the default-timeout test would fail if a local `.env` set
      `PASSWORD_RESET_TIMEOUT`
  - Running the full suite took longer than the two-minute tool timeout,
    so it finished in the background, and it passed.

## 2026-10-11 — Account security Phase 2: password change and security alerts

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 2."
2. "How can I manually verify this phase in the browser?"
3. "pdate PROMPTS.md with the standard prompt"

### Summary

- **Outcome:**
  - **Alerts:** `User.send_security_alert(action)` emails the verified
    address from the plain-text template
    `templates/accounts/email/security_alert.txt`. The email names the
    action, gives the time, and says to reset the password if it wasn't
    you. It sends nothing if there is no verified address. A
    `verified_email` property backs it. Phases 3 and 6 can reuse both.
  - **Password change:** `ChangePasswordView` (Django's
    `PasswordChangeView` plus `SuccessMessageMixin`) is at
    `/accounts/security/password/` (`accounts:password_change`). It uses
    `ChangePasswordForm`, Django's `PasswordChangeForm` with DaisyUI
    classes, and the template `templates/accounts/password_change.html`.
    On success it redirects to the hub with a flash message and sends the
    alert. Keeping this session and signing out the others is Django's
    built-in behavior; it isn't reimplemented.
  - **Hub:** the Password card's placeholder became a "Change password"
    button styled `btn-outline`, so the hub still has no `btn-primary`.
  - **Settings:** `DEFAULT_FROM_EMAIL` is read from `.env`, defaulting to
    `ThoughtTronix <security@thoughttronix.example>`.
  - **Tests:** added to `accounts/test_security.py`:
    - the login requirement and the hub's link to the change page
    - wrong-current, mismatch, and failing-validator inputs, run as one
      parametrized test; each gives a form error, changes nothing, and
      sends no mail
    - success redirects to the hub and keeps the user signed in
    - a second `Client` is signed out by the change
    - one alert with the time fixed by monkeypatching `timezone.now`
    - a blank-email user changes their password and gets no mail
    - an unverified email gets no alert

    Suite green at 359 passed, ruff clean.
  - **Plan:** Phase 2's acceptance criteria are ticked in
    `plans/account-security.md`.
  - **Manual check:** I gave browser steps for each acceptance criterion:
    - the three error cases
    - a successful change as `customer`, with the alert printed by the
      console email backend
    - a private window to see the other session signed out
    - a fresh signup with no email, to see that no alert goes out
    - the login redirect
    - restoring the demo password afterwards
  - **Still to do:** nothing is committed.
- **Deviations:**
  - The user asked a follow-up about verifying the phase by hand.
  - No recommendations were overridden.
  - `DEFAULT_FROM_EMAIL` was my addition and isn't in the plan. I flagged
    it for review.
- **Sideways:**
  - Nothing failed.
  - The alert says "reset your password" without a link, because the
    "Forgot password?" flow arrives in Phase 3. I flagged this so the email
    can point to that flow later.
  - The hub button uses a new DaisyUI class, and the compiled CSS is
    gitignored. I noted that `tailwind build --force` may be needed if the
    watcher doesn't pick the class up.
  - My first attempt to insert this entry failed because the text I matched
    against wasn't in the file. The second attempt worked.

## 2026-10-11 — Account security Phase 1: security center hub and grandfathering

### Prompts

1. "@prd/account-security.md @plans/account-security.md Do Phase 1."
2. "How can I manually verify this phase in the browser?"
3. "update PROMPTS.md with the standard prompt"

### Summary

- **Outcome:**
  - **Model:** `User` gained `email_verified_at` (nullable timestamp) and
    `pending_email` (blank by default), in migration
    `0003_user_email_verification`.
  - **Grandfathering:** data migration `0004_grandfather_verified_emails`
    stamps `email_verified_at` on every existing user with an email.
    Blank-email users stay unverified and blank. Reversing it is a no-op.
  - **Seed:** demo and background users are created with verified emails.
  - **Hub:** a login-required `SecurityView` at `/accounts/security/`
    (`accounts:security`, `templates/accounts/security.html`). The Email
    card shows the address with a Verified badge, or a "No email on file"
    recovery warning. The Password card is a placeholder until Phase 2.
    The page has no `btn-primary`.
  - **Navbar:** a "Security" link beside "Addresses" for every signed-in
    user, staff included.
  - **Admin:** the two new fields are shown read-only on the user page.
  - **Tests:** a new `verified_customer` fixture in `conftest.py`, and
    `accounts/test_security.py` covering the login requirement, the
    verified badge, the no-email warning, the staff view, the navbar link
    for users and visitors, and a real migration test (migrate back to
    0003, create users, migrate forward). The seed test now asserts every
    seeded user is verified. Suite green at 349 passed, ruff clean.
  - **Plan:** Phase 1's acceptance criteria are ticked in
    `plans/account-security.md`.
  - **Manual check:** I gave browser steps for each acceptance criterion:
    migrate first, then check the grandfathering in the admin before
    seeding. Then check the hub as `customer`, a fresh signup with no
    email, and `employee`; the login redirect; the navbar for visitors;
    and that sign-in is unchanged.
  - **Still to do:** nothing is committed. 
- **Deviations:**
  - The user asked a follow-up about verifying the phase by hand.
  - No recommendations were overridden.
- **Sideways:**
  - Nothing failed.
  - I didn't migrate `db.sqlite3` because it is the tracked grading
    snapshot. I flagged this instead, and suggested backing it up or
    running `git restore db.sqlite3` after testing by hand. *Note - I (the human) made the migrations to manually verify the new updates.
  - The PRD's pending-email display and "change email" link were left for
    Phase 6, where the plan places them.

## 2026-10-11 — Account security PRD: email change requires the current password

### Prompts

1. "Please make it so that changing the email will also require the
   current password. Add this to prd/account-security.md"
2. "Please add this new discussion to PROMPTS.md"

### Summary

- **Outcome:**
  - **Decision recorded.** The previous entry left open whether changing
    the email requires the current password. It now does.
  - **PRD updated (`prd/account-security.md`):**
    - User story 18 now has the customer enter their current password
      along with the new address.
    - The "Email change" implementation decision says the password is
      checked the same way Django's password change form checks it. A
      wrong password is a form error, and nothing is saved or sent.
    - The "Assumption to confirm" item was removed from Further Notes.
  - **Still to do:** nothing is committed, and no code has changed.
- **Deviations:** none. The user confirmed the option I had recommended
  but that was never formally decided.
- **Sideways:**
  - I did not edit the previous entry, which still lists this as
    undecided, because past entries are never rewritten.
  - This discussion is logged as a separate entry under the same date.

## 2026-10-11 — Account security center: grilled the design and wrote the PRD

### Prompts

1. "/grill-me We need to expand account security features through an
   account security center. Customers need to provide an email address
   when they create their account, the ability to change their passwords,
   and the ability to reset their passwords using their email address.
   Please also suggest one or two security features you think our web
   application would benefit from, and we will consider implementing them.
   Any other features must fit in with the security requirements listed
   and fit in with the design of our exisiting code base."
   — Q1 (are emails unique?): "Unique, case-insensitive" (my
   recommendation).
2. (Chose to clarify Q2, how to handle existing accounts with no email)
   "Why do you recommend option 1 over the others?"
   — then answered Q2: "Allow blank, prompt in center" (my
   recommendation).
3. (Chose to clarify Q3, how customers change their email) "Why do you
   recommend option 1 over option 2?"
4. (Interrupted my re-asked Q3) "Can we make it so that users have to
   verify their email upon signup and also have to verify their email
   when they reset it?"
   — then answered Q4–Q10, each with my recommendation:
   - Q4: unverified accounts cannot sign in.
   - Q5: grandfather existing accounts as verified.
   - Q6: build on Django's built-ins, not django-allauth.
   - Q7: record verification in an `email_verified_at` timestamp.
   - Q8: 1-hour reset links and 3-day verification links.
   - Q9: a hub page with separate form pages.
   - Q10: reset goes only to verified emails.

   Q11 (which extra features?): picked "Security alert emails" only.
5. "/to-prd"
6. "Append a session log to PROMPTS.md at the repo root, under today's
   date, newest entry at the top. Record every prompt I gave you this
   session, in order, including any corrections. End the entry with a
   short summary: the outcome, any places where I deviated from a
   recommended answer or asked follow-up questions, and anything that
   went sideways."

### Summary

- **Outcome:**
  - **Design settled in an 11-question grilling.** Signup requires a
    unique, case-insensitive email, and the customer must verify it before
    signing in. Changing the email also needs verification: it is held in
    `pending_email`, and the old address stays in force until then.
    Verification is recorded in a new `email_verified_at` field and
    enforced in `SignInForm.confirm_login_allowed`. `is_active` keeps
    meaning "deactivated by staff" only.
  - **Existing accounts:** those with emails are grandfathered as
    verified, and the one blank-email account is prompted, not forced.
  - **Pages and links:** Django's built-in password change and reset
    views; a `/accounts/security/` hub with separate form pages; 1-hour
    reset and 3-day verification links, both set from `.env`; neutral
    resend and reset forms; reset only to verified emails.
  - **Extra feature:** security alert emails on password change, password
    reset, and email-change requests.
  - **PRD:** written to `prd/account-security.md` with 32 user stories.
    Not committed. No code changed.
- **Deviations:**
  - **Follow-up questions:** asked why I recommended option 1 on Q2 and
    on Q3. On Q2 the user then took the recommendation.
  - **Q3 overridden:** I recommended confirming the current password with
    no email verification, and offered verification as a later extra.
    The user instead asked for verification at both signup and email
    change. That reshaped the rest of the interview (Q4–Q8 exist because
    of it).
  - **Q11, one of two recommended extras:** picked security alert emails;
    declined sign-in throttling and recent sign-in activity.
- **Sideways:**
  - **Wrong claim about the cart:** in Q4 I said the cart works without
    an account. Checking `orders/views.py` showed the cart and checkout
    require login, so I corrected it right after the answer. An
    unverified customer can only browse the catalog. The answer stood.
  - **Option walked back:** the Q6 option text suggested `is_active=False`
    for unverified accounts. I withdrew that in Q7, because a verification
    link would then undo a staff ban.
  - **Interpretation:** "verify their email when they reset it" was read
    as *changing* the email, since password reset already proves email
    ownership. The user didn't confirm or correct this.
  - **Undecided requirement:** whether the email-change form requires the
    current password was never decided, because the Q3 re-ask was
    interrupted. The PRD includes it and flags it as an assumption to
    confirm.

## 2026-10-04 — Product images: implemented from the handoff, verified, and shipped

### Prompts

1. "@HANDOFF.md Implement this feature"
2. (After rejecting my edit that moved an inline test import to the top
   of `products/test_images.py`) "Why do you want to make this edit?"
3. "go ahead with the import move"
4. (After rejecting my edits to `docs/ARCHITECTURE.md` and
   `docs/FRONTEND.md`) "We don't want to add verbose explanations to the
   files in docs/ What is the next step you would take?"
5. "Add jus the one sentence to the doc file. Then go ahead with ruff and
   the full test suite."
6. "run the seed"
7. "how can I  manually verify the feature in the browser"
8. "There is a major issue with the image thumbnails in the cart and in the
   back office. They are not displaying as small images, but instead as
   full-size images that take up almost the entire screen. Please fix this
   issue and make sure the thumbnails are small as originally discussed."
9. "It looks good. Please reseed."
10. "Commit and push the feature, with a message that says what changed."
    — then, asked where to push and what to do with `HANDOFF.md`: "Push to
    main" and "Leave it out" (both my recommendations).
11. "add our session log to PROMPTS.md"

### Summary

- **Outcome:**
  - **Built the `HANDOFF.md` design.** Fixed the missing
    `MEDIA_URL`/`MEDIA_ROOT` first. Added `Product.image` (migration
    `0004_product_image`), a shared resize-to-1200-px WebP step in
    `products/images.py`, and `display_image_url` / `display_image_alt`
    with the placeholder fallback. File cleanup lives in `save()` and
    `delete()` via `on_commit`. `ProductForm.clean_image` rejects files
    with plain-language reasons. Images show in a 4:3 frame on the
    catalog, detail page, cart, back-office list, and edit form. `seed`
    imports the 12 mapped photos and empties `media/products/` on wipe.
  - **Tests:** 24 new in `products/test_images.py`, plus an autouse
    throwaway `MEDIA_ROOT` and a `make_image` fixture in `conftest.py`.
    The full suite passed at 342 before the thumbnail fix; after it, only
    the image and order tests were re-run (173 passed). Ruff clean.
  - **Docs:** one sentence in `docs/ARCHITECTURE.md` saying production
    must serve `MEDIA_ROOT` at `MEDIA_URL`.
  - **Shipped:** seeded twice. Committed as `46dab1a` "Add product images"
    and pushed to `origin/main`, with `product-images/` and the
    design-session PROMPTS.md entry. `HANDOFF.md` left untracked.
- **Deviations:**
  - **Docs:** I drafted a multi-paragraph "Media files" section and a
    `FRONTEND.md` convention line. The user rejected both: no verbose
    explanations in `docs/`, just the one sentence the handoff named. The
    `FRONTEND.md` line was dropped.
  - **Import move:** the user stopped the edit to ask why. I explained
    (project style, ruff's import rule) and it went ahead.
  - **PROMPTS.md:** the handoff listed appending an entry as a finishing
    step. I skipped it because this file says entries are added only
    when asked, and said so. The user asked at the end.
  - **Beyond the handoff:** `FORM_RENDERER = TemplatesSetting` plus
    `"django.forms"` in `INSTALLED_APPS`, for a DaisyUI-styled
    remove-image checkbox. A `has_display_image` property. Fixed pixel
    sizes on thumbnails. Each was reported to the user.
- **Sideways:**
  - **First full run: 2 failures.** Django's form `ImageField` checks the
    file extension before `clean_image` runs, so a real PNG named `.txt`
    was rejected. My rename only got past the model's check. Fixed by
    dropping the form field's extension validator. The transparency test
    used a fully opaque RGBA image, which WebP saves without alpha; the
    fixture now uses a half-transparent fill.
  - **Megapixel message:** it would have read "(40 megapixels). The limit
    is 40" for an image just over the limit. Caught before any run; now
    one decimal place.
  - **Ruff's Django ordering rule (DJ012) took two tries,** because it
    counts `delete()` as a custom method. Its first `--fix` also re-sorted
    the imports in the user's uncommitted `config/urls.py`; reported.
  - **Full-size thumbnails, found by the user in the browser.** I could
    not reproduce the cause on the server. The markup was right, every
    class was in the compiled CSS, and the running server sent the
    current stylesheet. My best guess, still unconfirmed, is that the
    browser cached an old `tailwind.css`. I also lost time on grep
    patterns that wrongly assumed the CSS was minified. Fix: `width` and
    `height` attributes on the thumbnails, so they stay small without
    the CSS; a test now checks for them. The user confirmed it looks
    good.

## 2026-10-04 — Product images: design interview and handoff

### Prompts

1. `/grill-me` with: "We need to add available product images to our
   website. The images are locateed in the product-images folder within our
   thoughttronix-store repository. The images are labeled with the products
   they are associated with. We need to make sure that the display is
   consistent across the catalog and that pages do not slow down. Every
   product must display either its uploaded image when one is available, or
   the existing placeholder. Missing files and broken image icons are
   unacceptable. Employees will also need to upload product images through
   the back office. If an employee uploads an unusable file, reject it and
   explain in plain language why it was rejected."
2. (Q1, images per product) "1"
3. (Q2, keeping pages fast) "2"
4. (Q3, consistent frame) "2"
5. (Q4, a missing file on disk) "2"
6. (Q5, attaching the demo images) "1"
7. (Q6, which file goes with which product) "I agree witht the changed
   except 2. I want to use the text version for SyncRest."
8. (Q7, what counts as unusable) "2"
9. (Q8, old files on replace/delete) "2"
10. (Q9, where images appear) "2"
11. (Q10, saved file format) "1"
12. (Q11, alt text) "2"
13. (Q12, serving media with DEBUG off) "1"
14. (Q13, image files in tests) "A1 + B1"
15. (Q14, seed source file missing) "2"
16. `/handoff` with: "the next session implements the design we just agreed"
17. "add our session log to PROMPTS.md"

### Summary

- **Outcome:**
  - **Design interview (14 questions).** Before any question, the codebase
    was read: the placeholder logic (`Category.placeholder_image`), the
    two templates that show images, the 13 source PNGs (sizes, dimensions,
    and filenames that don't match product names exactly), the back-office
    form and its `StaffRequiredMixin` gate, and `seed`'s wipe. Settled:
    - **Storage:** one optional `ImageField` on `Product`; `media/`
      gitignored.
    - **Speed:** resize once on save to 1200 px max, WebP quality ~80,
      original discarded; `loading="lazy"` on catalog cards.
    - **Consistency:** a fixed 4:3 frame, `object-contain` on
      `bg-base-200`.
    - **Never broken:** a `Product.display_image_url` property that checks
      the file exists and falls back to the placeholder; generated alt text
      (`""` for placeholders).
    - **Uploads:** reject a file that isn't a real image, isn't
      JPEG/PNG/WebP, is over 10 MB, is under 600×450, or is over 40 MP,
      each with a plain-language message.
    - **Cleanup:** old files deleted in the model after commit; `seed`
      empties `media/products/`.
    - **Where shown:** catalog, detail, edit-form preview, cart and
      back-office list thumbnails; not order history or the dashboard.
    - **Seed:** an explicit name→file mapping for 12 products; warn and
      continue on a missing source file.
    - **Serving:** development only, documented in
      `docs/ARCHITECTURE.md`.
    - **Tests:** a throwaway `MEDIA_ROOT` per test, images generated with
      Pillow, one real-import `seed` test.
  - **Handoff:** the full design, mapping table, and placement guidance
    were written to `HANDOFF.md` for the next session to implement. No
    feature code was written and nothing was committed.
- **Deviations:**
  - **Q6:** the user overrode one of my three mapping recommendations,
    choosing `SyncRest GPT Text.png` over the recommended "No Text"
    version. The other two (MindSync, SoulSear Mark I only) were taken.
  - **Every other answer took the recommendation.**
  - The offered `plans/product-images.md` was not written; the user asked
    for a handoff instead, so `HANDOFF.md` is the only record of the
    design.
- **Sideways:**
  - **The user's uncommitted `config/urls.py` change breaks the app.** It
    serves `MEDIA_URL`/`MEDIA_ROOT`, but neither is defined in settings.
    Found while exploring, flagged, and recorded as the first fix in
    `HANDOFF.md`; not fixed this session.
  - **Two gaps in the agreed design were found mid-interview.**
    `seed`'s bulk `Product.objects.all().delete()` skips
    `Product.delete()`, so the Q8 cleanup wouldn't run on re-seed; I
    decided without asking that `_wipe()` empties `media/products/`.
    And the `DEBUG`-only media serving would show broken images with
    `DEBUG` off even when Q4's file check passes, which became Q12.

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
