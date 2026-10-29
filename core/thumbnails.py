"""Cached, responsive catalog images; uploaded originals are never modified."""

from hashlib import sha256
from io import BytesIO
import logging

from django.core.files.base import ContentFile
from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)
WIDTHS = (360, 720, 1080)
SIZES = (
    "(max-width: 480px) min(304px, calc(92vw - 16px)), "
    "(max-width: 760px) calc((92vw - 48px) / 2), "
    "(max-width: 1100px) calc((92vw - 84px) / 3), "
    "calc((min(1200px, 92vw) - 130px) / 4)"
)


def catalog_thumbnail(image):
    if not image:
        return {"src": "", "srcset": "", "sizes": SIZES}
    fallback = {"src": image.url, "srcset": "", "sizes": SIZES}
    storage = image.storage
    try:
        # A changed upload gets new URLs, including when its filename is reused.
        version = f"catalog-v1:{image.name}:{storage.size(image.name)}:{storage.get_modified_time(image.name).isoformat()}"
        key = sha256(version.encode()).hexdigest()[:24]
        candidates = []
        with storage.open(image.name, "rb") as source:
            with Image.open(source) as opened:
                source_width, source_height = opened.size
                if opened.getexif().get(274) in (5, 6, 7, 8):
                    source_width, source_height = source_height, source_width
                max_width = min(source_width, source_height * 4 // 5)
                widths = sorted({min(width, max_width) for width in WIDTHS})
                names = [f"catalog_thumbnails/{key}-{width}.webp" for width in widths]
                missing = [not storage.exists(name) for name in names]
                original = ImageOps.exif_transpose(opened).convert("RGB") if any(missing) else None
        for width, name, needs_creation in zip(widths, names, missing):
            height = round(width * 5 / 4)
            if needs_creation:
                thumbnail = ImageOps.fit(
                    original, (width, height), method=Image.Resampling.LANCZOS
                )
                thumbnail = thumbnail.filter(
                    ImageFilter.UnsharpMask(radius=0.6, percent=80, threshold=3)
                )
                output = BytesIO()
                thumbnail.save(output, "WEBP", quality=92, method=4)
                name = storage.save(name, ContentFile(output.getvalue()))
            candidates.append((storage.url(name), width))
        return {
            "src": candidates[0][0],
            "srcset": ", ".join(f"{url} {width}w" for url, width in candidates),
            "sizes": SIZES,
        }
    except (OSError, ValueError, NotImplementedError):
        logger.warning("Could not prepare catalog thumbnail for %s", image.name, exc_info=True)
        return fallback
