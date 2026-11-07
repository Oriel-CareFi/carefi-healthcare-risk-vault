"""Deterministic tests; all data are synthetic, NOT payer observations."""
import unittest

from healthcare_indices.chpi.engine import calculate, validate


def row(vintage, price, provider="p1", category="professional", code="99213"):
    return {"vintage":vintage,"payer":"synthetic","network":"n1","provider_id":provider,
            "geography":"00000","billing_code_type":"CPT","billing_code":code,
            "billing_class":"professional","negotiated_type":"negotiated",
            "negotiated_rate":str(price),"category":category,"rate_unit":"per_service"}


class CHPITests(unittest.TestCase):
    def test_exact_growth(self):
        result = calculate([row("2026Q1",100),row("2026Q2",110)],
            "2026Q1","2026Q2",{"professional":1.0})
        self.assertTrue(result["eligible_for_research_index"])
        self.assertAlmostEqual(result["index_level"],110.0)

    def test_no_composition_bias_from_new_provider(self):
        result=calculate([row("a",100),row("b",110),row("b",10000,provider="new")],
                         "a","b",{"professional":1.0})
        self.assertAlmostEqual(result["index_level"],110.0)

    def test_missing_base_cell_blocks_publication(self):
        result=calculate([row("a",100,"p1"),row("a",100,"p2"),row("b",110,"p1")],
                         "a","b",{"professional":1.0}, minimum_coverage=.8)
        self.assertFalse(result["eligible_for_research_index"])
        self.assertIsNone(result["index_level"])

    def test_duplicate_conflict_is_not_averaged(self):
        result=calculate([row("a",100),row("a",150),row("b",110)],
                         "a","b",{"professional":1.0})
        self.assertEqual(result["conflicted_vintage_cell_groups"],1)
        self.assertIsNone(result["index_level"])

    def test_reject_percent_contracts(self):
        r=row("a",12)
        r["negotiated_type"]="percentage"
        clean,reasons=validate([r])
        self.assertEqual(len(clean),0)
        self.assertEqual(reasons["non_dollar_or_ambiguous_payment"],1)

    def test_missing_category_not_reweighted(self):
        result=calculate([row("a",100),row("b",110)],
                         "a","b",{"professional":0.5,"imaging":0.5})
        self.assertIsNone(result["index_level"])


if __name__ == "__main__":
    unittest.main()
