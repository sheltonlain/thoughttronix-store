from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.detail import SingleObjectMixin

from .forms import (
    AddressForm,
    ChangePasswordForm,
    ResetPasswordForm,
    SetNewPasswordForm,
    SignInForm,
    SignupForm,
)
from .models import Address


class SignupView(SuccessMessageMixin, CreateView):
    """Create a customer account, then hand off to the login page.

    New users sign in themselves — auto-login after signup is left as a
    student exercise.
    """

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    success_message = "Account created — you can now sign in."


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SignInForm


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response


# --- The security center -----------------------------------------------------


class SecurityView(LoginRequiredMixin, TemplateView):
    """The account's security hub: its email and password, each with its
    own card. The same page for customers and staff."""

    template_name = "accounts/security.html"


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    """Change the password, then alert the verified address.

    Django's view keeps this session signed in and, because the session
    hash changes with the password, signs out every other session.
    """

    form_class = ChangePasswordForm
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:security")
    success_message = "Password changed. Your other sessions have been signed out."

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.send_security_alert("Your password was changed")
        return response


# --- Forgot password -----------------------------------------------------------
#
# Django's four-step reset flow: request, sent, set new password, complete.
# Links last PASSWORD_RESET_TIMEOUT and die once the password changes.


class ResetPasswordView(PasswordResetView):
    """Request a reset link. Always lands on the same "sent" page, whether
    or not a verified account matched."""

    form_class = ResetPasswordForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class ResetPasswordDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class ResetPasswordConfirmView(PasswordResetConfirmView):
    """Set a new password from the emailed link, then alert the verified
    address. The customer signs in themselves afterwards."""

    form_class = SetNewPasswordForm
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        form.user.send_security_alert("Your password was reset")
        return response


class ResetPasswordCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


# --- The address book --------------------------------------------------------
#
# Customers manage their saved addresses here; checkout reads from the
# same book. Private pages, so pk URLs per the URL conventions.


class OwnAddressesMixin(LoginRequiredMixin):
    """Addresses are always fetched through the owner — never by bare pk."""

    def get_queryset(self):
        return Address.objects.address_book(self.request.user)


class AddressListView(OwnAddressesMixin, ListView):
    """The address book: defaults first, then newest."""

    template_name = "accounts/address_list.html"
    context_object_name = "addresses"

    def get_queryset(self):
        return super().get_queryset().order_by("label")


class AddressCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Add an address; the first one saved also becomes the default."""

    model = Address
    form_class = AddressForm
    template_name = "accounts/address_form.html"
    success_url = reverse_lazy("accounts:addresses")
    success_message = "Address saved."

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        self.request.user.fill_empty_defaults(self.object)
        return response


class AddressUpdateView(OwnAddressesMixin, SuccessMessageMixin, UpdateView):
    form_class = AddressForm
    template_name = "accounts/address_form.html"
    success_url = reverse_lazy("accounts:addresses")
    success_message = "Address saved."


class AddressDeleteView(OwnAddressesMixin, SuccessMessageMixin, DeleteView):
    """Delete an address. A default pointing at it clears itself
    (``SET_NULL``); past orders keep their own copy."""

    context_object_name = "address"
    template_name = "accounts/address_confirm_delete.html"
    success_url = reverse_lazy("accounts:addresses")
    success_message = "Address deleted."


class SetDefaultAddressView(OwnAddressesMixin, SingleObjectMixin, View):
    """POST-only: make an address the default shipping or billing one."""

    kind = None  # "shipping" or "billing", set by the subclasses

    def post(self, request, pk):
        address = self.get_object()
        request.user.set_default_address(self.kind, address)
        messages.success(request, f"Default {self.kind} address updated.")
        return redirect("accounts:addresses")


class SetDefaultShippingView(SetDefaultAddressView):
    kind = "shipping"


class SetDefaultBillingView(SetDefaultAddressView):
    kind = "billing"
