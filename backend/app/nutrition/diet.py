"""Diet classification of foods, and which foods suit which diet.

Every food gets `diet`: "veg", "egg" or "nonveg", and `jain_ok`.
IFCT food codes start with their group letter: M eggs; N poultry; O meat;
P, Q, R, S fish and shellfish; F roots and tubers.
"""

import re
from typing import Literal

FoodDiet = Literal["veg", "egg", "nonveg"]
UserDiet = Literal["vegetarian", "eggetarian", "non_vegetarian", "jain"]

NONVEG_GROUPS = set("NOPQRS")
EGG_GROUPS = {"M"}
# Not eaten on a Jain diet: roots and tubers, plus these bulbs and rhizomes.
# garlic (3 kinds), fresh ginger, mango ginger, onions (big, small, stalk)
JAIN_EXCLUDED_CODES = {"G011", "G012", "G013", "G014", "G015", "G017", "G018", "D058"}
JAIN_EXCLUDED_GROUPS = {"F"}

_NONVEG_NAME = re.compile(
    r"\b(chicken|mutton|lamb|goat|beef|pork|meat|keema|fish|prawns?|shrimps?|crab|lobster|squid|anchov\w*|tuna|salmon|sardines?|mackerel|bacon|ham|sausages?|gelatin)\b",
    re.I,
)
_EGG_NAME = re.compile(r"\begg(s)?\b(?!\s*(plant|less))", re.I)
_NO_EGG_NAME = re.compile(r"\b(without\s+eggs?|eggless|egg[- ]free|vegetarian\s+egg)\b", re.I)
_JAIN_NAME = re.compile(r"\b(onions?|garlic|ginger|potato(es)?|carrots?|beetroot|radish|sweet potato|yam|aloo)\b", re.I)


def classify_ingredient(code: str | None, name: str) -> tuple[FoodDiet, bool]:
    group = (code or "")[:1]
    if group in NONVEG_GROUPS or _NONVEG_NAME.search(name):
        diet: FoodDiet = "nonveg"
    elif group in EGG_GROUPS or (_EGG_NAME.search(name) and not _NO_EGG_NAME.search(name)):
        diet = "egg"
    else:
        diet = "veg"
    jain_ok = diet == "veg" and group not in JAIN_EXCLUDED_GROUPS and (code or "") not in JAIN_EXCLUDED_CODES
    if jain_ok and not code and _JAIN_NAME.search(name):
        jain_ok = False
    return diet, jain_ok


def classify_dish(name: str, ingredients: list[dict]) -> tuple[FoodDiet, bool]:
    """A dish is as restrictive as its most restrictive ingredient (or its name)."""
    rank = {"veg": 0, "egg": 1, "nonveg": 2}
    diet, jain_ok = classify_ingredient(None, name)
    for ing in ingredients:
        d, j = classify_ingredient(ing.get("code"), str(ing.get("name") or ""))
        if rank[d] > rank[diet]:
            diet = d
        jain_ok = jain_ok and j
    return diet, jain_ok and diet == "veg"


def allowed_query(user_diet: UserDiet | None) -> dict:
    """Mongo filter for foods suitable for a user's diet."""
    if user_diet in (None, "non_vegetarian"):
        return {}
    if user_diet == "eggetarian":
        return {"diet": {"$in": ["veg", "egg"]}}
    if user_diet == "jain":
        return {"diet": "veg", "jain_ok": True}
    return {"diet": "veg"}
