"""Spelling-tolerant search keys for Indian food names.

Hindi words have many Roman spellings (aloo / alu / aaloo, gobhi / gobi,
paneer / panir, parantha / paratha, idli / idly). Both the stored names and
the query are reduced to the same key, so any of those spellings match.
"""

import re
import unicodedata

# Whole-word variants that letter rules can't reach.
_WORD_SYNONYMS = {
    "parantha": "paratha", "paranta": "paratha", "parotta": "paratha", "porotta": "paratha", "prantha": "paratha",
    "panner": "paneer", "paaner": "paneer", "pnr": "paneer",
    "chapathi": "chapati", "chapatti": "chapati", "phulka": "roti",
    "subzi": "sabzi", "sabji": "sabzi", "subji": "sabzi", "sabjee": "sabzi",
    "dahl": "dal", "daal": "dal", "dhal": "dal",
    "channa": "chana", "chhole": "chole", "chholey": "chole", "choley": "chole",
    "biriyani": "biryani", "briyani": "biryani", "biryanee": "biryani",
    "bhaat": "bhat", "chaawal": "chawal", "chawl": "chawal",
    "curd": "dahi", "yoghurt": "dahi", "yogurt": "dahi",
    "lady's": "bhindi", "ladies": "bhindi", "okra": "bhindi",
    "brinjal": "baingan", "eggplant": "baingan", "aubergine": "baingan",
    "cauliflower": "gobi", "potato": "alu", "potatoes": "alu", "spinach": "palak",
    "chickpea": "chana", "chickpeas": "chana", "kidney": "rajma", "rajmah": "rajma",
    "tea": "chai", "egg": "anda", "eggs": "anda", "omelette": "omlet", "omelet": "omlet",
    "masaala": "masala", "mutter": "matar", "mattar": "matar", "peas": "matar",
    "coke": "cola", "softdrink": "cold drink",
}

_SPLIT = re.compile(r"[^a-z0-9]+")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def normalize_word(word: str) -> str:
    """One spelling for the many ways a word is romanised."""
    w = _WORD_SYNONYMS.get(word, word)
    if " " in w:
        return " ".join(normalize_word(p) for p in w.split())
    w = w.replace("ck", "k").replace("ph", "f").replace("q", "k").replace("w", "v").replace("z", "j")
    w = w.replace("ee", "i").replace("oo", "u").replace("ou", "u")
    w = re.sub(r"([bcdgkpst])h", r"\1", w)  # aspirates: bh, ch, dh, gh, kh, sh, th
    w = w.replace("iy", "y")
    w = re.sub(r"(.)\1+", r"\1", w)  # doubled letters: aaloo -> alu, chilli -> chili
    if len(w) > 3 and w.endswith("y"):
        w = w[:-1] + "i"  # idly -> idli
    return w


def words(text: str) -> list[str]:
    raw = [w for w in _SPLIT.split(_fold(text)) if w]
    out: list[str] = []
    for w in raw:
        out.extend(normalize_word(w).split())
    return out


def key(*texts: str) -> str:
    """The stored search key: normalised words of the name and local names."""
    return " ".join(w for t in texts for w in words(t))


def food_key(food: dict) -> str:
    return key(food["name"], *food.get("local_names", []))
