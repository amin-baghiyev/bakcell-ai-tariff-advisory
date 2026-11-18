# Workbook inspection report

Source: `dataset/Peerstack Academy AI Contest - Tariff Advisor synthetic data.xlsx`
(read-only; the workbook was not modified). Inspection performed with
`python scripts/inspect_workbook.py` plus follow-up consistency checks.

> The workbook's own note (sheet `Paketlər`, last row) states: tariff names, prices
> and package contents are based on publicly announced real Bakcell tariffs from
> various years and may differ from current conditions; **customer and usage figures
> are fully synthetic**. This app therefore runs in demo mode and never implies the
> data is live Bakcell data.

## Sheets

| Sheet | Rows | Cols | Meaning |
|---|---|---|---|
| `Müştərilər` | 100 | 24 | One row per customer (profile + current package + 6-month aggregates) |
| `Paketlər` | 16 | 9 | Package catalog (9 tariffs), 3 ancillary service prices, 2 blank rows, 1 note row |
| `Aylıq_istifadə` | 600 | 14 | Monthly usage: 100 customers × 6 months (`2026-05` … `2026-10`) |

## Columns, types, missingness

### `Müştərilər` (customers)

| Source column (az) | Internal field | Type | Missing | Notes |
|---|---|---|---|---|
| `Müştəri ID` | `customer_id` | str | 0 | `BKC-0001`…`BKC-0100`, unique, no duplicates — used as the stable key |
| `Nömrə` | *(excluded)* | str | 0 | Phone number. **Excluded from import, features and UI entirely.** |
| `Yaş` | `age` | int | 0 | 16–61 |
| `Cins` | `gender` | str | 0 | `Kişi` / `Qadın` |
| `Region` | `region` | str | 0 | 10 regions (Bakı, Gəncə, …) |
| `Abunə növü` | `subscriber_type` | str | 0 | `Fakturasız` / `Fakturalı` |
| `Şəbəkədə staj (ay)` | `tenure_months` | int | 0 | 7–155 |
| `Cihaz` | `device` | str | 0 | iOS / Android / Düyməli telefon |
| `Şəbəkə` | `network` | str | 0 | 2G–5G |
| `Cari paket` | `current_tariff` | str | 0 | 9 distinct — all present in `Paketlər` |
| `Cari paketdə (ay)` | `months_on_tariff` | int | 0 | 6–48 |
| `Paket qiyməti (AZN)` | `price_azn` | int | 0 | 5–50, matches catalog for all 100 rows |
| `Paket: internet (GB)` | `plan_data_gb` | float | 0 | 0–20 GB; matches catalog for all rows |
| `Paket: ölkədaxili dəqiqə` | `plan_allnet_min` | int | 0 | matches catalog |
| `Paket: şəbəkədaxili dəqiqə` | `plan_onnet_min` | int | 0 | matches catalog |
| `Paket: şəbəkəxarici dəqiqə` | `plan_offnet_min` | int | 0 | matches catalog |
| `Paket: SMS` | `plan_sms` | int | 0 | matches catalog |
| `Paket: limitsiz tətbiqlər` | `plan_unlimited_apps` | str | 0 | `Yoxdur` / WhatsApp / +Facebook/Instagram — matches catalog |
| `6 ay orta internet (GB)` | `avg_data_gb` | float | 0 | = mean of usage sheet, verified exact |
| `6 ay orta dəqiqə` | `avg_minutes` | float | 0 | = mean of usage sheet, verified exact |
| `İnternet istifadə %` | `data_utilization` | **mixed str/float** | 0 raw | **6 values are the string `"-"`** (all `CIN 5`, whose plan data allowance is 0 → division undefined). Coerced to *unknown*, not 0. Otherwise = avg ÷ plan allowance (verified exact). |
| `Dəqiqə istifadə %` | `minute_utilization` | float | 0 | = avg total minutes ÷ total included minutes (verified) |
| `6 ay orta xərc (AZN)` | `avg_spend_azn` | float | 0 | = mean monthly spend, verified exact |
| `6 ayda əlavə internet (GB)` | `extra_gb_6m` | int | 0 | = sum of monthly extra purchases, verified exact |

### `Paketlər` (catalog)

- 9 real tariff rows: `Klass 5/10/15/25/50`, `DaimOnline 6/10/20`, `CIN 5` — complete
  (price, GB, three minute buckets, SMS, unlimited apps), no missing values inside these rows.
- 2 fully blank spacer rows (the only "duplicate rows" in the sheet; not data).
- 3 ancillary price rows (tariff name present, other columns blank):
  - `Əlavə 1 GB internet paketi (AZN)` = **3** (extra 1 GB pack)
  - `Paketdən kənar 1 dəqiqə (AZN)` = **0.08** (out-of-package minute)
  - `Rouminq gündəlik paket (AZN)` = **5** (roaming day pack)
