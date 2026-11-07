"""Hybrid cover tests on SYNTHETIC index and insured-loss values."""
import unittest
from healthcare_indices.chpi.hybrid import (
    CoverageTerms, IndexFixing, ValidationError, evaluate, scenario_grid,
    basis_risk_report, index_growth_pct
)


def fixing(level, date, state="RESEARCH", index="CHPI-US", methodology="CHPI-RESEARCH-0.1.0"):
    return IndexFixing(index, level, date, "SYNTHETIC", methodology,
                       "SYNTHETIC-HASH", state, "reviewer" if state=="FINAL" else "")


def terms(**kwargs):
    data = dict(coverage_id="TEST-001",reference_index="CHPI-US",
        attachment_pct=5,exhaustion_pct=10,scheduled_exposure_usd="20000000",
        policy_limit_usd="1000000",retained_share_pct=0)
    data.update(kwargs)
    return CoverageTerms(**data)


class HybridTests(unittest.TestCase):
    def test_below_attachment(self):
        r=evaluate(terms(), fixing(100,"2026-12-31"),fixing(104,"2027-12-31"))
        self.assertFalse(r["triggered"])
        self.assertEqual(r["index_implied_ceiling_usd"],"0.00")

    def test_trigger_and_cap(self):
        r=evaluate(terms(), fixing(100,"2026-12-31"),fixing(108,"2027-12-31"))
        self.assertEqual(r["index_implied_ceiling_usd"],"600000.00")
        r=evaluate(terms(), fixing(100,"2026-12-31"),fixing(114,"2027-12-31"))
        self.assertEqual(r["index_implied_ceiling_usd"],"1000000.00")

    def test_loss_cap(self):
        r=evaluate(terms(),fixing(100,"2026-12-31"),
                    fixing(108,"2027-12-31"),"220000")
        self.assertEqual(r["index_implied_ceiling_usd"],"220000.00")
        self.assertFalse(r["claim_payable"])

    def test_retained_share(self):
        r=evaluate(terms(retained_share_pct=25),fixing(100,"2026-12-31"),
                   fixing(108,"2027-12-31"))
        self.assertEqual(r["index_implied_ceiling_usd"],"450000.00")

    def test_reference_mismatch(self):
        with self.assertRaises(ValidationError):
            evaluate(terms(),fixing(100,"2026-12-31"),
                     fixing(108,"2027-12-31",index="CHPI-OTHER"))

    def test_methodology_break_blocks(self):
        with self.assertRaises(ValidationError):
            index_growth_pct(fixing(100,"2026-12-31"),
                             fixing(108,"2027-12-31", methodology="NEW"))

    def test_settlement_is_disabled_even_with_final_marks(self):
        with self.assertRaises(ValidationError):
            evaluate(terms(),fixing(100,"2026-12-31","FINAL"),
                     fixing(108,"2027-12-31","FINAL"),settlement_mode=True)

    def test_nonfinal_cannot_settle(self):
        with self.assertRaises(ValidationError):
            index_growth_pct(fixing(100,"2026-12-31"),
                             fixing(108,"2027-12-31"), require_final=True)

    def test_bad_coverage_terms(self):
        with self.assertRaises(ValidationError):
            terms(attachment_pct=10,exhaustion_pct=5).validate()
        with self.assertRaises(ValidationError):
            terms(policy_limit_usd="-1").validate()

    def test_basis_risk(self):
        r=basis_risk_report([2,4,8],[3,3,10])
        self.assertEqual(r["observation_count"],3)
        self.assertAlmostEqual(r["mean_absolute_basis_pp"],4/3)

    def test_scenario_grid(self):
        r=scenario_grid(terms(),fixing(100,"2026-12-31"),[102,106,109])
        self.assertEqual(len(r),3)
        self.assertTrue(all(not x["claim_payable"] for x in r))


if __name__ == "__main__":
    unittest.main()
