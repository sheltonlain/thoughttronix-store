"""Project-wide pytest fixtures.

Shared test data lives here as plain fixtures — no factories. The suite
grows with the project; tests never invoke the seed command.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Address
from orders.models import Cart, CartItem
from products.models import Category, Product, Tag


@pytest.fixture
def customer(db):
    return get_user_model().objects.create_user(
        username="customer", password="customer123"
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
