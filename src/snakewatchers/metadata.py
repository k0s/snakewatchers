"""What a directory's metadata says about thumbnails.

A directory asks for thumbnails in its ``index.json``::

    {"version": 1, "k0sngin": {"images": {"thumbnails": true, "width": 150}}}

or, in the older ``index.ini``, with ``/images = thumbnails, size=150x``. These
are the files the k0sNgin web server reads to lay out a gallery, so the
generator and the page that shows the thumbnails share one source. Where a
directory has both, ``index.json`` is the one that counts, as it is for the
server.

``images`` is not inherited: it applies to the directory that declares it.
"""

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DIR = "thumbs"
DEFAULT_PREFIX = "thumb_"


@dataclass(frozen=True)
class Thumbnails:
    """A directory's request for thumbnails."""
    width: int | None = None        # the size they are displayed at, if stated
    height: int | None = None
    directory: str = DEFAULT_DIR
    prefix: str = DEFAULT_PREFIX

    @property
    def conventional(self) -> bool:
        """Whether they go where the thumbnail rule writes them."""
        return (self.directory, self.prefix) == (DEFAULT_DIR, DEFAULT_PREFIX)


def _positive(value) -> int | None:
    return value if type(value) is int and value > 0 else None


def from_json(path: Path) -> Thumbnails | None | bool:
    """The request in an ``index.json``; None if it makes none; False if the
    file is not directory metadata at all (some other JSON with the name)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        return False
    namespace = data.get("k0sngin")
    images = namespace.get("images") if isinstance(namespace, dict) else None
    if not isinstance(images, dict) or images.get("thumbnails") is not True:
        return None
    return Thumbnails(width=_positive(images.get("width")),
                      height=_positive(images.get("height")),
                      directory=str(images.get("thumb_dir") or DEFAULT_DIR),
                      prefix=str(images.get("thumb_prefix") or DEFAULT_PREFIX))


def from_ini(path: Path) -> Thumbnails | None:
    """The request in an ``index.ini``'s ``/images`` line, if it makes one."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return None
    value = None
    for line in lines:
        key, separator, rest = line.partition("=")
        if separator and key.strip() == "/images" and not line[:1].isspace():
            value = rest            # a later line replaces an earlier one
    if value is None:
        return None
    flags, options = set(), {}
    for token in value.split(","):
        key, separator, rest = token.partition("=")
        if separator:
            options[key.strip()] = rest.strip()
        elif token.strip():
            flags.add(token.strip())
    if "thumbnails" not in flags:
        return None
    width = height = None
    if "x" in options.get("size", ""):
        try:
            width, height = (int(side) if side.strip() else None
                             for side in options["size"].split("x", 1))
        except ValueError:
            width = height = None
    return Thumbnails(width=_positive(width), height=_positive(height),
                      directory=options.get("thumb_dir") or DEFAULT_DIR,
                      prefix=options.get("thumb_prefix") or DEFAULT_PREFIX)


def thumbnails_wanted(directory: Path) -> Thumbnails | None:
    """What `directory` asks for, or None if it asks for no thumbnails."""
    found = from_json(directory / "index.json") if (directory / "index.json").is_file() else False
    if found is not False:
        return found
    return from_ini(directory / "index.ini") if (directory / "index.ini").is_file() else None
