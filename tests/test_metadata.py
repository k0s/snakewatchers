"""Reading a directory's request for thumbnails."""

import json
from pathlib import Path

import pytest

from snakewatchers.metadata import Thumbnails, thumbnails_wanted


def index_json(directory: Path, data) -> None:
    (directory / "index.json").write_text(data if isinstance(data, str) else json.dumps(data))


def index_ini(directory: Path, text: str) -> None:
    (directory / "index.ini").write_text(text)


def test_no_metadata_asks_for_nothing(tmp_path: Path) -> None:
    assert thumbnails_wanted(tmp_path) is None


@pytest.mark.parametrize("images, expected", [
    ({"thumbnails": True}, Thumbnails()),
    ({"thumbnails": True, "width": 150, "columns": 4}, Thumbnails(width=150)),
    ({"thumbnails": True, "width": 160, "height": 160}, Thumbnails(160, 160)),
    ({"thumbnails": True, "thumb_dir": "small", "thumb_prefix": "t_"},
     Thumbnails(directory="small", prefix="t_")),
    ({"thumbnails": True, "width": "150", "height": -4}, Thumbnails()),
])
def test_index_json(tmp_path: Path, images, expected) -> None:
    index_json(tmp_path, {"version": 1, "k0sngin": {"images": images}})
    assert thumbnails_wanted(tmp_path) == expected


@pytest.mark.parametrize("data", [
    {"version": 1},
    {"version": 1, "k0sngin": {"images": {"width": 150}}},
    {"version": 1, "k0sngin": {"images": {"thumbnails": False}}},
    {"version": 1, "k0sngin": {"images": {"thumbnails": "yes"}}},
    {"version": 1, "k0sngin": "nope"},
    "{broken",
])
def test_index_json_that_does_not_ask(tmp_path: Path, data) -> None:
    index_json(tmp_path, data)
    assert thumbnails_wanted(tmp_path) is None


@pytest.mark.parametrize("text, expected", [
    ("/images = thumbnails, size=150x, columns=4\n", Thumbnails(width=150)),
    ("/images = thumbnails,size=160x160,columns=5\n", Thumbnails(160, 160)),
    ("/images = size=x480, thumbnails\n", Thumbnails(height=480)),
    ("/images = thumbnails\n", Thumbnails()),
    ("/title = T\n/images = thumbnails, thumb_dir=small\na.jpg = A\n",
     Thumbnails(directory="small")),
    ("/images = size=x480\n", None),
    ("/images =\n", None),
    ("/title = thumbnails\n", None),
    ("a.jpg = /images = thumbnails\n", None),
    ("/images = thumbnails\n/images = size=400x\n", None),
])
def test_index_ini(tmp_path: Path, text, expected) -> None:
    index_ini(tmp_path, text)
    assert thumbnails_wanted(tmp_path) == expected


def test_index_json_counts_when_both_exist(tmp_path: Path) -> None:
    index_ini(tmp_path, "/images = thumbnails, size=150x\n")
    index_json(tmp_path, {"version": 1})
    assert thumbnails_wanted(tmp_path) is None
    index_json(tmp_path, {"version": 1, "k0sngin": {"images": {"thumbnails": True, "width": 99}}})
    assert thumbnails_wanted(tmp_path) == Thumbnails(width=99)


def test_data_named_index_json_does_not_hide_index_ini(tmp_path: Path) -> None:
    index_json(tmp_path, {"nodes": [1, 2, 3]})
    index_ini(tmp_path, "/images = thumbnails, size=150x\n")
    assert thumbnails_wanted(tmp_path) == Thumbnails(width=150)


def test_the_request_is_not_inherited(tmp_path: Path) -> None:
    index_json(tmp_path, {"version": 1, "k0sngin": {"images": {"thumbnails": True}}})
    (tmp_path / "sub").mkdir()
    assert thumbnails_wanted(tmp_path / "sub") is None


def test_only_the_default_location_is_conventional() -> None:
    assert Thumbnails().conventional
    assert not Thumbnails(directory="small").conventional
    assert not Thumbnails(prefix="t_").conventional
