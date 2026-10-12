# Architecture

## Deep modules

Exactly two deliberate deep modules, docstrings and type hints on every
public function: `orders/services.py` (`place_order`, which applies a
`coupon_code` via `coupon.evaluate()`) and `dashboard/queries.py` (the
dashboard's aggregations). Checkout's Apply preview and `place_order` share
`evaluate()`, so the price shown is the price paid.

## Access & roles

Roles are Django's own vocabulary: customers are plain users, employees are
`is_staff`, the admin is `is_superuser`. No role field, no Groups.
Marketing is staff holding the `coupons.manage_coupons` permission, granted
to each user directly.

## Email verification

`User.email_verified_at` (null = unverified) is the only verification flag;
`is_active` means "deactivated by staff" and nothing else. Sign-in refuses
an unverified email after the password check; blank-email accounts are
grandfathered in. Reset and alerts use only the verified address.

## Media files

Django serves uploaded product images only when `DEBUG` is on; production
must serve `MEDIA_ROOT` at `MEDIA_URL` itself.
