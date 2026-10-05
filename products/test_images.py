"""Product images: processing, the never-broken fallback, file cleanup,
back-office upload validation, where images render, and the seed import."""

from http import HTTPStatus
from io import StringIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image

from orders.models import CartItem

from .management.commands import seed
from .models import Product

pytestmark = pytest.mark.django_db

PLACEHOLDER_URL = "/static/images/placeholders/home-assistants.svg"


def product_data(category, **overrides):
    data = {
        "name": "MindSync Sleep Halo",
        "slug": "mindsync-sleep-halo",
        "price": "199.99",
        "is_available": "on",
        "category": str(category.pk),
    }
    data.update(overrides)
    return data


def update_data(product, **overrides):
    """A complete edit-form POST for ``product``, plus ``overrides``."""
    return product_data(
        product.category, name=product.name, slug=product.slug, **overrides
    )


@pytest.fixture
def product_with_image(product, make_image):
    product.set_image(make_image())
    product.save()
    return product


def stored(product):
    """The Pillow image in storage for ``product``."""
    with product.image.open("rb") as f:
        image = Image.open(f)
        image.load()
    return image


# --- Processing --------------------------------------------------------------


def test_set_image_resizes_and_stores_webp_named_by_slug(product, make_image):
    product.set_image(make_image(size=(2400, 1800)))
    product.save()

    assert product.image.name == "products/seraphine-home-hub.webp"
    image = stored(product)
    assert image.format == "WEBP"
    assert image.size == (1200, 900)


def test_small_images_are_not_enlarged(product, make_image):
    product.set_image(make_image(size=(800, 600)))
    product.save()

    assert stored(product).size == (800, 600)


def test_transparency_is_kept(product, make_image):
    product.set_image(make_image(mode="RGBA"))
    product.save()

    assert stored(product).mode == "RGBA"


# --- Never a broken image ----------------------------------------------------


def test_no_image_falls_back_to_the_category_placeholder(product):
    assert product.display_image_url == PLACEHOLDER_URL
    assert product.display_image_alt == ""


def test_uploaded_image_is_displayed(product_with_image):
    assert product_with_image.display_image_url == (
        "/media/products/seraphine-home-hub.webp"
    )
    assert product_with_image.display_image_alt == "Seraphine Home Hub product photo"


def test_missing_file_falls_back_to_the_placeholder(product_with_image):
    product_with_image.image.storage.delete(product_with_image.image.name)

    assert product_with_image.display_image_url == PLACEHOLDER_URL
    assert product_with_image.display_image_alt == ""


# --- File cleanup ------------------------------------------------------------


def test_replacing_an_image_deletes_the_old_file(
    product_with_image, make_image, django_capture_on_commit_callbacks
):
    old_name = product_with_image.image.name
    storage = product_with_image.image.storage

    with django_capture_on_commit_callbacks(execute=True):
        product_with_image.set_image(make_image(size=(1000, 750)))
        product_with_image.save()

    assert not storage.exists(old_name)
    assert storage.exists(product_with_image.image.name)


def test_clearing_an_image_in_the_back_office_deletes_the_file(
    client, staff_user, product_with_image, django_capture_on_commit_callbacks
):
    client.force_login(staff_user)
    name = product_with_image.image.name
    storage = product_with_image.image.storage

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse(
                "products:manage_product_update", kwargs={"pk": product_with_image.pk}
            ),
            update_data(product_with_image, **{"image-clear": "on"}),
        )

    product_with_image.refresh_from_db()
    assert not product_with_image.image
    assert not storage.exists(name)


def test_deleting_a_product_deletes_its_file(
    product_with_image, django_capture_on_commit_callbacks
):
    name = product_with_image.image.name
    storage = product_with_image.image.storage

    with django_capture_on_commit_callbacks(execute=True):
        product_with_image.delete()

    assert not storage.exists(name)


