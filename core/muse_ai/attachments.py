from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path

from PIL import Image


def _mime_for(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("image/"):
        return mime
    suffix = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "application/octet-stream")


def _prepare_image_bytes(
    path: Path,
    *,
    max_dimension: int = 2048,
    target_bytes: int = 3_500_000,
    force_compress: bool = False,
) -> tuple[bytes, str, str]:
    raw = path.read_bytes()
    mime = _mime_for(path)
    if not mime.startswith("image/"):
        raise ValueError(f"{path} is not a supported image")

    # The Muse web client sends image attachments inline as base64.  Browser-side
    # preprocessing can shrink large images; mirror that behavior enough to keep
    # the whole chat.stream request inside Noise's ~16 MiB assembly budget.
    if not force_compress and len(raw) <= target_bytes:
        return raw, mime, path.name

    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        if max(image.size) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha and not force_compress:
            out = io.BytesIO()
            image.save(out, format="WEBP", quality=88, method=6)
            data = out.getvalue()
            return data, "image/webp", path.stem + ".webp"

        image = image.convert("RGB")
        quality = 88 if not force_compress else 82
        data = b""
        while quality >= 40:
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=quality, optimize=True)
            data = out.getvalue()
            if len(data) <= target_bytes:
                break
            quality -= 8
        return data, "image/jpeg", path.stem + ".jpg"


def build_image_item(
    path: str | Path,
    *,
    max_dimension: int = 2048,
    target_bytes: int = 3_500_000,
    force_compress: bool = False,
) -> dict:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(source)
    data, mime, filename = _prepare_image_bytes(
        source,
        max_dimension=max_dimension,
        target_bytes=target_bytes,
        force_compress=force_compress,
    )
    return {
        "type": "image",
        "mime_type": mime,
        "data_base64": base64.b64encode(data).decode("ascii"),
        "filename": filename,
    }


def build_items(images: list[str | Path], prompt: str) -> list[dict]:
    n = len(images)
    if n <= 1:
        max_dim, budget, force = 1600, 2_500_000, False
    elif n <= 4:
        max_dim, budget, force = 1280, min(1_000_000, 4_500_000 // n), True
    else:
        max_dim = 1024 if n <= 8 else 768
        budget = max(180_000, 4_000_000 // n)
        force = True
    items = [
        build_image_item(
            path,
            max_dimension=max_dim,
            target_bytes=budget,
            force_compress=force,
        )
        for path in images
    ]
    items.append({"type": "text", "text": prompt})
    return items
