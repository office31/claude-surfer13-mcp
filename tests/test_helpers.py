from pathlib import Path

import pytest

from surfer_mcp.surfer import SurferError, normalize_xyz


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_normalize_csv_with_header(tmp_path):
    source = _write(
        tmp_path,
        "points.csv",
        "X,Y,Z\n0,0,10\n100,0,20\n0,100,30\n100,100,40\n",
    )
    normalized, count = normalize_xyz(source, 3)
    try:
        assert count == 4
        lines = normalized.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "0 0 10"
        assert lines[-1] == "100 100 40"
    finally:
        normalized.unlink(missing_ok=True)


def test_normalize_semicolon_and_extra_columns(tmp_path):
    source = _write(
        tmp_path,
        "points.txt",
        "X;Y;Z;id\n1;2;3;1\n4;5;6;2\n7;8;9;3\n10;11;12;4\n",
    )
    normalized, count = normalize_xyz(source, 3)
    try:
        assert count == 4
        assert normalized.read_text(encoding="utf-8").splitlines()[1] == "4 5 6 2"
    finally:
        normalized.unlink(missing_ok=True)


def test_normalize_skips_non_numeric_rows(tmp_path):
    source = _write(
        tmp_path,
        "points.xyz",
        "# comment\nX Y Z\n1 2 3\n4 5 6\nbroken line\n7 8 9\n10 11 12\n",
    )
    normalized, count = normalize_xyz(source, 3)
    try:
        assert count == 4
    finally:
        normalized.unlink(missing_ok=True)


def test_normalize_rejects_too_few_points(tmp_path):
    source = _write(tmp_path, "few.csv", "1,2,3\n4,5,6\n")
    with pytest.raises(SurferError):
        normalize_xyz(source, 3)


def test_normalize_requires_requested_columns(tmp_path):
    source = _write(tmp_path, "two.csv", "1,2\n3,4\n5,6\n7,8\n")
    with pytest.raises(SurferError):
        normalize_xyz(source, 3)
