"""Thumbnails: every image gets ``thumbs/thumb_<name>`` beside it.

Name this module in ``asp.json``::

    {"roots": {"site": "~/web/site"}, "watchers": ["snakewatchers.thumbs"]}

The rule applies in every root. The output sits in the image's own directory,
so a gallery page can link ``thumbs/thumb_<name>`` without knowing how it got
there. asp never runs a handler on its own outputs, so thumbnails are not
thumbnailed.
"""

from typing import BinaryIO

from asp import Event, rule
from PIL import Image, ImageOps

# Twice the 150px a gallery shows them at, for dense displays.
WIDTH = 300
# Tall enough that only extreme portraits are limited by height.
HEIGHT = 1200

FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".webp": "WEBP"}
MATCH = "**/*.{" + ",".join(
    case for suffix in FORMATS for case in (suffix[1:], suffix[1:].upper())) + "}"


def make_thumbnail(source, out: BinaryIO, format: str, width: int, height: int) -> None:
    """Write `source`, scaled to fit width x height, to `out`. An image that
    already fits is re-encoded at its own size, never enlarged."""
    with Image.open(source) as image:
        image.seek(0)                               # an animation's first frame
        image = ImageOps.exif_transpose(image)      # the pixels, the right way up
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        if format == "JPEG":
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(out, format, quality=85, optimize=True, progressive=True)
        elif format == "WEBP":
            image.save(out, format, quality=85)
        else:
            image.save(out, format, optimize=True)


@rule(name="thumbnail", on={"created", "modified"},
      match=MATCH, output="{dir}/thumbs/thumb_{name}",
      params={"width": WIDTH, "height": HEIGHT})
def thumbnail(event: Event, out: BinaryIO | None, width: int, height: int) -> BinaryIO | None:
    assert out is not None          # the rule declares an output
    make_thumbnail(event.path, out, FORMATS[event.path.suffix.lower()], width, height)
    return out
