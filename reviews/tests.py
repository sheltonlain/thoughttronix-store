from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Address
from orders.models import Order, OrderItem
from products.models import Category, Product

from .models import Eligibility, Review
from .templatetags.review_extras import stars


def make_user(username, **fields):
    return get_user_model().objects.create_user(
        username=username, password="x", **fields
    )


def make_review(user, product, rating=4, comment="Does what it says.", **fields):
    return Review.objects.create(
        user=user, product=product, rating=rating, comment=comment, **fields
    )


def detail_url(product):
    return reverse("products:detail", kwargs={"slug": product.slug})


# --- Eligibility ------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (Order.Status.DELIVERED, Eligibility.CAN_REVIEW),
        (Order.Status.PLACED, Eligibility.AWAITING_DELIVERY),
        (Order.Status.SHIPPED, Eligibility.AWAITING_DELIVERY),
        (Order.Status.CANCELLED, Eligibility.NOT_A_BUYER),
    ],
)
def test_eligibility_follows_the_buyers_order_status(
    customer, product, make_order, status, expected
):
    make_order(customer, product, status=status)

    assert Review.objects.eligibility(customer, product) == expected


def test_signed_out_viewers_are_signed_out(product):
    assert Review.objects.eligibility(AnonymousUser(), product) == (
        Eligibility.SIGNED_OUT
    )


def test_a_customer_with_no_order_is_not_a_buyer(customer, product, make_order):
    make_order(
        customer,
        Product.objects.create(
            name="Other", slug="other", price=Decimal("1.00"), category=product.category
        ),
        status=Order.Status.DELIVERED,
    )

    assert Review.objects.eligibility(customer, product) == Eligibility.NOT_A_BUYER


def test_a_delivered_order_counts_beside_a_cancelled_one(customer, product, make_order):
    make_order(customer, product, status=Order.Status.CANCELLED)
    make_order(customer, product, status=Order.Status.DELIVERED)

    assert Review.objects.eligibility(customer, product) == Eligibility.CAN_REVIEW


def test_a_reviewer_has_already_reviewed(customer, product, make_order):
    make_order(customer, product, status=Order.Status.DELIVERED)
    make_review(customer, product)

    assert Review.objects.eligibility(customer, product) == (
        Eligibility.ALREADY_REVIEWED
    )


def test_an_unavailable_product_is_reviewable_by_a_delivered_buyer(
    customer, unavailable_product, make_order
):
    make_order(customer, unavailable_product, status=Order.Status.DELIVERED)

    assert Review.objects.eligibility(customer, unavailable_product) == (
        Eligibility.CAN_REVIEW
    )


def test_staff_get_no_exemption(staff_user, product):
    assert Review.objects.eligibility(staff_user, product) == (Eligibility.NOT_A_BUYER)


def test_a_later_status_change_leaves_the_review_in_place(
    customer, product, make_order
):
    order = make_order(customer, product, status=Order.Status.DELIVERED)
    review = make_review(customer, product)

    order.status = Order.Status.CANCELLED
    order.save()

    assert Review.objects.filter(pk=review.pk).exists()
    assert Review.objects.eligibility(customer, product) == (
        Eligibility.ALREADY_REVIEWED
    )


def test_soulsear_eligibility_belongs_to_the_buying_account(db, make_order):
    defense = Category.objects.create(name="Defense", slug="defense")
    soulsear = Product.objects.create(
        name="SoulSear Mark II",
        slug="soulsear-mark-ii",
        price=Decimal("2400000.00"),
        category=defense,
    )
    owner = make_user("owner", first_name="Owen", last_name="Rourke")
    next_of_kin = make_user("kin", first_name="Kim", last_name="Rourke")
    # Same household, same address — still a different account.
    for user in (owner, next_of_kin):
        Address.objects.create(
            user=user,
            name=f"{user.first_name} Rourke",
            street="1 Range Road",
            city="Amarillo",
            state="TX",
            zip="79101",
        )
    make_order(owner, soulsear, status=Order.Status.DELIVERED)

    assert Review.objects.eligibility(owner, soulsear) == Eligibility.CAN_REVIEW
    assert Review.objects.eligibility(next_of_kin, soulsear) == (
        Eligibility.NOT_A_BUYER
    )


# --- Model ------------------------------------------------------------------


def test_review_str(customer, product):
    assert str(make_review(customer, product, rating=5)) == (
        "5★ Seraphine Home Hub by customer"
    )


