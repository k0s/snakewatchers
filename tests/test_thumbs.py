"""The thumbnail rule, run by a real engine over a temp tree."""

import json
import os
from pathlib import Path

import pytest
from asp import Engine
from PIL import Image


def picture(path: Path, size: tuple[int, int], mode: str = "RGB", **save) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, "teal" if mode != "L" else 128).save(path, **save)


def ask(directory: Path, **images) -> None:
    """Give a directory an index.json asking for thumbnails."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.json").write_text(json.dumps(
        {"version": 1, "k0sngin": {"images": {"thumbnails": True, **images}}}))


@pytest.fixture
def site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    picture(site / "logo.png", (1200, 800))             # nobody asked
    ask(site / "gallery", width=150)
    picture(site / "gallery/wide.jpg", (1200, 800))
    picture(site / "gallery/tall.PNG", (600, 1800), "RGBA")
    picture(site / "gallery/small.gif", (40, 30), "P")
    picture(site / "gallery/photo.webp", (900, 900))
    picture(site / "gallery/unasked/deeper.jpg", (900, 900))    # not inherited
    (site / "gallery/notes.txt").write_text("not an image")
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "db": "asp.db",
        "watchers": ["snakewatchers.thumbs"]}))
    return site


def run(site: Path) -> Engine:
    engine = Engine.from_config(site.parent / "asp.json", {})
    engine.run_once()
    return engine


def thumbs(site: Path) -> set[str]:
    return {p.relative_to(site).as_posix() for p in site.rglob("thumb_*")}


def size_of(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def test_only_directories_that_ask_get_thumbnails(site: Path) -> None:
    engine = run(site)
    assert thumbs(site) == {
        "gallery/thumbs/thumb_wide.jpg", "gallery/thumbs/thumb_tall.PNG",
        "gallery/thumbs/thumb_small.gif", "gallery/thumbs/thumb_photo.webp"}
    states = {j["rel"]: j["state"] for j in engine.journal.jobs()}
    assert states["logo.png"] == states["gallery/unasked/deeper.jpg"] == "skipped"
    assert states["gallery/wide.jpg"] == "done"


def test_thumbnails_are_the_size_the_directory_shows_them(site: Path) -> None:
    run(site)
    assert size_of(site / "gallery/thumbs/thumb_wide.jpg") == (150, 100)
    assert size_of(site / "gallery/thumbs/thumb_tall.PNG") == (150, 450)
    assert size_of(site / "gallery/thumbs/thumb_photo.webp") == (150, 150)


@pytest.mark.parametrize("images, expected", [
    ({"width": 160, "height": 160}, (160, 160)),    # both stated: exactly that, cropped
    ({"height": 100}, (150, 100)),
    ({}, (150, 100)),
])
def test_stated_sizes(tmp_path: Path, images, expected) -> None:
    site = tmp_path / "site"
    ask(site, **images)
    picture(site / "wide.jpg", (1200, 800))
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "watchers": ["snakewatchers.thumbs"]}))
    Engine.from_config(tmp_path / "asp.json", {}).run_once()
    assert size_of(site / "thumbs/thumb_wide.jpg") == expected


def test_a_box_is_filled_by_cropping_the_middle(tmp_path: Path) -> None:
    site = tmp_path / "site"
    ask(site, width=100, height=100)
    image = Image.new("RGB", (300, 100), "red")
    image.paste("blue", (100, 0, 200, 100))         # the middle third
    image.save(site / "stripes.png")
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "watchers": ["snakewatchers.thumbs"]}))
    Engine.from_config(tmp_path / "asp.json", {}).run_once()
    with Image.open(site / "thumbs/thumb_stripes.png") as thumb:
        assert thumb.size == (100, 100)
        assert thumb.convert("RGB").getpixel((50, 50)) == (0, 0, 255)
        assert thumb.convert("RGB").getpixel((2, 50)) == (0, 0, 255)


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
    assert len(thumbs(site)) == 4
    assert not list(site.rglob("thumbs/thumbs"))
    assert engine.run_once().events == 0


def test_a_phone_photo_comes_out_the_right_way_up(site: Path) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6                                # rotate 90 degrees to display
    picture(site / "gallery/sideways.jpg", (800, 600), exif=exif)
    run(site)
    assert size_of(site / "gallery/thumbs/thumb_sideways.jpg") == (150, 200)


def test_a_changed_image_gets_a_new_thumbnail(site: Path) -> None:
    engine = run(site)
    picture(site / "gallery/wide.jpg", (800, 1600))
    engine.run_once()
    assert size_of(site / "gallery/thumbs/thumb_wide.jpg") == (150, 300)


def test_a_broken_image_fails_its_job_and_leaves_nothing(site: Path) -> None:
    (site / "gallery/broken.jpg").write_bytes(b"not a jpeg")
    engine = run(site)
    (job,) = engine.journal.jobs(state="failed")
    assert job["rel"] == "gallery/broken.jpg" and "UnidentifiedImageError" in job["error"]
    assert not (site / "gallery/thumbs/thumb_broken.jpg").exists()
    assert not list(site.rglob(".asp-*"))


# --- thumbnails that were there first ---

def earlier_thumbnail(site: Path, name: str, size: tuple[int, int], newer: bool = True) -> Path:
    thumb = site / "gallery/thumbs" / f"thumb_{name}"
    picture(thumb, size)
    stamp = (site / "gallery" / name).stat().st_mtime + (60 if newer else -60)
    os.utime(thumb, (stamp, stamp))
    return thumb


def test_a_good_existing_thumbnail_is_left_untouched(site: Path) -> None:
    thumb = earlier_thumbnail(site, "wide.jpg", (150, 100))
    before = (thumb.read_bytes(), thumb.stat().st_mtime)
    engine = run(site)
    assert (thumb.read_bytes(), thumb.stat().st_mtime) == before
    assert {j["rel"]: j["state"] for j in engine.journal.jobs()}["gallery/wide.jpg"] == "skipped"


def test_one_pixel_of_rounding_is_still_a_good_thumbnail(site: Path) -> None:
    thumb = earlier_thumbnail(site, "wide.jpg", (150, 101))
    before = thumb.read_bytes()
    run(site)
    assert thumb.read_bytes() == before


def test_a_somewhat_larger_existing_thumbnail_is_kept(site: Path) -> None:
    thumb = earlier_thumbnail(site, "wide.jpg", (160, 107))
    before = thumb.read_bytes()
    run(site)
    assert thumb.read_bytes() == before


@pytest.mark.parametrize("size", [(90, 60), (400, 267), (150, 150), (100, 150)])
def test_a_wrong_sized_or_wrong_shaped_existing_thumbnail_is_replaced(site: Path, size) -> None:
    thumb = earlier_thumbnail(site, "wide.jpg", size)
    run(site)
    assert size_of(thumb) == (150, 100)


def test_an_existing_cropped_thumbnail_is_kept_where_a_box_is_asked_for(tmp_path: Path) -> None:
    site = tmp_path / "site"
    ask(site, width=160, height=160)
    picture(site / "wide.jpg", (1200, 800))
    thumb = site / "thumbs/thumb_wide.jpg"
    picture(thumb, (160, 160))
    os.utime(thumb, (2_000_000_000, 2_000_000_000))
    before = thumb.read_bytes()
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "watchers": ["snakewatchers.thumbs"]}))
    Engine.from_config(tmp_path / "asp.json", {}).run_once()
    assert thumb.read_bytes() == before


def test_a_thumbnail_older_than_its_image_is_replaced(site: Path) -> None:
    thumb = earlier_thumbnail(site, "wide.jpg", (150, 100), newer=False)
    before = thumb.read_bytes()
    run(site)
    assert size_of(thumb) == (150, 100) and thumb.read_bytes() != before


def test_an_empty_existing_thumbnail_is_replaced(site: Path) -> None:
    thumb = site / "gallery/thumbs/thumb_wide.jpg"
    thumb.parent.mkdir()
    thumb.write_bytes(b"")
    os.utime(thumb, (2_000_000_000, 2_000_000_000))
    run(site)
    assert size_of(thumb) == (150, 100)


def test_a_directory_that_puts_thumbnails_elsewhere_is_left_alone(tmp_path: Path) -> None:
    site = tmp_path / "site"
    ask(site, thumb_dir="small", thumb_prefix="t_")
    picture(site / "wide.jpg", (1200, 800))
    (tmp_path / "asp.json").write_text(json.dumps({
        "roots": {"site": "site"}, "watchers": ["snakewatchers.thumbs"]}))
    Engine.from_config(tmp_path / "asp.json", {}).run_once()
    assert not list(site.rglob("thumb_*")) and not (site / "small").exists()
