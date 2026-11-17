"""Thumbnails, for the directories that ask for them.

Name this module in ``asp.json``::

    {"roots": {"site": "~/web/site"}, "watchers": ["snakewatchers.thumbs"]}

An image gets ``thumbs/thumb_<name>`` beside it when its directory's metadata
asks for thumbnails (see ``metadata.py``): ``index.json`` with
``"k0sngin": {"images": {"thumbnails": true}}``, or ``index.ini`` with
``/images = thumbnails``. Every other image is left alone; asp records that
the rule had nothing to do.

The rule applies in every root. asp never runs a handler on its own outputs,
so thumbnails are not thumbnailed.
"""

from typing import BinaryIO

from asp import Event, rule
from PIL import Image, ImageOps

from .metadata import Thumbnails, thumbnails_wanted

# Used when a directory asks for thumbnails without saying how big it shows them.
WIDTH = 150
# Tall enough that only extreme portraits are limited by height.
HEIGHT = 1200

FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".webp": "WEBP"}
MATCH = "**/*.{" + ",".join(
    case for suffix in FORMATS for case in (suffix[1:], suffix[1:].upper())) + "}"
OUTPUT = "{dir}/thumbs/thumb_{name}"


def box(wanted: Thumbnails, scale: int) -> tuple[int, int]:
    """The size thumbnails must fit: the size the directory displays them at,
    times `scale`. A side it does not state is left loose."""
    if wanted.width is None and wanted.height is None:
        return WIDTH * scale, HEIGHT * scale
    return ((wanted.width or 10 * (wanted.height or WIDTH)) * scale,
            (wanted.height or 10 * (wanted.width or WIDTH)) * scale)


def fitted(size: tuple[int, int], within: tuple[int, int]) -> tuple[int, int]:
    """`size` scaled down to fit `within`, keeping its shape; never up."""
    ratio = min(within[0] / size[0], within[1] / size[1], 1.0)
    return max(1, round(size[0] * ratio)), max(1, round(size[1] * ratio))


def already_made(event: Event, within: tuple[int, int]) -> bool:
    """Whether a good thumbnail is already there: newer than its image, and
    the size this rule would make. Then it is left untouched, so thumbnails
    from before asp are kept and a re-run rewrites nothing."""
    existing = event.path.parent / "thumbs" / f"thumb_{event.path.name}"
    try:
        if existing.stat().st_mtime < event.path.stat().st_mtime or not existing.stat().st_size:
            return False
        with Image.open(existing) as thumb, Image.open(event.path) as image:
            source = ImageOps.exif_transpose(image).size
            want = fitted(source, within)
            # Resizers round differently; a pixel either way is the same thumbnail.
            return all(abs(have - wanted) <= 1 for have, wanted in zip(thumb.size, want))
    except (OSError, ValueError):
        return False


def make_thumbnail(source, out: BinaryIO, format: str, within: tuple[int, int]) -> None:
    """Write `source`, scaled to fit `within`, to `out`. An image that
    already fits is re-encoded at its own size, never enlarged."""
    with Image.open(source) as image:
        image.seek(0)                               # an animation's first frame
        image = ImageOps.exif_transpose(image)      # the pixels, the right way up
        image.thumbnail(within, Image.Resampling.LANCZOS)
        if format == "JPEG":
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(out, format, quality=85, optimize=True, progressive=True)
        elif format == "WEBP":
            image.save(out, format, quality=85)
        else:
            image.save(out, format, optimize=True)


@rule(name="thumbnail", on={"created", "modified"},
      match=MATCH, output=OUTPUT, params={"scale": 1})
def thumbnail(event: Event, out: BinaryIO | None, scale: int) -> BinaryIO | None:
    assert out is not None          # the rule declares an output
    wanted = thumbnails_wanted(event.path.parent)
    if wanted is None or not wanted.conventional:
        # Not asked for; or asked for somewhere this rule's fixed output
        # pattern can't put them.
        return None
    within = box(wanted, scale)
    if already_made(event, within):
        return None
    make_thumbnail(event.path, out, FORMATS[event.path.suffix.lower()], within)
    return out
