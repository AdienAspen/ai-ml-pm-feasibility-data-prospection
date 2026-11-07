import unittest

from study_methods.profile_scope import Node, consensus_profile, effective_profile, enabled_codes


class ProfileScopeTest(unittest.TestCase):
    def test_nearest_valid_ancestor_and_missing_profile(self):
        nodes = {
            "asset": Node("asset", None, "valid"),
            "child": Node("child", "asset", None),
            "leaf": Node("leaf", "child", "invalid"),
        }
        self.assertEqual(effective_profile("leaf", nodes, {"valid"}), ("valid", 2))
        self.assertEqual(effective_profile("leaf", nodes, set()), (None, 3))

    def test_group_to_code_expansion(self):
        associations = [("profile", "B", "group-a")]
        catalog = [("B", "group-a", "code-1"), ("B", "group-a", "code-2")]
        self.assertEqual(
            enabled_codes("profile", "B", associations, catalog),
            {("group-a", "code-1"), ("group-a", "code-2")},
        )

    def test_profile_consensus_without_node_consensus(self):
        self.assertEqual(consensus_profile(["profile", "profile"]), "profile")
        self.assertIsNone(consensus_profile(["profile", "other"]))


if __name__ == "__main__":
    unittest.main()
