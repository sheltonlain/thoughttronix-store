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
