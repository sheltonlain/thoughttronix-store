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
