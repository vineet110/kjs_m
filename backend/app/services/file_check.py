"""Is an uploaded file really what its name says, and whole?

A "card.pdf" that is really a program, or a price list that broke half way through the upload, is refused
before it is saved. Python's own tools only: every format starts with fixed bytes (a "magic number"), many
end with fixed bytes too, and zip-based files (xlsx, docx, pptx, zip) can test every part inside.
"""
import io
import zipfile

OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # old Office files: xls, doc, ppt
OFFICE_FOLDER = {"xlsx": "xl/", "docx": "word/", "pptx": "ppt/"}  # new Office files are zips with this folder
HEIC_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"mif1", b"msf1"}
MOV_ATOMS = {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip"}
MAX_UNZIPPED = 300 * 1024 * 1024  # a "zip bomb" is tiny but grows to gigabytes when opened


def _zip_ok(data: bytes, folder: str | None) -> bool:
    if not data.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            parts = z.infolist()
            if sum(p.file_size for p in parts) > MAX_UNZIPPED:
                return False
            if folder and not any(p.filename.startswith(folder) for p in parts):
                return False  # a plain zip renamed to .xlsx
            if any(p.flag_bits & 0x1 for p in parts):
                return False  # password-protected: we can't check (or preview) what's inside
            return z.testzip() is None  # None = every part inside reads back correctly
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, NotImplementedError, ValueError, RuntimeError):
        return False


def is_valid(ext: str, data: bytes) -> bool:
    """True when `data` looks like a whole .ext file. Unknown types are refused (they shouldn't get here)."""
    if ext == "pdf":
        return data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]  # cut short = no end marker
    if ext == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"IEND\xaeB`\x82")
    if ext in ("jpg", "jpeg"):
        # Needs its end marker too, but not as the very last bytes: some phones add extra data after it
        return data.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in data[3:]
    if ext == "gif":
        return data[:6] in (b"GIF87a", b"GIF89a") and data.endswith(b";")
    if ext == "webp":  # RIFF says its own size, so a cut-short file doesn't match
        return (data.startswith(b"RIFF") and data[8:12] == b"WEBP"
                and int.from_bytes(data[4:8], "little") + 8 == len(data))
    if ext == "heic":
        return data[4:8] == b"ftyp" and data[8:12] in HEIC_BRANDS
    if ext == "mp4":
        return data[4:8] == b"ftyp"
    if ext == "mov":
        return data[4:8] in MOV_ATOMS
    if ext in ("xls", "doc", "ppt"):
        return data.startswith(OLE)
    if ext in ("xlsx", "docx", "pptx", "zip"):
        return _zip_ok(data, OFFICE_FOLDER.get(ext))
    if ext in ("csv", "txt"):
        return b"\x00" not in data  # text never has zero bytes; programs and images do
    return False
