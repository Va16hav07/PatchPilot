# Indian Meal Nutrition Tracker — Plan

## Goal
Track nutrition of Indian meals, as precisely as practical. Individual users first; family later.

## Core principle
**Gemini understands, the database calculates.**
Gemini only parses input (text / photo / voice) into structured dish + portion guesses.
All nutrient numbers come from verified databases via a deterministic engine. No LLM-generated numbers.

```
input (text | photo | voice | search)
  -> Gemini (JSON-schema output: dish -> DB id, portion, confidence)
  -> user confirms / adjusts (dish, portion, oil level)
  -> nutrition engine (DB values x grams)
  -> daily log, targets, trends
```

## Data sources
| Source | Content | Notes |
|---|---|---|
| IFCT 2017 (ICMR-NIN) | ~542 raw foods, lab-measured | Available via `ifct2017` npm package / ifct2017.github.io |
| INDB (Indian Nutrient Databank) | ~1095 foods + ~1014 cooked recipes | Open-access; generate locally for personal use (license not redistributable) |
| Household measures table | katori, roti, ladle, tbsp, glass -> grams per dish | We build + calibrate |
| USDA FoodData Central / labels | Fallback for non-Indian / packaged | |

## Precision strategy
1. **Portions** — standard Indian household measures, S/M/L adjust, optional grams.
2. **Oil/ghee** — per-dish oil level (low / home / restaurant) adjusts fat & kcal.
3. **Custom recipes** — ingredients + cooked weight -> exact per-100g values.
4. **Regional variants** — INDB variants + your own saved recipes.
5. **AI guardrails** — Gemini must map to existing DB ids; low confidence -> ask user, never guess.
6. **Every entry shows its source** (IFCT / INDB / custom / USDA) so numbers are auditable.

## Decisions
- Platform: mobile-first PWA
- Inputs: text (Hinglish), photo, search & pick, voice
- Users: individual accounts for now (one Google account = one profile). Family sharing deferred to Phase 4
- Auth: Google sign-in only (no passwords)
- Database: MongoDB
- UI designed first (canvas: https://claude.ai/artifact/8XaGG5X6isaae1qCuqm3m8), then build
- Location: this repo

## Stack
- Backend: Python, FastAPI, MongoDB (Motor/Beanie)
- Auth: Google OAuth 2.0 / OpenID Connect -> app session (JWT, httpOnly cookie)
- AI: Gemini Flash, structured JSON output (text + vision)
- Voice: browser speech-to-text -> text pipeline
- Frontend: mobile-first PWA

## Phases
### Phase 1 — Core (built 2026-10-05)
- Import IFCT 2017 + INDB into MongoDB `foods` collection (with source tagging)
- Google sign-in + user profile
- Household measures table
- Nutrition engine + unit tests against known reference values
- Profile + targets (kcal, protein, carbs, fat, fibre)
- Search & pick logging + daily dashboard

### Phase 2 — AI logging (built 2026-10-05; Gemini flow awaiting first real-key test)
- Gemini key: user's own key stored only on their device (sent only to Google); optional shared server key as fallback
- Pipeline: Gemini parses -> DB candidates -> Gemini picks only from candidates -> user reviews -> save
- Text (Hinglish) parsing via Gemini -> confirm screen
- Voice -> text -> same pipeline
- Photo logging via Gemini Vision -> confirm screen
- Custom recipes, favourites, "same as yesterday"

### Phase 3 — Insights
- Micronutrients (iron, B12, calcium, vit D, etc.)
- Weekly trends per profile
- Gap suggestions from DB foods (e.g. low protein -> paneer, curd)

### Phase 4 — Family (later)
- Invite family by Gmail, managed profiles (no login), profile switcher on Today, shared recipes

## Data findings (Phase 1)
- INDB per-100 g values use raw-ingredient weight (water and evaporation ignored), so dishes are logged in standard servings, not grams.
- INDB does not define bowl volume; 1 bowl = 150 ml is our assumption, scaled to the user's katori and shown in the UI.
- 258 INDB recipes quarantined: 139 count deep-frying oil as eaten (e.g. paneer pulao 4,876 kcal/plate), 82 missing values, others implausible.
- IFCT: oils/ghee list 0 kJ (recomputed from fat); chicken leg energy is a transcription error (corrected from macros).
- Not tracked yet: vitamin B12 (in neither source), vitamin A (IFCT adds β-carotene 1:1 to retinol), vitamin D (implausible plant D2 values).
- Plain curd is in neither source; added from USDA FDC #171284.
- No plain toor/arhar dal in INDB; added as a curated dish derived from INDB washed moong dal (ASC151) with IFCT red gram dal.

## Open items
- Verify ICMR-NIN 2020 fibre guidance (currently 40 g / 2000 kcal) and carb share
- Curate cooked yields for common dishes so grams work for dishes
- Review quarantined dishes: fix frying-oil absorption for popular ones (puri, pakora, kofta)
- Gemini API key (env var `GEMINI_API_KEY`)
- Calibrate household measures against your own katori/glass sizes