def test_one_review_per_customer_per_product(customer, product):
    make_review(customer, product)

    with pytest.raises(IntegrityError):
        make_review(customer, product, rating=1)


@pytest.mark.parametrize("rating", [0, 6])
def test_the_database_rejects_ratings_outside_1_to_5(customer, product, rating):
    with pytest.raises(IntegrityError):
        make_review(customer, product, rating=rating)


def test_a_new_review_is_not_edited(customer, product):
    review = make_review(customer, product)

    assert review.updated_at == review.created_at
    assert not review.is_edited


def test_a_later_update_marks_the_review_edited(customer, product):
    posted = timezone.now() - timedelta(days=2)
    review = make_review(
        customer, product, created_at=posted, updated_at=posted + timedelta(days=1)
    )

    assert review.is_edited


def test_reviews_are_newest_first(customer, product):
    now = timezone.now()
    old = make_review(make_user("ana"), product, created_at=now - timedelta(days=3))
    new = make_review(make_user("ben"), product, created_at=now)
    mid = make_review(make_user("cal"), product, created_at=now - timedelta(days=1))

    assert list(Review.objects.all()) == [new, mid, old]


def test_deleting_a_product_deletes_its_reviews(customer, product):
    make_review(customer, product)

    product.delete()

    assert not Review.objects.exists()


def test_deleting_a_user_deletes_their_reviews(customer, product):
    make_review(customer, product)

    customer.delete()

    assert not Review.objects.exists()


# --- Summary ----------------------------------------------------------------


def test_summary_averages_only_this_products_reviews(
    product, accessory, featured_product
):
    for username, rating in [("ana", 4), ("ben", 5)]:
        Review.objects.create(
            user=make_user(username), product=product, rating=rating, comment="Ok."
        )
    Review.objects.create(
        user=make_user("cal"), product=accessory, rating=1, comment="No."
    )

    assert Review.objects.summary(product) == {"average": 4.5, "count": 2}
    assert Review.objects.summary(featured_product) == {"average": None, "count": 0}


def test_summary_is_one_query(product, django_assert_num_queries):
    make_review(make_user("ana"), product)

    with django_assert_num_queries(1):
        Review.objects.summary(product)


# --- Admin ------------------------------------------------------------------


def test_superusers_can_inspect_reviews_in_the_admin(admin_client, customer, product):
    make_review(customer, product, comment="Findable in the admin.")

    response = admin_client.get(
        reverse("admin:reviews_review_changelist"), {"rating__exact": 4, "q": "admin"}
    )

    assert response.status_code == 200
    assert "Seraphine Home Hub" in response.content.decode()


# --- Stars ------------------------------------------------------------------


@pytest.mark.parametrize(("value", "filled"), [(1, 1), (4.4, 4), (4.5, 5), (5, 5)])
def test_stars_round_to_the_nearest_whole_star(value, filled):
    assert stars(value)["filled"] == filled


# --- The product page's reviews section -------------------------------------


def test_visitors_get_a_sign_in_link_back_to_the_product(client, product):
    page = client.get(detail_url(product)).content.decode()

    login = reverse("accounts:login")
    assert "Sign in to review" in page
    assert f'{login}?next=/products/seraphine-home-hub/"' in page


def test_a_customer_awaiting_delivery_is_told_to_wait(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.SHIPPED)
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert "You can review this once your order is delivered." in page


def test_a_non_buyer_is_told_only_buyers_review(client, customer, product):
    client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()

    assert "Only customers who've received this product can review it." in page


def test_staff_who_havent_bought_get_the_same_message(client, staff_user, product):
    client.force_login(staff_user)

    page = client.get(detail_url(product)).content.decode()

    assert "Only customers who've received this product can review it." in page


