# PRD: The ThoughtTronix Store — Account Security Center

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

---

## Problem Statement

A ThoughtTronix account today is a username and a password, and nothing else. Signup deliberately asks for no email, so the store has no trusted way to reach a customer. A customer who forgets their password has no way back into their account, their order history, or their saved addresses. A customer who suspects someone else knows their password has no way to change it. And if someone did change it, nobody would tell them.

Customers need a place to look after their own account: to know which email the store has for them, to change their password, and to recover their account when they're locked out. The store needs that email to be one the customer actually controls. Otherwise "we sent you a reset link" just sends account access to whoever owns a mistyped address.

## Solution

An **Account Security Center** for every signed-in user, plus email-backed account recovery.

- **Signup requires an email address, and the customer must verify it** by clicking a link sent to that address before they can sign in.
- **The security center** (`/accounts/security/`, linked as "Security" in the navbar) shows the account's email and whether it's verified, any pending email change, and a way to change the password. Each action has its own page and returns to the hub with a confirmation message.
- **Changing the email also requires verification.** The new address takes effect only after the customer clicks a link sent to it. Until then, the old address stays in force.
- **"Forgot password?"** on the sign-in page sends a time-limited reset link to the account's verified email.
- **Security alert emails** go to the customer's current verified address whenever their password changes or an email change is requested, so a hijacker can't quietly take over an account.

Accounts that existed before this feature keep working. Accounts that already had an email are treated as verified. The one account with no email is asked by the security center to add one.

## User Stories

**Visitor (not signed in)**

