# CHPI reimbursement-risk product architecture — v0.2 (research)
**Status:** Design and nonbinding simulation; not an insurance form, quote, or settlement authorization.

## Decisions carried forward
- First product is the **Commercial Healthcare Price Index (CHPI)**, a fixed-basket, exposure-relevant negotiated reimbursement-price index. It is not paid claims inflation, total cost of care, utilization, or a provider cost-containment guarantee.
- **Tynbil** supplies history and a normalized current feed. **Oriel** owns governed eligibility, fixed-weight index calculation, source version control, index fixing and revision policy. **CareFi** originates risks, builds exposure schedules and basis-risk/underwriting models. A **licensed insurer/reinsurer** issues and funds coverage and handles regulated claims functions.
- Insured interests are directional: **payer/risk bearer** faces adverse negotiated reimbursement-price increases; **provider** faces adverse reimbursement-price underperformance or revenue pressure. A provider product needs a distinct loss-direction formula; do not use the payer inflation formula unchanged.
- Prefer an insurer-issued index-based / potentially surplus-lines product for this reimbursement exposure. An **index-triggered indemnity hybrid** is an alternative to explore with capacity partners. **CLIP belongs primarily to separate contractual performance guarantees** (e.g. pharmacy/maternity), not the default CHPI policy.

## Two mutually distinct coverage modes

### A. Index-parametric reimbursement-price corridor
Insured: plan, delegated-risk payer or eligible self-insured arrangement demonstrating financial exposure to contracted commercial unit prices.

Reference: independently approved CHPI index for agreed service mix, region, and measurement period.

Trigger: CHPI annual return g exceeds agreed attachment K. Scheduled exposed reimbursement amount E is established prior to risk period. Payout indicator = E × max(0, min(g,U)-K)/100 × (1-retained_share), capped by policy aggregate limit L.

**Trigger and payout do not require claim-by-claim reconciliation** if policy/regulatory structure permits; insured interest and exposure must nevertheless be documented before binding. Exclude claims utilization, severity/case mix and benefit-design drift from represented insured risk. No double recovery against overlapping coverages.

### B. Index-triggered indemnity hybrid
Same objective CHPI trigger. Payout cap is additionally limited to **verified, qualifying adverse reimbursement-price loss**, defined with advance exclusions and an independently verifiable reconciliation methodology. The qualifying-loss calculation must isolate the contracted **price** component of changes in insured expenses from utilization, mix, severity, enrollment and benefit changes. Result = min(index formula amount, verified eligible loss, policy limit). Carrier/TPA resolves claims and disputes.

### Optional, separate provider-side lane
Protects **reimbursement shortfall** or reimbursement growth below an agreed benchmark/cost index. Requires its own insured-interest schedule, negative-direction trigger, exposure design, and separate actuarial tests. It is not a simple switch on the payer-side formula.

## Index/reference controls
1. Methodology version, declared basket, weights, source vintage manifest/hash and payer/network/provider-code matching rules.
2. Explicit eligible/conditional/excluded negotiated-rate types. Treat derived-rate dollar quotes only with unit/documentation verification and sensitivity comparisons.
3. Fixed calendar; first-print vs corrected print convention; minimum matched coverage per active constituent category; missed/missing source and revision fallback.
4. Independently approved final fixing and locked, append-only ledger before any real claim can reference the index.
5. Data license explicitly permits publication, derived analytics, insurance-reference use, third-party audit, and settlement licensing.

## Insured exposure schedule (collected independently of Tynbil)
- Insured entity, payer/provider role and legally relevant exposure, policy term.
- Commercial reimbursement amount at risk E by CBSA, provider category/site of care, contracted network, and medical service basket.
- Measurement base period and exposure schedule frozen before attachment. Document utilization used **only** to weight exposure, not to represent CHPI as a utilization index.
- Retained attachment, exhaustion, coinsurance, limit, eligible exclusions, other recoveries, and risk aggregation.
- Independent evidence to assess basis risk. Insured claims may be used privately for underwriting and hybrid reconciliation; they do **not** change independently published CHPI fixings.

## Basis-risk and actuarial validation
- Tynbil matched panel: 60 research baskets, 3–5 payers, approximately 5 geographies, >=24 months targeted; no row-count expenditure weights.
- Out-of-sample matched price movements, category coverage, concentration, renewal clustering, repricing frequency and composition bias.
- Compare commercial reference to each insured's measured **price-only** expense movement. Report under-/over-compensation, false triggers, and insured adverse movements without trigger.
- Calibrate attachment K and exhaustion U, expected loss, tail scenarios, catastrophe/correlation, limit adequacy, capacity, reinsurance, collateral, and premium using observed history; no invented loss rates.
- Screen insured-interest, state and surplus-lines/admitted insurance form treatment with insurer/counsel, plus any derivatives/parametric concerns, before binding.

## Implementation boundaries
- Existing `healthcare_indices/chpi/engine.py`: **research index** from normalized feed; no live Tynbil connection or approved national weights.
- Existing `healthcare_indices/chpi/hybrid.py`: **payer-side scenario model only**. `settlement_mode=True` intentionally rejects every request; the output is an index-implied ceiling, not a payable claim.
- A future product-specific adapter should consume **final approved** index values only and remain separate from the index calculation agent.
- Do not wire CHPI into the existing vault's tokenization, Kalshi order handling, CLIP, or automated claims workflows by default.

## Build order
1. Feed schema + source quality and historical cohort diagnostics.
2. Economic basket/weight governance; quarterly/annual return backtesting.
3. Separate parametric versus indemnity-hybrid policy prototypes and exposure schedules.
4. Historical payout and basis-risk replay; sensitivity around rate eligibility, renewal concentration and insured price-only growth.
5. Carrier/reinsurer/counsel review; official independent fixing governance.
6. Pilot with a single payer/risk-bearing insured and defined region/service exposure.
