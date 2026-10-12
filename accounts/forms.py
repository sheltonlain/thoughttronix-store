from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

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
    """The stock authentication form, dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class ChangePasswordForm(PasswordChangeForm):
    """Django's password change form — current password, then the new one
    twice, checked by the store's password validators — in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


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
