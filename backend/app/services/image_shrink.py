"""Shrinks website pictures on upload (Pillow): the longest side at most site_ui.ini image_max_px, saved again
at image_quality. Also turns the picture upright (phone photos) and drops hidden data such as GPS position.

Used for file owners registered with shrink=True (file_service.register_owner), e.g. the home page hero.
"""
import io
import warnings

from PIL import Image, ImageOps

from app.core.config.ini import cfg

# Security limit, not in an ini (a typo must never weaken it): a picture claiming more pixels than this is
# refused before it is decoded, so a tiny file can't unpack into gigabytes of memory.
MAX_PIXELS = 50_000_000
FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


class NotAPicture(ValueError):
    """The bytes are not a picture Pillow can read (or one far too big)."""


def shrink(ext: str, data: bytes) -> bytes:
    """The picture smaller and cleaned, in the same format. Unknown types come back unchanged."""
    fmt = FORMATS.get(ext)
    if fmt is None:
        return data
    s = cfg().site_ui
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            if img.width * img.height > MAX_PIXELS:
                raise NotAPicture("too many pixels")
            img = ImageOps.exif_transpose(img)  # upright, as the phone showed it
            img.thumbnail((s.image_max_px, s.image_max_px))  # only ever makes it smaller
            if fmt == "JPEG" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")  # JPEG has no transparency
            out = io.BytesIO()
            if fmt == "PNG":
                img.save(out, fmt, optimize=True)
            else:
                img.save(out, fmt, quality=s.image_quality, optimize=fmt == "JPEG")
    except NotAPicture:
        raise
    except Exception as e:  # noqa: BLE001 - Pillow raises many kinds; all mean "can't use this picture"
        raise NotAPicture(str(e)) from e
    # Always the re-saved copy, even if a little bigger: the original may carry GPS position and camera data
    return out.getvalue()
