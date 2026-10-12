from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.urls import reverse
from django.utils.html import format_html

from .models import Address, User


class SignupForm(UserCreationForm):
    """Django's stock signup fields plus a required email.

    The email is how the store verifies the customer, recovers the account,
    and sends security alerts, so it must be one no other account uses.
    (Saying "already in use" reveals the address has an account; unique
    emails can't be enforced without it.) The widgets carry DaisyUI
    classes because plain Django forms own their own styling here.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank is allowed on the model for grandfathered accounts only.
        self.fields["email"].required = True
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email address is already in use.")
        return email


class SignInForm(AuthenticationForm):
    """The stock authentication form, dressed in DaisyUI, that refuses an
    account whose email isn't verified yet.

    Django calls ``confirm_login_allowed`` only after the password checks
    out, so "verify first" is never shown to someone guessing passwords.
    Blank-email accounts (grandfathered) still sign in.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.email and not user.email_verified_at:
            raise forms.ValidationError(
                format_html(
                    "Please verify your email before signing in. Lost the link? "
                    '<a href="{}" class="link">Send a new one</a>.',
                    reverse("accounts:resend_verification"),
                ),
                code="unverified",
            )


class ResendVerificationForm(forms.Form):
    """Ask for a fresh verification link by email address.

    Sends only to an unverified account with that email, matched
    case-insensitively, but the view replies the same way regardless, so
    the form can't be used to find out who has an account.
    """

    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "input w-full"}))

    def save(self, request):
        """Email a new link to the unverified account with this address, if
        there is one."""
        user = User.objects.filter(
            email__iexact=self.cleaned_data["email"], email_verified_at__isnull=True
        ).first()
        if user is not None:
            user.send_verification_email(request)


class ChangePasswordForm(PasswordChangeForm):
    """Django's password change form — current password, then the new one
    twice, checked by the store's password validators — in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class ChangeEmailForm(forms.Form):
    """Request a new email address, confirmed with the current password.

    The password stops anyone at an unattended signed-in session from
    redirecting the account's recovery. The address must differ from the
    current one and belong to no other account, ignoring capitalization.
    """

    email = forms.EmailField(
        label="New email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if email.lower() == self.user.email.lower():
            raise forms.ValidationError("That's already your email address.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email address is already in use.")
        return email

    def clean_password(self):
        # Checked the way Django's PasswordChangeForm checks the old one.
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(
                "Your password was entered incorrectly. Please enter it again.",
                code="password_incorrect",
            )
        return password

    def save(self, request):
        self.user.request_email_change(self.cleaned_data["email"], request)


class ResetPasswordForm(PasswordResetForm):
    """Django's reset request form, limited to verified emails.

    Django already matches case-insensitively and skips inactive accounts
    and unusable passwords; this only adds the verification rule, so a
    reset never goes to an address the customer hasn't proven they own.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"

    def get_users(self, email):
        return (user for user in super().get_users(email) if user.email_verified_at)


class SetNewPasswordForm(SetPasswordForm):
    """Django's set-new-password form — the new password twice, checked by
    the store's password validators — in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class AddressForm(forms.ModelForm):
    """Add or edit a saved address. The model's fields carry the rules —
    the same state list and ZIP validator checkout uses."""

    class Meta:
        model = Address
        fields = ["label", *Address.PARTS]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"
