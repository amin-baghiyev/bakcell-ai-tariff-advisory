"""Application configuration.

All secrets come from environment variables (see ``.env.example``).
The workbook path is configurable; by default it points at the supplied
synthetic dataset outside the package (read-only input asset).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


class Config:
    """Flask + pipeline configuration."""

    SECRET_KEY = _env("SECRET_KEY", "dev-only-secret-change-me")
    DATABASE_PATH = _env("DATABASE_PATH", str(BASE_DIR / "tariff_advisor.sqlite3"))
    WORKBOOK_PATH = _env(
        "WORKBOOK_PATH",
        str(
            BASE_DIR
            / "dataset"
            / "Peerstack Academy AI Contest - Tariff Advisor synthetic data.xlsx"
        ),
    )
    RESULTS_DIR = _env("RESULTS_DIR", str(BASE_DIR / "results"))

    # Customer timezone for scheduling / reminder dates (demo default).
    TIMEZONE = _env("TZ_NAME", "Asia/Baku")

    # Recommendation engine knobs (documented in README).
    HISTORY_WINDOW_MONTHS = int(_env("HISTORY_WINDOW_MONTHS", "3"))
    DEMAND_BUFFER_RATIO = float(_env("DEMAND_BUFFER_RATIO", "0.5"))
    EXTRA_PACK_SIZE_GB = float(_env("EXTRA_PACK_SIZE_GB", "1.0"))

    # Demo credentials — intentionally obvious, documented in README.
    DEMO_CUSTOMER_EMAIL = _env("DEMO_CUSTOMER_EMAIL", "customer@demo.local")
    DEMO_CUSTOMER_PASSWORD = _env("DEMO_CUSTOMER_PASSWORD", "Demo-Customer-2026")
    DEMO_CUSTOMER2_EMAIL = _env("DEMO_CUSTOMER2_EMAIL", "customer2@demo.local")
    DEMO_CUSTOMER2_PASSWORD = _env("DEMO_CUSTOMER2_PASSWORD", "Demo-Customer2-2026")
    DEMO_ADMIN_EMAIL = _env("DEMO_ADMIN_EMAIL", "admin@demo.local")
    DEMO_ADMIN_PASSWORD = _env("DEMO_ADMIN_PASSWORD", "Demo-Admin-2026")

    DEMO_MODE = _env("DEMO_MODE", "1") not in ("0", "false", "False")

    # Demo-mock tariff end dates used ONLY to exercise the reminder flow.
    # Keys are customer IDs; values are offsets in days from "today".
    # Any customer not listed here keeps tariff_end_date = NULL (as in the source).
    DEMO_TARIFF_END_OFFSETS_DAYS = {
        "BKC-0001": 5,   # reminder should be created by the next run
        "BKC-0002": 3,   # already inside the 5-day window
        "BKC-0003": 21,  # outside the window (no reminder yet)
        "BKC-0005": 4,   # inside window BUT opted out -> skipped with reason "opted_out"
        # BKC-0004: left NULL -> skipped with reason "missing_end_date"
    }
    DEMO_OPTED_OUT_CUSTOMERS = {"BKC-0005"}


# --------------------------------------------------------------------------- #
# Configurable source-column mapping (documentation.md §5)
# --------------------------------------------------------------------------- #
# internal field -> source header, per sheet. The importer validates that every
# required header exists and reports missing ones instead of guessing names.

SHEET_CUSTOMERS = "Müştərilər"
SHEET_CATALOG = "Paketlər"
SHEET_USAGE = "Aylıq_istifadə"

CUSTOMER_COLUMNS = {
    "customer_id": "Müştəri ID",
    "phone": "Nömrə",                      # imported only to be excluded explicitly
    "age": "Yaş",
    "gender": "Cins",
    "region": "Region",
    "subscriber_type": "Abunə növü",
    "tenure_months": "Şəbəkədə staj (ay)",
    "device": "Cihaz",
    "network": "Şəbəkə",
    "current_tariff": "Cari paket",
    "months_on_tariff": "Cari paketdə (ay)",
    "price_azn": "Paket qiyməti (AZN)",
    "plan_data_gb": "Paket: internet (GB)",
    "plan_allnet_min": "Paket: ölkədaxili dəqiqə",
    "plan_onnet_min": "Paket: şəbəkədaxili dəqiqə",
    "plan_offnet_min": "Paket: şəbəkəxarici dəqiqə",
    "plan_sms": "Paket: SMS",
    "plan_unlimited_apps": "Paket: limitsiz tətbiqlər",
    "avg_data_gb": "6 ay orta internet (GB)",
    "avg_minutes": "6 ay orta dəqiqə",
    "data_utilization": "İnternet istifadə %",
    "minute_utilization": "Dəqiqə istifadə %",
    "avg_spend_azn": "6 ay orta xərc (AZN)",
    "extra_gb_6m": "6 ayda əlavə internet (GB)",
}

# Columns never used as features, never displayed, never logged.
EXCLUDED_COLUMNS = ("phone",)

CATALOG_COLUMNS = {
    "name": "Tarif",
    "family": "Ailə",
    "price_azn": "Aylıq qiymət (AZN)",
    "data_gb": "İnternet (GB)",
    "allnet_min": "Ölkədaxili dəqiqə (bütün şəbəkələr)",
    "onnet_min": "Şəbəkədaxili dəqiqə",
    "offnet_min": "Şəbəkəxarici dəqiqə",
    "sms": "SMS",
    "unlimited_apps": "Limitsiz tətbiqlər",
}

USAGE_COLUMNS = {
    "customer_id": "Müştəri ID",
    "month": "Ay",
    "tariff": "Paket",
    "data_gb": "İnternet istifadəsi (GB)",
    "total_minutes": "Dəqiqə istifadəsi (cəmi)",
    "onnet_min": "Şəbəkədaxili dəqiqə",
    "offnet_min": "Şəbəkəxarici dəqiqə",
    "sms": "SMS sayı",
    "extra_gb": "Əlavə alınan internet (GB)",
    "out_of_bundle_min": "Paketdən kənar dəqiqə",
    "roaming_days": "Rouminq günləri",
    "topup_count": "Balans artırma sayı",
    "callcenter_contacts": "Çağrı mərkəzinə müraciət",
    "spend_azn": "Aylıq xərc (AZN)",
}

# Ancillary prices are stored in the catalog sheet under the tariff-name column.
ANCILLARY_PRICE_KEYS = {
    "extra_1gb_azn": "Əlavə 1 GB internet paketi (AZN)",
    "out_of_bundle_1min_azn": "Paketdən kənar 1 dəqiqə (AZN)",
    "roaming_day_azn": "Rouminq gündəlik paket (AZN)",
}


# --------------------------------------------------------------------------- #
# Scoring weights (documented, tunable — see README "Recommendation engine")
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Weights:
    adequacy: float = 0.40
    cost: float = 0.30
    oversupply: float = 0.15
    affordability: float = 0.15

    def as_dict(self) -> dict:
        return {
            "adequacy": self.adequacy,
            "cost": self.cost,
            "oversupply": self.oversupply,
            "affordability": self.affordability,
        }


DEFAULT_WEIGHTS = Weights()
