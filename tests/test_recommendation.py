"""Unit tests for the rule-based recommendation engine (no Flask needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Weights
from services import recommendation as reco

# Catalog facts taken from the workbook's Paketlər sheet (9 tariffs).
CATALOG = [
    reco.Plan(name="Klass 5", family="Klass", price_azn=5, data_gb=0.5,
              allnet_min=100, onnet_min=0, offnet_min=0, sms=0, unlimited_apps="Yoxdur"),
    reco.Plan(name="Klass 10", family="Klass", price_azn=10, data_gb=2,
              allnet_min=300, onnet_min=0, offnet_min=0, sms=0, unlimited_apps="Yoxdur"),
    reco.Plan(name="Klass 15", family="Klass", price_azn=15, data_gb=5,
              allnet_min=450, onnet_min=0, offnet_min=0, sms=0, unlimited_apps="Yoxdur"),
    reco.Plan(name="Klass 25", family="Klass", price_azn=25, data_gb=15,
              allnet_min=0, onnet_min=800, offnet_min=250, sms=0, unlimited_apps="Yoxdur"),
    reco.Plan(name="DaimOnline 6", family="DaimOnline", price_azn=6, data_gb=2,
              allnet_min=0, onnet_min=50, offnet_min=0, sms=0, unlimited_apps="WhatsApp"),
    reco.Plan(name="DaimOnline 10", family="DaimOnline", price_azn=10, data_gb=5,
              allnet_min=0, onnet_min=200, offnet_min=0, sms=0,
              unlimited_apps="WhatsApp, Facebook, Instagram"),
    reco.Plan(name="CIN 5", family="CIN", price_azn=5, data_gb=0,
              allnet_min=0, onnet_min=600, offnet_min=0, sms=300, unlimited_apps="Yoxdur"),
]


def _usage(months, data, minutes, extra=0, spend=10, onnet=0, offnet=0):
    return [
        {"month": m, "data_gb": d, "total_minutes": t, "onnet_min": on, "offnet_min": off,
         "extra_gb": e, "spend_azn": s}
        for m, d, t, on, off, e, s in zip(months, data, minutes, onnet * len(months) if False else [on] * len(months),
                                          [off] * len(months), [extra] * len(months), [spend] * len(months))
    ]


def _demand(rows, **kw):
    return reco.summarize_history(rows, extra_unit_price=3.0, **kw)


class TestDemand:
    def test_window_is_last_three_months(self):
        rows = _usage(["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"],
                      [1, 2, 3, 4, 5, 6], [100] * 6)
        d = _demand(rows)
        assert d.months == ["2026-08", "2026-09", "2026-10"]
        assert d.data_mean == 5.0  # (4+5+6)/3

    def test_buffer_applied(self):
        rows = _usage(["2026-09", "2026-10"], [4, 6], [100, 100])
        d = _demand(rows)  # default buffer 0.5
        assert d.data_est > d.data_mean
        assert abs(d.data_est - (5 + 0.5 * (2 ** 0.5))) < 1e-9

    def test_short_history_flagged_no_buffer(self):
        rows = _usage(["2026-10"], [4], [100])
        d = _demand(rows)
        assert d.short_history is True
        assert d.data_est == 4.0

    def test_empty_history_returns_none(self):
        assert _demand([]) is None


class TestScoring:
    def test_top3_and_current_included(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [4.0, 4.4, 4.2], [250] * 3,
                      extra=1, spend=14)
        d = _demand(rows)
        res = reco.recommend(CATALOG, d, current_tariff="Klass 10",
                             unit_extra_gb=3.0, unit_minute=0.08)
        ranked = res["ranked"]
        assert 1 <= len(ranked) <= 3
        names = [p["name"] for p in ranked]
        assert "Klass 10" in names, "current tariff must be part of the comparison"
        assert res["flags"]["current_included"] is True

    def test_data_covers_estimated_demand(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [1.0, 1.2, 1.1], [60] * 3, spend=6)
        d = _demand(rows)
        res = reco.recommend(CATALOG, d, current_tariff="DaimOnline 6",
                             unit_extra_gb=3.0, unit_minute=0.08)
        best = res["ranked"][0]
        assert best["adequacy_data"] == 1.0, "small demand should be covered by the top pick"

    def test_shortfall_flag_when_no_plan_covers(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [18.0, 19.0, 20.0], [3000] * 3, spend=50)
        d = _demand(rows)
        res = reco.recommend(CATALOG, d, current_tariff="Klass 50",
                             unit_extra_gb=3.0, unit_minute=0.08)
        assert res["flags"]["shortfall_any"] is True
        # every candidate must carry an explicit shortfall warning
        assert all(p["shortfall"] for p in res["ranked"])

    def test_unknown_allowance_excluded_from_scoring(self):
        plan = reco.Plan(name="Mystery", price_azn=10, data_gb=None, allnet_min=None)
        rows = _usage(["2026-08", "2026-09", "2026-10"], [3, 3, 3], [100] * 3)
        d = _demand(rows)
        ev = reco.evaluate_plan(plan, d, current_tariff=None, weights=Weights(),
                                unit_extra_gb=3.0, unit_minute=0.08)
        assert ev.components["adequacy"] is None
        assert ev.score is not None, "score still computable from known components"
        assert "unknown_data_allowance" in ev.reason_codes

    def test_tie_break_prefers_cheaper_then_less_excess(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [1.0, 1.0, 1.0], [50] * 3, spend=5)
        d = _demand(rows)
        twins = [
            reco.Plan(name="Big", price_azn=30, data_gb=20, allnet_min=500),
            reco.Plan(name="Small", price_azn=30, data_gb=1, allnet_min=500),
        ]
        res = reco.recommend(twins, d, current_tariff=None,
                             unit_extra_gb=3.0, unit_minute=0.08)
        assert res["ranked"][0]["name"] == "Small"

    def test_estimated_cost_uses_catalog_unit_prices(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [4.0, 4.0, 4.0], [100] * 3)
        d = _demand(rows)
        plan = reco.Plan(name="P", price_azn=10, data_gb=2, allnet_min=500)
        cost, parts = reco.estimate_total_cost(plan, d, 3.0, 0.08)
        # est data 4.0 GB → 2 GB over → 2 packs of 1 GB @ 3 AZN
        assert parts["extra_data_packs"] == 2
        assert cost == 10 + 6
        assert parts.get("out_of_bundle_min") == 0

    def test_call_coverage_all_network_vs_buckets(self):
        rows = _usage(["2026-08", "2026-09", "2026-10"], [1.0] * 3, [400] * 3)
        d = _demand(rows)
        klass = reco.Plan(name="K", price_azn=15, data_gb=5, allnet_min=450)
        daim = reco.Plan(name="D", price_azn=10, data_gb=5, allnet_min=0,
                         onnet_min=200, offnet_min=0)
        assert reco.call_coverage(klass, d) == 1.0      # 450 ≥ 400 total
        assert reco.call_coverage(daim, d) < 1.0        # 200 on-net only
        assert reco.call_coverage(reco.Plan(name="U", price_azn=1), d) is None


class TestExplanations:
    def test_explanation_uses_only_computed_facts(self):
        from services import explanation as expl

        rows = _usage(["2026-08", "2026-09", "2026-10"], [4.0, 4.4, 4.2], [250] * 3,
                      extra=1, spend=14)
        d = _demand(rows)
        res = reco.recommend(CATALOG, d, current_tariff="Klass 10",
                             unit_extra_gb=3.0, unit_minute=0.08)
        out = expl.explain_ranked(res, d, "Klass 10")
        assert out["summary"]
        assert len(out["per_plan"]) == len(res["ranked"])
        for p in out["per_plan"]:
            assert p["text"] and "AZN" in p["text"] or "GB" in p["text"]
        assert "guaranteed" in out["disclaimer"].lower()
