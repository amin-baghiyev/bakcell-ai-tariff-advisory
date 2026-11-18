"""Plain-language explanations rendered from computed facts only.

No LLM, no invented numbers: every value in the templates comes from the
workbook-derived facts produced by :mod:`services.recommendation`.

All sentences are localized at render time (``lang`` = ``az`` | ``en``), so
switching the UI language re-renders them — nothing English is baked into
the stored snapshots beyond the archival copy.
"""

from __future__ import annotations

from config import Weights
from i18n import translate


def _t(lang: str, key: str, **params) -> str:
    return translate(lang, key, **params)


def _fmt_gb(v, lang: str = "en") -> str:
    if v is None:
        return _t(lang, "expl.unknown_amount")
    return f"{v:g} GB"


def _fmt_azn(v, lang: str = "en") -> str:
    if v is None:
        return _t(lang, "expl.unknown_amount")
    return f"{v:g} AZN"


def _fmt_min(v, lang: str = "en") -> str:
    if v is None:
        return _t(lang, "common.unknown")
    return f"{v:g} min"


def _allowance_sentence(plan: dict, lang: str = "en") -> str:
    if plan.get("data_gb") is None:
        return _t(lang, "expl.allow_no_data")
    mins = plan.get("allnet_min")
    if mins and mins > 0:
        minute_part = _t(lang, "expl.min_any_net", m=f"{mins:g}")
    else:
        on, off = plan.get("onnet_min"), plan.get("offnet_min")
        bits = []
        if on:
            bits.append(_t(lang, "expl.min_onnet", m=f"{on:g}"))
        if off:
            bits.append(_t(lang, "expl.min_offnet", m=f"{off:g}"))
        minute_part = ", ".join(bits) if bits else _t(lang, "expl.min_unknown")
    return _t(lang, "expl.allowance_includes",
              gb=_fmt_gb(plan["data_gb"], lang), minpart=minute_part)


def explain_ranked(result: dict, demand, current_tariff: str | None,
                   lang: str = "en") -> dict:
    """Build per-plan explanations + an overall summary for the ranked list.

    ``result`` is the dict returned by :func:`services.recommendation.recommend`,
    ``demand`` is the matching :class:`~services.recommendation.Demand`.
    """
    ranked = result.get("ranked", [])
    flags = result.get("flags", {})
    per_plan = []
    for i, plan in enumerate(ranked, start=1):
        per_plan.append(
            dict(
                explain_plan(plan, demand, current_tariff, rank=i, flags=flags, lang=lang),
                short_reason=short_reason(plan, lang),
            )
        )

    summary = _summary(ranked, demand, current_tariff, flags, lang)
    return {
        "summary": summary,
        "per_plan": per_plan,
        "disclaimer": _t(lang, "expl.disclaimer"),
        "window": list(flags.get("window", [])),
        "weights": flags.get("weights", {}),
        "model_version": flags.get("model_version", ""),
    }


def _summary(ranked: list[dict], demand, current_tariff: str | None, flags: dict,
             lang: str = "en") -> str:
    if not ranked:
        return _t(lang, "expl.no_reco")
    best = ranked[0]
    parts = [
        _t(lang, "expl.summary_usage",
           n=len(demand.months), months=", ".join(demand.months),
           gb=f"{demand.data_mean:g}", min=f"{demand.total_min_mean:g}",
           extra=f"{demand.extra_gb_mean:g}")
    ]
    if flags.get("current_is_best"):
        parts.append(_t(lang, "expl.summary_current_best", name=best["name"]))
    else:
        parts.append(
            _t(lang, "expl.summary_rank_first", name=best["name"],
               allowance=_allowance_sentence(best, lang),
               cost=_fmt_azn(best.get("est_total_cost"), lang))
        )
    if flags.get("shortfall_any"):
        parts.append(_t(lang, "expl.summary_shortfall_warn"))
    if flags.get("current_included") and not flags.get("current_is_best"):
        cur = next((p for p in ranked if p.get("is_current")), None)
        if cur is not None:
            parts.append(_t(lang, "expl.summary_current_included",
                            name=cur["name"], n=ranked.index(cur) + 1))
    return " ".join(parts)


