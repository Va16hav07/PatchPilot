"""Download IFCT 2017 and INDB, validate them, and load them into MongoDB.

    python -m scripts.import_foods            # download (if needed) + import
    python -m scripts.import_foods --dry-run  # validate and report only

Raw files go to data/raw/ (git-ignored: INDB has no published license, so we
never redistribute it). A quality report is written to data/import_report.md.
"""

import argparse
import asyncio
import collections
import urllib.request
from pathlib import Path

import openpyxl
from pymongo import ReplaceOne

from app import db as dbmod
from app.config import get_settings
from app import search_text
from app.importers import brands, curated, ifct, indb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "data" / "import_report.md"

IFCT_URL = "https://unpkg.com/ifct2017@2.1.2/compositions/index.csv"
INDB_BASE = "https://raw.githubusercontent.com/lindsayjaacks/Indian-Nutrient-Databank-INDB-/main/"
INDB_FILES = ("INDB.xlsx", "recipes.xlsx", "recipes_servingsize.xlsx")


def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, dest)
    return dest


def sheet(path: Path):
    return openpyxl.load_workbook(path, read_only=True).active.iter_rows(values_only=True)


def load_all() -> list[dict]:
    ifct_csv = fetch(IFCT_URL, RAW / "ifct2017_compositions.csv")
    paths = {f: fetch(INDB_BASE + f, RAW / f) for f in INDB_FILES}
    with open(ifct_csv, encoding="utf-8") as fh:
        foods = ifct.load(fh)
    dishes = indb.build(sheet(paths["INDB.xlsx"]), sheet(paths["recipes.xlsx"]), sheet(paths["recipes_servingsize.xlsx"]))
    docs = curated.apply(foods + dishes) + brands.load()
    for d in docs:
        d["search_key"] = search_text.food_key(d)
    return docs


def write_report(docs: list[dict]) -> None:
    by_source = collections.Counter(d["source"] for d in docs)
    quarantined = [d for d in docs if d["quarantined"]]
    flags = collections.Counter(f for d in docs for f in d["quality_flags"])
    lines = [
        "# Food import report",
        "",
        *(f"- {src}: {n} items" for src, n in sorted(by_source.items())),
        f"- Quarantined (hidden from search): {len(quarantined)}",
        "",
        "## Quality flags",
        "",
        *(f"- `{f}`: {n}" for f, n in flags.most_common()),
        "",
        "## Flagged items",
        "",
        "| id | name | flags | quarantined |",
        "|---|---|---|---|",
        *(
            f"| {d['_id']} | {d['name']} | {', '.join(d['quality_flags'])} | {'yes' if d['quarantined'] else ''} |"
            for d in docs
            if d["quality_flags"]
        ),
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {REPORT}")


async def upsert(docs: list[dict]) -> None:
    settings = get_settings()
    db = dbmod.connect(settings.mongo_uri, settings.mongo_db)
    try:
        await dbmod.ensure_indexes(db)
        result = await db.foods.bulk_write([ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs])
        # Shared foods that were renamed or dropped from a source. Users' recipes have no
        # such prefix and are never touched; past log entries keep their own snapshot.
        stale = await db.foods.delete_many({
            "_id": {"$regex": "^(ifct|indb|usda|curated|brand):", "$nin": [d["_id"] for d in docs]},
        })
        print(f"foods: {result.upserted_count} inserted, {result.modified_count} updated, {stale.deleted_count} removed")
    finally:
        await dbmod.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    docs = load_all()
    write_report(docs)
    print(f"{len(docs)} items, {sum(d['quarantined'] for d in docs)} quarantined")
    if not args.dry_run:
        asyncio.run(upsert(docs))


if __name__ == "__main__":
    main()
