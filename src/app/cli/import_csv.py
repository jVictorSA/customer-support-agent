import argparse
import asyncio
import logging
from pathlib import Path

from app.db.session import get_engine
from app.infrastructure.importing.csv_importer import (
    CsvImportError,
    CsvImporter,
)

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="import-csv",
        description=(
            "Import categories, products, customers, orders, order_items and "
            "promotions from a directory of CSV files."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Directory containing the six CSV files.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing rows before importing.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        asyncio.run(_run(args.source, truncate=args.truncate))
    except CsvImportError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc


async def _run(source: Path, *, truncate: bool) -> None:
    try:
        counts = await CsvImporter().import_directory(
            source,
            truncate=truncate,
        )
    finally:
        await get_engine().dispose()

    for table, count in counts.items():
        logger.info("%s: %s rows", table, count)
    logger.info("Import finished successfully")


if __name__ == "__main__":
    main()
