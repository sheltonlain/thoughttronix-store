# Handoff — Product images

**Next session's job:** implement the product-images design below. The design
was settled in a `/grill-me` interview (14 questions, all answered). No code
has been written yet, and no plan file exists. This document is the only
record of the decisions.

Read first: `CLAUDE.md`, `docs/ARCHITECTURE.md` (touching permissions/seed),
`docs/FRONTEND.md` (templates/views), `docs/TESTING.md` (tests).

## Requirements (from the user)

- Show the images in `product-images/` (repo root) on their products.
- Display consistent across the catalog; pages must not slow down.
- Every product shows its uploaded image or the existing placeholder — never a
  missing file or broken-image icon.
- Staff upload product images in the back office; unusable files are rejected
  with a plain-language reason.

## Current state of the working tree (uncommitted, user's own changes)

- `pyproject.toml` / `uv.lock`: `pillow>=12.3.0` added.
- `config/urls.py`: serves `MEDIA_URL` from `MEDIA_ROOT` when `DEBUG`.
  **`config/settings.py` does not define `MEDIA_URL`/`MEDIA_ROOT` yet, so this
  currently breaks** — fix first.
- `product-images/`: 13 untracked PNGs (~1.7–2.5 MB each, RGB, mostly
  ~1122×1402 portrait; `MindSync Duo.png` is 1536×1024).

## Relevant existing code

- `products/models.py` — `Category.placeholder_image` returns a *static* path
  (`images/placeholders/<slug>.svg` or `default.svg`). All placeholders are
  400×300 (4:3), in `assets/images/placeholders/`.
- `templates/products/catalog.html:64` and `templates/products/detail.html:17`
  — the only `<img>` tags today; both use `{% static product.category.placeholder_image %}`.
- `products/forms.py` — `ProductForm(StyledModelForm)`; `StyledModelForm`
  assigns DaisyUI classes per widget type in `__init__` (a file input would
  currently fall into the `input w-full` branch — give it `file-input w-full`).
- `products/views.py` — back-office product CRUD; all gated by
  `StaffRequiredMixin` (any staff may manage products; no roles/groups).
- `products/management/commands/seed.py` — `CATALOG` dict of products;
  `_wipe()` (line ~583) bulk-deletes with `Product.objects.all().delete()`,
  which skips `Product.delete()`.
- Back-office/cart templates to touch: `templates/products/manage_products.html`,
  the product create/update template, `templates/orders/partials/_cart_contents.html`.

## Agreed design (decision → choice)

1. **Storage:** one optional `image` `ImageField` on `Product` (no gallery).
   Add `MEDIA_URL`/`MEDIA_ROOT` to settings (with working defaults, per
   CLAUDE.md); add `media/` to `.gitignore`. Migration required.
2. **Performance:** on save, resize to max 1200 px on the long side,
   re-encode, discard the original. One file serves cards and detail page.
   Add `loading="lazy"` on catalog cards.
3. **Consistency:** fixed 4:3 frame in templates (`aspect-[4/3]`),
   `object-contain`, `bg-base-200` behind it. No cropping.
4. **Never broken:** `Product.display_image_url` returns the image URL only if
   `image` is set **and** `image.storage.exists(image.name)`; otherwise the
   category placeholder's static URL. Templates use only this property.
5. **Demo import:** `seed` imports from `product-images/` through an explicit
   product-name → filename mapping, using the same processing code as uploads.
6. **Mapping** (12 products; all others keep placeholders):

   | Product | File |
   |---|---|
   | Calm Collar | `Calm Collar GPT Man.png` |
   | CrowdCalm Array | `CrowdCalm Array No Text.png` |
   | DreamWeaver | `DreamWeaver Matrix GPT 3.png` |
   | Hush | `Hush GPT No Text.png` |
   | MindSync | `MindSync GPT 2.png` |
   | MindSync Duo | `MindSync Duo.png` |
   | MoodSet | `MoodSet GPT No Text.png` |
   | RecallPro | `RecallPro.png` |
   | Seraphine | `Seraphine GPT Text.png` |
   | SoulSear Mark I | `SoulSear No Text.png` |
   | SyncRest | `SyncRest GPT Text.png` (user chose the *Text* version) |
   | Veil | `Veil GPT Text.png` |

   `SyncRest GPT No Text.png` is unused. SoulSear Mark II / Tactical Core keep
   the placeholder.
7. **Upload validation** (in the form; each with a plain-language message;
   limits as named constants):
   - A. really an image (Pillow opens/verifies it, extension ignored)
   - B. format JPEG, PNG, or WebP only (reject GIF, SVG, HEIC, TIFF…)
   - C. ≤ 10 MB
   - D. ≥ 600 × 450 px
   - E. ≤ 40 megapixels (decompression-bomb guard)
   - (No aspect-ratio rule — `object-contain` handles shapes.)
   Messages should name the actual value, e.g. "This file is 24 MB. The limit
   is 10 MB…", "We accept JPEG, PNG, or WebP images. This file is a GIF."
8. **File cleanup:** in the model. `Product.save()` remembers the previous
   file; after a successful save, delete it if no longer referenced.
   `Product.delete()` deletes the image. Defer deletions with
   `transaction.on_commit`. Also: `seed._wipe()` empties `media/products/`
   (bulk delete bypasses the model). Form uses Django's `ClearableFileInput`
   (clear checkbox) plus a preview of the current image on the edit page.
9. **Where images appear:** catalog/category cards, product detail, back-office
   edit-form preview, **plus** thumbnails in the cart and back-office product
   list. Not in order history (orders snapshot `product_name`) or the dashboard.
10. **Format:** WebP, quality ~80, keep transparency. Filenames from the product
    slug, e.g. `products/veil.webp` (storage may add a suffix on replace — fine).
11. **Alt text:** `Product.display_image_alt` → `"<name> product photo"` for a
    real image, `""` for a placeholder (decorative; name is in the card title).
12. **Serving:** keep the `DEBUG`-only media serving. Add a "Media files"
    section to `docs/ARCHITECTURE.md` stating production must serve
    `MEDIA_ROOT` at `MEDIA_URL`.
13. **Tests:** autouse fixture in root `conftest.py` setting
    `settings.MEDIA_ROOT = tmp_path`; a fixture that builds images in memory
    with Pillow (size/format parameters). One test per rejection rule, tests
    for `display_image_url` fallback (no image, missing file), cleanup on
    replace/clear/delete, and one `seed` test asserting the 12 mapped products
    get images.
14. **Missing seed source file:** warn (styled warning naming file + product)
    and continue; that product keeps its placeholder.

## Placement guidance (per CLAUDE.md conventions)

- Resize/encode code: a model method or small helper in `products/` shared by
  form-save and seed (logic in models; views stay thin).
- Validation: form `clean_image()` (forms own their validation).
- Templates: Tailwind + DaisyUI classes only; no JS beyond HTMX.

## Suggested skills

- `/code-review` — review the diff once implementation is done.
- `/security-review` — file uploads are an attack surface (format spoofing,
  decompression bombs); worth a pass before committing.
- `/simplify` — tidy the processing/cleanup code after it works.
- `/run` — launch the dev server and visually confirm catalog, detail, cart,
  back-office list, and the upload-rejection messages.

## Finishing steps

- `uv run python manage.py makemigrations` then `migrate`; `uv run python manage.py seed`.
- `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
- Append an entry to `PROMPTS.md` (append only; never rewrite history).
- Commit only when the user asks.
