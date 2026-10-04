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
