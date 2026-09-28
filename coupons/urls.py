from django.urls import path

from . import views

app_name = "coupons"

urlpatterns = [
    # Back office — Marketing-only, pk URLs per the URL conventions.
    path(
        "backoffice/coupons/",
        views.ManageCouponListView.as_view(),
        name="manage_coupons",
    ),
    path(
        "backoffice/coupons/add/",
        views.ManageCouponCreateView.as_view(),
        name="manage_coupon_create",
    ),
    path(
        "backoffice/coupons/<int:pk>/edit/",
        views.ManageCouponUpdateView.as_view(),
        name="manage_coupon_update",
    ),
    path(
        "backoffice/coupons/<int:pk>/delete/",
        views.ManageCouponDeleteView.as_view(),
        name="manage_coupon_delete",
    ),
    path(
        "backoffice/coupons/<int:pk>/archive/",
        views.ManageCouponArchiveView.as_view(),
        name="manage_coupon_archive",
    ),
    path(
        "backoffice/coupons/<int:pk>/restore/",
        views.ManageCouponRestoreView.as_view(),
        name="manage_coupon_restore",
    ),
]
