"""Extract fast-food nutrition from the brands' official India nutrition PDFs.

    python -m scripts.extract_brand_pdfs   # needs `pdftotext` (poppler-utils)

Writes data/brands/<brand>.json, which is reviewed and committed; the food
import reads those files. Every item keeps its source document and is
checked: stated energy must agree with 4/4/9 kcal per g of carbs/protein/fat.
"""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "brands"
OUT = ROOT / "data" / "brands"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

SOURCES = {
    "pizza_hut": {
        "brand": "Pizza Hut",
        "url": "https://www.pizzahut.co.in/order/pdfs/in/nutritionals.2602cddd8cb981ebba811b2951cfad28.pdf",
        "title": "Pizza Hut India: Menu card nutrition & allergen information booklet (lab-tested, FSSAI format)",
        "published": "2022",
    },
    "kfc": {
        "brand": "KFC",
        "url": "https://about.kfc.co.in/assets/files/jsk/nutrition-booklet-11.pdf",
        "title": "KFC India: Menu card nutrition & allergen information booklet (FSSAI format)",
        "published": "2022-05",
    },
    "mcdonalds": {
        "brand": "McDonald's",
        "url": "https://mcdindia.com/wp-content/uploads/2025/12/product-nutritional-information-bookletpdf.pdf",
        "title": "McDonald's India (North & East): Product nutritional information booklet",
        "published": "2025-12",
    },
}

NUM = r"(?:\d+(?:\.\d+)?|ND|NA|-)"


