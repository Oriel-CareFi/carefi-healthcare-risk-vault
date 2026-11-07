"""CHPI pricing tests: only synthetic history, not actuarial observations."""
import unittest
from dataclasses import replace
from healthcare_indices.chpi.exposure import ExposureLine, ExposureSchedule
from healthcare_indices.chpi.hybrid import CoverageTerms, ValidationError
from healthcare_indices.chpi.pricing import PricingAssumptions, technical_pricing, price_sensitivity

def schedule():
    return ExposureSchedule("SYNTHETIC","POLICY","payer_cost_increase",
        "2027-01-01","2027-12-31","2026-12-15",(
            ExposureLine("1","TEST","outpatient","N1","12000000","CHPI-US"),
            ExposureLine("2","TEST","professional","N1","8000000","CHPI-US")))
def terms():
    return CoverageTerms("POLICY","CHPI-US",5,10,"20000000","1000000")
def history():
    return [
        {"period":"A","index_growth_pct":2,"insured_price_only_growth_pct":3,"eligible_loss_usd":"0"},
        {"period":"B","index_growth_pct":8,"insured_price_only_growth_pct":10,"eligible_loss_usd":"800000"},
        {"period":"C","index_growth_pct":7,"insured_price_only_growth_pct":4,"eligible_loss_usd":"0"},
        {"period":"D","index_growth_pct":4,"insured_price_only_growth_pct":9,"eligible_loss_usd":"400000"}
    ]
def assumptions(**kw):
    p=dict(expense_ratio=.12, commission_ratio=.04, target_margin_ratio=.08,
        fixed_expense_usd="10000", capital_quantile=.95,
        annual_capital_cost_rate=.10, reinsurance_cession_ratio=0,
        reinsurance_premium_usd="0")
    p.update(kw)
    return PricingAssumptions(**p)

class PricingTests(unittest.TestCase):
    def test_expected_loss_and_technical_premium(self):
        x=technical_pricing(schedule(),terms(),history(),[.25]*4, assumptions())
        self.assertEqual(x["expected_gross_loss_usd"],"250000.00")
        # Quantile 600k; capital proxy 350k; charge 35k;
        # (250k+35k+10k)/(1-.12-.04-.08) = 388157.8947
        self.assertAlmostEqual(float(x["premium_usd"]),295000/.76, places=2)
        self.assertFalse(x["is_bindable_quote"])

    def test_premium_nonzero_without_events_if_fixed_cost(self):
        h=[{"period":"A","index_growth_pct":1,"insured_price_only_growth_pct":1},
           {"period":"B","index_growth_pct":2,"insured_price_only_growth_pct":2}]
        x=technical_pricing(schedule(),terms(),h,[.5,.5],assumptions())
        self.assertEqual(x["expected_gross_loss_usd"],"0.00")
        self.assertGreater(float(x["premium_usd"]),0)

    def test_probabilities_must_sum_one(self):
        with self.assertRaises(ValidationError):
            technical_pricing(schedule(),terms(),history(),[.3]*4,assumptions())

    def test_negative_probabilities_rejected(self):
        with self.assertRaises(ValidationError):
            technical_pricing(schedule(),terms(),history(),[-.1,.5,.3,.3],assumptions())

    def test_expense_ratio_invalid(self):
        with self.assertRaises(ValidationError):
            assumptions(expense_ratio=.9).validate()

    def test_hybrid_respects_loss_cap(self):
        x=technical_pricing(schedule(),terms(),history(),[.25]*4,
                            assumptions(),mode="indemnity_hybrid")
        self.assertEqual(x["expected_gross_loss_usd"],"150000.00")

    def test_reinsurance_cession_and_premium(self):
        x=technical_pricing(schedule(),terms(),history(),[.25]*4,
                            assumptions(reinsurance_cession_ratio=.5,reinsurance_premium_usd="140000"))
        self.assertEqual(x["expected_retained_loss_usd"],"125000.00")
        self.assertEqual(x["reinsurance_premium_usd"],"140000.00")

    def test_minimum_premium(self):
        x=technical_pricing(schedule(),terms(),history(),[.25]*4,
                            assumptions(minimum_premium_usd="500000"))
        self.assertEqual(x["premium_usd"],"500000.00")

    def test_sensitivity(self):
        rows=price_sensitivity(schedule(),terms(),history(),[.25]*4,
                               assumptions(),[4,5,6],[8,10])
        self.assertEqual(len(rows),6)
        self.assertGreater(float(rows[0]["premium_usd"]),float(rows[-1]["premium_usd"]))

    def test_provenance_gated(self):
        with self.assertRaises(ValidationError):
            technical_pricing(schedule(),terms(),history(),[.25]*4,
                              assumptions(),provenance="APPROVED_QUOTE")

if __name__=="__main__":
    unittest.main()