def test_saving_without_a_new_image_keeps_the_file(
    product_with_image, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        product_with_image.price = 1
        product_with_image.save()

    assert product_with_image.has_display_image


# --- Back-office uploads -----------------------------------------------------


def post_new_product(client, category, image):
    return client.post(
        reverse("products:manage_product_create"),
        product_data(category, image=image),
    )


def test_staff_can_upload_an_image(client, staff_user, category, make_image):
    client.force_login(staff_user)

    response = post_new_product(client, category, make_image(size=(1600, 1200)))

    assert response.status_code == HTTPStatus.FOUND
    product = Product.objects.get(slug="mindsync-sleep-halo")
    assert product.image.name == "products/mindsync-sleep-halo.webp"
    assert stored(product).size == (1200, 900)


def test_upload_extension_is_ignored(client, staff_user, category, make_image):
    """A real PNG named .txt is still a real PNG."""
    client.force_login(staff_user)

    post_new_product(client, category, make_image(name="photo.txt"))

    assert Product.objects.get(slug="mindsync-sleep-halo").has_display_image


@pytest.mark.parametrize(
    ("image_kwargs", "message"),
    [
        pytest.param(
            {"padding": 11 * 1024 * 1024},
            "The limit is 10 MB",
            id="too-large",
        ),
        pytest.param({"fmt": "GIF"}, "This file is a GIF.", id="wrong-format"),
        pytest.param(
            {"size": (300, 200)},
            "This image is 300 × 200 pixels. It needs to be at least 600 × 450",
            id="too-small",
        ),
        pytest.param(
            {"size": (9000, 5000), "mode": "L"},
            "9,000 × 5,000 pixels (45.0 megapixels). The limit is 40 megapixels",
            id="too-many-pixels",
        ),
    ],
)
def test_unusable_images_are_rejected_with_a_reason(
    client, staff_user, category, make_image, image_kwargs, message
):
    client.force_login(staff_user)

    response = post_new_product(client, category, make_image(**image_kwargs))

    assert response.status_code == HTTPStatus.OK
    assert message in response.content.decode()
    assert not Product.objects.exists()


def test_a_file_that_is_not_an_image_is_rejected(client, staff_user, category):
    client.force_login(staff_user)
    fake = SimpleUploadedFile("photo.png", b"definitely not a picture")

    response = post_new_product(client, category, fake)

    assert response.status_code == HTTPStatus.OK
    assert "We couldn&#x27;t read this file as an image" in response.content.decode()
    assert not Product.objects.exists()


def test_edit_page_previews_the_current_image(client, staff_user, product_with_image):
    client.force_login(staff_user)

    page = client.get(
        reverse("products:manage_product_update", kwargs={"pk": product_with_image.pk})
    ).content.decode()

    assert product_with_image.display_image_url in page
    assert "Remove the current image" in page
    assert 'enctype="multipart/form-data"' in page


# --- Where images render -----------------------------------------------------


def test_catalog_card_shows_the_image_lazily(client, product_with_image):
    page = client.get(reverse("products:catalog")).content.decode()

    assert product_with_image.display_image_url in page
    assert 'alt="Seraphine Home Hub product photo"' in page
    assert 'loading="lazy"' in page


def test_catalog_card_placeholder_has_empty_alt(client, product):
    page = client.get(reverse("products:catalog")).content.decode()

    assert PLACEHOLDER_URL in page
    assert 'alt=""' in page


def test_detail_page_shows_the_image(client, product_with_image):
    page = client.get(product_with_image.get_absolute_url()).content.decode()

    assert product_with_image.display_image_url in page


def test_cart_and_back_office_list_show_small_thumbnails(
    client, customer, staff_user, cart, product_with_image
):
    """Thumbnails carry a fixed size in the HTML, so a stale or missing
    stylesheet can't blow them up to the image's full 1200 px."""
    CartItem.objects.create(cart=cart, product=product_with_image)
    client.force_login(customer)
    cart_page = client.get(reverse("orders:cart")).content.decode()

    client.force_login(staff_user)
    list_page = client.get(reverse("products:manage_products")).content.decode()

    for page in (cart_page, list_page):
        assert product_with_image.display_image_url in page
        assert 'width="64" height="48"' in page


# --- The seed import ---------------------------------------------------------


def test_seed_imports_the_mapped_demo_photos(db):
    call_command("seed", stdout=StringIO())

    with_images = Product.objects.exclude(image="")
    assert set(with_images.values_list("name", flat=True)) == set(seed.PRODUCT_IMAGES)
    assert all(product.has_display_image for product in with_images)
    assert Product.objects.get(name="Veil").image.name == "products/veil.webp"


def test_seed_warns_and_continues_when_a_source_file_is_missing(db, monkeypatch):
    monkeypatch.setattr(seed, "PRODUCT_IMAGES", {"Veil": "No Such File.png"})
    out = StringIO()

    call_command("seed", stdout=out)

    assert "Image not found for Veil" in out.getvalue()
    assert not Product.objects.get(name="Veil").image
