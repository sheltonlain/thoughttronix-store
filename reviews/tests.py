import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

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

from .forms import ReviewForm
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


def test_revise_marks_a_staff_edit_and_an_author_edit_clears_it(
    customer, staff_user, product
):
    review = make_review(customer, product, rating=4, comment="First words.")

    review.revise(2, "Moderated words.", by=staff_user)
    review.refresh_from_db()

    assert (review.rating, review.comment) == (2, "Moderated words.")
    assert review.edited_by_staff is True
    assert review.is_edited

    review.revise(3, "My words again.", by=customer)
    review.refresh_from_db()

    assert (review.rating, review.comment) == (3, "My words again.")
    assert review.edited_by_staff is False
    assert review.is_edited


def test_deleting_a_product_deletes_its_reviews(customer, product):
    make_review(customer, product)

    product.delete()

    assert not Review.objects.exists()


def test_deleting_a_user_deletes_their_reviews(customer, product):
    make_review(customer, product)

    customer.delete()

    assert not Review.objects.exists()


# --- Submitting -------------------------------------------------------------


def test_a_duplicate_submit_returns_the_existing_review_untouched(
    customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    existing = make_review(customer, product, rating=4, comment="First words.")

    review, created = Review.objects.submit(customer, product, 1, "Stale tab.")

    assert created is False
    assert review == existing
    existing.refresh_from_db()
    assert (existing.rating, existing.comment) == (4, "First words.")
    assert Review.objects.count() == 1


# --- The create endpoint ----------------------------------------------------


def create_url(product):
    return reverse("reviews:create", kwargs={"pk": product.pk})


@pytest.mark.parametrize(
    ("username", "status"),
    [
        ("customer", None),  # never bought it
        ("customer", Order.Status.PLACED),
        ("customer", Order.Status.SHIPPED),
        ("employee", None),  # staff who haven't bought it
    ],
)
def test_ineligible_users_are_refused_and_nothing_is_created(
    client, customer, staff_user, product, make_order, username, status
):
    user = customer if username == "customer" else staff_user
    if status:
        make_order(user, product, status=status)
    client.force_login(user)

    response = client.post(create_url(product), {"rating": 5, "comment": "Sneaky."})

    assert response.status_code == 403
    assert not Review.objects.exists()


def test_a_delivered_buyers_review_is_pinned_and_counted(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    make_review(make_user("ana"), product, rating=2, comment="Someone else's words.")
    client.force_login(customer)

    response = client.post(
        create_url(product), {"rating": 5, "comment": "She finishes my sentences."}
    )
    page = response.content.decode()

    review = Review.objects.get(user=customer, product=product)
    assert (review.rating, review.comment) == (5, "She finishes my sentences.")
    assert response.status_code == 200
    assert page.lstrip().startswith('<section id="reviews-section"')
    assert "<html" not in page
    assert "3.5 out of 5" in page
    assert "2 reviews" in page
    assert page.index("Your review") < page.index("She finishes my sentences.")
    assert page.index("She finishes my sentences.") < page.index("Someone else")
    assert 'class="review-form' not in page


def test_a_stale_invalid_form_still_gets_the_already_reviewed_note(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    make_review(customer, product, rating=4, comment="First words.")
    client.force_login(customer)

    response = client.post(create_url(product), {"rating": "", "comment": "   "})
    page = response.content.decode()

    assert response.status_code == 200
    assert "You've already reviewed this product." in page
    assert "First words." in page
    review = Review.objects.get(user=customer, product=product)
    assert (review.rating, review.comment) == (4, "First words.")


def test_create_requires_sign_in(client, product):
    response = client.post(create_url(product), {"rating": 5, "comment": "Hi."})

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))
    assert not Review.objects.exists()


def test_create_rejects_get(client, customer, product, make_order):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    assert client.get(create_url(product)).status_code == 405


def test_a_missing_rating_errors_and_keeps_the_comment(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.post(create_url(product), {"comment": "Kept words."})
    page = response.content.decode()

    assert response.status_code == 200
    assert "Choose a star rating." in page
    assert "Kept words.</textarea>" in page
    assert not Review.objects.exists()


@pytest.mark.parametrize("comment", ["", "   \n  "])
def test_a_blank_comment_errors_and_keeps_the_rating(
    client, customer, product, make_order, comment
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.post(create_url(product), {"rating": 3, "comment": comment})
    form = response.context["review_form"]

    assert form.errors["comment"] == ["Write a few words about it."]
    assert re.search(r'value="3"[^>]*\bchecked\b', response.content.decode())
    assert not Review.objects.exists()


def test_a_comment_over_2000_characters_is_rejected(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.post(create_url(product), {"rating": 4, "comment": "x" * 2001})

    assert "at most 2000 characters" in response.content.decode()
    assert not Review.objects.exists()


def test_a_comment_of_exactly_2000_characters_is_accepted(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    client.post(create_url(product), {"rating": 4, "comment": "x" * 2000})

    assert Review.objects.get().comment == "x" * 2000


def test_a_valid_duplicate_post_shows_the_note_and_changes_nothing(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    make_review(customer, product, rating=4, comment="First words.")
    client.force_login(customer)

    page = client.post(
        create_url(product), {"rating": 1, "comment": "Second thoughts."}
    ).content.decode()

    assert "You've already reviewed this product." in page
    assert "Second thoughts." not in page
    review = Review.objects.get()
    assert (review.rating, review.comment) == (4, "First words.")


def test_a_concurrent_duplicate_is_caught_by_the_unique_constraint(
    customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    existing = make_review(customer, product, rating=4, comment="Won the race.")

    # The other request passed the eligibility check before this one's
    # review was saved, so it believes it can still create.
    with patch.object(
        type(Review.objects), "eligibility", return_value=Eligibility.CAN_REVIEW
    ):
        review, created = Review.objects.submit(customer, product, 1, "Lost it.")

    assert created is False
    assert review == existing
    assert Review.objects.get().comment == "Won the race."


def test_a_delivered_buyer_can_review_an_unavailable_product(
    client, customer, unavailable_product, make_order
):
    make_order(customer, unavailable_product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.post(
        create_url(unavailable_product), {"rating": 2, "comment": "Recalled, fairly."}
    )

    assert response.status_code == 200
    assert Review.objects.get().product == unavailable_product


def test_a_soulsear_owner_can_review_it_through_the_endpoint(client, db, make_order):
    defense = Category.objects.create(name="Defense", slug="defense")
    soulsear = Product.objects.create(
        name="SoulSear Mark II",
        slug="soulsear-mark-ii",
        price=Decimal("2400000.00"),
        category=defense,
    )
    owner = make_user("owner", first_name="Owen", last_name="Rourke")
    make_order(owner, soulsear, status=Order.Status.DELIVERED)
    client.force_login(owner)

    response = client.post(
        create_url(soulsear), {"rating": 5, "comment": "Peace of mind. Mostly."}
    )

    assert response.status_code == 200
    assert Review.objects.get().user == owner


def test_the_star_widget_renders_five_labelled_unchecked_radios():
    html = str(ReviewForm()["rating"])

    radios = re.findall(r"<input [^>]*>", html)
    assert len(radios) == 5
    assert all('type="radio"' in radio for radio in radios)
    assert all("mask-star-2" in radio for radio in radios)
    labels = re.findall(r'aria-label="([^"]+)"', html)
    assert labels == ["1 star", "2 stars", "3 stars", "4 stars", "5 stars"]
    assert "checked" not in html


# --- Editing and deleting ---------------------------------------------------


@pytest.mark.parametrize(
    ("method", "name", "note"),
    [
        ("get", "reviews:edit", True),
        ("post", "reviews:edit", True),
        ("get", "reviews:card", True),
        ("post", "reviews:delete", False),
    ],
    ids=["edit", "save", "cancel", "delete"],
)
def test_changes_reach_only_reviews_the_user_may_change(
    client, customer, product, method, name, note
):
    theirs = make_review(make_user("ana"), product, rating=5, comment="Ana's words.")
    client.force_login(customer)
    send = getattr(client, method)
    data = {"product": product.pk, "rating": 1, "comment": "Hijacked."}

    # Someone else's review: not found, and left untouched.
    response = send(reverse(name, kwargs={"pk": theirs.pk}), data)

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert (theirs.rating, theirs.comment) == (5, "Ana's words.")

    # A review that doesn't exist at all: a fresh section, with a note
    # unless deleting (already done).
    response = send(reverse(name, kwargs={"pk": theirs.pk + 1000}), data)
    page = response.content.decode()

    assert response.status_code == 200
    assert page.lstrip().startswith('<section id="reviews-section"')
    assert ("That review no longer exists." in page) is note


def test_an_author_who_deletes_their_review_gets_the_form_back(
    client, customer, product, make_order
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    mine = make_review(customer, product, comment="Taking it back.")
    client.force_login(customer)

    response = client.post(
        reverse("reviews:delete", kwargs={"pk": mine.pk}), {"product": product.pk}
    )
    page = response.content.decode()

    assert response.status_code == 200
    assert not Review.objects.exists()
    assert page.lstrip().startswith('<section id="reviews-section"')
    assert "Taking it back." not in page
    assert "No reviews yet." in page
    assert f'hx-post="{create_url(product)}"' in page


def change_url(name, review):
    return reverse(name, kwargs={"pk": review.pk})


@pytest.mark.parametrize(
    ("method", "name"),
    [
        ("get", "reviews:edit"),
        ("post", "reviews:edit"),
        ("get", "reviews:card"),
        ("post", "reviews:delete"),
    ],
)
def test_changing_a_review_requires_sign_in(client, customer, product, method, name):
    review = make_review(customer, product, comment="Still here.")

    response = getattr(client, method)(
        change_url(name, review), {"rating": 1, "comment": "Anon."}
    )

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))
    review.refresh_from_db()
    assert review.comment == "Still here."


def test_delete_rejects_get_and_cancel_rejects_post(client, customer, product):
    review = make_review(customer, product)
    client.force_login(customer)

    assert client.get(change_url("reviews:delete", review)).status_code == 405
    assert client.post(change_url("reviews:card", review)).status_code == 405
    assert Review.objects.exists()


def test_who_may_change_a_review(customer, staff_user, product):
    review = make_review(customer, product)
    other = make_user("ana")
    theirs = make_review(other, product)

    assert review.may_change(customer)
    assert not review.may_change(other)
    assert review.may_change(staff_user)
    assert not review.may_change(AnonymousUser())

    assert list(Review.objects.changeable_by(customer)) == [review]
    assert list(Review.objects.changeable_by(other)) == [theirs]
    assert set(Review.objects.changeable_by(staff_user)) == {review, theirs}
    assert not Review.objects.changeable_by(AnonymousUser()).exists()


def test_edit_swaps_in_a_prefilled_form_and_cancel_restores_the_card(
    client, customer, product
):
    review = make_review(customer, product, rating=3, comment="Before.")
    client.force_login(customer)

    form = client.get(
        change_url("reviews:edit", review), {"product": product.pk}
    ).content.decode()

    assert form.lstrip().startswith(f'<form id="review-{review.pk}"')
    assert re.search(r'value="3"[^>]*\bchecked\b', form)
    assert "Before.</textarea>" in form
    assert 'id="reviews-section"' not in form

    card = client.get(
        change_url("reviews:card", review), {"product": product.pk}
    ).content.decode()

    assert card.lstrip().startswith(f'<article id="review-{review.pk}"')
    assert "Before." in card
    assert ">Edit</button>" in card
    review.refresh_from_db()
    assert (review.rating, review.comment, review.is_edited) == (3, "Before.", False)


@pytest.mark.parametrize(
    ("editor", "label"), [("author", ">Edited<"), ("staff", ">Edited by staff<")]
)
def test_save_rerenders_the_section_labelled_and_in_place(
    client, customer, staff_user, product, editor, label
):
    now = timezone.now()
    make_review(make_user("ana"), product, comment="Newest.", created_at=now)
    review = make_review(
        customer,
        product,
        rating=2,
        comment="Middle.",
        created_at=now - timedelta(days=1),
    )
    make_review(
        make_user("ben"), product, comment="Oldest.", created_at=now - timedelta(days=2)
    )
    client.force_login(customer if editor == "author" else staff_user)

    response = client.post(
        change_url("reviews:edit", review),
        {"product": product.pk, "rating": 5, "comment": "Middle, revised."},
    )
    page = response.content.decode()

    assert response.status_code == 200
    assert page.lstrip().startswith('<section id="reviews-section"')
    assert response["HX-Retarget"] == "#reviews-section"
    review.refresh_from_db()
    assert (review.rating, review.comment) == (5, "Middle, revised.")
    assert review.edited_by_staff is (editor == "staff")
    assert label in page
    if editor == "staff":
        # Staff see every review in the list, in creation order.
        assert page.index("Newest.") < page.index("Middle, revised.")
        assert page.index("Middle, revised.") < page.index("Oldest.")
    assert "4.3 out of 5" in page  # the summary follows the new rating


def test_an_invalid_save_rerenders_only_the_form_and_changes_nothing(
    client, customer, product
):
    review = make_review(customer, product, rating=4, comment="Original.")
    client.force_login(customer)

    response = client.post(
        change_url("reviews:edit", review),
        {"product": product.pk, "rating": 2, "comment": "   "},
    )
    page = response.content.decode()

    assert response.status_code == 200
    assert page.lstrip().startswith(f'<form id="review-{review.pk}"')
    assert 'id="reviews-section"' not in page
    assert "HX-Retarget" not in response
    assert "Write a few words about it." in page
    assert re.search(r'value="2"[^>]*\bchecked\b', page)
    review.refresh_from_db()
    assert (review.rating, review.comment, review.is_edited) == (4, "Original.", False)


def test_staff_can_delete_any_review(client, customer, staff_user, product):
    review = make_review(customer, product, comment="Spam, probably.")
    client.force_login(staff_user)

    response = client.post(
        change_url("reviews:delete", review), {"product": product.pk}
    )
    page = response.content.decode()

    assert response.status_code == 200
    assert not Review.objects.exists()
    assert "Spam, probably." not in page
    assert "Only customers who've received this product can review it." in page


@pytest.mark.parametrize("viewer", ["visitor", "author", "other", "staff"])
def test_edit_and_delete_appear_only_on_changeable_cards(
    client, customer, staff_user, product, make_order, viewer
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    mine = make_review(customer, product, comment="Mine.")
    theirs = make_review(make_user("ana"), product, comment="Theirs.")
    users = {"author": customer, "other": make_user("ben"), "staff": staff_user}
    if viewer in users:
        client.force_login(users[viewer])

    page = client.get(detail_url(product)).content.decode()

    expected = {
        "visitor": set(),
        "author": {mine},
        "other": set(),
        "staff": {mine, theirs},
    }[viewer]
    for review in (mine, theirs):
        has_buttons = change_url("reviews:edit", review) in page
        assert has_buttons is (review in expected), review
        assert (change_url("reviews:delete", review) in page) is has_buttons
    if expected:
        assert "hx-confirm=" in page


def test_a_staff_viewer_still_has_one_primary_button(
    client, customer, staff_user, product
):
    make_review(customer, product)
    client.force_login(staff_user)

    page = client.get(detail_url(product)).content.decode()

    assert ">Edit</button>" in page
    assert page.count("btn-primary") == 1


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


def test_a_delivered_buyer_sees_the_review_form(client, customer, product, make_order):
    make_order(customer, product, status=Order.Status.DELIVERED)
    client.force_login(customer)

    response = client.get(detail_url(product))
    page = response.content.decode()

    assert response.context["eligibility"] == Eligibility.CAN_REVIEW
    assert f'hx-post="{create_url(product)}"' in page
    assert 'hx-target="#reviews-section"' in page


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


@pytest.mark.parametrize(
    ("signed_in", "reviewed"), [(False, True), (True, True), (True, False)]
)
def test_add_to_cart_stays_the_only_primary_button(
    client, customer, product, make_order, signed_in, reviewed
):
    make_order(customer, product, status=Order.Status.DELIVERED)
    if reviewed:
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
