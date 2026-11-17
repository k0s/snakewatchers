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

from pathlib import Path
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


def target(size: tuple[int, int], wanted: Thumbnails, scale: int) -> tuple[int, int]:
    """The size a thumbnail of an image of `size` should be.

    A directory that states both a width and a height shows every thumbnail
    at exactly that size, so the thumbnail is exactly that size (cropped to
    fill it). One that states a single side, or neither, gets the image
    scaled to that side, keeping its shape. Nothing is enlarged.
    """
    if wanted.width and wanted.height:
        return wanted.width * scale, wanted.height * scale
    if wanted.height:
        ratio = min(wanted.height * scale / size[1], 1.0)
    else:
        ratio = min((wanted.width or WIDTH) * scale / size[0], HEIGHT * scale / size[1], 1.0)
    return max(1, round(size[0] * ratio)), max(1, round(size[1] * ratio))


def good_enough(have: tuple[int, int], want: tuple[int, int]) -> bool:
    """Whether an existing thumbnail of size `have` will do where `want` is
    wanted: the same shape, and from the wanted size up to twice it. A
    thumbnail someone made a little larger is not worth replacing; one that is
    the wrong shape (cropped differently, or lying on its side) is."""
    same_shape = abs(have[0] * want[1] - have[1] * want[0]) <= 0.03 * have[0] * want[1] + want[1]
    return (same_shape and want[0] - 1 <= have[0] <= 2 * want[0] + 1
            and want[1] - 1 <= have[1] <= 2 * want[1] + 1)


def already_made(source: Path, wanted: Thumbnails, scale: int) -> bool:
    """Whether a good thumbnail is already there: newer than its image and
    good enough. Then it is left untouched, so thumbnails from before asp are
    kept and a re-run rewrites nothing."""
    existing = source.parent / "thumbs" / f"thumb_{source.name}"
    try:
        if existing.stat().st_mtime < source.stat().st_mtime or not existing.stat().st_size:
            return False
        with Image.open(existing) as thumb, Image.open(source) as image:
            return good_enough(thumb.size,
                               target(ImageOps.exif_transpose(image).size, wanted, scale))
    except (OSError, ValueError):
        return False


def make_thumbnail(source, out: BinaryIO, format: str, wanted: Thumbnails,
                   scale: int = 1) -> None:
    """Write a thumbnail of `source` to `out`, sized by `target`."""
    with Image.open(source) as image:
        image.seek(0)                               # an animation's first frame
        image = ImageOps.exif_transpose(image)      # the pixels, the right way up
        size = target(image.size, wanted, scale)
        if wanted.width and wanted.height:
            # Fill the box exactly, cropping the overflow evenly from both sides.
            image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
        else:
            image = image.resize(size, Image.Resampling.LANCZOS)
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
    if already_made(event.path, wanted, scale):
        return None
    make_thumbnail(event.path, out, FORMATS[event.path.suffix.lower()], wanted, scale)
    return out
