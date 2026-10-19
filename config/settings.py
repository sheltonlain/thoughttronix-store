"""Django settings for the ThoughtTronix Store.

Values are read from a `.env` file at the project root via environs.
Every setting has a working default: the app runs with no `.env` present.

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

from pathlib import Path

from environs import env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env.read_env(BASE_DIR / ".env", recurse=False)

# SECURITY WARNING: the default is for development only —
# set SECRET_KEY in .env for anything beyond a laptop.
SECRET_KEY = env.str(
    "SECRET_KEY",
    default="django-insecure-your-thoughts-our-business-dev-only",
)

DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",
    # Third-party
    "django_tailwind_cli",
    # Local
    "accounts",
    "products",
    "orders",
    "coupons",
    "dashboard",
    "wishlist",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "orders.context_processors.cart",
            ],
        },
    },
]

# Widget templates resolve through TEMPLATES, so a project template can
# restyle a widget (templates/products/widgets/). Needs "django.forms".
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Authentication
# Customers are plain users; employees are is_staff; the admin is is_superuser.

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "products:catalog"

LOGOUT_REDIRECT_URL = "products:catalog"

# Seconds a password reset link stays valid: one hour by default.
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=60 * 60)

# Seconds an email verification link stays valid: three days by default.
EMAIL_VERIFICATION_TIMEOUT = env.int(
    "EMAIL_VERIFICATION_TIMEOUT", default=3 * 24 * 60 * 60
)

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

STATICFILES_DIRS = [BASE_DIR / "assets"]


# Media (staff-uploaded product images)
# Served by Django only when DEBUG is on; production must serve MEDIA_ROOT
# at MEDIA_URL itself (see docs/ARCHITECTURE.md).

MEDIA_URL = "media/"

MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")


# Tailwind CSS + DaisyUI (django-tailwind-cli, standalone binary — no Node.js)

TAILWIND_CLI_USE_DAISY_UI = True

# Pinned tailwind-cli-extra release (bundles Tailwind CSS + DaisyUI).
TAILWIND_CLI_VERSION = "2.9.2"

TAILWIND_CLI_SRC_CSS = "assets/css/source.css"


# Email — console only; real mail is out of scope for the core. The backend
# prints decoded bodies so long links copy whole from the terminal.

EMAIL_BACKEND = "accounts.mail.ReadableConsoleEmailBackend"
DEFAULT_FROM_EMAIL = env.str(
    "DEFAULT_FROM_EMAIL", default="ThoughtTronix <security@thoughttronix.example>"
)
