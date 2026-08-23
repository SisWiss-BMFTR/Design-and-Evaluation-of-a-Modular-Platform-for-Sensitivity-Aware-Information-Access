import sys
import unittest
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from security.output_leakage_verifier import verify_answer_against_restricted_fields


class OutputLeakageVerifierTests(unittest.TestCase):
    def setUp(self):
        self.restricted = [{
            "field_name": "formulation_percentage",
            "value": "15.55",
            "entity_id": "formulation:R-001",
        }]

    def verify(self, answer, allowed=()):
        return verify_answer_against_restricted_fields(answer, self.restricted, allowed)

    def test_matches_decimal_format_variants(self):
        for answer in ("15.55", "15,55", "15.55%", "15,55 %", "15.550"):
            with self.subTest(answer=answer):
                self.assertTrue(self.verify(answer).leakage_detected)

    def test_numeric_matching_observes_token_boundaries(self):
        for answer in ("115.55", "15.551", "215,55"):
            with self.subTest(answer=answer):
                self.assertFalse(self.verify(answer).leakage_detected)

    def test_unrelated_allowed_field_with_same_value_does_not_authorize_secret(self):
        allowed = [{
            "field_name": "public_test_score",
            "value": "15.55",
            "entity_id": "product:P-001",
        }]
        self.assertTrue(self.verify("The protected percentage is 15.55.", allowed).leakage_detected)

    def test_same_structured_field_in_allowed_inventory_is_not_blocked(self):
        self.assertFalse(self.verify("The percentage is 15.55.", self.restricted).leakage_detected)


if __name__ == "__main__":
    unittest.main()