- 1 note row (provenance disclaimer, quoted above).
- Units: prices **AZN**, data **GB**, minutes **minutes**, SMS **count**. No MB/GB
  ambiguity anywhere; the customer sheet uses GB, not MB. Units are preserved as-is.

### `Aylıq_istifadə` (monthly usage)

- 600 rows = 100 customers × 6 months; key (`Müştəri ID`, `Ay`) has **0 duplicates**;
  each customer has exactly one row per month, no gaps.
- No missing values, no negative values in any numeric column, months are `YYYY-MM`
  strings `2026-05`…`2026-10` (all in the past relative to today, so no future records).
- Columns: data GB, total minutes, on-net/off-net minutes, SMS, extra internet bought (GB),
  out-of-package minutes, roaming days, top-up count, call-center contacts, monthly spend (AZN).
- `Paket` (tariff used that month) is constant per customer over all 6 months —
  **no customer changed tariff** in the observed window.

## Consistency checks (all verified by script)

1. **No duplicates**: customers unique by ID; usage unique by (ID, month);
   customer-sheet aggregates exactly equal aggregates recomputed from the usage sheet
   (avg data, avg minutes, avg spend, 6-month extra GB — all exact).
2. **Catalog vs customer sheet**: every customer's package attributes equal the catalog
   row (price, GB, minutes, SMS, apps) — 0 mismatches. Catalog and customer sheet agree.
3. **Cost model reconciles 600/600 rows exactly**:

   ```
   monthly spend = tariff price
                 + 3   × extra internet GB bought
                 + 0.08× out-of-package minutes
                 + 5   × roaming days
   ```

4. **Out-of-package minutes** are reproducible 600/600:
   - plans with `Ölkədaxili > 0` (Klass): `max(0, total minutes − ölkədaxili)`;
   - plans with only on/off-net buckets (DaimOnline, CIN):
     `max(0, onnet − şəbəkədaxili) + max(0, offnet − şəbəkəxarici)`.
5. **Extra internet purchases** are 1 GB packs: for all 188 buyer-months,
   `bought GB = ceil(max(0, usage − allowance))` (exact). 44 month-customer rows had an
   overage but no purchase (customer simply did not buy).
6. `İnternet istifadə %` = avg ÷ plan GB (6 `"-"` rows exactly where plan GB = 0).

## Observed aggregates (for admin reconciliation)

- Customers: 100; tariff distribution: Klass 10 (18), DaimOnline 10 (17),
  DaimOnline 20 (13), DaimOnline 6 (13), Klass 15 (12), Klass 5 (10), Klass 25 (8),
  CIN 5 (6), Klass 50 (3).
- 31/100 customers average above their data allowance; 6 have a 0 GB plan (CIN 5).
- Extra internet bought: **568 GB** over 6 months (188 buyer-months) → **1 704 AZN**
  at the catalog's 3 AZN/GB; out-of-package minutes cost 1 104.72 AZN;
  roaming day packs 930 AZN (186 roaming days). Mean observed monthly spend 19.21 AZN.
- Utilization: 31 customers > 100% of data allowance (6m average).

## Missing fields and the resulting limitations

| Missing in source | Consequence in the app |
|---|---|
| **Tariff end / renewal date** (no column anywhere) | Import stores `tariff_end_date = NULL` with source `missing_in_source`. The reminder job **skips these customers and records the reason**. For the demo only, `scripts/seed_demo.py` assigns clearly labelled *demo-mock* end dates to a handful of demo customers so the five-day reminder flow is visible in-app; provenance is stored (`demo_mock`) and the UI says the date is mocked. |
| **App-usage data** (which unlimited apps a customer actually uses) | The unlimited-apps scoring component is **excluded from scoring** (unknown on the customer side). Plan-side app lists are shown as catalog facts only. |
| **Account balance / credit debt** | No balance is shown anywhere (the screenshots' balance row is not reproduced with invented numbers). |
| **Push/SMS provider credentials** | Reminders are **in-app demo notifications only**; the UI states this explicitly. A provider interface is defined but not claimed as delivered. |
| **Churn, revenue, ARPU, contract type** | Not shown; admin dashboard marks unsupported metrics as *Unavailable*, never as 0. |
| `İnternet istifadə %` = `"-"` (6 rows) | Treated as *unknown* (None), not 0. |

## Units summary

Prices in **AZN** (AZN is written `AZN` in headers; the UI shows `₼`), data in **GB**,
minutes in **minutes**, SMS in **count**, tenure/months in **months**, roaming in **days**.
No unit conversion is performed anywhere except display formatting.
