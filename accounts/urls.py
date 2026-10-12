from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("signup/sent/", views.SignupSentView.as_view(), name="signup_sent"),
    path(
        "verify/resend/",
        views.ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path(
        "verify/<uidb64>/<token>/",
        views.VerifyEmailView.as_view(),
        name="verify_email",
    ),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path("security/", views.SecurityView.as_view(), name="security"),
    path(
        "security/password/",
        views.ChangePasswordView.as_view(),
        name="password_change",
    ),
    path(
        "password-reset/",
        views.ResetPasswordView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        views.ResetPasswordDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        views.ResetPasswordConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        views.ResetPasswordCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("addresses/", views.AddressListView.as_view(), name="addresses"),
    path("addresses/add/", views.AddressCreateView.as_view(), name="address_add"),
    path(
        "addresses/<int:pk>/edit/",
        views.AddressUpdateView.as_view(),
        name="address_edit",
    ),
    path(
        "addresses/<int:pk>/delete/",
        views.AddressDeleteView.as_view(),
        name="address_delete",
    ),
    path(
        "addresses/<int:pk>/default-shipping/",
        views.SetDefaultShippingView.as_view(),
        name="address_default_shipping",
    ),
    path(
        "addresses/<int:pk>/default-billing/",
        views.SetDefaultBillingView.as_view(),
        name="address_default_billing",
    ),
]
