"""Research replay tests using only synthetic fixtures."""
import unittest
from dataclasses import replace
from healthcare_indices.chpi.exposure import ExposureLine, ExposureSchedule
from healthcare_indices.chpi.hybrid import CoverageTerms, ValidationError
from healthcare_indices.chpi.replay import replay,sensitivity

def schedule():
    return ExposureSchedule("FAKE-INSURED","PILOT-01","payer_cost_increase",
        "2027-01-01","2027-12-31","2026-12-15",(
            ExposureLine("1","BOSTON","outpatient","N1","12000000","CHPI-US"),
            ExposureLine("2","BOSTON","professional","N1","8000000","CHPI-US")
        ))
def terms():
    return CoverageTerms("PILOT-01","CHPI-US",5,10,"20000000","1000000")
def history():
    return [
      {"period":"2022","index_growth_pct":2,"insured_price_only_growth_pct":3,"eligible_loss_usd":"0"},
      {"period":"2023","index_growth_pct":8,"insured_price_only_growth_pct":10,"eligible_loss_usd":"800000"},
      {"period":"2024","index_growth_pct":7,"insured_price_only_growth_pct":4,"eligible_loss_usd":"0"},
      {"period":"2025","index_growth_pct":4,"insured_price_only_growth_pct":9,"eligible_loss_usd":"400000"}
    ]

class ReplayTests(unittest.TestCase):
    def test_freeze_before_cover(self):
        bad=replace(schedule(),frozen_at="2027-01-01")
        with self.assertRaises(ValidationError):bad.validate()
    def test_reproducible_digest_order_independent(self):
        a=schedule()
        b=replace(a,lines=tuple(reversed(a.lines)))
        self.assertEqual(a.digest(),b.digest())
    def test_reference_weights(self):
        self.assertEqual(schedule().reference_weight_map(),{"CHPI-US":1.0})
    def test_exposure_must_equal_coverage(self):
        with self.assertRaises(ValidationError):
            replay(schedule(),replace(terms(),scheduled_exposure_usd="21000000"),history())
    def test_parametric_miss_and_overpay_flags(self):
        result=replay(schedule(),terms(),history())
        self.assertEqual(result["observation_count"],4)
        self.assertEqual(result["missed_adverse_trigger_count"],1)
        self.assertEqual(result["trigger_without_adverse_count"],1)
        self.assertEqual(result["periods"][1]["model_ceiling_usd"],600000.0)
        self.assertTrue(all(not v["claim_payable"] for v in result["periods"]))
    def test_hybrid_loss_reconciliation(self):
        result=replay(schedule(),terms(),history(),mode="indemnity_hybrid")
        self.assertEqual(result["periods"][1]["model_ceiling_usd"],600000.0)
        self.assertEqual(result["periods"][2]["model_ceiling_usd"],0.0)
    def test_hybrid_requires_loss_for_every_period(self):
        h=history();del h[0]["eligible_loss_usd"]
        with self.assertRaises(ValidationError):
            replay(schedule(),terms(),h,mode="indemnity_hybrid")
    def test_no_duplicate_period(self):
        with self.assertRaises(ValidationError):
            replay(schedule(),terms(),history()[:1]*2)
    def test_negative_growth_extreme_rejected(self):
        h=history();h[0]["index_growth_pct"]=-100
        with self.assertRaises(ValidationError):
            replay(schedule(),terms(),h)
    def test_sensitivity_grid(self):
        r=sensitivity(schedule(),terms(),history(),[4,5,6],[8,10])
        self.assertEqual(len(r),6)
        self.assertTrue(all(x["mean_index_ceiling_usd"]>=0 for x in r))

if __name__=="__main__":
    unittest.main()
