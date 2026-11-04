from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.infrastructure.importing.csv_importer import (
    CsvImportError,
    CsvImporter,
)


def test_parse_bool_accepts_common_representations() -> None:
    importer = CsvImporter()
    row = {"a": "1", "b": "false", "c": "YES"}

    assert importer._bool(row, "a") is True
    assert importer._bool(row, "b") is False
    assert importer._bool(row, "c") is True

    with pytest.raises(CsvImportError):
        importer._bool({"a": "maybe"}, "a")


def test_parse_decimal_and_datetime() -> None:
    importer = CsvImporter()
    row = {"price": "599.90", "date": "2025-10-15"}

    assert importer._decimal(row, "price") == Decimal("599.90")
    assert importer._datetime(row, "date") == datetime(
        2025, 10, 15, tzinfo=UTC
    )


def test_parse_json_requires_object() -> None:
    importer = CsvImporter()
    row = {"specs": '{"top": "Spruce"}'}

    assert importer._json(row, "specs", default={}) == {"top": "Spruce"}
    assert importer._json({"specs": ""}, "specs", default={"x": 1}) == {
        "x": 1
    }

    with pytest.raises(CsvImportError):
        importer._json({"specs": "[1, 2]"}, "specs", default={})


def test_read_csv_validates_required_columns(tmp_path: Path) -> None:
    importer = CsvImporter()
    path = tmp_path / "categories.csv"
    path.write_text(
        "category_id,name,description\n1,Guitarras,Guitarras elétricas\n",
        encoding="utf-8",
    )

    rows = importer._read_csv(path, required=("category_id", "name"))

    assert rows == [
        {
            "category_id": "1",
            "name": "Guitarras",
            "description": "Guitarras elétricas",
        }
    ]

    bad_path = tmp_path / "bad.csv"
    bad_path.write_text("category_id\n1\n", encoding="utf-8")

    with pytest.raises(CsvImportError, match="name"):
        importer._read_csv(bad_path, required=("category_id", "name"))
