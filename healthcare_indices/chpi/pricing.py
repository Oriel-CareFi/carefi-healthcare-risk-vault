"""Non-binding CHPI underwriting and technical pricing workbench.

Outputs are RESEARCH_ONLY and NOT a rate filing, insurer quote, actuarial
opinion, or approved settlement model. Accepts frequency/severity scenario
weights supplied by the analyst; never implies synthetic inputs are empirical.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite, sqrt
import hashlib
import json

from .exposure import ExposureSchedule
from .hybrid import CoverageTerms, ValidationError, positive_money
from .replay import replay


def _number(value, label):
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be numeric") from exc
    if not isfinite(v):
        raise ValidationError(f"{label} must be finite")
    return v


def _usd(value):
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _weighted_quantile(values, probabilities, quantile):
    # Conservative left-continuous weighted loss quantile.
    cumulative = 0.0
    for value, probability in sorted(zip(values, probabilities)):
        cumulative += probability
        if cumulative + 1e-12 >= quantile:
            return value
    return max(values)


@dataclass(frozen=True)
class PricingAssumptions:
    expense_ratio: float
    commission_ratio: float
    target_margin_ratio: float
    fixed_expense_usd: str
    capital_quantile: float = 0.95
    annual_capital_cost_rate: float = 0.10
    reinsurance_cession_ratio: float = 0.0
    reinsurance_premium_usd: str = "0"
    # The insurer/carrier pays insured gross loss and recovers ceded share.
    # The broker/insurer should provide a reinsurance cost quote separately.
    minimum_premium_usd: str = "0"
    assumptions_id: str = "SYNTHETIC-RESEARCH"

    def validate(self):
        for name in ("expense_ratio", "commission_ratio", "target_margin_ratio",
                     "annual_capital_cost_rate", "reinsurance_cession_ratio"):
            value = _number(getattr(self, name), name)
            if not 0 <= value <= 1:
                raise ValidationError(f"{name} must be between 0 and 1")
        if self.expense_ratio + self.commission_ratio + self.target_margin_ratio >= 1:
            raise ValidationError("Expense + commission + margin must be less than 100%")
        q = _number(self.capital_quantile, "capital_quantile")
        if not 0 < q < 1:
            raise ValidationError("Capital quantile must be in (0,1)")
        positive_money(self.fixed_expense_usd, "Fixed expenses", allow_zero=True)
        positive_money(self.reinsurance_premium_usd, "Reinsurance premium", allow_zero=True)
        positive_money(self.minimum_premium_usd, "Minimum premium", allow_zero=True)
        if not self.assumptions_id:
            raise ValidationError("Assumptions ID is required")


def technical_pricing(schedule: ExposureSchedule, terms: CoverageTerms,
                      scenario_history: list[dict], probabilities: list[float],
                      assumptions: PricingAssumptions, mode="parametric",
                      provenance="SYNTHETIC"):
    """Calculate conditional scenario-based technical indicated premium.

    All scenarios must be supplied explicitly with probabilities summing to 1.
    A set of observed overlapping annual returns is not an independent actuarial
    sample; user is responsible for probability and dependence assumptions.
    """
    assumptions.validate()
    if provenance not in ("SYNTHETIC", "TYNBIL_UNVERIFIED", "OBSERVED_UNREVIEWED"):
        raise ValidationError("Unrecognized provenance; no production approval exists")
    if not scenario_history or len(probabilities) != len(scenario_history):
        raise ValidationError("One probability required per scenario")
    probabilities = [_number(p, "Probability") for p in probabilities]
    if any(p < 0 for p in probabilities) or not abs(sum(probabilities) - 1) <= 1e-9:
        raise ValidationError("Scenario probabilities must be nonnegative and sum to 1")
    response = replay(schedule, terms, scenario_history, mode=mode, provenance=provenance)
    losses = [p["model_ceiling_usd"] for p in response["periods"]]
    limit = float(positive_money(terms.policy_limit_usd, "Policy limit"))
    expected_gross = sum(w * loss for w, loss in zip(probabilities, losses))
    second_moment = sum(w * loss * loss for w, loss in zip(probabilities, losses))
    standard_deviation = sqrt(max(0.0, second_moment - expected_gross ** 2))
    tail = _weighted_quantile(losses, probabilities, assumptions.capital_quantile)
    cession = assumptions.reinsurance_cession_ratio
    expected_retained = expected_gross * (1 - cession)
    retained_tail = tail * (1 - cession)
    # Capital is an indicative quantile-minus-expected-loss proxy, not an RBC,
    # Solvency II or rating agency capital measure. No diversification credit.
    capital_proxy = max(0.0, retained_tail - expected_retained)
    capital_cost = capital_proxy * assumptions.annual_capital_cost_rate
    reinsurance_cost = float(positive_money(assumptions.reinsurance_premium_usd, "Reinsurance premium", allow_zero=True))
    fixed = float(positive_money(assumptions.fixed_expense_usd, "Fixed expenses", allow_zero=True))
    numerator = expected_retained + capital_cost + reinsurance_cost + fixed
    denominator = 1 - (assumptions.expense_ratio +
                        assumptions.commission_ratio + assumptions.target_margin_ratio)
    uncapped_indicated = numerator / denominator
    minimum = float(positive_money(assumptions.minimum_premium_usd, "Minimum premium", allow_zero=True))
    premium = max(uncapped_indicated, minimum)
    insured_exposure = float(schedule.total_exposure())
    assumptions_dump = asdict(assumptions)
    checksum = hashlib.sha256(json.dumps({
        "schedule": schedule.digest(), "terms": asdict(terms),
        "history": scenario_history, "probabilities": probabilities,
        "assumptions": assumptions_dump, "mode": mode,
        "provenance": provenance
    }, sort_keys=True, separators=(",",":")).encode()).hexdigest()
    return {
        "status": "RESEARCH_ONLY",
        "is_bindable_quote": False,
        "assumptions_id": assumptions.assumptions_id,
        "provenance": provenance,
        "mode": mode,
        "coverage_id": terms.coverage_id,
        "scenario_count": len(losses),
        "premium_usd": _usd(premium),
        "premium_per_1000_exposure_usd": _usd(premium / insured_exposure * 1000),
        "premium_pct_exposure": round(100 * premium / insured_exposure, 6),
        "technical_indication_before_minimum_usd": _usd(uncapped_indicated),
        "expected_gross_loss_usd": _usd(expected_gross),
        "expected_retained_loss_usd": _usd(expected_retained),
        "loss_stddev_usd": _usd(standard_deviation),
        "gross_empirical_quantile_usd": _usd(tail),
        "retained_capital_proxy_usd": _usd(capital_proxy),
        "annual_capital_cost_usd": _usd(capital_cost),
        "reinsurance_premium_usd": _usd(reinsurance_cost),
        "fixed_expense_usd": _usd(fixed),
        "expense_ratio": assumptions.expense_ratio,
        "commission_ratio": assumptions.commission_ratio,
        "target_margin_ratio": assumptions.target_margin_ratio,
        "gross_policy_limit_usd": _usd(limit),
        "trigger_probability_assumed": round(sum(
            p for p, loss in zip(probabilities, losses) if loss > 0), 8),
        "loss_ratio_expected_gross_to_premium": round(expected_gross / premium, 8) if premium > 0 else None,
        "exposure_schedule_sha256": schedule.digest(),
        "model_input_sha256": checksum,
        "basis_risk": response["basis_risk"],
        "alerts": [
            "Hypothetical technical indication, not premium adequacy or underwriting approval",
            "Scenario probabilities are assumptions, not empirically estimated event likelihoods",
            "No diversification, renewal dependency, claims inflation or reinsurance default modeled",
            "Reinsurance premium must be independently quoted; cession without sufficient RI cost can underprice",
            "Hybrid needs eligible loss validation; parametric requires pre-bound insurable-interest assessment",
            "Independent final CHPI fixings and insurer/legal approvals remain unavailable"
        ]
    }


def price_sensitivity(schedule, terms, history, probabilities, assumptions,
                      attachments, exhaustions, mode="parametric", provenance="SYNTHETIC"):
    from dataclasses import replace
    results = []
    for attachment in attachments:
        for exhaustion in exhaustions:
            attachment = _number(attachment, "Attachment")
            exhaustion = _number(exhaustion, "Exhaustion")
            if exhaustion <= attachment:
                continue
            adjusted = replace(terms, attachment_pct=attachment, exhaustion_pct=exhaustion)
            result = technical_pricing(schedule, adjusted, history, probabilities,
                                       assumptions, mode, provenance)
            results.append({
                "attachment_pct":attachment, "exhaustion_pct":exhaustion,
                "premium_usd":result["premium_usd"],
                "expected_gross_loss_usd":result["expected_gross_loss_usd"],
                "trigger_probability_assumed":result["trigger_probability_assumed"],
                "retained_capital_proxy_usd":result["retained_capital_proxy_usd"]
            })
    return results


if __name__ == "__main__":
    from pathlib import Path
    import argparse
    from .exposure import read_schedule
    from .replay import read_history

    parser = argparse.ArgumentParser(description="CHPI non-binding research premium indications")
    parser.add_argument("schedule")
    parser.add_argument("terms")
    parser.add_argument("history")
    parser.add_argument("pricing_input")
    parser.add_argument("--mode",choices=("parametric","indemnity_hybrid"),default="parametric")
    parser.add_argument("--output",default="chpi_pricing_research.json")
    args=parser.parse_args()
    terms=CoverageTerms(**json.loads(Path(args.terms).read_text()))
    p=json.loads(Path(args.pricing_input).read_text())
    assumptions=PricingAssumptions(**p["assumptions"])
    result=technical_pricing(read_schedule(args.schedule),terms,
        read_history(args.history),p["scenario_probabilities"],assumptions,
        args.mode,p.get("provenance","SYNTHETIC"))
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in (
        "status","mode","premium_usd","expected_gross_loss_usd")}))
