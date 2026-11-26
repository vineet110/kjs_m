"""image_shrink (R43): the odd pictures real people upload. Product photos from a designer (CMYK, colour
profiles), phone photos (turned sideways in EXIF, with GPS), transparent logos, 16-bit PNGs, animations,
broken files and "picture bombs" that claim billions of pixels."""
import io
import struct
import zlib

import pytest
from PIL import Image, ImageCms

from app.core.config.ini import cfg
from app.services import image_shrink


def _save(img: Image.Image, fmt: str, **kw) -> bytes:
    b = io.BytesIO()
    img.save(b, fmt, **kw)
    return b.getvalue()


def _open(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def test_a_big_photo_is_made_smaller_keeping_its_shape():
    big = cfg().site_ui.image_max_px * 2
    out = _open(image_shrink.shrink("jpg", _save(Image.new("RGB", (big, big // 2), "red"), "JPEG")))
    assert out.format == "JPEG" and max(out.size) == cfg().site_ui.image_max_px and out.size[0] == 2 * out.size[1]


def test_a_small_photo_is_not_made_bigger():
    assert _open(image_shrink.shrink("png", _save(Image.new("RGB", (40, 30)), "PNG"))).size == (40, 30)


def test_gps_is_dropped_and_a_sideways_phone_photo_is_turned_upright():
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: the phone was held sideways (shown turned 90 degrees)
    exif[0x8825] = {1: "N", 2: (17.0, 23.0, 0.0)}  # GPSInfo: Hyderabad
    data = _save(Image.new("RGB", (300, 100), "blue"), "JPEG", exif=exif)
    assert _open(data).getexif().get(0x8825) is not None
    out = _open(image_shrink.shrink("jpeg", data))
    assert out.size == (100, 300)  # upright, as the phone showed it
    assert not out.getexif().get(0x8825) and not out.getexif().get(0x0112)


def test_a_cmyk_jpeg_from_a_designer_becomes_rgb():
    out = _open(image_shrink.shrink("jpg", _save(Image.new("CMYK", (50, 50), (0, 255, 255, 0)), "JPEG")))
    assert out.mode == "RGB"


def test_a_colour_profile_is_kept_so_colours_do_not_change():
    """Phone and camera photos carry a colour profile (Display P3, Adobe RGB). Without it a browser reads the
    numbers as plain sRGB and the photo looks dull or wrong."""
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for ext, fmt in [("jpg", "JPEG"), ("png", "PNG"), ("webp", "WEBP")]:
        out = _open(image_shrink.shrink(ext, _save(Image.new("RGB", (20, 20), "green"), fmt, icc_profile=icc)))
        assert out.info.get("icc_profile") == icc, ext


def test_a_cmyk_profile_is_not_put_on_the_rgb_copy():
    """The profile describes CMYK numbers; on the RGB copy it would be wrong, so it is left off."""
    cmyk = Image.new("CMYK", (20, 20), (0, 255, 255, 0))
    data = _save(cmyk, "JPEG", icc_profile=b"\x00" * 128)
    out = _open(image_shrink.shrink("jpg", data))
    assert out.mode == "RGB" and not out.info.get("icc_profile")


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P", "I;16", "L", "1"])
def test_unusual_png_modes_stay_png(mode):
    img = Image.new(mode, (30, 30))
    if mode == "P":
        img.info["transparency"] = 0  # a transparent logo
    out = _open(image_shrink.shrink("png", _save(img, "PNG")))
    assert out.format == "PNG" and out.size == (30, 30)


def test_a_transparent_png_saved_as_jpg_is_flattened_not_refused():
    """Someone renames logo.png to logo.jpg: Pillow still opens it, and JPEG has no transparency."""
    data = _save(Image.new("RGBA", (30, 30), (0, 0, 0, 0)), "PNG")
    assert _open(image_shrink.shrink("jpg", data)).format == "JPEG"


def test_an_animation_is_refused():
    frames = [Image.new("RGB", (20, 20), c) for c in ("red", "blue")]
    data = _save(frames[0], "WEBP", save_all=True, append_images=frames[1:])
    with pytest.raises(image_shrink.NotAPicture):
        image_shrink.shrink("webp", data)


@pytest.mark.parametrize("data", [b"", b"not a picture", b"\xff\xd8\xff\xe0" + b"\x00" * 20, b"\x89PNG\r\n\x1a\n..IEND\xaeB`\x82"])
def test_broken_or_fake_pictures_are_refused(data):
    with pytest.raises(image_shrink.NotAPicture):
        image_shrink.shrink("jpg", data)


def test_a_cut_off_jpeg_is_refused():
    whole = _save(Image.effect_noise((400, 400), 50).convert("RGB"), "JPEG")
    with pytest.raises(image_shrink.NotAPicture):
        image_shrink.shrink("jpg", whole[: len(whole) // 3])


def test_a_picture_bomb_is_refused_before_it_is_unpacked():
    """A tiny PNG whose header says 100 000 x 100 000 pixels (10 billion): refused from the header alone."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 100_000, 100_000, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" * 1000)) + chunk(b"IEND", b""))
    assert len(data) < 200
    with pytest.raises(image_shrink.NotAPicture):
        image_shrink.shrink("png", data)


def test_other_files_are_left_alone():
    pdf = b"%PDF-1.4 spec sheet %%EOF"
    assert image_shrink.shrink("pdf", pdf) == pdf


def test_a_palette_picture_saved_as_jpeg_keeps_its_rgb_profile():
    import io
    from PIL import Image, ImageCms
    from app.services import image_shrink
    srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    b = io.BytesIO()
    Image.new("P", (10, 10)).save(b, "PNG", icc_profile=srgb)
    out = Image.open(io.BytesIO(image_shrink.shrink("jpg", b.getvalue())))
    assert out.info.get("icc_profile")  # only a CMYK profile is dropped on the way to RGB


def test_a_typo_in_shrink_is_refused():
    import pytest
    from app.services import file_service
    with pytest.raises(ValueError):
        file_service.register_owner("typo-owner", lambda *a: True, shrink="Public")
