"""Fast food and packaged drinks from the brands' own published India nutrition data.

Reads data/brands/*.json (built and reviewed by scripts/extract_brand_pdfs.py,
or hand-entered from official product pages). Restaurant items become dishes
with one serving = one slice / piece / serving / glass. Packaged drinks become
per-100 ml ingredients so any volume can be logged.

Brands publish energy, macros, sugar, saturated fat, cholesterol and sodium
only; vitamins and other minerals are unknown and stored as 0, which is
flagged so insights can say so.
"""

import json
import re
from pathlib import Path

from app.nutrition import nutrients as N

BRANDS_DIR = Path(__file__).resolve().parents[2] / "data" / "brands"

ALIASES = {
    "Pizza Hut": ["Pizza Hut", "Pizzahut"],
    "KFC": ["KFC", "Kentucky"],
    "McDonald's": ["McDonald's", "McDonalds", "Mcd", "McD"],
    "Coca-Cola India": [],
}
# Everyday names for specific products.
PRODUCT_ALIASES = [
    (re.compile(r"Coca-Cola(?! Zero)", re.I), ["Coke"]),
    (re.compile(r"Coca-Cola Zero|Coke Zero", re.I), ["Coke Zero"]),
    (re.compile(r"^Aloo Tikki Burger", re.I), ["McAloo Tikki", "McAloo"]),
    (re.compile(r"Mountain Dew", re.I), ["Dew"]),
    (re.compile(r"Thums Up", re.I), ["Thumbs up"]),
]


def _aliases(brand: str, product: str) -> list[str]:
    names = list(ALIASES.get(brand, [brand]))
    for pattern, extra in PRODUCT_ALIASES:
        if pattern.search(product):
            names += extra
    return names


_KEEP = {"energy_kcal", "protein_g", "carb_g", "fat_g", "fibre_g", "sugar_g", "sat_fat_g", "cholesterol_mg", "sodium_mg"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _nutrients(values: dict) -> dict:
    return N.rounded({**N.zero(), **{k: float(v) for k, v in values.items() if k in _KEEP and v is not None}})


def _source_note(src: dict) -> str:
    return f"{src['title']} ({src['published']}). {src['url']}"


def load(directory: Path = BRANDS_DIR) -> list[dict]:
    docs = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        src = data["source"]
        brand = src["brand"]
        for f in data.get("foods", []):
            name = f"{brand} {f['name']}"
            docs.append({
                "_id": f"brand:{path.stem}:{_slug(f['name'])}",
                "source": brand,
                "source_code": None,
                "kind": "dish",
                "name": name,
                "brand": brand,
                "local_names": _aliases(brand, f["name"]),
                "group": f["category"],
                "serving": {
                    "unit": f["serving_unit"],
                    "container_ml": None,
                    "nutrients": _nutrients(f["per_serving"]),
                    "added_fat_g": None,
                    "size": f["serving_size"],
                },
                "source_note": _source_note(src) + (f" ({f['ref']})" if f.get("ref") else ""),
                "diet": f["diet"],
                "jain_ok": False,  # ingredients not published
                "quality_flags": sorted(set(f["flags"]) | {"partial_nutrients"}),
                "quarantined": False,
            })
        for d in data.get("per_100ml", []):
            docs.append({
                "_id": f"brand:{path.stem}:{_slug(d['name'])}",
                "source": brand,
                "source_code": None,
                "kind": "ingredient",
                "name": d["name"],
                "brand": brand,
                "local_names": _aliases(brand, d["name"]) + ["cold drink", "soft drink"],
                "group": "Beverages",
                "per_100g": _nutrients(d["values"]),  # per 100 ml; density 1.0 so g == ml
                "density_g_per_ml": 1.0,
                "source_note": f"{src['brand']} product page, per 100 ml ({src['published']}). {d['url']}",
                "diet": "veg",
                "jain_ok": True,
                "quality_flags": ["partial_nutrients"],
                "quarantined": False,
            })
    ids = [d["_id"] for d in docs]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate brand food ids: {dupes[:5]}")
    return docs
