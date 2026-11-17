"""The thumbnail rule, run by a real engine over a temp tree."""

import json
from pathlib import Path

import pytest
from asp import Engine
from PIL import Image


def picture(path: Path, size: tuple[int, int], mode: str = "RGB", **save) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, "teal" if mode != "L" else 128).save(path, **save)


@pytest.fixture
def site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    picture(site / "wide.jpg", (1200, 800))
    picture(site / "gallery/tall.PNG", (600, 1800), "RGBA")
    picture(site / "gallery/small.gif", (40, 30), "P")
    picture(site / "gallery/photo.webp", (900, 900))
    (site / "gallery/notes.txt").write_text("not an image")
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "db": "asp.db",
        "watchers": ["snakewatchers.thumbs"]}))
    return site


def run(site: Path) -> Engine:
    engine = Engine.from_config(site.parent / "asp.json", {})
    engine.run_once()
    return engine


def size_of(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def test_every_image_gets_a_thumbnail_beside_it(site: Path) -> None:
    run(site)
    thumbs = {p.relative_to(site).as_posix() for p in site.rglob("thumb_*")}
    assert thumbs == {"thumbs/thumb_wide.jpg", "gallery/thumbs/thumb_tall.PNG",
                      "gallery/thumbs/thumb_small.gif", "gallery/thumbs/thumb_photo.webp"}


def test_thumbnails_fit_the_width_and_keep_their_shape(site: Path) -> None:
    run(site)
    assert size_of(site / "thumbs/thumb_wide.jpg") == (300, 200)
    assert size_of(site / "gallery/thumbs/thumb_tall.PNG") == (300, 900)
    assert size_of(site / "gallery/thumbs/thumb_photo.webp") == (300, 300)


def test_small_images_are_not_enlarged(site: Path) -> None:
    run(site)
    assert size_of(site / "gallery/thumbs/thumb_small.gif") == (40, 30)


def test_formats_are_kept(site: Path) -> None:
    run(site)
    formats = {}
    for thumb in site.rglob("thumb_*"):
        with Image.open(thumb) as image:
            formats[thumb.suffix.lower()] = image.format
    assert formats == {".jpg": "JPEG", ".png": "PNG", ".gif": "GIF", ".webp": "WEBP"}


def test_thumbnails_are_not_thumbnailed(site: Path) -> None:
    engine = run(site)
    for _ in range(3):
        engine.run_once()
    assert len(list(site.rglob("thumb_*"))) == 4
    assert not list(site.rglob("thumbs/thumbs"))
    assert engine.run_once().events == 0


def test_a_phone_photo_comes_out_the_right_way_up(site: Path) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6                                # rotate 90 degrees to display
    picture(site / "sideways.jpg", (800, 600), exif=exif)
    run(site)
    assert size_of(site / "thumbs/thumb_sideways.jpg") == (300, 400)


def test_a_changed_image_gets_a_new_thumbnail(site: Path) -> None:
    engine = run(site)
    picture(site / "wide.jpg", (800, 1600))
    engine.run_once()
    assert size_of(site / "thumbs/thumb_wide.jpg") == (300, 600)


def test_a_broken_image_fails_its_job_and_leaves_nothing(site: Path) -> None:
    (site / "broken.jpg").write_bytes(b"not a jpeg")
    engine = run(site)
    (job,) = engine.journal.jobs(state="failed")
    assert job["rel"] == "broken.jpg" and "UnidentifiedImageError" in job["error"]
    assert not (site / "thumbs/thumb_broken.jpg").exists()
    assert not list(site.rglob(".asp-*"))
