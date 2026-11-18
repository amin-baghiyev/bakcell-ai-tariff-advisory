# Tariff Advisor — Bakcell-inspired demo (Python MVC web app)

A runnable Flask (MVC) web app that ranks tariff suggestions for demo customers from
their **synthetic** usage history, with separate customer/admin logins, an admin
business dashboard, and idempotent five-day in-app tariff-end reminders.

> **Demo data only.** The workbook is synthetic (its own note says so); nothing here
> is live Bakcell data, and no saving is guaranteed. Source assets in `dataset/`
> (bundled with this package) and `../screenshoots/` are read-only inputs and were
> not modified.

---

## Quick start

```bash
cd tariff_advisor
python -m venv .venv && . .venv/Scripts/activate     # optional
pip install -r requirements.txt

python scripts/import_data.py           # 1) inspect + import workbook (writes results/import_report.md)
python scripts/seed_demo.py             # 2) demo-mock renewal dates + one opt-out (clearly labelled)
python scripts/generate_recommendations.py  # 3) rule-based top-3 for all 100 customers
python scripts/run_reminders.py         # 4) five-day reminders (idempotent — run twice, still 1 each)
python scripts/evaluate.py              # 5) evaluation report + recommendations.csv

python app.py                           # 6) http://127.0.0.1:5000
```

Equivalent Flask CLI: `flask --app app init-db | import-data | recommendations | reminders`.

### Demo credentials (clearly marked, demo mode only — hashed at rest)

| Role | URL | Email | Password |
|---|---|---|---|
| Customer | `/customer/login` | `customer@demo.local` | `Demo-Customer-2026` |
| Customer 2 | `/customer/login` | `customer2@demo.local` | `Demo-Customer2-2026` |
| Admin | `/admin/login` | `admin@demo.local` | `Demo-Admin-2026` |

Admin sign-in is a **separate page/namespace**; it is never linked from the customer
login. Roles are enforced on every protected route (not just navigation).
Configured in `config.py` / `.env.example` (`DEMO_*`, `SECRET_KEY`).

---

## Routes

```text
/                        → redirect to the right login/home
/customer/login          customer sign-in (no admin option)
/customer                dashboard: current-tariff card, usage summary, SUGGESTED TARIFFS row
/customer/recommendations ranked top-3 + comparison/trade-offs + score components
/customer/history         monthly data/minutes/spend bars, top-ups, extra internet, renewal
/customer/notifications   in-app reminders + preference toggle + skip log
/admin/login             admin sign-in
/admin                   business dashboard (filters, charts, unavailable-metrics states)
/admin/customers         paginated customer/recommendation table (IDs only, no phone)
/admin/customers/<id>    customer detail (no phone number anywhere)
/health                  JSON health check
```

---

## Data inspection & mapping (done before any recommendation code)

Full report: **`docs/DATA_INSPECTION.md`**; machine-readable copy in
`results/import_report.md` / `.json`. Highlights:

- 3 sheets: `Müştərilər` (100 customers × 24), `Paketlər` (9 tariffs + 3 ancillary
  prices + note/blank rows), `Aylıq_istifadə` (600 rows = 100 × 6 months `2026-05…2026-10`).
- 0 duplicate customers, 0 duplicate (customer, month) keys, no negatives, no missing
  values except `İnternet istifadə %` = `"-"` for the six 0 GB-plan customers → stored
  as **unknown**, never 0.
- Units preserved: **AZN, GB, minutes, SMS count, `YYYY-MM`** — no conversions.
- **`Nömrə` (phone) is excluded at import** — not stored, not a feature, not displayed.
- Cost model reconciles **600/600 rows exactly**:
  `spend = price + 3×extra GB + 0.08×out-of-pkg min + 5×roaming day`
  (unit prices all come from the workbook).
- Column mapping is configurable in `config.py` (`CUSTOMER_COLUMNS`, `CATALOG_COLUMNS`,
  `USAGE_COLUMNS`); the importer validates headers and fails loudly instead of guessing.

---

## Recommendation engine (`services/recommendation.py`, Flask-independent)

1. **Demand** = `mean(last 3 complete months) + 0.5 × std` (configurable window/buffer;
   1-month histories get no buffer and are flagged `short_history`).
2. **Per-plan components** (each 0–1, `None` = unknown → component excluded and
   remaining weights renormalised — never treated as zero):
   - *adequacy* — data coverage + call coverage (all-network bucket vs on/off-net
     buckets weighted by demand share),
   - *cost* — inverse of **estimated total cost** = price + extra-data packs
     (1 GB packs @ catalog price) + out-of-bundle minutes @ 0.08 (roaming excluded:
     plan-independent),
   - *oversupply* — penalises buying far more GB than estimated demand,
   - *affordability* — preference vs observed average spend (not a constraint).
