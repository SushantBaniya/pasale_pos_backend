
import cloudinary.uploader

from PIL import Image, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(image):

    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            "Image size cannot exceed 5 MB."
        )

    try:
        image.seek(0)

        with Image.open(image) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ValidationError(
                    "Only JPEG, PNG and WEBP images are allowed."
                )

            img.verify()

        image.seek(0)

    except (UnidentifiedImageError, OSError):
        raise ValidationError("Invalid image file.")


def upload_product_image(image, business_id):

    validate_image(image)

    result = cloudinary.uploader.upload(
        image,
        folder=f"pasale/products/business_{business_id}",
        resource_type="image",
        transformation=[
            {
                "quality": "auto",
                "fetch_format": "auto"
            }
        ]
    )

    return {
        "image_url": result["secure_url"],
        "image_public_id": result["public_id"]
    }


def delete_product_image(public_id):

    if not public_id:
        return

    result = cloudinary.uploader.destroy(
        public_id,
        resource_type="image",
        invalidate=True
    )

    return result
