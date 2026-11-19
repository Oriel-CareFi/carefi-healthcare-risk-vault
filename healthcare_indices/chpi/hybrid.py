"""CHPI index-hybrid insurance research model.

Independent CHPI observations are inputs, never calculated from insured losses.
This module does NOT issue policies, quote premiums, or perform regulated claims
administration. All example exposures and results are synthetic.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from typing import Optional


class ValidationError(ValueError):
    pass


def money(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError("Invalid monetary value")
    if not d.is_finite():
        raise ValidationError("Non-finite monetary value")
    return d


def positive_money(value, name, allow_zero=False):
    d = money(value)
    if d < 0 or (not allow_zero and d == 0):
        raise ValidationError(name + " must be positive")
    return d


@dataclass(frozen=True)
class IndexFixing:
    index_id: str
    level: float
    fixing_date: str
    vintage: str
    methodology: str
    source_hash: str
    publication_state: str = "RESEARCH"
    approved_by: str = ""

    def validate(self, require_final=False):
        if not self.index_id or not self.methodology or not self.source_hash:
            raise ValidationError("Index fixing requires reference provenance")
        if not math.isfinite(self.level) or self.level <= 0:
            raise ValidationError("Index level must be positive and finite")
        try:
            datetime.fromisoformat(self.fixing_date)
        except ValueError:
            raise ValidationError("Fixing date must be ISO 8601")
        if self.publication_state not in ("RESEARCH", "PROVISIONAL", "FINAL"):
            raise ValidationError("Unknown publication state")
        if require_final and (self.publication_state != "FINAL" or not self.approved_by):
            raise ValidationError("Unapproved index fixing cannot authorize settlement")


@dataclass(frozen=True)
class CoverageTerms:
    # Price inflation protection: annual CHPI growth above a fixed attachment.
    coverage_id: str
    reference_index: str
    attachment_pct: float
    exhaustion_pct: float
    scheduled_exposure_usd: str
    policy_limit_usd: str
    retained_share_pct: float = 0.0
    exposure_region: str = "UNSPECIFIED"
    requires_documented_loss: bool = True

    def validate(self):
        if not self.coverage_id or not self.reference_index:
            raise ValidationError("Coverage and index IDs required")
        numbers = (self.attachment_pct, self.exhaustion_pct, self.retained_share_pct)
        if not all(math.isfinite(v) for v in numbers):
            raise ValidationError("Non-finite contract percentage")
        if not -100 < self.attachment_pct < self.exhaustion_pct:
            raise ValidationError("Exhaustion must exceed attachment")
        if not 0 <= self.retained_share_pct < 100:
            raise ValidationError("Retained share must be in [0,100)")
        positive_money(self.scheduled_exposure_usd, "Exposure")
        positive_money(self.policy_limit_usd, "Limit")


def index_growth_pct(base: IndexFixing, final: IndexFixing, require_final=False):
    base.validate(require_final)
    final.validate(require_final)
    if base.index_id != final.index_id:
        raise ValidationError("Different index IDs")
    if base.methodology != final.methodology:
        raise ValidationError("Methodology change requires an approved rebasing rule")
    if base.fixing_date >= final.fixing_date:
        raise ValidationError("Final observation must follow base")
    return 100.0 * (final.level / base.level - 1.0)


def evaluate(terms: CoverageTerms, base: IndexFixing, final: IndexFixing,
             documented_adverse_loss_usd: Optional[str] = None,
             settlement_mode=False):
    """Return non-binding, deterministic scenario payout.

    Trigger: positive index growth above attachment.
    Gross price-linked amount: exposure * excess percentage points / 100.
    Excess is capped at exhaustion threshold and then retention applied.
    Optional documented adverse loss caps a hybrid indemnity payout.
    The deductible/retained exposure and all amounts are illustrative.
    """
    terms.validate()
    if terms.reference_index != base.index_id or terms.reference_index != final.index_id:
        raise ValidationError("Coverage index mismatch")
    growth = index_growth_pct(base, final, require_final=settlement_mode)
    if settlement_mode:
        raise ValidationError("Settlement disabled: no bound policy, approved fixing register, or claims administrator")
    excess = max(0.0, min(growth, terms.exhaustion_pct) - terms.attachment_pct)
    indexed_amount = positive_money(terms.scheduled_exposure_usd, "Exposure") * Decimal(str(excess)) / Decimal("100")
    insurer_share = Decimal("1") - Decimal(str(terms.retained_share_pct)) / Decimal("100")
    calculated = indexed_amount * insurer_share
    capped = min(calculated, positive_money(terms.policy_limit_usd, "Limit"))
    if documented_adverse_loss_usd is not None:
        capped = min(capped, positive_money(documented_adverse_loss_usd, "Adverse loss", allow_zero=True))
    elif terms.requires_documented_loss:
        # Informative modeled ceiling, not an enforceable payable claim.
        pass
    payout = capped.quantize(Decimal("0.01"))
    return {
        "mode": "RESEARCH_ONLY", "coverage_id": terms.coverage_id,
        "growth_pct": round(growth, 8),
        "triggered": excess > 0,
        "index_excess_percentage_points": round(excess, 8),
        "index_implied_ceiling_usd": str(payout),
        "documented_loss_supplied": documented_adverse_loss_usd is not None,
        "claim_payable": False,
        "reason": "Requires executed policy, insured-interest check, approved final fixings, and claims review",
        "input_digest_sha256": hashlib.sha256(json.dumps({
            "terms": asdict(terms), "base": asdict(base), "final": asdict(final),
            "adverse_loss": documented_adverse_loss_usd,
        }, sort_keys=True).encode()).hexdigest()
    }


def scenario_grid(terms, base, target_levels, insured_loss_usd=None):
    output = []
    for level in target_levels:
        final = IndexFixing(index_id=base.index_id, level=float(level),
            fixing_date="2027-12-31", vintage="synthetic_2027Q4",
            methodology=base.methodology, source_hash="SYNTHETIC-NOT-TIC")
        output.append(evaluate(terms, base, final, insured_loss_usd))
    return output


def basis_risk_report(index_growth, insured_cost_growth, weights=None):
    """Descriptive scenario basis risk; not predictive of future indemnity."""
    if len(index_growth) != len(insured_cost_growth) or len(index_growth) < 2:
        raise ValidationError("Need >=2 paired index and insured growth observations")
    if weights is not None and len(weights) != len(index_growth):
        raise ValidationError("Weights length mismatch")
    pairs = [(float(a), float(b)) for a, b in zip(index_growth, insured_cost_growth)]
    if not all(math.isfinite(a) and math.isfinite(b) for a,b in pairs):
        raise ValidationError("Non-finite paired observation")
    errors = [b-a for a,b in pairs]
    n = len(errors)
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e*e for e in errors) / n)
    mean = sum(errors) / n
    return {
        "observation_count": n,
        "mean_insured_minus_index_pp": round(mean, 6),
        "mean_absolute_basis_pp": round(mae, 6),
        "root_mean_square_basis_pp": round(rmse, 6),
        "max_absolute_basis_pp": round(max(map(abs,errors)), 6),
        "loss_direction_mismatch_count": sum((a > 0) != (b > 0) for a,b in pairs),
        "notes": "Descriptive paired-growth difference; not an actuarial loss or premium estimate"
    }
