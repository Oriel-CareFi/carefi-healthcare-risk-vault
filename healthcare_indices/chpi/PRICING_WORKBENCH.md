# CHPI Underwriting and Technical Pricing — research workbench

**Not an insurance quote, premium filing, actuarial opinion, capital adequacy
estimate, insurer authorization, or policy binding.** No real CHPI historical
rate movements have yet been ingested.

## Architecture

- Tynbil: historical normalized commercial negotiated-rate observations.
- Oriel: governed CHPI methodology, published index histories, fixing state and quality diagnostics.
- CareFi: independently frozen insured exposure schedule, index-parametric or
  index-triggered indemnity-hybrid risk structuring, pricing/replay.
- Licensed insurer/reinsurer: underwriter of record, actuarial approval, regulatory
  form/licensing, capacity and claims administration.

The pricing engine consumes existing `ExposureSchedule`, `CoverageTerms`,
and replay observations. It cannot authorize payments or produce bindable quotes.
Only payer-side adverse commercial reimbursement-price increases are modeled.
Provider reimbursement shortfall is a separate future insurance product.

## Inputs

- One insured exposure schedule frozen before policy inception; total dollars must
  match coverage terms.
- One annual price-only growth and CHPI growth scenario per row. Hybrid additionally
  requires `eligible_loss_usd` per row. Repeated historical annual rolling windows
  are dependent; do not treat them as independent observations.
- Explicit probability for every scenario, summing to 1. These are **assumed**
  probabilities; the engine never estimates probabilities from Tynbil automatically.
- Expense ratio, commission, target margin, fixed underwriting expense, capital
  quantile proxy, annual cost of capital, optional quota-share cession and separately
  input reinsurer premium, and optional minimum annual premium.

## Gross-to-net technical indication

Let `L_s` be the index-parametric or hybrid scenario amount, `p_s` scenario
probability, `q` the supplied capital quantile, and `c` the assumed quota share.

- Gross scenario loss expectation: `EL_g = sum(p_s * L_s)`.
- Retained expected loss: `EL_r = (1-c) * EL_g`.
- Retained capital proxy: `K = max(0, (1-c)*weighted_quantile_q(L_s) - EL_r)`.
- Capital charge: `k*K`.
- Indicated premium before minimum:
  `(EL_r + k*K + quoted_reinsurance_premium + fixed_expense) /
   (1 - variable_expenses - commission - target_margin)`.
- Apply a specified minimum premium floor, if any.

This is **only a transparent technical illustration**, not an actuarial estimate.
Empirical tail quantiles with short scenario sets are unstable and should not
be used for pricing or risk capital decisions. Reinsurance recoverability,
basis-risk tail, renewals, aggregation, portfolio diversification, stochastic
volatility, and data/revision contingencies are outside the model.

## Run

```bash
python -m unittest discover -s healthcare_indices/chpi/tests -v
python -m healthcare_indices.chpi.pricing \
  healthcare_indices/chpi/examples/synthetic_exposure.json \
  healthcare_indices/chpi/examples/synthetic_terms.json \
  healthcare_indices/chpi/examples/synthetic_growth_history.csv \
  healthcare_indices/chpi/examples/synthetic_pricing.json \
  --mode parametric --output /tmp/chpi_pricing.json
```

Run again with `--mode indemnity_hybrid` to evaluate the distinct indemnity
cap. Use `price_sensitivity` for attachment/exhaustion comparisons.

## Outstanding gates

- Verified Tynbil 24+ month matched-rate history and rate-type eligibility.
- Independently reviewed CHPI index history and source-fixing governance.
- Insured price-only exposure data and basis risk; agreed indemnity
  reconciliation definitions for hybrid mode.
- Representative scenario probability/tail calibration by credentialed
  actuaries; claims inflation, correlations, data gaps, and settlement stress.
- Reinsurance cost/terms, insurer capital requirements, expenses, commissions,
  legal/regulatory review and carrier signoff.
- No model output should be presented to partners as a binding or actuarially
  priced insurance offering.
