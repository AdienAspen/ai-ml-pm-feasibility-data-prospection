import unittest

from study_methods.crosswalk import CatalogEntry, candidate_codes, score_candidate


class CrosswalkTest(unittest.TestCase):
    def test_returns_candidate_list_without_claiming_ground_truth(self):
        entries = [
            CatalogEntry("group-a", "code-1", "pump seal"),
            CatalogEntry("group-a", "code-2", "valve stem"),
        ]
        found = candidate_codes("pump seal replacement", entries)
        self.assertEqual([(item.group, item.code) for item in found], [("group-a", "code-1")])
        self.assertEqual(found[0].evidence_type, "expert_inference")
        self.assertEqual(score_candidate("", "pump seal"), 0)


if __name__ == "__main__":
    unittest.main()
