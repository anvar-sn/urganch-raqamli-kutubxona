"""Helpers for extracting genuine Page-1 title/cover images from PDF files."""

import io
import pymupdf
from PIL import Image


def _page_has_ink(pix) -> bool:
    """Return True if rendered pixmap has visible non-white content."""
    if pix.width == 0 or pix.height == 0:
        return False
    mode = 'RGBA' if pix.alpha else 'RGB'
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert('L')
    # Downscale to 64x64 for fast ink density estimation
    thumb = img.resize((64, 64))
    pixels = thumb.getdata()
    non_white = sum(1 for v in pixels if v < 242)
    return non_white >= 18


def render_pdf_cover_bytes(pdf_source, max_width: int = 520, quality: int = 88) -> bytes | None:
    """Render the first non-blank page (title page / cover) of a PDF to JPEG bytes."""
    doc = None
    try:
        if isinstance(pdf_source, (bytes, bytearray)):
            doc = pymupdf.open(stream=pdf_source, filetype='pdf')
        else:
            doc = pymupdf.open(str(pdf_source))
        if len(doc) == 0:
            return None

        chosen_pix = None
        for idx in range(min(3, len(doc))):
            page = doc[idx]
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                continue
            scale = max(1.0, min(2.5, max_width / rect.width))
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            if _page_has_ink(pix) or idx == min(2, len(doc) - 1):
                chosen_pix = pix
                break

        if chosen_pix is None:
            return None

        img = Image.frombytes('RGB', (chosen_pix.width, chosen_pix.height), chosen_pix.samples)
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        return buf.getvalue()
    except Exception:
        return None
    finally:
        if doc is not None:
            doc.close()
