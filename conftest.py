"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from accounts.models import Address
from orders.models import Cart, CartItem
from products.models import Category, Product, Tag


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Every test writes uploaded files to its own throwaway MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


@pytest.fixture
def make_image():
    """Build an image upload in memory with Pillow.

    ``size`` and ``fmt`` pick the picture; ``name`` is the uploaded
    filename (its extension needn't match); ``mode`` RGBA gives a
    half-transparent fill; ``padding`` appends junk bytes to inflate it.
    """

    def make(size=(800, 600), fmt="PNG", name=None, mode="RGB", padding=0):
        buffer = BytesIO()
        color = (0, 128, 128, 128) if mode == "RGBA" else "teal"
        Image.new(mode, size, color).save(buffer, fmt)
        name = name or f"photo.{fmt.lower()}"
        return SimpleUploadedFile(name, buffer.getvalue() + b"\0" * padding)

    return make


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(
        username="customer", password="customer123"
    )


@pytest.fixture
def verified_customer(db):
    """A customer whose email is on file and verified — unlike ``customer``,
    who has no email at all."""
    return get_user_model().objects.create_user(
        username="verified",
        password="verified123",
        email="verified@example.com",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="employee",
        password="employee123",
        is_staff=True,
        job_title="Junior Thought Curator",
    )


@pytest.fixture
def marketing_user(db):
    """Staff with the one extra permission coupons need — granted to the
    user directly, since the project uses no Groups."""
    from django.contrib.auth.models import Permission

    user = get_user_model().objects.create_user(
        username="marketing",
        password="marketing123",
        is_staff=True,
        job_title="Director of Persuasion",
    )
    user.user_permissions.add(
        Permission.objects.get(
            codename="manage_coupons", content_type__app_label="coupons"
        )
    )
    return user


@pytest.fixture
def category(db):
    return Category.objects.create(name="Home Assistants", slug="home-assistants")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="Seraphine Home Hub",
        slug="seraphine-home-hub",
        tagline="She's always listening. In a good way.",
        description="The flagship Seraphine hub with a seven-microphone array.",
        price=Decimal("349.99"),
        category=category,
    )


@pytest.fixture
def featured_product(category):
    return Product.objects.create(
        name="Cortex Crown",
        slug="cortex-crown",
        tagline="Wear your thoughts on your head.",
        price=Decimal("899.00"),
        is_featured=True,
        category=category,
    )


@pytest.fixture
def accessory(category):
    return Product.objects.create(
        name="Seraphine Wall Mount",
        slug="seraphine-wall-mount",
        tagline="Keep her at eye level.",
        price=Decimal("49.00"),
        category=category,
    )


@pytest.fixture
def unavailable_product(category):
    return Product.objects.create(
        name="EchoPatch",
        slug="echopatch",
        tagline="Never miss a word. Anyone's.",
        price=Decimal("139.00"),
        is_available=False,
        category=category,
    )


@pytest.fixture
def tag(db):
    return Tag.objects.create(name="bestseller", slug="bestseller")


@pytest.fixture
def cart(customer):
    return Cart.for_user(customer)


@pytest.fixture
def cart_item(cart, product):
    return CartItem.objects.create(cart=cart, product=product, quantity=2)


@pytest.fixture
def make_coupon(db):
    """Build coupons: live, 50% off the whole order, unless overridden.

    A builder rather than a single coupon, because coupon tests need
    several states side by side. ``products`` limits the coupon.
    """
    from coupons.models import Coupon

    def make(products=(), **overrides):
        now = timezone.now()
        fields = {
            "code": "SERAPHINE50",
            "discount_type": Coupon.DiscountType.PERCENT,
            "value": Decimal("50"),
            "starts_at": now - timedelta(days=1),
            "expires_at": now + timedelta(days=14),
        }
        fields.update(overrides)
        coupon = Coupon.objects.create(**fields)
        coupon.products.set(products)
        return coupon

    return make


@pytest.fixture
def make_order(db):
    """Build an order for ``user`` with one line per product: Placed,
    unless ``status`` says otherwise.

    A builder, because order-history tests need orders in several
    statuses side by side. Addresses and card are filler.
    """
    from orders.models import Order, OrderItem

    def make(user, *products, status=Order.Status.PLACED):
        order = Order.objects.create(
            user=user,
            status=status,
            total=sum((p.price for p in products), Decimal("0.00")),
            email=user.email or "buyer@example.com",
            shipping_name="Casey Monroe",
            shipping_street="214 Synapse Street",
            shipping_city="Canyon",
            shipping_state="TX",
            shipping_zip="79015",
            billing_name="Casey Monroe",
            billing_street="214 Synapse Street",
            billing_city="Canyon",
            billing_state="TX",
            billing_zip="79015",
            card_last4="4242",
        )
        for p in products:
            OrderItem.objects.create(
                order=order,
                product=p,
                product_name=p.name,
                unit_price=p.price,
                quantity=1,
            )
        return order

    return make


@pytest.fixture
def address(customer):
    return Address.objects.create(
        user=customer,
        label="Home",
        name="Casey Monroe",
        street="214 Synapse Street",
        city="Canyon",
        state="TX",
        zip="79015",
    )


@pytest.fixture
def other_users_address(db):
    stranger = get_user_model().objects.create_user(username="stranger", password="x")
    return Address.objects.create(
        user=stranger,
        name="Sam Stranger",
        street="9 Axon Avenue",
        city="Norman",
        state="OK",
        zip="73019",
    )
