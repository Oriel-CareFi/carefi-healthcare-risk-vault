"""CHPI payout backtest, scenario sensitivity and basis-risk stress.

No insurer pricing, claims adjudication, or official settlement. Input history
may be synthetic or Tynbil-matched observed series, labeled by caller.
"""
from __future__ import annotations
import csv
import json
import math
from dataclasses import replace
from pathlib import Path
from .exposure import ExposureSchedule
from .hybrid import CoverageTerms, IndexFixing, ValidationError, evaluate, positive_money, basis_risk_report

def _finite(v,name):
    try: x=float(v)
    except (ValueError,TypeError) as exc: raise ValidationError(name+" invalid") from exc
    if not math.isfinite(x): raise ValidationError(name+" non-finite")
    return x

def replay(schedule:ExposureSchedule, terms:CoverageTerms, observations:list[dict], mode="parametric", provenance="SYNTHETIC"):
    """Replay matched annual growth observations, no payable claims.

    Each record:
      period, index_growth_pct, insured_price_only_growth_pct, eligible_loss_usd
    HYBRID requires a measured eligible loss for EVERY period, including zero.
    PARAMETRIC payout does not depend on a loss field. For parametric mismatch
    diagnostics only, separately supply insured price-only annual growth.
    """
    schedule.validate()
    terms.validate()
    if mode not in ("parametric","indemnity_hybrid"):
        raise ValidationError("Unsupported mode")
    if schedule.policy_id != terms.coverage_id:
        raise ValidationError("Exposure schedule and coverage ID mismatch")
    if schedule.total_exposure() != positive_money(terms.scheduled_exposure_usd,"Exposure"):
        raise ValidationError("Coverage exposure differs from frozen schedule total")
    if set(schedule.reference_weight_map()) != {terms.reference_index}:
        raise ValidationError("Replay supports one CHPI reference only")
    if not observations: raise ValidationError("No history supplied")
    periods=set()
    rows=[]
    for obs in observations:
        period=str(obs.get("period",""))
        if not period or period in periods:
            raise ValidationError("Period missing or duplicated")
        periods.add(period)
        growth=_finite(obs.get("index_growth_pct"),"Index growth")
        insured=_finite(obs.get("insured_price_only_growth_pct"),"Insured price-only growth")
        if growth <= -100:
            raise ValidationError("Impossible index growth <= -100%")
        eligible=obs.get("eligible_loss_usd")
        if mode=="indemnity_hybrid" and eligible is None:
            raise ValidationError("Hybrid requires verified eligible loss for each period")
        base=IndexFixing(terms.reference_index,100.0,"2025-01-01",period+"-BASE",
            "CHPI-RESEARCH-0.1.0","REPLAY-"+provenance)
        final=IndexFixing(terms.reference_index,100.0*(1.0+growth/100),
            "2026-01-01",period+"-FINAL","CHPI-RESEARCH-0.1.0","REPLAY-"+provenance)
        out=evaluate(terms,base,final,documented_adverse_loss_usd=eligible if mode=="indemnity_hybrid" else None)
        payout=float(out["index_implied_ceiling_usd"])
        # ECONOMIC proxy: reimbursement price changes above the same attachment
        # on scheduled exposure; does not include loss adjustment expenses.
        economic_adverse=max(0.0,(insured-terms.attachment_pct))*float(schedule.total_exposure())/100
        shortfall=max(0.0,economic_adverse-payout)
        excess=max(0.0,payout-economic_adverse)
        rows.append({
            "period":period,"index_growth_pct":growth,"insured_price_only_growth_pct":insured,
            "index_trigger":out["triggered"],"model_ceiling_usd":payout,
            "insured_adverse_price_proxy_usd":round(economic_adverse,2),
            "unprotected_adverse_proxy_usd":round(shortfall,2),
            "index_overpayment_proxy_usd":round(excess,2),
            "missed_adverse_trigger":bool(economic_adverse>0 and not out["triggered"]),
            "trigger_without_adverse_exposure":bool(out["triggered"] and economic_adverse==0),
            "claim_payable":False
        })
    n=len(rows)
    basis=basis_risk_report([r["index_growth_pct"] for r in rows],
                            [r["insured_price_only_growth_pct"] for r in rows]) if n>=2 else None
    return {
        "status":"RESEARCH_ONLY",
        "provenance":provenance,"mode":mode,
        "exposure_schedule_sha256":schedule.digest(),
        "coverage_id":terms.coverage_id,
        "observation_count":n,
        "trigger_frequency":sum(r["index_trigger"] for r in rows)/n,
        "mean_index_ceiling_usd":round(sum(r["model_ceiling_usd"] for r in rows)/n,2),
        "maximum_index_ceiling_usd":max(r["model_ceiling_usd"] for r in rows),
        "total_unprotected_adverse_proxy_usd":round(sum(r["unprotected_adverse_proxy_usd"] for r in rows),2),
        "total_index_overpayment_proxy_usd":round(sum(r["index_overpayment_proxy_usd"] for r in rows),2),
        "missed_adverse_trigger_count":sum(r["missed_adverse_trigger"] for r in rows),
        "trigger_without_adverse_count":sum(r["trigger_without_adverse_exposure"] for r in rows),
        "basis_risk":basis,
        "periods":rows,
        "not_an_actuarial_expected_loss":True
    }

def sensitivity(schedule, terms, observations, attachments, exhaustions, mode="parametric",provenance="SYNTHETIC"):
    results=[]
    for a in attachments:
        for e in exhaustions:
            if e<=a: continue
            adjusted=replace(terms,attachment_pct=float(a),exhaustion_pct=float(e))
            outcome=replay(schedule,adjusted,observations,mode,provenance)
            results.append({k:outcome[k] for k in (
                "mode","observation_count","trigger_frequency","mean_index_ceiling_usd",
                "maximum_index_ceiling_usd","total_unprotected_adverse_proxy_usd",
                "total_index_overpayment_proxy_usd","missed_adverse_trigger_count",
                "trigger_without_adverse_count"
            )}|{"attachment_pct":float(a),"exhaustion_pct":float(e)})
    return results

def read_history(path):
    src=Path(path)
    if src.suffix.lower()==".csv":
        with src.open(newline="",encoding="utf-8-sig") as handle:
            return list(csv.DictReader(handle))
    if src.suffix.lower()==".json":
        x=json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(x,list): raise ValidationError("Expected history JSON array")
        return x
    raise ValidationError("History must be .csv or .json")

if __name__=="__main__":
    import argparse
    from .exposure import read_schedule
    p=argparse.ArgumentParser(description="CHPI research payout historical replay")
    p.add_argument("exposure_schedule")
    p.add_argument("coverage_terms")
    p.add_argument("growth_history")
    p.add_argument("--mode",choices=("parametric","indemnity_hybrid"),default="parametric")
    p.add_argument("--provenance",default="SYNTHETIC")
    p.add_argument("--output",default="chpi_replay_research.json")
    a=p.parse_args()
    sch=read_schedule(a.exposure_schedule)
    terms=CoverageTerms(**json.loads(Path(a.coverage_terms).read_text(encoding="utf-8")))
    result=replay(sch,terms,read_history(a.growth_history),a.mode,a.provenance)
    Path(a.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","mode","observation_count","mean_index_ceiling_usd")}))
