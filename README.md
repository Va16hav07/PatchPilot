# Thali — Indian meal nutrition tracker

Track what you eat, katori by katori. Nutrition numbers come from verified
Indian food tables, never from an AI model. See `PLAN.md` for the roadmap.

## Data sources

| Source | What | Notes |
|---|---|---|
| IFCT 2017 (ICMR-NIN) | 542 raw foods, per 100 g | via the `ifct2017` package CSV |
| INDB | 1,014 recipes, per standard serving | no published license: downloaded locally, never committed |
| USDA FoodData Central | gap fillers (e.g. plain curd) | public domain, cited per item |

`python -m scripts.import_foods` downloads, validates and loads them, and writes
`backend/data/import_report.md`. Items failing quality checks (e.g. INDB recipes
that count deep-frying oil as eaten) are quarantined: kept, but hidden from search.

## Run locally

Needs Python 3.12+, Node 20+, MongoDB, and a Google OAuth client ID
(Google Cloud Console > Credentials > OAuth client ID > Web application,
authorised JavaScript origin `http://localhost:5173`).

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # fill GOOGLE_CLIENT_ID and SESSION_SECRET
.venv/bin/python -m scripts.import_foods
.venv/bin/uvicorn app.main:app --reload --port 8000
.venv/bin/python -m pytest      # API tests need MongoDB running

# frontend
cd frontend
npm install
cp .env.example .env.local      # same GOOGLE_CLIENT_ID
npm run dev                     # http://localhost:5173 (proxies /api to :8000)
```
