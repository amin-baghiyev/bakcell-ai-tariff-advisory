"""Rule-based recommendation engine (no Flask dependency — CLI and test runnable).

Scoring model (documented in README, tunable via ``config.Weights``):

    score = Σ (weight_i × component_i) / Σ (weight_i for known components)

Components (each in [0, 1], ``None`` when unknown — unknown components are
excluded and the remaining weights renormalised, never treated as 0):

* ``adequacy``   – how well the plan's known allowances cover estimated demand,
                   averaged over the known of (data, calls) coverage ratios.
* ``cost``       – normalised inverse of the *estimated total monthly cost*
                   (plan price + extra-data packs + out-of-bundle minutes, using
                   the catalog's own unit prices).
* ``oversupply`` – penalises buying far more allowance than estimated demand.
* ``affordability`` – preference: estimated cost vs. the customer's observed
                   average monthly spend (never a hard constraint).

Demand estimation (documentation.md §6):

    est = mean(last N complete months) + buffer_ratio × std(last N complete months)

with N = 3 (configurable) and buffer_ratio = 0.5 (configurable). Short
histories (N = 1) get buffer 0 and are flagged ``short_history``.

Units: GB, minutes, AZN — exactly as in the source workbook.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from config import DEFAULT_WEIGHTS, Weights

MODEL_VERSION = "rule-based-v1"

#: Unlimited-app matching requires app-usage data on the customer side, which
#: the workbook does not contain. This component is therefore never scored.
UNLIMITED_APPS_SCORABLE = False


# --------------------------------------------------------------------------- #
# Data shapes
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Plan:
    name: str
    family: str | None = None
    price_azn: float | None = None
    data_gb: float | None = None
    allnet_min: float | None = None
    onnet_min: float | None = None
    offnet_min: float | None = None
    sms: float | None = None
    unlimited_apps: str | None = None
    source: str = "workbook"

    @classmethod
    def from_mapping(cls, m: Mapping) -> "Plan":
        def opt(key):
            v = m[key] if key in m.keys() else None  # sqlite3.Row / Series / dict
            return None if v is None else v

        return cls(
            name=str(opt("name")),
            family=opt("family"),
            price_azn=opt("price_azn"),
            data_gb=opt("data_gb"),
            allnet_min=opt("allnet_min"),
            onnet_min=opt("onnet_min"),
            offnet_min=opt("offnet_min"),
            sms=opt("sms"),
            unlimited_apps=opt("unlimited_apps"),
            source=str(opt("source") or "workbook"),
        )


@dataclass
class Demand:
    """Summarised recent history for one customer."""

    months: list[str]
    data_mean: float
    data_std: float
    data_est: float
    total_min_mean: float
    total_min_std: float
    total_min_est: float
    onnet_est: float
    offnet_est: float
    extra_gb_mean: float          # observed extra GB bought per month
    extra_cost_mean: float        # observed extra GB × unit price, per month
    avg_spend: float              # observed mean monthly spend (AZN)
    short_history: bool = False

    @property
    def window(self) -> tuple[str, str]:
        return (self.months[0], self.months[-1]) if self.months else ("", "")


@dataclass
class PlanEval:
    plan: Plan
    score: float | None
    components: dict                 # component name -> float | None
    est_total_cost: float | None
    cost_parts: dict
    adequacy_data: float | None
    adequacy_calls: float | None
    shortfall: str | None             # 'data' | 'calls' | 'data+calls' | None
    excess_gb: float | None
    is_current: bool
    reason_codes: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        p = self.plan
        return {
            "name": p.name,
            "family": p.family,
            "price_azn": p.price_azn,
            "data_gb": p.data_gb,
            "allnet_min": p.allnet_min,
            "onnet_min": p.onnet_min,
            "offnet_min": p.offnet_min,
            "sms": p.sms,
            "unlimited_apps": p.unlimited_apps,
            "score": round(self.score, 4) if self.score is not None else None,
            "components": {k: (round(v, 4) if v is not None else None) for k, v in self.components.items()},
            "est_total_cost": round(self.est_total_cost, 2) if self.est_total_cost is not None else None,
            "cost_parts": self.cost_parts,
            "adequacy_data": self.adequacy_data,
            "adequacy_calls": self.adequacy_calls,
            "shortfall": self.shortfall,
            "excess_gb": self.excess_gb,
            "is_current": self.is_current,
            "reason_codes": self.reason_codes,
            "facts": self.facts,
        }


# --------------------------------------------------------------------------- #
# Demand estimation
# --------------------------------------------------------------------------- #

def _mean_std(values: Sequence[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    m = sum(values) / n
    if n == 1:
        return m, 0.0
    var = sum((v - m) ** 2 for v in values) / (n - 1)  # sample variance
    return m, math.sqrt(var)


def summarize_history(
    usage_rows: Iterable[Mapping],
    window_months: int = 3,
    buffer_ratio: float = 0.5,
    extra_unit_price: float | None = None,
) -> Demand | None:
    """Build a :class:`Demand` from a customer's usage rows (mapping-like).

    Rows must carry ``month``, ``data_gb``, ``total_minutes``, ``onnet_min``,
    ``offnet_min``, ``extra_gb``, ``spend_azn``. Only the *last*
    ``window_months`` complete months are used (rows are sorted by month, so
    future records can never leak into an earlier recommendation).
    """
    rows = sorted(
        (r for r in usage_rows if r["month"] is not None),
        key=lambda r: str(r["month"]),
    )
    if not rows:
        return None
    window = rows[-window_months:] if window_months > 0 else rows
    short = len(window) == 1

    data = [float(r["data_gb"] or 0.0) for r in window]
    total = [float(r["total_minutes"] or 0.0) for r in window]
    onnet = [float(r["onnet_min"] or 0.0) for r in window]
    offnet = [float(r["offnet_min"] or 0.0) for r in window]
    extra = [float(r["extra_gb"] or 0.0) for r in window]
    spend = [float(r["spend_azn"] or 0.0) for r in window]

    d_mean, d_std = _mean_std(data)
    t_mean, t_std = _mean_std(total)
    o_mean, _ = _mean_std(onnet)
    f_mean, _ = _mean_std(offnet)
    e_mean, _ = _mean_std(extra)
    s_mean, _ = _mean_std(spend)

    buffer = 0.0 if short else buffer_ratio
    return Demand(
        months=[str(r["month"]) for r in window],
        data_mean=d_mean,
        data_std=d_std,
        data_est=d_mean + buffer * d_std,
        total_min_mean=t_mean,
        total_min_std=t_std,
        total_min_est=t_mean + buffer * t_std,
        onnet_est=o_mean + buffer * _mean_std(onnet)[1],
        offnet_est=f_mean + buffer * _mean_std(offnet)[1],
        extra_gb_mean=e_mean,
        extra_cost_mean=(e_mean * extra_unit_price) if extra_unit_price else 0.0,
        avg_spend=s_mean,
        short_history=short,
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def _ratio(allowance: float | None, demand: float) -> float | None:
    """Coverage ratio in [0, 1]; ``None`` when the allowance is unknown."""
    if allowance is None:
        return None
    if demand <= 0:
        return 1.0
    return max(0.0, min(1.0, allowance / demand))


def call_coverage(plan: Plan, demand: Demand) -> float | None:
    """Coverage of estimated call demand by the plan's known minute buckets.

    * Plans with an all-network allowance (Klass): it covers on-net and
      off-net alike → compare against total minute demand.
    * Plans with only on/off-net buckets (DaimOnline, CIN): each bucket is
      compared against the matching demand component, weighted by demand share.
    * If no bucket is known → ``None`` (unknown, excluded from scoring).
    """
    if plan.allnet_min is not None and plan.allnet_min > 0:
        return _ratio(float(plan.allnet_min), demand.total_min_est)

    known_any = plan.onnet_min is not None or plan.offnet_min is not None
    if not known_any:
        return None
    if demand.total_min_est <= 0:
        return 1.0

    on_demand, off_demand = demand.onnet_est, demand.offnet_est
    share = on_demand + off_demand
    if share <= 0:  # demand known to be zero but buckets exist
        return 1.0
    on_cov = _ratio(float(plan.onnet_min) if plan.onnet_min is not None else None, on_demand)
    off_cov = _ratio(float(plan.offnet_min) if plan.offnet_min is not None else None, off_demand)
    # unknown bucket for a component with demand > 0 → component unknown
    parts, weights = [], []
    if on_demand > 0 and on_cov is not None:
        parts.append(on_cov)
        weights.append(on_demand)
    if off_demand > 0 and off_cov is not None:
        parts.append(off_cov)
        weights.append(off_demand)
    if not parts:
        return None
    return sum(p * w for p, w in zip(parts, weights)) / sum(weights)


def estimate_extra_packs(plan: Plan, demand: Demand, pack_size_gb: float = 1.0) -> float | None:
    """Extra 1 GB packs the customer would still need to buy, in packs."""
    if plan.data_gb is None:
        return None
    over = demand.data_est - float(plan.data_gb)
    if over <= 0:
        return 0.0
    return math.ceil(over / pack_size_gb) if pack_size_gb > 0 else over


def estimate_out_of_bundle(plan: Plan, demand: Demand) -> float | None:
    """Estimated out-of-package minutes (same rule that reproduces the workbook 600/600)."""
    if plan.allnet_min is not None and plan.allnet_min > 0:
        return max(0.0, demand.total_min_est - float(plan.allnet_min))
    if plan.onnet_min is None and plan.offnet_min is None:
        return None
    on = 0.0 if plan.onnet_min is None else max(0.0, demand.onnet_est - float(plan.onnet_min))
    off = 0.0 if plan.offnet_min is None else max(0.0, demand.offnet_est - float(plan.offnet_min))
    return on + off


def estimate_total_cost(
    plan: Plan, demand: Demand, unit_extra_gb: float | None, unit_minute: float | None,
    pack_size_gb: float = 1.0,
) -> tuple[float | None, dict]:
    """Plan price + estimated extra-data packs + estimated out-of-bundle minutes.

    Returns ``(None, {})`` when the plan price is unknown. Extra-data cost is
    only added when the unit price and the purchase behaviour are known.
    """
    if plan.price_azn is None:
        return None, {}
    parts = {"plan_price": float(plan.price_azn)}
    packs = estimate_extra_packs(plan, demand, pack_size_gb)
    if packs is not None and unit_extra_gb is not None:
        parts["extra_data_packs"] = packs
        parts["extra_data_cost"] = round(packs * unit_extra_gb, 2)
    oob = estimate_out_of_bundle(plan, demand)
    if oob is not None and unit_minute is not None:
        parts["out_of_bundle_min"] = round(oob, 1)
        parts["out_of_bundle_cost"] = round(oob * unit_minute, 2)
    total = float(plan.price_azn) + parts.get("extra_data_cost", 0.0) + parts.get("out_of_bundle_cost", 0.0)
    return round(total, 2), parts


def evaluate_plan(
    plan: Plan,
    demand: Demand,
    *,
    current_tariff: str | None,
    weights: Weights,
    unit_extra_gb: float | None,
    unit_minute: float | None,
    pack_size_gb: float = 1.0,
    cost_range: tuple[float, float] | None = None,
    est_total_cost: float | None = None,
    cost_parts: dict | None = None,
) -> PlanEval:
    """Score one plan (cost normalisation needs ``cost_range`` across plans)."""
    is_current = current_tariff is not None and plan.name == current_tariff

    if est_total_cost is None:
        est_total_cost, cost_parts = estimate_total_cost(
            plan, demand, unit_extra_gb, unit_minute, pack_size_gb
        )
    cost_parts = cost_parts or {}

    adequacy_data = _ratio(plan.data_gb, demand.data_est)
    adequacy_calls = call_coverage(plan, demand)
    known_adequacy = [v for v in (adequacy_data, adequacy_calls) if v is not None]
    adequacy = sum(known_adequacy) / len(known_adequacy) if known_adequacy else None

    # shortfall detection (only for known dimensions)
    short = []
    if adequacy_data is not None and adequacy_data < 1.0:
        short.append("data")
    if adequacy_calls is not None and adequacy_calls < 1.0:
        short.append("calls")
    shortfall = "+".join(short) if short else None

    # oversupply penalty
    if plan.data_gb is None or demand.data_est <= 0:
        oversupply_score = None
        excess_gb = None
    else:
        excess = max(0.0, float(plan.data_gb) - demand.data_est)
        excess_gb = round(excess, 2)
        oversupply_score = 1.0 - min(1.0, excess / demand.data_est)

    # affordability preference
    if est_total_cost is None or est_total_cost <= 0:
        affordability = None
    else:
        affordability = max(0.0, min(1.0, demand.avg_spend / est_total_cost))

    # cost score (normalised across the candidate set)
    if est_total_cost is None or cost_range is None:
        cost_score = None
    else:
        lo, hi = cost_range
        cost_score = 1.0 if hi <= lo else (hi - est_total_cost) / (hi - lo)

    components = {
        "adequacy": adequacy,
        "cost": cost_score,
        "oversupply": oversupply_score,
        "affordability": affordability,
    }
    weight_of = {
        "adequacy": weights.adequacy,
        "cost": weights.cost,
        "oversupply": weights.oversupply,
        "affordability": weights.affordability,
    }
    known = {k: v for k, v in components.items() if v is not None}
    if known:
        wsum = sum(weight_of[k] for k in known)
        score = sum(weight_of[k] * v for k, v in known.items()) / wsum if wsum else None
    else:
        score = None

    # ---- reason codes + computed facts ------------------------------------ #
    codes: list[str] = []
    current_price = None
    if current_tariff and plan.name == current_tariff:
        codes.append("keeps_current")
    if adequacy_data is not None:
        codes.append("covers_data" if adequacy_data >= 1.0 else "shortfall_data")
    if adequacy_calls is not None:
        codes.append("covers_calls" if adequacy_calls >= 1.0 else "shortfall_calls")
    if est_total_cost is not None and plan.price_azn is not None:
        codes.append("estimated_cost_known")
    if plan.data_gb is None:
        codes.append("unknown_data_allowance")
    if plan.unlimited_apps in (None, "", "Yoxdur"):
        codes.append("no_unlimited_apps_listed")
    if not UNLIMITED_APPS_SCORABLE:
        codes.append("unlimited_apps_match_unknown")

    facts = {
        "est_data_gb": round(demand.data_est, 2),
        "observed_data_mean_gb": round(demand.data_mean, 2),
        "observed_extra_gb_per_month": round(demand.extra_gb_mean, 2),
        "observed_extra_cost_per_month": round(demand.extra_cost_mean, 2),
        "est_total_min": round(demand.total_min_est, 1),
        "plan_data_gb": plan.data_gb,
        "plan_total_min": _plan_total_min(plan),
        "est_total_cost_azn": est_total_cost,
        "observed_avg_spend_azn": round(demand.avg_spend, 2),
        "window": list(demand.window),
        "short_history": demand.short_history,
        "current_tariff": current_tariff,
        "current_price_azn": current_price,
        "cost_parts": cost_parts,
        "shortfall": shortfall,
    }

    return PlanEval(
        plan=plan,
        score=score,
        components=components,
        est_total_cost=est_total_cost,
        cost_parts=cost_parts,
        adequacy_data=adequacy_data,
        adequacy_calls=adequacy_calls,
        shortfall=shortfall,
        excess_gb=excess_gb,
        is_current=is_current,
        reason_codes=codes,
        facts=facts,
    )


def _plan_total_min(plan: Plan) -> float | None:
    if plan.allnet_min is not None and plan.allnet_min > 0:
        return float(plan.allnet_min)
    if plan.onnet_min is None and plan.offnet_min is None:
        return None
    return float(plan.onnet_min or 0) + float(plan.offnet_min or 0)


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #

def recommend(
    catalog: Sequence[Plan],
    demand: Demand,
    *,
    current_tariff: str | None,
    weights: Weights = DEFAULT_WEIGHTS,
    unit_extra_gb: float | None = None,
    unit_minute: float | None = None,
    pack_size_gb: float = 1.0,
    top_n: int = 3,
) -> dict:
    """Rank the catalog for one customer and return up to ``top_n`` plans.

    The current tariff is always included when its catalog data is known.
    Tie-break: lower estimated total cost, then smaller excess allowance,
    then name. If no plan covers estimated demand, every result carries a
    ``shortfall`` warning instead of a silent pass.
    """
    if not catalog:
        return {"ranked": [], "flags": {"empty_catalog": True}}

    evaluated: list[PlanEval] = []
    costs: list[float] = []
    for plan in catalog:
        cost, parts = estimate_total_cost(
            plan, demand, unit_extra_gb, unit_minute, pack_size_gb
        )
        if cost is not None:
            costs.append(cost)
        evaluated.append(
            evaluate_plan(
                plan, demand,
                current_tariff=current_tariff, weights=weights,
                unit_extra_gb=unit_extra_gb, unit_minute=unit_minute,
                pack_size_gb=pack_size_gb,
                cost_range=None, est_total_cost=cost, cost_parts=parts,
            )
        )

    cost_range = (min(costs), max(costs)) if costs else None
    # second pass with the shared cost range for normalisation
    final: list[PlanEval] = []
    for ev in evaluated:
        final.append(
            evaluate_plan(
                ev.plan, demand,
                current_tariff=current_tariff, weights=weights,
                unit_extra_gb=unit_extra_gb, unit_minute=unit_minute,
                pack_size_gb=pack_size_gb,
                cost_range=cost_range, est_total_cost=ev.est_total_cost,
                cost_parts=ev.cost_parts,
            )
        )

    def sort_key(ev: PlanEval):
        cost = ev.est_total_cost if ev.est_total_cost is not None else float("inf")
        excess = ev.excess_gb if ev.excess_gb is not None else float("inf")
        score = ev.score if ev.score is not None else float("-inf")
        return (-score, cost, excess, ev.plan.name)

    final.sort(key=sort_key)

    current_ev = next((e for e in final if e.is_current), None)
    picked = final[:top_n]
    if current_ev is not None and current_ev not in picked:
        picked[-1] = current_ev  # keep the current plan inside the top-3 window
        picked.sort(key=sort_key)

    current_plan = next((p for p in catalog if current_tariff and p.name == current_tariff), None)
    current_price = current_plan.price_azn if current_plan else None
    for ev in final:
        ev.facts["current_price_azn"] = current_price
        if current_price is not None and ev.est_total_cost is not None and not ev.is_current:
            diff = round(ev.est_total_cost - current_price, 2)
            ev.facts["cost_diff_vs_current_azn"] = diff
            ev.reason_codes.append("cheaper_than_current" if diff < 0 else
                                   ("same_cost_as_current" if diff == 0 else "dearer_than_current"))

    flags = {
        "shortfall_any": any(e.shortfall for e in picked),
        "current_included": current_ev is not None,
        "current_is_best": bool(picked and picked[0].is_current),
        "unlimited_apps_scorable": UNLIMITED_APPS_SCORABLE,
        "weights": weights.as_dict(),
        "window": list(demand.window),
        "model_version": MODEL_VERSION,
    }
    return {"ranked": [e.as_dict() for e in picked], "evaluated_count": len(final), "flags": flags}
