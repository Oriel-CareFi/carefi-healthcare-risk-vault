"""Real published TiC examples, transcribed from Tynbil's public documentation.

Source: https://github.com/tynbil/transparency-in-coverage (Highmark PA July 2023)
CC BY-NC-SA attribution. Published price records are real but this is *not* a
complete normalized feed: issuer/network and provider identity are not provided
for all rows, so these examples MUST NOT form a CHPI level or matched time series.
"""
import unittest
from healthcare_indices.chpi.engine import validate, calculate

SOURCE = "https://github.com/tynbil/transparency-in-coverage"


def observed(rate, modifiers, service):
    return {
        "vintage":"2023-07", "payer":"Highmark Inc.", "network":"NOT_RESOLVED",
        "provider_id":"NOT_RESOLVED", "geography":"NOT_RESOLVED",
        "billing_code_type":"CPT", "billing_code":"99214",
        "billing_class":"professional", "negotiated_type":"derived",
        "negotiated_rate":str(rate), "category":"professional",
        "modifier":modifiers, "service_code":service, "rate_unit":"per_service"
    }


class TynbilPublishedExamples(unittest.TestCase):
    def test_published_real_values_do_not_pass_unverified_derived_policy(self):
        rows = [
            observed(100.39,"25|95","10|11"),
            observed(123.09,"","11"),
            observed(103.27,"","11|20")
        ]
        clean, excluded = validate(rows)
        self.assertEqual(len(clean),0)
        self.assertEqual(excluded["non_dollar_or_ambiguous_payment"],3)

    def test_no_annual_change_may_be_inferred_from_one_vintage(self):
        rows=[observed(100.39,"25|95","10|11"),
              observed(123.09,"","11"),
              observed(103.27,"","11|20")]
        result=calculate(rows,"2023-07","2023-08",{"professional":1.0})
        self.assertIsNone(result["index_level"])
        self.assertFalse(result["eligible_for_research_index"])


if __name__=="__main__":
    unittest.main()
