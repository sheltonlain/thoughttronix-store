"""Product image processing, shared by back-office uploads and the seed.

Every stored product image passes through ``encode_product_image``: one
WebP, at most ``MAX_EDGE`` pixels on its long side, which serves both the
catalog cards and the detail page. The original upload is discarded.
"""

from io import BytesIO

from PIL import Image, ImageOps

# Stored images: the long side is capped here, then re-encoded as WebP.
MAX_EDGE = 1200
WEBP_QUALITY = 80

# Upload limits, enforced by ProductForm.clean_image.
MAX_UPLOAD_MB = 10
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MIN_WIDTH, MIN_HEIGHT = 600, 450
MAX_MEGAPIXELS = 40

# Accepted Pillow formats -> the extension the upload is renamed to.
# MPO is how Pillow reports many phone-camera JPEGs.
ACCEPTED_FORMATS = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp"}


def encode_product_image(file) -> bytes:
    """Resize ``file`` to fit ``MAX_EDGE`` and return it as WebP bytes.

    ``file`` is anything Pillow can open: an upload or an open file.
    Camera rotation is applied, transparency is kept, and nothing is
    cropped — the templates frame every image with ``object-contain``.
    """
    if hasattr(file, "seek"):
        file.seek(0)
    with Image.open(file) as original:
        image = ImageOps.exif_transpose(original)
        image.thumbnail((MAX_EDGE, MAX_EDGE))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if image.has_transparency_data else "RGB")
        buffer = BytesIO()
        image.save(buffer, "WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue()
