# snakewatchers

Rules for [asp](https://github.com/k0s/asp), the filesystem data pipeline. asp is
the engine and holds no rules of its own; a **watcher** is a module of rules that
`asp.json` names.

## `snakewatchers.thumbs`

Every image under any root gets a thumbnail beside it:

```
gallery/photo.jpg  ->  gallery/thumbs/thumb_photo.jpg
```

```json
{"roots": {"site": "/home/me/site"},
 "db": "/home/me/.local/state/asp/asp.db",
 "watchers": ["snakewatchers.thumbs"]}
```

- Matches `.jpg`, `.jpeg`, `.png`, `.gif` and `.webp`, in lower or upper case.
- Thumbnails are at most 300 pixels wide (and 1200 tall), keep their shape and
  their format, and are never larger than the original.
- EXIF orientation is applied, so phone photos come out the right way up.
- An animated image yields its first frame.
- A file that can't be decoded fails its job, which asp retries and then parks
  where the dashboard shows it. Nothing is written for it.
- asp never runs a handler on its own outputs, so `thumbs/thumb_*` files are not
  thumbnailed in turn. Any image you put at such a path yourself is skipped too.
- An existing `thumbs/thumb_<name>` is overwritten the first time asp sees its image.

The width and height are `WIDTH` and `HEIGHT` in
[`thumbs.py`](src/snakewatchers/thumbs.py).

## Install

Into the environment asp runs in:

```sh
uv pip install "snakewatchers @ git+https://github.com/k0s/snakewatchers"
```

## Development

```sh
uv sync --group dev
uv run pytest
```

The tests run a real asp engine over a temp tree of generated pictures.
