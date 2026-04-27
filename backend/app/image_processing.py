from __future__ import annotations

import io
import re

from PIL import Image, ImageOps, UnidentifiedImageError

IMAGE_SIZE_PATTERN = re.compile(r"^([1-9]\d{1,4})x([1-9]\d{1,4})$")
MAX_GENERATED_IMAGE_SIDE_PX = 4096
MAX_GENERATED_IMAGE_PIXELS = MAX_GENERATED_IMAGE_SIDE_PX * MAX_GENERATED_IMAGE_SIDE_PX


def parse_target_image_size(value: str | None) -> tuple[int, int] | None:
    normalized = (value or "").strip().lower()
    if not normalized or normalized == "auto":
        return None
    match = IMAGE_SIZE_PATTERN.match(normalized)
    if not match:
        raise ValueError("Image size must be auto or WIDTHxHEIGHT, for example 1024x1024.")
    width = int(match.group(1))
    height = int(match.group(2))
    if (
        width > MAX_GENERATED_IMAGE_SIDE_PX
        or height > MAX_GENERATED_IMAGE_SIDE_PX
        or width * height > MAX_GENERATED_IMAGE_PIXELS
    ):
        raise ValueError("Image size must be 4096x4096 pixels or smaller.")
    return width, height


def _pillow_format(output_format: str) -> str:
    normalized_format = output_format.strip().lower()
    if normalized_format in {"jpeg", "jpg"}:
        return "JPEG"
    if normalized_format == "webp":
        return "WEBP"
    return "PNG"


def _image_for_output_format(image: Image.Image, output_format: str) -> Image.Image:
    normalized_format = output_format.strip().lower()
    if normalized_format in {"jpeg", "jpg"}:
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")
    if image.mode not in {"RGB", "RGBA"}:
        return image.convert("RGBA" if "A" in image.getbands() else "RGB")
    return image


def prepare_generated_image_bytes(
    *,
    content: bytes,
    output_format: str,
    target_size: str | None = None,
) -> bytes:
    target_dimensions = parse_target_image_size(target_size)
    if target_dimensions is None:
        return content

    try:
        with Image.open(io.BytesIO(content)) as raw_image:
            image = ImageOps.exif_transpose(raw_image)
            if image.size != target_dimensions:
                image = ImageOps.fit(
                    image,
                    target_dimensions,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
            else:
                image = image.copy()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Image generation returned invalid image data.") from exc

    image = _image_for_output_format(image, output_format)
    buffer = io.BytesIO()
    save_options: dict[str, object] = {}
    normalized_format = output_format.strip().lower()
    if normalized_format in {"jpeg", "jpg", "webp"}:
        save_options["quality"] = 95
    image.save(buffer, format=_pillow_format(output_format), **save_options)
    return buffer.getvalue()
