"""Access-control mixins for the back office.

Per the PRD, back-office views gate on ``is_staff`` via mixins — roles
are Django's own vocabulary, nothing else.
"""

from django.contrib.auth.mixins import UserPassesTestMixin


class StaffRequiredMixin(UserPassesTestMixin):
    """Allow staff only: anonymous users are redirected to the login
    page; signed-in non-staff get 403 (``AccessMixin``'s default split)."""

    def test_func(self):
        return self.request.user.is_staff


class CouponManagerRequiredMixin(StaffRequiredMixin):
    """Staff holding ``coupons.manage_coupons`` — Marketing, and superusers.

    The permission is granted to each user directly (no Groups), so
    Marketing is a set of staff, not a role.
    """

    def test_func(self):
        return super().test_func() and self.request.user.has_perm(
            "coupons.manage_coupons"
        )