3. **Score** = weighted mean of known components. Default weights
   `0.40 / 0.30 / 0.15 / 0.15` (`config.Weights`); tie-break → lower estimated cost →
   smaller excess → name. **Current plan is always included**; if it ranks first the UI
   recommends keeping it. Top-3 only; every shortfall is flagged, never hidden.
4. **Unlimited-app matching is NOT scored** — the workbook has no app-usage field
   (plan-side lists are shown as catalog facts only).
5. Plain-language explanations are deterministic templates over computed facts
   (`services/explanation.py`) — no LLM invents anything.

**ML experiment** (`scripts/ml_experiment.py`, exploratory): predicts *next-month
internet demand* (never the customer's current tariff — that's not ground truth) with a
time-aware split (train months 1–5, test month 6):

| model | MAE (GB) | RMSE | R² |
|---|---|---|---|
| mean-baseline | 5.109 | 7.231 | 0.000 |
| linear regression | 0.919 | 1.511 | 0.956 |
| random forest | 0.894 | 1.514 | 0.956 |
| hist. gradient boosting* | 1.000 | 1.708 | 0.944 |

\* sklearn stand-in — lightgbm/catboost are not installed. Results are **exploratory**
(one synthetic dataset, 400 train / 100 test rows); no claim of a production model.
Outputs: `results/ml_experiment.json`.

**Sensitivity** (`scripts/sensitivity.py`): five weight configurations; top-1 agreement
with default ranges 76 % (adequacy-heavy) → 96 % (affordability-heavy); report in
`results/sensitivity_report.md`.

**Evaluation** (`scripts/evaluate.py`): demand coverage, estimated spend difference vs
current, extra-data effect, keep-current rate → `results/evaluation_report.md` +
`results/recommendations.csv`. Latest run (100/100):
top pick covers data 49/100, calls 48/100, shortfall flagged 75×, estimated cheaper
23 / dearer 8 / same 69, keep-current picks 69. All labelled estimates.

---

## Notifications

`services/notification_service.py` — daily job (CLI `scripts/run_reminders.py` or
`flask reminders`) finds periods ending within **5 calendar days**, creates **one**
reminder per (customer, type, period) via `UNIQUE` constraint → repeat runs are
no-ops. Opt-outs and missing end dates are skipped **with recorded reasons**
(`notification_skips`), visible on the notifications page. Timezone `Asia/Baku`.

**Limitation:** the workbook has **no tariff end/renewal date column**, so imported
customers keep `NULL` (reason `missing_end_date`). To make the flow demonstrable,
`scripts/seed_demo.py` assigns **demo-mock** dates to 4 customers (provenance stored,
UI labels them “demo mock”). Delivery is **in-app only** — a `NotificationProvider`
interface exists for future push/SMS, but nothing is claimed as delivered.

---

## Tests / checks

```bash
python -m pytest tests/ -q        # recommendation + notification tests (optional)
python scripts/inspect_workbook.py  # read-only workbook inspection
```

---

## Project layout

```text
tariff_advisor/
  app.py                  # app factory + Flask CLI commands
  config.py               # env config, column mapping, scoring weights
  models/schema.py        # SQLite DDL (users, customers, tariffs, usage, recs, notifications)
  controllers/            # auth, customer, admin, health + security (CSRF, roles)
  services/               # import, recommendation, explanation, notification,
                          # analytics, evaluation, pipeline
  repositories/           # db + per-entity access (no business rules)
  templates/              # base / auth / customer / admin / errors
  static/                 # app.css (Bakcell palette), app.js
  scripts/                # import_data, seed_demo, generate_recommendations,
                          # run_reminders, evaluate, sensitivity, ml_experiment,
                          # inspect_workbook
  tests/                  # pytest suites
  docs/DATA_INSPECTION.md # workbook findings (schema, missingness, units, limits)
  results/                # generated reports (import, evaluation, sensitivity, ML)
  requirements.txt  .env.example  README.md
```

Stack: Flask + Jinja, stdlib `sqlite3` (no ORM dependency), pandas/numpy/scikit-learn.
Server-rendered CSS bar charts (no CDN/JS dependency), keyboard-focusable controls,
mobile-first layout with bottom nav (< 900 px) per the supplied screenshots.

## Security notes

CSRF token on every POST, session regenerated at login (fixation), open-redirect-safe
`next`, role checks on every protected route, cross-customer access impossible
(customer data is scoped to the session's `customer_id`), password hashing (werkzeug),
no stack traces/secrets in UI, no phone numbers anywhere.

## Known limitations (missing source fields)

| Missing field | Effect |
|---|---|
| Tariff end/renewal date | NULL on import + recorded skips; demo-mock dates only for seeded demo customers |
| App usage per customer | unlimited-app fit never scored |
| Account balance / credit | not displayed (screenshots' balance row not reproduced with fake numbers) |
| Push/SMS provider | in-app demo notifications only |
| Churn / revenue / ARPU | admin marks them *Unavailable*, never 0 |
| `İnternet istifadə %` = `"-"` (6 rows) | unknown, not 0 |