def test_a_delivered_buyer_sees_the_can_review_placeholder(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.get(detail_url(product))

    assert response.context["eligibility"] == Eligibility.CAN_REVIEW
    assert "Reviewing opens soon." in response.content.decode()


def test_a_reviewer_sees_their_own_review_pinned_once(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    mine = make_review(customer, product, comment="My own words.")
    make_review(make_user("ana"), product, comment="Someone else's words.")
    client.force_login(customer)

    response = client.get(detail_url(product))
    page = response.content.decode()

    assert response.context["own_review"] == mine
    assert mine not in response.context["other_reviews"]
    assert page.count("My own words.") == 1
    assert page.index("Your review") < page.index("My own words.")
    assert page.index("My own words.") < page.index("Someone else&#x27;s words.")


def test_the_list_is_everyone_elses_reviews_newest_first(client, product):
    now = timezone.now()
    make_review(
        make_user("ana"), product, comment="Older.", created_at=now - timedelta(days=5)
    )
    make_review(make_user("ben"), product, comment="Newer.", created_at=now)

    page = client.get(detail_url(product)).content.decode()

    assert page.index("Newer.") < page.index("Older.")


def test_the_summary_shows_average_and_count(client, product):
    make_review(make_user("ana"), product, rating=4)
    make_review(make_user("ben"), product, rating=5)

    page = client.get(detail_url(product)).content.decode()

    assert "4.5 out of 5" in page
    assert "2 reviews" in page
    assert "No reviews yet." not in page


def test_a_product_with_no_reviews_says_so(client, product):
    page = client.get(detail_url(product)).content.decode()

    assert "No reviews yet." in page


def test_a_card_shows_public_name_and_verified_badge(client, product):
    author = make_user("cmonroe", first_name="Casey", last_name="Monroe")
    make_review(author, product)

    page = client.get(detail_url(product)).content.decode()

    assert "Casey M." in page
    assert "Monroe" not in page
    assert "Verified purchase" in page


def test_a_card_escapes_the_comment_and_keeps_line_breaks(client, product):
    make_review(make_user("ana"), product, comment="<b>Loud</b>\nSecond line")

    page = client.get(detail_url(product)).content.decode()

    assert "&lt;b&gt;Loud&lt;/b&gt;<br>Second line" in page
    assert "<b>Loud</b>" not in page


def test_cards_label_edits(client, product):
    posted = timezone.now() - timedelta(days=3)
    later = posted + timedelta(days=1)
    make_review(make_user("ana"), product, comment="Untouched.", created_at=posted)
    make_review(
        make_user("ben"),
        product,
        comment="Author edit.",
        created_at=posted,
        updated_at=later,
    )
    make_review(
        make_user("cal"),
        product,
        comment="Staff edit.",
        created_at=posted,
        updated_at=later,
        edited_by_staff=True,
    )

    response = client.get(detail_url(product))
    cards = {
        review.comment: card
        for review, card in zip(
            response.context["other_reviews"],
            response.content.decode().split('class="review-card')[1:],
            strict=True,
        )
    }

    assert "Edited" not in cards["Untouched."]
    assert ">Edited<" in cards["Author edit."]
    assert "Edited by staff" not in cards["Author edit."]
    assert "Edited by staff" in cards["Staff edit."]


@pytest.mark.parametrize("signed_in", [False, True])
def test_add_to_cart_stays_the_only_primary_button(
    client, customer, product, make_order, signed_in
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    make_review(customer, product)
    make_review(make_user("ana"), product)
    if signed_in:
        client.force_login(customer)

    page = client.get(detail_url(product)).content.decode()
    section = page[page.index('id="reviews-section"') :]
    section = section[: section.index("</section>")]

    assert "btn-primary" not in section
    if signed_in:
        # Visitors also get the navbar's Sign up, which predates reviews.
        assert page.count("btn-primary") == 1


# --- Seed -------------------------------------------------------------------


def test_seed_builds_the_review_demo(db):
    out = StringIO()
    call_command("seed", stdout=out)

    assert Review.objects.count() > 0
    assert f"{Review.objects.count()} reviews" in out.getvalue()

    # Every seeded author received the product they reviewed.
    for review in Review.objects.select_related("user", "product"):
        assert OrderItem.objects.filter(
            order__user=review.user,
            order__status=Order.Status.DELIVERED,
            product=review.product,
        ).exists(), review

    assert Review.objects.filter(edited_by_staff=True).count() == 1

    customer = get_user_model().objects.get(username="customer")
    expected = {
        "dreamweaver": Eligibility.ALREADY_REVIEWED,
        "mindsync": Eligibility.CAN_REVIEW,
        "syncrest": Eligibility.CAN_REVIEW,
        "seraphine-mini": Eligibility.AWAITING_DELIVERY,
        "veil": Eligibility.AWAITING_DELIVERY,
    }
    for slug, state in expected.items():
        product = Product.objects.get(slug=slug)
        assert Review.objects.eligibility(customer, product) == state, slug
        # Each demo page has other people's reviews in its list.
        assert product.reviews.exclude(user=customer).exists(), slug
    assert customer.reviews.count() == 1
