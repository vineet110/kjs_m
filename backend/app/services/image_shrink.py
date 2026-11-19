"""Shrinks website pictures on upload (Pillow): the longest side at most site_ui.ini image_max_px, saved again
at image_quality. Also turns the picture upright (phone photos) and drops hidden data such as GPS position.

Used for file owners registered with shrink=True (file_service.register_owner), e.g. the home page hero.
"""
import io

from PIL import Image, ImageOps

from app.core.config.ini import cfg

# Security limit, not in an ini (a typo must never weaken it): a picture claiming more pixels than this is
# refused before it is decoded, so a tiny file can't unpack into gigabytes of memory.
MAX_PIXELS = 50_000_000
# Pillow's own guard, set once here instead of changing warning filters per upload (those are shared by every
# thread, and uploads are shrunk in threads). Pillow refuses at twice this number, i.e. at MAX_PIXELS.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS // 2
FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


class NotAPicture(ValueError):
    """The bytes are not a picture Pillow can read (or one far too big, or an animation)."""


def shrink(ext: str, data: bytes) -> bytes:
    """The picture smaller and cleaned, in the same format. Unknown types come back unchanged."""
    fmt = FORMATS.get(ext)
    if fmt is None:
        return data
    s = cfg().site_ui
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise NotAPicture("too many pixels")
        # An animated WebP or PNG would lose its animation (only the first frame is saved): refused instead
        if getattr(img, "n_frames", 1) > 1:
            raise NotAPicture("animated pictures are not supported")
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
    except Exception as e:  # noqa: BLE001 - Pillow raises many kinds (incl. DecompressionBombError); all mean "can't use it"
        raise NotAPicture(str(e)) from e
    # Always the re-saved copy, even if a little bigger: the original may carry GPS position and camera data
    return out.getvalue()
