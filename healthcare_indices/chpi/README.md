# Oriel Healthcare — Commercial Healthcare Price Index (CHPI)

**Research prototype only. Not an official settlement index or insurance quote.**

This isolated module consumes **Tynbil-normalized rate observations**, not raw Transparency in Coverage JSON. Tynbil owns MRF ingestion, normalization, and historical source-data extraction; Oriel owns the declared basket, index methodology, quality controls, fixing governance, and downstream reference outputs. Neither actuarial pricing nor insurance payout logic belongs in this calculation module.

## Required normalized feed (CSV or JSON array)

Required columns: `vintage,payer,network,provider_id,geography,billing_code_type,billing_code,billing_class,negotiated_type,negotiated_rate,category`.

Optional matching columns: `modifier,service_code,rate_unit`. Feed-v1 uses a stable `provider_id` provided by Tynbil, **not** an assumed facility location from TIN alone. `geography` is an explicitly validated region identifier. Negotiated rate must be a positive, comparable dollar amount with explicit unit/payment method.

Supported research categories: `inpatient,outpatient,professional,imaging,laboratory,emergency,post_acute,behavioral`. The initial defaults give each category 12.5% **solely for engine testing**; no production economic weights have been approved. Prefer an explicitly governed weights JSON for substantive backtests.

## Quick start

From repository root:

```bash
python -m unittest discover -s healthcare_indices/chpi/tests -v
python -m healthcare_indices.chpi.engine healthcare_indices/chpi/examples/synthetic_rates.csv 2026Q1 2026Q2 --weights healthcare_indices/chpi/examples/synthetic_weights.json --output /tmp/chpi_research.json
```

No external Python dependencies. Synthetic inputs exist to verify arithmetic and missing-data behavior, **not** as purported market data.

## Current rules and limitations

- Match on payer, network, provider, region, code system/code/modifier, billing class, service code, rate unit, rate type, and category.
- Exclude ambiguous, non-dollar, zero/negative, or unsupported units.
- Exclude a vintage/cell when conflicting prices are submitted. Identical duplicate rows are deduplicated.
- Equal weight for matched provider/procedure cells **within** each category; published basket weights must be predeclared and sum to 1.
- A category missing more than 20% of base cells fails the default prototype quality gate. A failing category prevents any headline level; there is **no silent reweighting**.
- Calculate geometric mean matched price relatives within each category, then aggregate with declared category weights. This is a **research variant**; compare against a fixed-base arithmetic Laspeyres approach before approving a final methodology.
- Research output records data SHA-256, calculation timestamp, method version, exclusion counts, matching coverage, and artifact SHA-256.
- **No official fixing or append-only settlement ledger exists yet.** Insurers must not settle policies from these research artifacts.
- Actual insurer/insured basis risk, exposure weighting, multiple networks under one payer, contract renewals, error revisions, representativeness, and historical volatility remain unvalidated.

## Before live Tynbil integration

Confirm signed feed contract, unique row identity, published code dictionary, code/contract units, stable provider/region mapping, payer and network crosswalk, observed vintage versus effective date, source revisions, archived datasets, duplicate semantics, licensed usage and redistribution rights. Add a true immutable fixing pipeline with source snapshots, reviewer approvals, a fixing calendar, dispute handling, revision policy and independent calculation review.

Keep CHPI calculation upstream of CareFi Markets forecasts and CareFi insurance/capacity workflows.