def fetch_text(key: str) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    pdf = RAW / f"{key}.pdf"
    if not pdf.exists():
        req = urllib.request.Request(SOURCES[key]["url"], headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
        pdf.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def num(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None  # ND (not detected), NA, -


def _clean(name: str) -> str:
    name = name.replace("\u200b", " ")
    return re.sub(r"\s+", " ", name).strip(" .")


# ---- Pizza Hut ---------------------------------------------------------------
# Food rows: weight, [slices], kcal, kcal%, then (from index 0 below) carb, protein, fibre,
#            sugar, added sugar, added%, fat, fat%, MUFA, PUFA, sat, sat%, trans, trans%,
#            cholesterol, sodium, sodium%
# Drink rows (in "Beverages"): volume ml, kcal, kcal%, carb, protein, fibre, sugar, ...same tail


PH_SECTIONS = [
    "Pan Pizza", "TnC Pizza", "Ultimate Cheese Pizzas", "Spicy Range Pizzas", "Spicy 3-IN-1", "Crafted Flatzz",
    "New Menu Gap Pizzas - Pan Pizzas", "New Menu Gap Pizzas - TnC Range", "Melts", "Flavour Fun Pizza",
    "Triple Spice Range Dips", "Triple Spice Range Fries", "Dips", "Garlic Breads", "Chicken Wings Spicy Range",
    "Chicken Wings", "Pastas", "Sides", "Dessert", "Beverages", "Hot Beverages", "Crust Upgrade",
    "Golden Hand Stretched Pizzas",
]


def parse_pizza_hut(text: str) -> list[dict]:
    items, section = [], ""
    row = re.compile(r"^\s{2,}([A-Za-z][\w '&()/.,+\-’]*?)\s{2,}((?:" + NUM + r"\s+){12,}" + NUM + r")(?=\s|$)")
    for line in text.splitlines():
        stripped = line.strip()
        known = next((s for s in PH_SECTIONS if stripped.lower() == s.lower()), None)
        if known:
            section = known
            continue
        m = row.match(line)
        if not m:
            continue
        name, v = _clean(m.group(1)), m.group(2).split()
        drink = section in ("Beverages", "Hot Beverages")
        if drink:
            vol, kcal, rest = num(v[0]), num(v[1]), v[3:]
            slices = None
        elif len(v) >= 21:
            vol, slices, kcal, rest = num(v[0]), num(v[1]), num(v[2]), v[4:]
        else:
            vol, slices, kcal, rest = num(v[0]), None, num(v[1]), v[3:]
        g = lambda i: num(rest[i]) if i < len(rest) else None  # noqa: E731
        items.append({
            "name": name, "section": section, "drink": drink,
            "weight": vol, "pieces": slices,
            "per_serving": {
                "energy_kcal": kcal, "carb_g": g(0), "protein_g": g(1), "fibre_g": g(2), "sugar_g": g(3),
                "fat_g": g(6), "sat_fat_g": g(10), "cholesterol_mg": g(14), "sodium_mg": g(15),
            },
        })
    return items


# ---- KFC -----------------------------------------------------------------------
# weight, servings, kcal, carb, protein, fat, fat%, trans, trans%, MUFA, PUFA, sat, sat%,
# sodium (g), sodium%, sugar, sugar%. The name wraps over the lines above, in the first column.


def parse_kfc(text: str) -> list[dict]:
    items, name_parts = [], []
    row = re.compile(r"^(\S.{0,9}?)?\s+(\d+(?:\.\d+)?)\s+(\d+)\s+(\d+\.\d+)\s+((?:" + NUM + r"\s+){12,}" + NUM + r")")
    skip = re.compile(r"^(Products|Snacks|Avg\.?|Portion|Weight|g|Total|Energ|Caffeine|and|Artificial|Stateme|nt)$", re.I)
    for line in text.splitlines():
        m = row.match(line)
        if m:
            name = _clean(" ".join(name_parts + [m.group(1) or ""]))
            v = m.group(5).split()
            items.append({
                "name": name, "section": "", "drink": False,
                "weight": num(m.group(2)), "pieces": None, "servings": num(m.group(3)),
                "per_serving": {
                    "energy_kcal": num(m.group(4)), "carb_g": num(v[0]), "protein_g": num(v[1]), "fat_g": num(v[2]),
                    "sat_fat_g": num(v[8]), "sodium_mg": (num(v[10]) or 0) * 1000, "sugar_g": num(v[12]),
                },
            })
            name_parts = []
            continue
        # The product name wraps over the first ~10 columns of the lines above its row.
        left = line[:10].strip()
        if left and not skip.match(left) and not re.fullmatch(r"[\d.%\s]+", left):
            name_parts.append(left)
    return items


# ---- McDonald's ------------------------------------------------------------------
# One product per page; labelled values, name in the left margin.

_MCD_FIELDS = {
    "serve": r"Serve Size \((?:g|ml)\)\s+([\d.]+)\s*(g|ml)",
    "energy_kcal": r"Energy \(kCal\)\s+([\d.]+)",
    "protein_g": r"Protein \(g\)\s+([\d.]+)",
    "fat_g": r"Total fat \(g\)\s+([\d.]+)",
    "sat_fat_g": r"Sat Fat \(g\)\s+([\d.]+)",
    "cholesterol_mg": r"Cholesterols? \(mg\)\s+([\d.]+)",
    "carb_g": r"\(g\)\s+([\d.]+)\s+(?:Not\s+)?recommended",  # "Total carbohydrate (g)" wraps
    "sugar_g": r"Total Sugars \(g\)\s+([\d.]+)",
    "sodium_mg": r"Sodium \(mg\)\s+([\d.]+)",
}
_MCD_LABELS = re.compile(r"Serve|Energy|Protein|Total|Sat Fat|Trans|Cholest|Added|Sodium|Not|recommended|Menu|PRODUCT|Allergen|per serve|percentage|contribution|RDA|Dietary|\(g\)")


def parse_mcdonalds(text: str) -> list[dict]:
    items = []
    for page in text.split("\f"):
        if "Energy (kCal)" not in page:
            continue
        found = {}
        for key, pat in _MCD_FIELDS.items():
            m = re.search(pat, page)
            if m:
                found[key] = m.groups()
        carb = re.search(r"Total carbohydrate.*?\n\s*\(g\)\s+([\d.]+)", page, re.S)
        name_parts = []
        for line in page.splitlines():
            left = line[:18].strip()
            if left and not _MCD_LABELS.search(left) and not re.fullmatch(r"[\d.%\s]+", left):
                name_parts.append(left)
        if "serve" not in found or "energy_kcal" not in found:
            continue
        size, unit = found["serve"]
        items.append({
            "name": _clean(" ".join(name_parts)), "section": "", "drink": unit == "ml",
            "weight": float(size), "pieces": None,
            "per_serving": {
                "energy_kcal": float(found["energy_kcal"][0]),
                "protein_g": float(found["protein_g"][0]) if "protein_g" in found else None,
                "fat_g": float(found["fat_g"][0]) if "fat_g" in found else None,
                "sat_fat_g": float(found["sat_fat_g"][0]) if "sat_fat_g" in found else None,
                "cholesterol_mg": float(found["cholesterol_mg"][0]) if "cholesterol_mg" in found else None,
                "carb_g": float(carb.group(1)) if carb else None,
                "sugar_g": float(found["sugar_g"][0]) if "sugar_g" in found else None,
                "sodium_mg": float(found["sodium_mg"][0]) if "sodium_mg" in found else None,
            },
        })
    return items


PARSERS = {"pizza_hut": parse_pizza_hut, "kfc": parse_kfc, "mcdonalds": parse_mcdonalds}

# ---- Curation ------------------------------------------------------------------------
# Turns parsed rows into loggable foods. Every correction is recorded in `flags`.

NONVEG = re.compile(r"chicken|keema|pepperoni|sausage|murg|wing|seekh|fish|filet|tikka supreme|non[- ]?veg|nugget|zinger|popcorn chicken|strips|bucket|crisper(?!.*veg)|double down|smoky|hot & cri", re.I)
EGG = re.compile(r"\begg\b|mayo(?!.*eggless)", re.I)
VEG_OVERRIDE = re.compile(r"\bveg\b|paneer|veggie|aloo|corn|margherita|mushroom|fries", re.I)


def diet_for(name: str) -> str:
    if NONVEG.search(name) and not re.search(r"\bveg\b(?! *[- ]?non)", name, re.I) or re.search(r"non[- ]?veg", name, re.I):
        return "nonveg"
    if EGG.search(name):
        return "egg"
    return "veg"


def _food(name, category, unit, size, n, *, flags=(), diet=None, ref=""):
    n = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in n.items() if v is not None}
    flags = list(flags)
    if "carb_g" not in n and n.get("energy_kcal") is not None:
        # Not published: carbohydrate by difference (Atwater 4/4/9), an estimate.
        carb = (n["energy_kcal"] - 4 * n.get("protein_g", 0) - 9 * n.get("fat_g", 0)) / 4
        n["carb_g"] = round(max(carb, 0.0), 2)
        flags.append("carbs_by_difference")
    return {"name": name, "category": category, "serving_unit": unit, "serving_size": size,
            "per_serving": n, "diet": diet or diet_for(name), "flags": flags, "ref": ref}


PIZZA_SECTIONS = {"Pan Pizza": "Pan", "TnC Pizza": "Thin 'n Crispy", "Ultimate Cheese Pizzas": "Ultimate Cheese",
                  "Spicy Range Pizzas": "Pan", "New Menu Gap Pizzas - Pan Pizzas": "Pan",
                  "New Menu Gap Pizzas - TnC Range": "Thin 'n Crispy", "Flavour Fun Pizza": "Pan",
                  "Golden Hand Stretched Pizzas": "Hand Stretched"}


def curate_pizza_hut(items: list[dict]) -> tuple[list[dict], list[str]]:
    foods, dropped = [], []
    names = {}
    for it in items:
        names.setdefault((it["section"], it["name"]), []).append(it)
    for it in items:
        name, sec, n = it["name"], it["section"], dict(it["per_serving"])
        if not it["energy_check"]:
            dropped.append(f"{name}: energy disagrees with its macros in the source")
            continue
        if "+" in name and sec == "Spicy Range Pizzas":
            dropped.append(f"{name}: 3-in-1 combo whose name wraps across lines in the source")
            continue
        twins = names[(sec, name)]
        diet = None
        piece_section = sec in {"Chicken Wings", "Chicken Wings Spicy Range", "Garlic Breads", "Melts", "Sides"}
        if len(twins) == 2 and sec == "Spicy Range Pizzas":
            # Checked on page 5: each name appears as a veg pizza, then a chicken one.
            veg = twins[0] is it
            name = name.replace(" (", " (Veg, " if veg else " (Chicken, ", 1) if "(" in name else f"{name} ({'Veg' if veg else 'Chicken'})"
            diet = "veg" if veg else "nonveg"
        elif len(twins) > 1 and not it["drink"] and not piece_section:
            dropped.append(f"{name} ({sec}): listed twice; the booklet tells them apart only by a veg/non-veg symbol")
            continue
        if it["drink"] and name in {"Mirinda", "Pepsi Black"} and it["weight"] == 330:
            dropped.append(f"{name} 330 ml: inconsistent with the 250 ml row of the same drink")
            continue
        if sec == "Crust Upgrade":
            dropped.append(f"{name}: crust add-on, not a dish")
            continue
        pieces = it["pieces"]
        packed = re.search(r"\((\d+)\s*pc\.?\)\s*(\d+)$", name)
        if packed:  # e.g. "Wings (6pc.) 231": pieces and weight run into the name in the source
            pieces, it = float(packed.group(1)), {**it, "weight": float(packed.group(2))}
            name = name[: packed.start()].strip()
        size = f"{it['weight']:g} {'ml' if it['drink'] else 'g'}" if it["weight"] else ""
        if it["drink"]:
            foods.append(_food(f"{name} ({size})", "Beverages", "glass", size, n, diet="veg", ref=sec))
        elif sec in PIZZA_SECTIONS and pieces and pieces > 1:
            crust = PIZZA_SECTIONS[sec]
            has_crust = re.search(rf"\b{re.escape(crust)}\b", name, re.I) or re.search(r"\bTnC\b", name)
            label = name if has_crust else f"{name}, {crust}"
            per = {k: v / pieces for k, v in n.items() if v is not None}
            foods.append(_food(f"{label} ({int(pieces)} slices per pizza)", "Pizza", "slice", f"{it['weight'] / pieces:.0f} g", per, diet=diet, ref=sec))
        elif pieces and pieces > 1 and piece_section:
            clean = re.sub(r"\s*\(\d+\s*pc\.?\)", "", name)
            if sec == "Melts" and "melt" not in clean.lower():
                clean = f"{clean} Melts"
            if any(f["name"] == clean for f in foods):
                continue  # same item in a bigger pack: per-piece values already added
            per = {k: v / pieces for k, v in n.items() if v is not None}
            foods.append(_food(clean, sec, "piece", f"{it['weight'] / pieces:.0f} g", per, ref=sec))
        else:
            suffix = {"Triple Spice Range Dips": "dip", "Triple Spice Range Fries": "fries", "Crafted Flatzz": "Crafted Flatzz",
                      "Pastas": "pasta", "Melts": "Melts"}.get(sec, "")
            if suffix and suffix.lower() not in name.lower():
                name = f"{name} {suffix}"
            foods.append(_food(name, sec or "Other", "serving", size, n, ref=sec))
    return foods, dropped


# KFC: hand-reviewed against the PDF (row index in the parsed table -> name, per-piece count).
KFC_KEEP: dict[int, tuple[str, int, str]] = {
    0: ("Hot Wings", 2, "piece"), 1: ("Veg Strips", 4, "piece"), 3: ("Popcorn Chicken (Regular)", 1, "serving"),
    4: ("Popcorn Chicken (Medium)", 1, "serving"), 5: ("Popcorn Chicken (Large)", 1, "serving"),
    6: ("Boneless Strips", 3, "piece"), 8: ("Veg Biryani", 1, "serving"), 9: ("Classic Chicken Biryani", 1, "serving"),
    10: ("Popcorn Chicken Biryani", 1, "serving"), 11: ("Smoky Chicken Biryani", 1, "serving"),
    12: ("Veg Zinger Burger", 1, "serving"), 13: ("Chicken Zinger Burger", 1, "serving"),
    14: ("Spicy Zinger Burger", 1, "serving"), 17: ("Classic Chicken Crisper Burger", 1, "serving"),
    18: ("Spicy Chicken Crisper Burger", 1, "serving"), 23: ("Double Down Burger", 1, "serving"),
    24: ("Hot & Crispy Chicken", 1, "piece"), 30: ("Smoky Grilled Chicken", 1, "piece"),
    48: ("7Up Krush Lime (210 ml)", 1, "glass"), 51: ("Fries (Regular)", 1, "serving"),
    52: ("Fries (Medium)", 1, "serving"), 53: ("Fries (Large)", 1, "serving"), 54: ("Choco Mud Pie", 1, "serving"),
    55: ("Coffee Mousse Cake", 1, "serving"), 56: ("Pepsi (330 ml)", 1, "glass"), 57: ("Mirinda (330 ml)", 1, "glass"),
    58: ("7Up (330 ml)", 1, "glass"), 59: ("Mountain Dew (330 ml)", 1, "glass"), 60: ("Dynamite Mayo dip", 1, "serving"),
    61: ("Eggless Mayo dip", 1, "serving"), 62: ("Tandoori Masala Mayo dip", 1, "serving"),
    65: ("Red Bull (250 ml)", 1, "glass"),
}
KFC_DIET = {"Veg Strips": "veg", "Veg Biryani": "veg", "Veg Zinger Burger": "veg", "Eggless Mayo dip": "veg",
            "Dynamite Mayo dip": "egg", "Tandoori Masala Mayo dip": "egg"}


def curate_kfc(items: list[dict]) -> tuple[list[dict], list[str]]:
    foods = []
    for idx, (name, pieces, unit) in KFC_KEEP.items():
        it = items[idx]
        n = {k: v for k, v in it["per_serving"].items() if v is not None}
        flags = []
        if idx == 48:  # carbohydrate and protein columns are swapped for this drink in the source
            n["carb_g"], n["protein_g"] = n["protein_g"], n["carb_g"]
            flags.append("source_columns_corrected")
        if not energy_ok(n):
            raise ValueError(f"KFC row {idx} {name} fails the energy check")
        per = {k: v / pieces for k, v in n.items()}
        size = f"{it['weight'] / pieces:.0f} {'ml' if unit == 'glass' else 'g'}"
        diet = KFC_DIET.get(name) or ("veg" if unit == "glass" or name.startswith(("Fries", "Choco", "Coffee")) else "nonveg")
        foods.append(_food(name, "KFC", unit, size, per, flags=flags, diet=diet, ref=f"row {idx}"))
    dropped = [
        "Classic/Spicy Veg Crisper, Tandoori Zinger, Zinger Doubles, Crisper doubles: energy disagrees with macros in the source",
        "Thousand Island Mayo: 108 g carbohydrate in a 20 g dip in the source",
        "Multi-piece buckets and promotions: values are per serving of a bucket; log pieces instead",
        "Two Krusher drinks: names unreadable in the source",
    ]
    return foods, dropped


# McDonald's multi-size pages (28-60), read from the PDF page images. (page, name, unit, size, values)
MCD_MANUAL: list[tuple[int, str, str, str, dict, str]] = [
    (28, "McFlavor Fries (Regular)", "serving", "110 g", dict(energy_kcal=289.81, protein_g=5.19, fat_g=15.54, sat_fat_g=7.77, cholesterol_mg=3.22, carb_g=29.98, sugar_g=1.14, sodium_mg=329.84), "veg"),
    (28, "McFlavor Fries (Medium)", "serving", "155 g", dict(energy_kcal=408.42, protein_g=7.3, fat_g=21.89, sat_fat_g=10.94, cholesterol_mg=4.5, carb_g=42.37, sugar_g=1.5, sodium_mg=463.09), "veg"),
    (29, "Chicken Nuggets", "piece", "16 g", dict(energy_kcal=168.58 / 4, protein_g=10.03 / 4, fat_g=9.54 / 4, sat_fat_g=4.45 / 4, sodium_mg=313.25 / 4), "nonveg"),
    (30, "Fries (Regular)", "serving", "77 g", dict(energy_kcal=215.77, protein_g=3.38, fat_g=10.39, sat_fat_g=4.97, sodium_mg=153.15), "veg"),
    (30, "Fries (Medium)", "serving", "109 g", dict(energy_kcal=304.92, protein_g=4.79, fat_g=14.7, sat_fat_g=7.04, sodium_mg=216.79), "veg"),
    (30, "Fries (Large)", "serving", "154 g", dict(energy_kcal=431.11, protein_g=6.76, fat_g=20.77, sat_fat_g=9.95, sodium_mg=306.29), "veg"),
    (31, "Hot Coffee (200 ml)", "glass", "200 ml", dict(energy_kcal=6.8, protein_g=0, fat_g=0, carb_g=1.7, sugar_g=0, sodium_mg=0), "veg"),
    (32, "Soft Serve Cone", "serving", "81 g", dict(energy_kcal=85.73, protein_g=1.99, fat_g=1.82, sat_fat_g=1.31, cholesterol_mg=4.75, carb_g=15.23, sugar_g=10.68, sodium_mg=40.78), "veg"),
    (33, "Boba Sundae (Regular)", "serving", "115 g", dict(energy_kcal=147.28, protein_g=2.6, fat_g=3, sat_fat_g=2.2, cholesterol_mg=8, carb_g=27.44, sugar_g=25.19, sodium_mg=57.87), "veg"),
    (33, "Boba Sundae (Medium)", "serving", "145 g", dict(energy_kcal=185, protein_g=3.5, fat_g=4, sat_fat_g=2.9, cholesterol_mg=10.72, carb_g=34, sugar_g=31.19, sodium_mg=75.35), "veg"),
    (34, "McSwirl ButterScotch", "serving", "95 g", dict(energy_kcal=173.54, protein_g=2.82, fat_g=8.11, sat_fat_g=5.5, cholesterol_mg=6.09, carb_g=22.18, sugar_g=16.87, sodium_mg=39.67), "veg"),
    (35, "Waffle Cone (Regular)", "serving", "82 g", dict(energy_kcal=132.33, protein_g=3.5, fat_g=2.8, sat_fat_g=1.89, cholesterol_mg=6.69, carb_g=25.49, sugar_g=18.97, sodium_mg=70.95), "veg"),
    (35, "Waffle Cone (Mini)", "serving", "35 g", dict(energy_kcal=74.58, protein_g=1.9, fat_g=1.63, sat_fat_g=1.13, cholesterol_mg=4, carb_g=14.04, sugar_g=10.86, sodium_mg=38.78), "veg"),
    (36, "Sundae Mango (Regular)", "serving", "86 g", dict(energy_kcal=193.73, protein_g=3.09, fat_g=10, sat_fat_g=7.68, cholesterol_mg=6.69, carb_g=22.84, sugar_g=21.27, sodium_mg=57.5), "veg"),
    (36, "Sundae Mango (Medium)", "serving", "128 g", dict(energy_kcal=252.37, protein_g=4.39, fat_g=11.5, sat_fat_g=8.78, cholesterol_mg=10.72, carb_g=32.81, sugar_g=30.39, sodium_mg=84.05), "veg"),
    (37, "McSwirl Mango Dip", "serving", "91 g", dict(energy_kcal=150.03, protein_g=2.6, fat_g=9.32, sat_fat_g=5.3, cholesterol_mg=4.75, carb_g=19.4, sugar_g=14.8, sodium_mg=49.78), "veg"),
    (38, "Waffle McSwirl Choco (Regular)", "serving", "97 g", dict(energy_kcal=226.78, protein_g=4.12, fat_g=10.11, sat_fat_g=7.7, cholesterol_mg=6.69, carb_g=31.86, sugar_g=26.12, sodium_mg=87.45), "veg"),
    (38, "Waffle McSwirl Choco (Mini)", "serving", "42 g", dict(energy_kcal=120.58, protein_g=2.65, fat_g=5.3, sat_fat_g=3.9, cholesterol_mg=4, carb_g=19.86, sugar_g=13.88, sodium_mg=47.22), "veg"),
    (39, "Waffle McSwirl Mango (Regular)", "serving", "97 g", dict(energy_kcal=228.78, protein_g=4.42, fat_g=10.3, sat_fat_g=7.74, cholesterol_mg=6.69, carb_g=31.79, sugar_g=25.12, sodium_mg=84.45), "veg"),
    (39, "Waffle McSwirl Mango (Mini)", "serving", "42 g", dict(energy_kcal=122.58, protein_g=2.35, fat_g=5.33, sat_fat_g=3.93, cholesterol_mg=4.03, carb_g=19.4, sugar_g=13.96, sodium_mg=45.58), "veg"),
    (40, "McSwirl Chocodip", "serving", "93 g", dict(energy_kcal=160.14, protein_g=2.71, fat_g=7.14, sat_fat_g=5.25, cholesterol_mg=5.71, carb_g=20.92, sugar_g=15.39, sodium_mg=51.31), "veg"),
    (41, "Waffle McSwirl ButterScotch (Regular)", "serving", "99 g", dict(energy_kcal=230.78, protein_g=4, fat_g=11.11, sat_fat_g=8.7, cholesterol_mg=6.89, carb_g=32.26, sugar_g=26.8, sodium_mg=89.45), "veg"),
    (41, "Waffle McSwirl ButterScotch (Mini)", "serving", "44 g", dict(energy_kcal=121.8, protein_g=2.36, fat_g=6.3, sat_fat_g=4.1, cholesterol_mg=4.04, carb_g=19.27, sugar_g=12.88, sodium_mg=45.22), "veg"),
    (42, "Sundae Chocolate (92 g)", "serving", "92 g", dict(energy_kcal=121.64, protein_g=2.25, fat_g=4.02, sat_fat_g=3.01, cholesterol_mg=5.85, carb_g=19.11, sugar_g=17.07, sodium_mg=65.56), "veg"),
    (42, "Sundae Chocolate (132 g)", "serving", "132 g", dict(energy_kcal=197.45, protein_g=3.49, fat_g=6.87, sat_fat_g=5.16, cholesterol_mg=8.55, carb_g=30.42, sugar_g=27.01, sodium_mg=110.39), "veg"),
    (43, "McFlurry Choco Crunch (Regular)", "serving", "94 g", dict(energy_kcal=154.19, protein_g=2.62, fat_g=5.39, sat_fat_g=3.91, cholesterol_mg=5.37, carb_g=23.67, sugar_g=17.36, sodium_mg=420), "veg"),
    (43, "McFlurry Choco Crunch (Medium)", "serving", "167 g", dict(energy_kcal=332.91, protein_g=5.04, fat_g=16, sat_fat_g=6.94, cholesterol_mg=9.53, carb_g=42.02, sugar_g=33.6, sodium_mg=700), "veg"),
    (46, "Fanta (Small, 299 ml)", "glass", "299 ml", dict(energy_kcal=129.48, protein_g=0, fat_g=0, carb_g=32.37, sugar_g=32.37, sodium_mg=55.53), "veg"),
    (46, "Fanta (Medium, 394 ml)", "glass", "394 ml", dict(energy_kcal=178.88, protein_g=0, fat_g=0, carb_g=44.72, sugar_g=44.72, sodium_mg=76.71), "veg"),
    (46, "Fanta (Large, 544 ml)", "glass", "544 ml", dict(energy_kcal=256.88, protein_g=0, fat_g=0, carb_g=64.22, sugar_g=64.22, sodium_mg=110.16), "veg"),
    (47, "McFlurry Oreo (Regular)", "serving", "87 g", dict(energy_kcal=116.36, protein_g=2.05, fat_g=3.7, sat_fat_g=2.25, cholesterol_mg=4.8, carb_g=18.69, sugar_g=14.49, sodium_mg=80.73), "veg"),
    (47, "McFlurry Oreo (Medium)", "serving", "147 g", dict(energy_kcal=209.39, protein_g=3.58, fat_g=6.81, sat_fat_g=4.07, cholesterol_mg=8, carb_g=33.42, sugar_g=25.35, sodium_mg=150.9), "veg"),
    (48, "Coca-Cola (Small, 299 ml)", "glass", "299 ml", dict(energy_kcal=109.56, protein_g=0, fat_g=0, carb_g=27.39, sugar_g=27.39, sodium_mg=21.17), "veg"),
    (48, "Coca-Cola (Medium, 394 ml)", "glass", "394 ml", dict(energy_kcal=151.36, protein_g=0, fat_g=0, carb_g=37.84, sugar_g=37.84, sodium_mg=29.24), "veg"),
    (48, "Coca-Cola (Large, 544 ml)", "glass", "544 ml", dict(energy_kcal=217.36, protein_g=0, fat_g=0, carb_g=54.34, sugar_g=54.34, sodium_mg=41.99), "veg"),
    (49, "Sundae Strawberry (Regular)", "serving", "92 g", dict(energy_kcal=100.99, protein_g=1.54, fat_g=1.77, sat_fat_g=1.3, cholesterol_mg=4.85, carb_g=19.78, sugar_g=17.66, sodium_mg=34.51), "veg"),
    (49, "Sundae Strawberry (Medium)", "serving", "132 g", dict(energy_kcal=156.14, protein_g=2.05, fat_g=2.36, sat_fat_g=1.74, cholesterol_mg=6.55, carb_g=31.77, sugar_g=28.2, sodium_mg=48.28), "veg"),
    (51, "Sundae Chocolate Brownie (Regular)", "serving", "111 g", dict(energy_kcal=203.26, protein_g=3.2, fat_g=5.45, sat_fat_g=3.65, cholesterol_mg=6.04, carb_g=35.26, sugar_g=20.75, sodium_mg=100.89), "veg"),
    (51, "Sundae Chocolate Brownie (Medium)", "serving", "155 g", dict(energy_kcal=307.39, protein_g=4.65, fat_g=7.46, sat_fat_g=4.71, cholesterol_mg=7.78, carb_g=55.24, sugar_g=27.94, sodium_mg=146.4), "veg"),
    (53, "Coca-Cola Zero (300 ml)", "glass", "300 ml", dict(energy_kcal=0, protein_g=0, fat_g=0, carb_g=0, sugar_g=0, sodium_mg=7.5), "veg"),
    (54, "Sprite (Small, 299 ml)", "glass", "299 ml", dict(energy_kcal=119.52, protein_g=0, fat_g=0, carb_g=29.88, sugar_g=29.88, sodium_mg=2.02), "veg"),
    (54, "Sprite (Medium, 394 ml)", "glass", "394 ml", dict(energy_kcal=165.12, protein_g=0, fat_g=0, carb_g=41.28, sugar_g=41.28, sodium_mg=2.79), "veg"),
    (54, "Sprite (Large, 544 ml)", "glass", "544 ml", dict(energy_kcal=237.12, protein_g=0, fat_g=0, carb_g=59.28, sugar_g=59.28, sodium_mg=4), "veg"),
    (55, "Cold Coffee (300 ml)", "glass", "300 ml", dict(energy_kcal=301.1, protein_g=9.75, fat_g=11.15, sat_fat_g=7.45, cholesterol_mg=27.4, carb_g=40.2, sodium_mg=175), "veg"),
    (55, "Cold Coffee (270 ml)", "glass", "270 ml", dict(energy_kcal=270.05, protein_g=5.91, fat_g=7.18, sat_fat_g=4.89, cholesterol_mg=15.81, carb_g=45.44, sodium_mg=173.59), "veg"),
    (56, "McFloat Coke", "glass", "287 ml", dict(energy_kcal=138.76, fat_g=1.75, sat_fat_g=1.28, sugar_g=24.54, sodium_mg=44.53), "veg"),
    (56, "McFloat Fanta", "glass", "287 ml", dict(energy_kcal=151.56, fat_g=1.75, sat_fat_g=1.28, sugar_g=27.74, sodium_mg=66.61), "veg"),
    (56, "McFloat Sprite", "glass", "287 ml", dict(energy_kcal=145.16, fat_g=1.75, sat_fat_g=1.28, sugar_g=26.14, sodium_mg=47.09), "veg"),
    (57, "Masala Chai (150 ml)", "glass", "150 ml", dict(energy_kcal=94.23, fat_g=1.46, sat_fat_g=0.87, sugar_g=13.68, sodium_mg=7.08), "veg"),
    (57, "Masala Chai (90 ml)", "glass", "90 ml", dict(energy_kcal=54.97, fat_g=0.85, sat_fat_g=0.51, sugar_g=7.98, sodium_mg=4.13), "veg"),
    (58, "Minute Maid Pulpy Orange (300 ml)", "glass", "300 ml", dict(energy_kcal=156, protein_g=0, sugar_g=34.5, sodium_mg=1), "veg"),
    (59, "Coke Zero (330 ml)", "glass", "330 ml", dict(energy_kcal=0.1, fat_g=0, sugar_g=0, sodium_mg=24.75), "veg"),
    (61, "Mustard Dip Sauce", "serving", "25 g", dict(energy_kcal=81.18, protein_g=0.52, fat_g=5.57, sat_fat_g=1.78, cholesterol_mg=0.29, carb_g=7.24, sugar_g=6.65, sodium_mg=221.32), "veg"),
    (62, "Barbeque Dip Sauce", "serving", "25 g", dict(energy_kcal=54.89, protein_g=0.26, fat_g=0.49, sat_fat_g=0.15, cholesterol_mg=0.25, carb_g=12.36, sugar_g=7.65, sodium_mg=113.23), "veg"),
    (64, "Cheese Slice (Extra)", "serving", "14 g", dict(energy_kcal=51.03, protein_g=3.06, fat_g=3.99, sat_fat_g=2.89, cholesterol_mg=13.43, carb_g=0.72, sugar_g=0.54, sodium_mg=178.95), "veg"),
    (65, "Tomato Ketchup sachet", "serving", "8 g", dict(energy_kcal=10, protein_g=0, fat_g=0, carb_g=2.5, sugar_g=2, sodium_mg=78.8), "veg"),
]
MCD_NAME_FIX = {"Filet-o-Fis Burger": "Filet-O-Fish Burger", "Cripsy Veggie Burger": "Crispy Veggie Burger",
                "Cheesy Mushroom Burger Ch": "Cheesy Mushroom Burger", "Cheesy Chicken Burger Ch": "Cheesy Chicken Burger",
                "McCrispy Chicken Burger Ch": "McCrispy Chicken Burger"}


def curate_mcdonalds(items: list[dict]) -> tuple[list[dict], list[str]]:
    foods, dropped = [], []
    for idx, it in enumerate(items[:27]):  # one-product pages, parsed from text
        name = MCD_NAME_FIX.get(it["name"], it["name"])
        if not it["energy_check"]:
            dropped.append(f"{name}: energy disagrees with its macros in the source")
            continue
        if it["drink"]:
            continue
        foods.append(_food(name, "McDonald's", "serving", f"{it['weight']:g} g", it["per_serving"], ref=f"page {idx + 1}"))
    for page, name, unit, size, values, diet in MCD_MANUAL:
        f = _food(name, "McDonald's", unit, size, values, diet=diet, ref=f"page {page} (read from page image)")
        if not energy_ok(f["per_serving"]):
            raise ValueError(f"McDonald's {name} fails the energy check")
        foods.append(f)
    dropped.append("Maple Flavoured Syrup: 72 g carbohydrate in a 28 g serving in the source")
    return foods, dropped


CURATORS = {"pizza_hut": curate_pizza_hut, "kfc": curate_kfc, "mcdonalds": curate_mcdonalds}


def energy_ok(n: dict) -> bool:
    kcal = n.get("energy_kcal")
    if kcal is None:
        return False
    macros = 4 * (n.get("carb_g") or 0) + 4 * (n.get("protein_g") or 0) + 9 * (n.get("fat_g") or 0)
    if kcal < 15 and macros < 15:
        return True  # zero-calorie drinks
    return abs(kcal - macros) <= max(25.0, 0.15 * kcal)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, parse in PARSERS.items():
        items = parse(fetch_text(key))
        for it in items:
            it["energy_check"] = energy_ok(it["per_serving"])
        foods, dropped = CURATORS[key](items)
        doc = {"source": SOURCES[key], "foods": foods, "not_included": dropped}
        (OUT / f"{key}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{key}: {len(foods)} foods, {len(dropped)} rows not included")


if __name__ == "__main__":
    main()