1. As a visitor, I want to give an email address when I sign up, so that the store can reach me and I can recover my account later.
2. As a visitor, I want signup to tell me when an email address is already in use (regardless of capitalization), so that I don't end up with a duplicate or look-alike account.
3. As a visitor, I want to see a "check your inbox" page after signing up, so that I know my account was created and what to do next.
4. As a visitor, I want to receive a verification email containing a single-use link, so that I can prove the address is mine.
5. As a visitor, I want clicking a valid verification link to verify my email and send me to sign in with a success message, so that I know my account is ready.
6. As a visitor, I want a clear message when a verification link is expired, already used, or invalid, so that I know to request a new one.
7. As a visitor who has not verified my email, I want sign-in to tell me (after I enter the correct password) that I must verify my email first and link me to resend the verification, so that I'm not left guessing why I can't get in.
8. As a visitor, I want to request a new verification email by entering my email address, so that I can recover from a lost or expired link.
9. As a visitor, I want the resend form to give the same reply whether or not an unverified account exists for that address, so that the form can't be used to check who has an account.
10. As a visitor who forgot my password, I want a "Forgot password?" link on the sign-in page, so that I can start account recovery.
11. As a visitor, I want to enter my email and receive a password reset link if my account's email is verified, so that only an address I've proven I control can take over my account.
12. As a visitor, I want the reset request page to give the same reply whether or not a matching account exists, so that it can't be used to check who has an account.
13. As a visitor, I want the reset link to expire after one hour and work only once, so that an old or leaked link can't be used against me.
14. As a visitor, I want to choose a new password from the reset link (subject to the store's password rules), then sign in with it, so that I regain access.

**Customer (signed in)**

15. As a customer, I want a "Security" link in the navbar, so that I can find my account security settings.
16. As a customer, I want a security center page that shows my email address and whether it's verified, so that I know where recovery emails will go.
17. As a customer with no email on file, I want the security center to warn me that I can't recover my account and invite me to add an email, so that I can fix it.
18. As a customer, I want to request a change of email from its own page by entering the new address and my current password, so that I can keep my contact address current and nobody using my unattended signed-in session can change it.
19. As a customer, I want the change to my email to take effect only after I click a verification link sent to the new address, so that a typo can't cut me off from account recovery.
20. As a customer, I want my current email to stay in force (for sign-in recovery and alerts) until the new one is verified, so that I'm never left without a working address.
21. As a customer, I want the security center to show a pending email change, so that I know I still need to check my new inbox.
22. As a customer, I want requesting another email change to replace any pending one and invalidate its link, so that only my latest request can complete.
23. As a customer, I want an email change rejected if the new address already belongs to another account, so that two accounts never share an email.
24. As a customer, I want to change my password from its own page by entering my current password and a new one twice, so that I can replace a password I think is compromised.
25. As a customer, I want to stay signed in on this device after changing my password while my other sessions are signed out, so that anyone else using my old password is kicked out.
26. As a customer, I want a security alert email at my verified address when my password is changed or reset, so that I'm warned if it wasn't me.
27. As a customer, I want a security alert email at my current verified address when someone requests a change to my email, so that a hijacker can't silently redirect my account recovery.

**Existing accounts**

28. As a customer who had an email before this feature, I want to keep signing in without verifying again, so that the upgrade doesn't lock me out.
29. As a customer who had no email before this feature, I want to keep signing in, so that I'm not locked out of an account I already use.
30. As a staff member, I want the security center to work for my account just as it does for customers, so that I can protect my own account too.

**Developer / demo**

31. As a developer, I want `seed` to create demo users whose emails are already verified, so that the demo logins keep working.
32. As a developer, I want the link lifetimes to be read from `.env` with working defaults, so that the app runs with no `.env` and the timeouts can be tuned.

## Implementation Decisions

**Foundation**

- Built on Django's built-in authentication: its password change and password reset views and forms, and its token generator. django-allauth is not used. The existing signup and sign-in views stay and are extended.
- Logic that only touches the user lives on the `User` model as methods (like the existing address-default methods), and views stay thin. Examples: sending a verification email, confirming a verification token, starting an email change, and sending security alerts. No new service module: these workflows involve a single model, and the architecture doc fixes the deep modules at two.

**Model and database (`accounts.User`)**

- New nullable `email_verified_at` timestamp. Null means "not verified." A date records when it was verified.
- New `pending_email` field (blank by default) holds a requested new address until it's verified.
- A database-level unique constraint on the lowercased email, applied only to non-blank emails. Blank emails stay allowed, so existing blank accounts don't collide with each other.
- `email` stays blank-allowed at the model level. Signup and the email-change form are where an email is required.
- `is_active` is **not** used for verification. It keeps meaning "deactivated by staff" only, so a verification link can never reactivate a deactivated account.
- A data migration sets `email_verified_at` for every existing user with a non-blank email (grandfathering). Users with a blank email stay unverified and blank.

**Sign-in rule**

- The sign-in form's `confirm_login_allowed` hook refuses accounts that have an email but no `email_verified_at`, with a message that points to the resend-verification page.
- That hook runs only after the password has been checked, so the "verify first" message is shown only to someone who knows the password.
- Accounts with a blank email (only the grandfathered one) are allowed to sign in.
- Sign-in stays by username. Email is for verification, recovery, and alerts.

**Signup**

- The signup form adds a required email field. Its validation rejects an address that matches any existing account's email, case-insensitively, with a clear "already in use" error. (Unlike the reset and resend forms, signup reveals that the address has an account. That trade-off was accepted.)
- On success, the account is created unverified, a verification email is sent, and the customer is redirected to a "check your inbox" page.
- No automatic sign-in after signup or after verification, which matches the existing decision that new users sign in themselves.

**Verification tokens and links**

- Verification links use a subclass of Django's token generator whose hash includes the email, pending email, and `email_verified_at`. A link therefore stops working once it's used, and also when a newer email change replaces it.
- Links carry the user id encoded the way Django's reset links do, plus the token.
- **Signup verification:** a valid link sets `email_verified_at` and redirects to sign-in with a success message.
- **Email-change verification:** a valid link re-checks that no other account now holds the address, moves `pending_email` into `email`, clears `pending_email`, sets `email_verified_at`, and redirects with a success message. If the address was taken in the meantime, the change is refused with a message.
- Invalid, expired, or used links render a friendly error page with a link to resend.
- **Link lifetimes:** reset links expire after **1 hour** (Django's `PASSWORD_RESET_TIMEOUT`). Verification links (signup and email change) expire after **3 days** (a new verification-timeout setting). Both are read from `.env` via environs with those defaults.

**Resend verification**

- A public form takes an email address. If an account has that email and isn't verified, a fresh verification email is sent.
- The form always shows the same neutral confirmation, so it doesn't reveal whether an account exists.

**Password reset**

- Django's four-step reset flow: request, "sent", set-new-password, "complete". Each step gets a DaisyUI-styled template.
- A "Forgot password?" link is added to the sign-in page.
- The reset request form only finds accounts whose email is **verified**. Matching is case-insensitive, and the account must still be active and have a usable password. Django's neutral "if an account exists, we sent a link" behavior is kept.
- Completing a reset sends a security alert email to the verified address.

**Password change**

- Django's password change view and form, styled in DaisyUI: current password, new password, and confirmation, validated by the store's existing password validators.
- Django keeps the current session signed in and invalidates the account's other sessions. That built-in behavior is relied on, not reimplemented.
- On success, redirect to the security center with a flash message and send a security alert email.

**Email change**

- Its own page and form. The new address must not be in use by any other account (case-insensitive), and it must differ from the current email.
- The form requires the current password, checked the same way Django's password change form checks it. A wrong password is a form error, and nothing is saved or sent.
- On success: store the address in `pending_email`, send a verification email to the **new** address, send a security alert to the **current** verified address (if there is one), and redirect to the hub with a "check your new inbox" message.
- The grandfathered account with a blank email adds an email through this same flow. No alert is sent because there's no current address.

**Security center hub**

- A login-required page with an **Email** card and a **Password** card.
  - The Email card shows the current email with a verified badge, any pending change, and a link to change it. When no email is on file, it shows a warning explaining that account recovery is unavailable until one is added and verified.
  - The Password card links to the password change page.
- A "Security" link in the navbar beside "Addresses", shown to all signed-in users.
- Each page follows the frontend conventions: it extends the base template, has at most one `btn-primary`, and uses named URLs under the `accounts:` namespace. Email change and password change each have their own page and return to the hub with a flash message.

**Email**

- All email keeps going through the console backend already configured. Messages print to the terminal in development.
- Email bodies (verification, email-change verification, password reset, and the security alerts) are plain-text templates in the accounts template directory.
- Each alert names the action, gives the time, and tells the customer to reset their password if the action wasn't theirs.

**Seed and admin**

- `seed` marks its demo users' emails as verified.
- Staff can still edit a user's email in the Django admin. That path skips verification by design.

## Out of Scope

- **Sign-in throttling and lockout** (limiting failed password attempts, and rate-limiting reset or resend emails). Considered and deferred.
- **Recent sign-in activity** (a sign-in history with time, browser, and IP). Considered and deferred.
- **Signing in by email** instead of username.
- **Two-factor authentication**, passkeys, and social or third-party sign-in.
- **Real email delivery** (SMTP or a provider). The console backend stays.
- **Account deletion** and data export.
- **A "sign out all other devices" button.** Other sessions end only as a side effect of a password change or reset.
- **Cancelling a pending email change** other than by requesting a new one.
- **Forcing grandfathered accounts to re-verify**, or forcing the blank-email account to add an email. It's prompted, not required.
- **Staff-facing tools** for viewing or managing customers' verification status, beyond the existing Django admin.

## Further Notes

- **Supersedes** core-platform user story 6 ("sign up … with a username and password (no email)") and the signup form's "No email" docstring rationale.
- **Known gap:** a customer whose email is unverified can't use "Forgot password". They must verify first, through resend. That's intentional: reset should never bypass verification.
- **Known gap:** the grandfathered account with no email can't recover a lost password until it adds and verifies an email.
- **Enumeration posture:** the reset and resend forms are neutral, but signup and email change reveal "already in use." This is accepted, because unique emails can't be enforced without saying so.
- **Testing:** follow `docs/TESTING.md`. Assert on sent mail with Django's test outbox, extract links from email bodies, and cover these paths: expired, tampered, used, and superseded tokens; the address being taken between the email-change request and its confirmation; the grandfathering migration; and the sign-in rule for verified, unverified, and blank-email accounts. Control time when testing expiry.
- **Docs to update on implementation:** `docs/ARCHITECTURE.md` (the verification model, and that `is_active` stays "deactivated" only) and `CLAUDE.md` (what the `accounts/` app now contains).
