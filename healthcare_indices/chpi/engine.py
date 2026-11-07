"""CHPI research calculation engine for Tynbil-normalized negotiated-rate observations.

No raw Transparency in Coverage JSON ingestion is performed here.
No calculation from this package constitutes an official settlement fixing.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = (
    "vintage", "payer", "network", "provider_id", "geography",
    "billing_code_type", "billing_code", "billing_class", "negotiated_type",
    "negotiated_rate", "category"
)
ELIGIBLE_TYPES = {"negotiated", "fee_for_service", "dollar", "negotiated_dollar"}
CATEGORIES = (
    "inpatient", "outpatient", "professional", "imaging", "laboratory",
    "emergency", "post_acute", "behavioral"
)
METHODOLOGY = "CHPI-RESEARCH-0.1.0"


def _stable_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(payload):
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_feed(path):
    """Read a normalized Tynbil-style CSV or JSON array (not raw TiC MRF)."""
    source = Path(path)
    if source.suffix.lower() == ".csv":
        with source.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
    elif source.suffix.lower() == ".json":
        rows = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError("Normalized JSON feed must be an array of records")
    else:
        raise ValueError("Expected .csv or .json normalized feed")
    return rows, hashlib.sha256(source.read_bytes()).hexdigest()


def _key(row):
    # Preserve the *same* unit and payment method across source vintages.
    return tuple(str(row.get(k, "")).strip() for k in (
        "payer", "network", "provider_id", "geography", "billing_code_type",
        "billing_code", "modifier", "billing_class", "service_code",
        "negotiated_type", "rate_unit", "category"
    ))


def validate(rows):
    """Return clean observations and transparent exclusion counters."""
    clean, rejected = [], defaultdict(int)
    for raw in rows:
        if any(not str(raw.get(k, "")).strip() for k in REQUIRED):
            rejected["missing_required"] += 1
            continue
        row = {k: str(v).strip() if v is not None else "" for k, v in raw.items()}
        if row["category"] not in CATEGORIES:
            rejected["unknown_category"] += 1
            continue
        if row["negotiated_type"].lower() not in ELIGIBLE_TYPES:
            rejected["non_dollar_or_ambiguous_payment"] += 1
            continue
        if row.get("rate_unit", "per_service") not in ("", "per_service", "per_unit", "per_case"):
            rejected["unsupported_unit"] += 1
            continue
        try:
            price = float(row["negotiated_rate"])
        except (ValueError, TypeError):
            rejected["invalid_price"] += 1
            continue
        if not math.isfinite(price) or price <= 0:
            rejected["invalid_price"] += 1
            continue
        row["price"] = price
        clean.append(row)
    return clean, dict(rejected)


def calculate(rows, base_vintage, target_vintage, category_weights=None,
              minimum_coverage=0.80, max_abs_log_change=None):
    """Matched-cell, geometric price-relative research index.

    Each unique payer/network/provider/procedure/unit cell gets equal weight
    WITHIN its declared category. Category weights are explicit, not inferred
    from TiC row counts. A conflicted duplicate is excluded, not averaged.
    Missing base constituents remain in the coverage denominator.
    """
    if base_vintage == target_vintage:
        raise ValueError("Base and target vintages must differ")
    weights = category_weights or {c: 1 / len(CATEGORIES) for c in CATEGORIES}
    if not weights or any(c not in CATEGORIES or float(w) < 0 for c, w in weights.items()):
        raise ValueError("Invalid category weights")
    total = sum(float(w) for w in weights.values())
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise ValueError("Category weights must sum to 1")
    if not 0 <= minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be 0..1")
    clean, rejected = validate(rows)
    grouped = defaultdict(list)
    for r in clean:
        if r["vintage"] in (base_vintage, target_vintage):
            grouped[(r["vintage"], _key(r))].append(r["price"])
    stable = {}
    conflicts = 0
    for k, prices in grouped.items():
        if max(prices) != min(prices):
            conflicts += 1
        else:
            stable[k] = prices[0]
    base = {key: price for (vintage, key), price in stable.items() if vintage == base_vintage}
    target = {key: price for (vintage, key), price in stable.items() if vintage == target_vintage}
    by_category = {}
    contributions = []
    for category, weight in weights.items():
        keys = [k for k in base if k[-1] == category]
        matches = [k for k in keys if k in target]
        coverage = len(matches) / len(keys) if keys else 0.0
        if not matches:
            by_category[category] = {"base_cells":len(keys),"matched_cells":0,
                "coverage":coverage,"relative":None,"weight":float(weight)}
            continue
        logs = [math.log(target[k] / base[k]) for k in matches]
        if max_abs_log_change is not None:
            if max_abs_log_change < 0:
                raise ValueError("max_abs_log_change must be nonnegative")
            logs = [max(-max_abs_log_change, min(max_abs_log_change, x)) for x in logs]
        relative = math.exp(sum(logs) / len(logs))
        by_category[category] = {"base_cells":len(keys),"matched_cells":len(matches),
            "coverage":coverage,"relative":relative,"weight":float(weight)}
        contributions.append((float(weight), math.log(relative)))
    eligible = all(
        by_category[c]["matched_cells"] > 0 and by_category[c]["coverage"] >= minimum_coverage
        for c, w in weights.items() if float(w) > 0
    )
    # No silent redistribution when a category disappears.
    index = 100 * math.exp(sum(w * value for w, value in contributions)) if eligible else None
    return {
        "methodology":METHODOLOGY, "status":"RESEARCH_ONLY",
        "base_vintage":base_vintage, "target_vintage":target_vintage,
        "eligible_for_research_index":eligible,
        "index_level":round(index, 8) if index is not None else None,
        "growth_pct":round(index - 100, 8) if index is not None else None,
        "categories":by_category, "excluded":rejected,
        "conflicted_vintage_cell_groups":conflicts,
        "matched_cell_policy":"exact payer/network/provider/code/billing/method/unit/geography",
        "weighting":"declared category weights; equal matched cells within each category",
        "coverage_policy":"unmatched base cells count against category coverage",
        "notes":"No actual paid claims, utilization weights, insured loss or official settlement fixing"
    }


def create_research_artifact(source_path, base_vintage, target_vintage, output_path,
                             category_weights=None, minimum_coverage=0.8):
    rows, source_hash = read_feed(source_path)
    result = calculate(rows, base_vintage, target_vintage,
                       category_weights=category_weights,
                       minimum_coverage=minimum_coverage)
    result["source_sha256"] = source_hash
    result["calculated_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["artifact_sha256"] = _sha256(_stable_json(result))
    Path(output_path).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",
                                 encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Research CHPI from normalized Tynbil-style rates")
    p.add_argument("feed")
    p.add_argument("base_vintage")
    p.add_argument("target_vintage")
    p.add_argument("--output", default="chpi_research.json")
    p.add_argument("--weights", help="JSON file mapping category to fixed weights")
    p.add_argument("--minimum-coverage", type=float, default=0.80)
    a = p.parse_args()
    weights = json.loads(Path(a.weights).read_text()) if a.weights else None
    result = create_research_artifact(a.feed, a.base_vintage, a.target_vintage,
                                    a.output, weights, a.minimum_coverage)
    print(json.dumps({"eligible":result["eligible_for_research_index"],
                      "index_level":result["index_level"],"output":a.output}, indent=2))
