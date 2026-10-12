# Plan: Account Security Center

> Source PRD: `prd/account-security.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: `accounts`. No new app and no new service module. Workflows
  that touch only the user (sending verification, confirming a token,
  starting an email change, sending alerts) are methods on `User`; views
  stay thin.
- **Foundation**: Django's built-in auth: its password change and reset
  views and forms, and its token generator. No django-allauth. The existing
  signup and sign-in views are extended, not replaced.
- **Models** (`accounts.User`):
  - `email_verified_at`: nullable timestamp; null means "not verified".
  - `pending_email`: blank by default; holds a requested address until it
    is verified.
  - A database unique constraint on the lowercased email, applied only to
    non-blank emails.
  - `email` stays blank-allowed at the model level; signup and the email
    change form are where it is required.
  - `is_active` is not used for verification; it keeps meaning
    "deactivated by staff" only.
- **Sign-in rule**: the sign-in form's `confirm_login_allowed` refuses an
  account that has an email but no `email_verified_at`. It runs after the
  password check. Blank-email accounts are allowed. Sign-in stays by
  username.
- **Tokens**: verification links use a subclass of Django's token generator
  whose hash includes `email`, `pending_email`, and `email_verified_at`, so
  a link dies once used or once a newer email change replaces it. Links
  carry a base64 user id plus the token, like Django's reset links.
- **Link lifetimes**: reset links last 1 hour (`PASSWORD_RESET_TIMEOUT`);
  verification links last 3 days (a new verification-timeout setting). Both
  are read from `.env` via environs with those defaults.
- **URLs** (all named under the `accounts:` namespace, mounted at
  `/accounts/`):
  - `security/`: the security center hub (login required)
  - `security/password/`: password change
  - `security/email/`: email change request
  - `security/email/confirm/<uidb64>/<token>/`: email change confirmation
  - `signup/sent/`: "check your inbox"
  - `verify/<uidb64>/<token>/`: signup email verification
  - `verify/resend/`: resend verification (public)
  - `password-reset/`, `password-reset/sent/`, `reset/<uidb64>/<token>/`,
    `reset/done/`: Django's four-step reset flow
- **Email**: the existing console backend. Bodies are plain-text templates
  in the accounts template directory. Every alert names the action, gives
  the time, and says to reset the password if it wasn't you.
- **Frontend**: every page extends `base.html`, has at most one
  `btn-primary`, and is styled with Tailwind and DaisyUI only. Actions return
  to the hub with a flash message.
- **Testing**: per `docs/TESTING.md`, plain fixtures in `conftest.py`.
  Assert on Django's test outbox, extract links from email bodies, and
  control time for expiry. The suite is green at every phase boundary.

---

## Phase 1: Security center and grandfathering

**User stories**: 15, 16, 17, 28, 29, 30, 31

### What to build

The read-only spine of the feature. Add `email_verified_at` and
`pending_email` to `User`, plus a data migration that stamps
`email_verified_at` on every existing user with a non-blank email.
Blank-email users stay unverified and blank. `seed` marks its demo users
verified. A login-required hub at `/accounts/security/` shows an **Email**
card: the current address with a verified badge, or a warning that account
recovery is unavailable until an email is added and verified. It also shows
a **Password** card, a placeholder until Phase 2 adds the change page. A
"Security" link sits beside "Addresses" in the navbar for every signed-in
user, staff included.

### Acceptance criteria

- [x] Migrations add both fields; the data migration verifies existing
      users with an email and leaves blank-email users untouched (tested).
- [x] `seed` produces demo users whose emails are verified.
- [x] The hub requires login and shows the email with a verified badge for
      a verified user.
- [x] A user with no email sees the "recovery unavailable" warning.
- [x] A staff user sees the same hub as a customer.
- [x] The navbar shows "Security" to signed-in users only.
- [x] Existing sign-in behavior is unchanged; the full suite passes.

---

## Phase 2: Password change and security alerts

**User stories**: 24, 25, 26 (change)

### What to build

From the hub's Password card, a page using Django's password change view
and form, styled in DaisyUI, that asks for the current password and the new
one twice. It is validated by the store's existing password validators.
Django keeps the current session signed in and ends the others; that
behavior is relied on, not reimplemented. On success the customer returns
to the hub with a flash message, and a security alert email goes to their
verified address if they have one. This phase establishes the plain-text
email templates and the `User` alert method that later phases reuse.

### Acceptance criteria

- [x] A wrong current password, mismatched new passwords, or a password
      that fails the validators is shown as a form error, with no change
      and no email.
- [x] Success redirects to the hub with a flash message; the user stays
      signed in.
- [x] After a change, another client's session for the same user is signed
      out.
- [x] One alert email goes to the verified address, naming the action and
      the time and telling the customer to reset their password if the
      change wasn't theirs.
- [x] A blank-email user can change their password, and no email is sent.

---

## Phase 3: Forgot password

**User stories**: 10, 11, 12, 13, 14, 26 (reset), 32 (reset timeout)

### What to build

A "Forgot password?" link on the sign-in page leads into Django's four-step
reset flow (request, sent, set new password, complete), with each step in
a DaisyUI template. The request form finds only accounts whose email is
**verified**, matching case-insensitively. The account must also be active
and have a usable password. The reply is the same whether or not an account
matched. `PASSWORD_RESET_TIMEOUT` is read from `.env` with a 1-hour
default. Completing a reset sends a security alert to the verified address.

### Acceptance criteria

- [x] The sign-in page links to the reset request page.
- [x] A verified email (in any capitalization) receives a reset link; an
      unverified, unknown, inactive, or unusable-password account receives
      nothing, and the page reads the same in every case.
- [x] The link sets a new password, subject to the store's validators, and
      the customer can then sign in with it.
- [x] The link fails after one use and after one hour (time controlled in
      tests).
- [x] Completing a reset sends a security alert email.
- [x] The app runs with no `.env`; the timeout can be overridden from it.

---

## Phase 4: Signup with a verified email

**User stories**: 1, 2, 3, 4, 5, 6, 32 (verification timeout)

### What to build

Signup gains a required email field that rejects any address already on an
account, case-insensitively, with an "already in use" error. A migration
adds the lowercased-email unique constraint for non-blank emails. Before
applying it, check existing data for addresses that collide when case is
ignored. A new account is created unverified, a verification email with a
single-use link is sent, and the customer lands on a "check your inbox"
page instead of being signed in. The verification token generator lives
here. A valid link sets `email_verified_at` and redirects to sign-in with a
success message. An expired, used, or tampered link shows a friendly error
page. The verification timeout setting is read from `.env` with a 3-day
default. The signup form's "No email" docstring is replaced, since this
supersedes core-platform story 6.

### Acceptance criteria

- [x] Signup without an email fails; an email matching an existing one in
      any capitalization fails with "already in use".
- [x] The database rejects a second account with the same email in
      different capitalization; blank emails still coexist.
- [x] Successful signup creates an unverified, active user, sends one
      verification email, and redirects to the "check your inbox" page.
- [x] The emailed link verifies the account and redirects to sign-in with
      a success message.
- [x] Used, tampered, and expired (time controlled) links show the error
      page and change nothing.
- [x] Existing signup tests are updated to the new form; the suite passes.

---

## Phase 5: Sign-in block and resend verification

**User stories**: 7, 8, 9

### What to build

Sign-in enforces verification through `confirm_login_allowed`. An account
with an email but no `email_verified_at` is refused after the correct
password, with a message that links to the resend page. Blank-email
accounts still sign in. A public resend page takes an email address. If an
unverified account has that email, a fresh verification email is sent. The
reply is the same neutral confirmation either way. The Phase 4 error page
now links here. `docs/ARCHITECTURE.md` gains the verification model and the
rule that `is_active` means "deactivated by staff" only.

### Acceptance criteria

- [x] A verified user signs in; a blank-email user signs in; an unverified
      user with the correct password is refused with a link to resend.
- [x] An unverified user with a wrong password sees only the normal
      invalid-credentials error.
- [x] Verification never changes `is_active`; a deactivated user stays
      unable to sign in after verifying.
- [x] Resend sends a new link to an unverified account (matched
      case-insensitively) and sends nothing for verified or unknown
      addresses; the response is the same in every case.
- [x] The bad-link error page links to resend.
- [x] `docs/ARCHITECTURE.md` is updated.

---

## Phase 6: Email change

**User stories**: 18, 19, 20, 21, 22, 23, 27

### What to build

From the hub's Email card, an email change page asks for the new address
and the current password. The password is checked the way Django's password
change form checks it. The new address must differ from the current one and
must not belong to any other account (case-insensitive). On success the
address is stored in `pending_email`, a verification link goes to the
**new** address, and a security alert goes to the **current** verified
address, if there is one. The customer then returns to the hub with a
"check your new inbox" message, and the hub shows the pending change. A new
request replaces the pending one and invalidates its link. The confirmation
link re-checks that the address is still free, moves `pending_email` into
`email`, clears `pending_email`, sets `email_verified_at`, and shows a
success message. If the address was taken in the meantime, the change is
refused with a message. Until confirmation, the old email keeps working for
reset and alerts. The blank-email account adds an email through this same
flow, with no alert. `CLAUDE.md` is updated to describe what `accounts/`
now contains.

### Acceptance criteria

- [ ] A wrong password, an unchanged address, or an address held by another
      account (any capitalization) is a form error: nothing is saved and
      nothing is sent.
- [ ] A valid request sets `pending_email`, emails the new address a link,
      emails the old address an alert, and the hub shows the pending
      change.
- [ ] While the change is pending, password reset still goes to the old
      address.
- [ ] A second request supersedes the first; the first link no longer
      works.
- [ ] Confirming swaps the address in and marks it verified; reusing the
      link fails.
- [ ] If another account claims the address between the request and its
      confirmation, the confirmation is refused and the email is unchanged.
- [ ] A blank-email user can add an email this way, and no alert is sent.
- [ ] `CLAUDE.md` is updated.
