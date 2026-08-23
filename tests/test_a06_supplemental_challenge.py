import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from evaluation2.a06_supplemental_profiles import PROFILES
from evaluation2.run_prompt_injection_poisoned_row import (
    build_attack_prompt,
    build_poisoned_document,
    build_target_panel,
    load_xlsx_multilevel,
)
from security.prompt_injection_guard import detect_prompt_injection_text


class A06SupplementalChallengeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = load_xlsx_multilevel(ROOT / "data/SiSWiss_Testdaten.xlsx")

    def test_stable_supplemental_mapping_is_shard_independent(self):
        identifiers = [f"R-{index:03d}" for index in range(1, 8)]
        panel = build_target_panel(
            self.documents, identifiers, stable_poison_ids=True
        )
        self.assertEqual(
            [target.poison_product_id for target in panel],
            [f"P-9{index:02d}" for index in range(1, 8)],
        )
        for target in panel:
            isolated = build_target_panel(
                self.documents, [target.rezeptur_id], stable_poison_ids=True
            )[0]
            self.assertEqual(asdict(target), asdict(isolated))

    def test_legacy_mapping_remains_backward_compatible(self):
        isolated = build_target_panel(self.documents, ["R-006"])[0]
        self.assertEqual(isolated.poison_product_id, "P-901")

    def test_frozen_user_prompts_omit_attack_labels_and_canaries(self):
        target = build_target_panel(
            self.documents, ["R-006"], stable_poison_ids=True
        )[0]
        for profile_id in PROFILES:
            prompt = build_attack_prompt(target, challenge_profile=profile_id)
            normalized = prompt.casefold()
            self.assertNotIn("prompt injection", normalized)
            self.assertNotIn("poisoned row", normalized)
            self.assertNotIn("attack6", normalized)
            self.assertNotIn(target.canary.casefold(), normalized)

    def test_adversarial_and_benign_documents_are_separated(self):
        target = build_target_panel(
            self.documents, ["R-007"], stable_poison_ids=True
        )[0]
        for profile_id, profile in PROFILES.items():
            document = build_poisoned_document(target, challenge_profile=profile_id)
            blob = json.dumps(document, ensure_ascii=False)
            metadata_blob = " ".join(str(value) for value in document["metadata"].values())
            matches = detect_prompt_injection_text(document["text"] + " " + metadata_blob)
            if profile.classification.startswith("adversarial"):
                self.assertIn(target.canary, blob)
                self.assertTrue(matches)
                self.assertEqual(document["metadata"]["rezeptur_id"], target.rezeptur_id)
            else:
                self.assertNotIn(target.canary, blob)
                self.assertFalse(matches)
                self.assertNotIn("rezeptur_id", document["metadata"])
                self.assertNotIn(target.rezeptur_id, document["text"])


if __name__ == "__main__":
    unittest.main()