def explain_plan(
    plan: dict, demand, current_tariff: str | None, rank: int,
    flags: dict | None = None, lang: str = "en",
) -> dict:
    """One short paragraph + bullets for a single ranked plan."""
    facts = plan.get("facts", {})
    name = plan.get("name", "the plan")
    current_price = facts.get("current_price_azn")
    est_cost = plan.get("est_total_cost")

    sentences = [_t(lang, "expl.plan_head", name=name,
                    allowance=_allowance_sentence(plan, lang)) + "."]

    if est_cost is not None:
        if plan.get("is_current"):
            sentences.append(
                _t(lang, "expl.cost_current", est=_fmt_azn(est_cost, lang),
                   price=_fmt_azn(plan.get("price_azn"), lang))
            )
        else:
            diff = facts.get("cost_diff_vs_current_azn")
            if diff is not None and current_price is not None:
                if diff == 0:
                    sentences.append(
                        _t(lang, "expl.cost_same", est=_fmt_azn(est_cost, lang),
                           cur=_fmt_azn(current_price, lang))
                    )
                else:
                    direction = _t(lang, "expl.less" if diff < 0 else "expl.more")
                    sentences.append(
                        _t(lang, "expl.cost_diff", est=_fmt_azn(est_cost, lang),
                           diff=_fmt_azn(abs(diff), lang), dir=direction,
                           cur=_fmt_azn(current_price, lang))
                    )
            else:
                sentences.append(_t(lang, "expl.cost_est_only",
                                    est=_fmt_azn(est_cost, lang)))

    # usage vs allowance
    if facts.get("plan_data_gb") is not None:
        used = facts.get("est_data_gb")
        allow = facts.get("plan_data_gb")
        if used is not None:
            if used <= allow:
                sentences.append(
                    _t(lang, "expl.data_fits", used=f"{used:g}", allow=f"{allow:g}")
                )
            else:
                sentences.append(
                    _t(lang, "expl.data_exceeds", used=f"{used:g}",
                       allow=f"{allow:g}", over=f"{round(used - allow, 2):g}")
                )

    # calls
    ac = plan.get("adequacy_calls")
    if ac is None:
        sentences.append(_t(lang, "expl.calls_unknown"))
    elif ac >= 1.0:
        sentences.append(
            _t(lang, "expl.calls_fit",
               n=f"{facts.get('est_total_min', demand.total_min_est):g}")
        )
    else:
        sentences.append(
            _t(lang, "expl.calls_partial", pct=f"{round(ac * 100)}")
        )

    if plan.get("shortfall"):
        sentences.append(
            _t(lang, "expl.shortfall_warn", s=plan["shortfall"])
        )
    if plan.get("is_current"):
        sentences.append(_t(lang, "expl.is_current_note"))

    bullets = _bullets(plan, demand, lang)
    return {
        "rank": rank,
        "name": name,
        "text": " ".join(sentences),
        "bullets": bullets,
        "is_current": bool(plan.get("is_current")),
        "reason_codes": plan.get("reason_codes", []),
        "score": plan.get("score"),
        "shortfall": plan.get("shortfall"),
    }


def _bullets(plan: dict, demand, lang: str = "en") -> list[str]:
    facts = plan.get("facts", {})
    out: list[str] = []
    obs_extra = facts.get("observed_extra_gb_per_month")
    if obs_extra:
        out.append(
            _t(lang, "expl.bul_extra_bought", x=f"{obs_extra:g}",
               c=_fmt_azn(facts.get("observed_extra_cost_per_month"), lang))
        )
    parts = plan.get("cost_parts", {})
    if parts.get("extra_data_packs"):
        extras = _t(lang, "expl.bul_extras_1",
                    packs=f"{parts['extra_data_packs']:g}",
                    cost=_fmt_azn(parts.get("extra_data_cost"), lang))
        if parts.get("out_of_bundle_min"):
            extras += _t(lang, "expl.bul_extras_2",
                         m=f"{parts.get('out_of_bundle_min', 0):g}",
                         c=_fmt_azn(parts.get("out_of_bundle_cost"), lang))
        out.append(extras + ".")
    if plan.get("excess_gb"):
        out.append(_t(lang, "expl.bul_excess", x=f"{plan['excess_gb']:g}"))
    apps = plan.get("unlimited_apps")
    if apps and apps != "Yoxdur":
        out.append(_t(lang, "expl.bul_apps", apps=apps))
    out.append(_t(lang, "expl.bul_spend",
                  s=_fmt_azn(facts.get("observed_avg_spend_azn"), lang)))
    return out


def short_reason(plan: dict, lang: str = "en") -> str:
    """Compact one-liner for suggestion cards (≤ ~120 chars, facts only)."""
    facts = plan.get("facts", {})
    bits: list[str] = []
    if plan.get("adequacy_data") == 1.0:
        bits.append(_t(lang, "expl.sr_covers", g=f"{facts.get('est_data_gb', '?')}"))
    elif plan.get("adequacy_data") is not None:
        bits.append(_t(lang, "expl.sr_less_data"))
    if plan.get("adequacy_calls") == 1.0:
        bits.append(_t(lang, "expl.sr_calls_fit"))
    elif plan.get("adequacy_calls") is not None:
        bits.append(_t(lang, "expl.sr_calls_maybe"))
    diff = facts.get("cost_diff_vs_current_azn")
    if diff is not None:
        if diff < 0:
            bits.append(_t(lang, "expl.sr_cheaper", d=f"{-diff:g}"))
        elif diff > 0:
            bits.append(_t(lang, "expl.sr_dearer", d=f"{diff:g}"))
        else:
            bits.append(_t(lang, "expl.sr_same_cost"))
    if plan.get("is_current"):
        bits.insert(0, _t(lang, "expl.sr_current"))
    if plan.get("excess_gb"):
        bits.append(_t(lang, "expl.sr_excess", x=f"{plan['excess_gb']:g}"))
    return " · ".join(bits) if bits else _t(lang, "expl.sr_fallback")


def weight_note(weights: Weights, lang: str = "en") -> str:
    return _t(lang, "expl.weights_note",
              a=weights.adequacy, c=weights.cost,
              o=weights.oversupply, f=weights.affordability)
