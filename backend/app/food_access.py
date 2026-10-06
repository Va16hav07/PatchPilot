"""Which foods a user can see, and food search.

Shared foods (IFCT, INDB, USDA) have no `owner_id`. A user's own recipes carry
`owner_id` and are visible only to that user.
"""

import difflib
import re
import time

from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app import search_text

SEARCH_POOL = 200
_PROJECTION = {"ingredients": 0, "per_100g_raw_basis": 0}


def visible(user: dict) -> dict:
    # {"$in": [None, id]} also matches documents without the field.
    return {"owner_id": {"$in": [None, user["_id"]]}}


async def get_visible_food(db: AsyncDatabase, user: dict, food_id: str) -> dict:
    food = await db.foods.find_one({"_id": food_id, **visible(user)})
    if food is None:
        raise HTTPException(404, "food not found")
    return food


async def get_loggable_food(db: AsyncDatabase, user: dict, food_id: str) -> dict:
    food = await get_visible_food(db, user, food_id)
    if food.get("quarantined"):
        raise HTTPException(422, "this food failed data-quality checks and can't be logged")
    return food


def _match_tier(name: str, q: str) -> int:
    """0 exact; 1/2 starts with / contains q as a whole word; 3/4 the same as part
    of a longer word ("dosa" in "Dosakaya"); 5 contains; 6 no match."""
    n = name.lower()
    if n == q:
        return 0
    word = rf"\b{re.escape(q)}\b"
    if re.match(word, n):
        return 1
    if re.search(word, n):
        return 2
    if n.startswith(q):
        return 3
    if re.search(rf"\b{re.escape(q)}", n):
        return 4
    return 5 if q in n else 6


def rank(food: dict, q: str) -> tuple:
    """A match on the food's own name beats a local-name match up to one tier better;
    then the user's own recipes, then dishes before ingredients, then shorter names.
    Compared on spelling-normalised keys, so "aloo paratha" ranks like "alu parantha"."""
    name = food["name"]
    brand = food.get("brand")
    if brand and name.startswith(brand + " "):
        name = name[len(brand) + 1:]  # for brand foods, match the product name
    nq = search_text.key(q)
    brand_key = search_text.key(brand) if brand else ""
    if brand_key and nq.startswith(brand_key + " "):
        nq = nq[len(brand_key) + 1:]
    name_tier = _match_tier(search_text.key(name), nq)
    local_tier = min((_match_tier(search_text.key(n), nq) for n in food.get("local_names", [])), default=6)
    best = min(name_tier * 2, local_tier * 2 + 3)
    own = 0 if food.get("owner_id") else 1
    return (best, own, 0 if food["kind"] == "dish" else 1, len(food["name"]))


_VOCAB_TTL_S = 600
_vocab: tuple[float, list[str]] = (0.0, [])


async def _vocabulary(db: AsyncDatabase) -> list[str]:
    """Every word in shared food names, for typo correction. Cached for a few minutes."""
    global _vocab
    if time.monotonic() - _vocab[0] > _VOCAB_TTL_S or not _vocab[1]:
        seen: set[str] = set()
        async for f in db.foods.find({"quarantined": False, "owner_id": None}, {"search_key": 1}):
            seen.update((f.get("search_key") or "").split())
        _vocab = (time.monotonic(), sorted(seen))
    return _vocab[1]


def _word_start(w: str) -> dict:
    """Matches words starting with w ("parat" finds "parata"), not w inside a word ("cole" in "coleslaw")."""
    return {"search_key": {"$regex": f"(^| ){re.escape(w)}"}}


def _whole_word(w: str) -> dict:
    return {"search_key": {"$regex": f"(^| ){re.escape(w)}( |$)"}}


def _all_words_query(user: dict, words: list[str], kind: str | None, whole: bool = False) -> dict:
    match = _whole_word if whole else _word_start
    query: dict = {"quarantined": False, "$and": [visible(user), *(match(w) for w in words)]}
    if kind:
        query["kind"] = kind
    return query


def _correct(word: str, vocab: list[str]) -> str:
    """A cautious typo fix: only for longer words, and only to a near-identical known word
    ("biryni" -> "biryani", "panier" -> "panir"), never a loose guess ("samosa" -> "sosa")."""
    if len(word) < 5 or any(v.startswith(word) for v in vocab):
        return word
    for candidate in difflib.get_close_matches(word, vocab, n=3, cutoff=0.85):
        if candidate[0] == word[0] and abs(len(candidate) - len(word)) <= 1:
            return candidate
    return word


async def search(db: AsyncDatabase, user: dict, q: str, kind: str | None = None, limit: int = 25) -> list[dict]:
    """Every word must appear, in any order and any common spelling. If nothing
    matches, typos are corrected against known food words; if still nothing,
    foods matching most of the words are returned (e.g. "rajma chawal")."""
    term = " ".join(q.strip().split())
    words = list(dict.fromkeys(search_text.words(term)))[:6]
    if not words:
        return []

    foods = await db.foods.find(_all_words_query(user, words, kind), _PROJECTION).limit(SEARCH_POOL).to_list()

    if not foods:  # typo correction: "biryni" -> "biryani", "paneeer" -> "panir"
        vocab = await _vocabulary(db)
        fixed = [_correct(w, vocab) for w in words]
        if fixed != words:
            words = fixed
            foods = await db.foods.find(_all_words_query(user, words, kind), _PROJECTION).limit(SEARCH_POOL).to_list()

    if not foods and len(words) > 1:
        # No single food has every word ("rajma chawal"): show the best match for each
        # word, alternating, so all the parts of the meal are near the top.
        per_word = []
        for w in words:
            if len(w) < 3:
                continue
            found = await db.foods.find(_all_words_query(user, [w], kind, whole=True), _PROJECTION).limit(SEARCH_POOL).to_list()
            found.sort(key=lambda f: rank(f, w))
            per_word.append(found)
        merged, seen = [], set()
        if len(words) >= 3:
            # Foods with all but one of the words come first ("paneer butter masala" -> paneer makhani masala).
            counts: dict[str, int] = {}
            by_id: dict[str, dict] = {}
            for found in per_word:
                for f in found:
                    counts[f["_id"]] = counts.get(f["_id"], 0) + 1
                    by_id[f["_id"]] = f
            close = [by_id[i] for i, c in counts.items() if c >= len(words) - 1]
            close.sort(key=lambda f: rank(f, term))
            for f in close:
                seen.add(f["_id"])
                merged.append(f)
        for i in range(max((len(f) for f in per_word), default=0)):
            for found in per_word:
                if i < len(found) and found[i]["_id"] not in seen:
                    seen.add(found[i]["_id"])
                    merged.append(found[i])
        return merged[:limit]

    foods.sort(key=lambda f: rank(f, term))
    return foods[:limit]
