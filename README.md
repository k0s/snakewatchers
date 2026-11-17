# snakewatchers

Rules for [asp](https://github.com/k0s/asp), the filesystem data pipeline. asp is
the engine and holds no rules of its own; a **watcher** is a module of rules that
`asp.json` names.

## `snakewatchers.thumbs`

Images get a thumbnail beside them, in the directories that ask for one:

```
gallery/photo.jpg  ->  gallery/thumbs/thumb_photo.jpg
```

```json
{"roots": {"site": "/home/me/site"},
 "db": "/home/me/.local/state/asp/asp.db",
 "watchers": ["snakewatchers.thumbs"]}
```

A directory asks in its metadata, the same file the
[k0sNgin](https://github.com/k0s/k0sNgin) web server reads to lay out a gallery,
so the page and the generator cannot disagree:

```json
{"version": 1, "k0sngin": {"images": {"thumbnails": true, "width": 150}}}
```

in `index.json`, or `/images = thumbnails, size=150x` in an `index.ini`. Where a
directory has both, `index.json` counts. The request is not inherited by
subdirectories.

- **Size.** Thumbnails fit the `width` and `height` the directory shows them at
  (150 wide if it states neither), keep their shape and their format, and are
  never larger than the original.
- **Existing thumbnails are kept** when they are newer than their image and
  already the right size, so thumbnails made by something else survive, and a
  re-run rewrites nothing. Otherwise the thumbnail is replaced.
- Matches `.jpg`, `.jpeg`, `.png`, `.gif` and `.webp`, in lower or upper case.
- EXIF orientation is applied, so phone photos come out the right way up.
- An animated image yields its first frame.
- A file that can't be decoded fails its job, which asp retries and then parks
  where the dashboard shows it. Nothing is written for it.
- asp never runs a handler on its own outputs, so `thumbs/thumb_*` files are not
  thumbnailed in turn.
- A directory that sets `thumb_dir` or `thumb_prefix` to something else is left
  alone: the rule writes to one fixed place.
- Images in directories that don't ask show in asp as `skipped` jobs.

**Asking later does not look back.** A rule runs when an image is created or
changes. Turning thumbnails on for a directory whose images asp has already seen
makes none until those images change, or asp's journal is deleted so that it
sees everything afresh.

To make them larger than they are shown, for dense displays, change `scale` in
the rule's `params` in [`thumbs.py`](src/snakewatchers/thumbs.py).

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
