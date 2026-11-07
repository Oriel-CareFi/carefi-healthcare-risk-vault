# Exposure-linked CHPI insurance pilot — Phase 2

This module performs **research-only historical replay** of the CHPI index-parametric and index-triggered indemnity-hybrid reimbursement-price insurance designs. It accepts Tynbil/Oriel index growth observations and an independent insured **price-only** growth or eligible-loss panel. No raw insurer TiC data is processed.

## Frozen exposure schedule
The insured-side schedule is JSON with insured ID, coverage ID, coverage direction, policy term, freeze date (required before start), evidence reference and separate exposure lines by region, service category, network, reference index and scheduled reimbursement-at-risk dollars. The schedule's canonical SHA-256 digest allows a model reviewer to verify that lines did not change after freeze.

Exposure weights are **not** automatically CHPI index weights. This is an insurance-specific underwriting schedule; the independent index calculation cannot be altered to fit a claim.

## Two coverage modes
- `parametric`: objective annual CHPI excess movement above attachment determines an *illustrative* modeled ceiling, independent of insured claim-by-claim loss. Insured economic interest still needs prebinding documentation.
- `indemnity_hybrid`: the same index trigger, with the indicative amount further capped by verified `eligible_loss_usd` for that period. Explicit zero amounts are valid. No implicit inference of eligible loss from cost growth.

For all modes the engine calculates a **basis-risk proxy**, not loss adjustment or actuarial risk capital: `max(0, insured price-only growth - attachment) * scheduled exposure`. This is an intentionally simplified retrospective economic benchmark; it may differ from verified indemnifiable loss. A parametric trigger may overpay this proxy and miss an actual adverse price movement; both are reported. **No computed payout is payable**.

Only payer-side price-increase coverage is supported. Provider-side adverse revenue or reimbursement-wage-cost spread contracts require separate models and evidence.

## Reproducible test

From repo root:

```bash
python -m unittest discover -s healthcare_indices/chpi/tests -v
python -m healthcare_indices.chpi.replay \
 healthcare_indices/chpi/examples/synthetic_exposure.json \
 healthcare_indices/chpi/examples/synthetic_terms.json \
 healthcare_indices/chpi/examples/synthetic_growth_history.csv \
 --mode parametric --output /tmp/chpi_parametric_replay.json

python -m healthcare_indices.chpi.replay \
 healthcare_indices/chpi/examples/synthetic_exposure.json \
 healthcare_indices/chpi/examples/synthetic_terms.json \
 healthcare_indices/chpi/examples/synthetic_growth_history.csv \
 --mode indemnity_hybrid --output /tmp/chpi_hybrid_replay.json
```

All fixtures are explicitly **SYNTHETIC**. No empirical historical CHPI series or insurer-side price-only outcomes have been supplied yet.

## Required next dependencies
1. Tynbil matched-rate history and a governed CHPI index history with a signed methodology, source vintage manifest, coverage and revision diagnostics.
2. Insurance pilot partner's independently documented exposure schedule and price-only change history.
3. Joint actuarial/reinsurance evaluation of trigger frequency, basis risk, tail concentration, pricing and limit.
4. Carrier/counsel approval for insurable-interest treatment, pure-parametric vs indemnity requirements, claims administrator and policy terms.
5. Index fixing ledger and independent calculation approval prior to any real-world settlement or payment authorization.

## Caveats
The replay treats each supplied historical period as a comparable annual measurement and does not claim independent year observations; overlapping annual windows should be labeled and treated as dependent. No probability distribution, actuarial expected loss, premium, or risk capital estimate is inferred from four synthetic examples.
