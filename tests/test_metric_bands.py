import unittest

import dash_bootstrap_components as dbc
import pandas as pd

from zebramotif import data as catalog
from zebramotif.pages import search


def text_content(component):
    if component is None:
        return ""
    if isinstance(component, (list, tuple)):
        return " ".join(filter(None, (text_content(child) for child in component)))
    if isinstance(component, dbc.Tooltip):
        return ""
    if hasattr(component, "children"):
        return text_content(component.children)
    return str(component)


class MetricBandDisplayTests(unittest.TestCase):
    def setUp(self):
        self.row = pd.Series(
            {
                "motif_id": "ZM00000019516.1",
                "n_members": 8,
                "num_specs": 47,
                "support_band": "Medium",
                "hom_jaspar": "MA1564.2",
                "homer_sim": 0.8264,
                "homer_sim_band": "High",
                "p_value": 0.01831,
                "recovery": 0.6032,
                "recovery_band": "Medium",
                "relationship": "primary_refined",
                "corr_to_primary": 0.88,
            }
        )

    def test_numbers_are_visible_and_tooltips_keep_detailed_values(self):
        for metric, label, value, details in [
            ("support", "Medium", "8/47 (17%)", ["8 of 47 predictions", "17.0%"]),
            ("homer_sim", "High", "HOMER 0.83, p=0.018", ["0.826", "0.018"]),
            ("recovery", "Medium", "60%", ["0.603", "60.3%"]),
        ]:
            with self.subTest(metric=metric):
                badge = search._metric_badge(self.row, metric)
                self.assertEqual(text_content(badge), f"{label} {value}")
                target, tooltip = badge.children
                self.assertIsInstance(tooltip, dbc.Tooltip)
                self.assertEqual(tooltip.target, target.id)
                self.assertEqual(tooltip.id, f"{target.id}-tooltip")
                self.assertEqual(tooltip.trigger, "hover focus")
                for value in details:
                    self.assertIn(value, tooltip.children)
                self.assertNotIn("reference:", tooltip.children)
                props = target.to_plotly_json()["props"]
                self.assertEqual(props["tabIndex"], 0)
                self.assertIn(label, props["aria-label"])
                self.assertIn(tooltip.children, props["aria-label"])

    def test_tooltip_targets_are_unique_across_modes_and_metrics(self):
        targets = []
        for motif_id in ["ZM00000019516.1", "ZM00000019516.2"]:
            row = self.row.copy()
            row["motif_id"] = motif_id
            for metric in ["support", "homer_sim", "recovery"]:
                target, tooltip = search._metric_badge(row, metric).children
                self.assertEqual(tooltip.target, target.id)
                self.assertNotIn(".", target.id)
                targets.append(target.id)
        self.assertEqual(len(set(targets)), 6)

    def test_missing_reference_is_neutral(self):
        for metric in ["homer_sim", "recovery"]:
            row = self.row.copy()
            row[metric] = None
            row[f"{metric}_band"] = "No reference"
            badge = search._metric_badge(row, metric)
            self.assertEqual(text_content(badge), "No reference")
            target, tooltip = badge.children
            self.assertEqual(target.children[0].color, "secondary")
            self.assertIn("No reference motif comparison", tooltip.children)

    def test_alternates_display_their_own_metric_bands(self):
        text = text_content(search._mode_profile(self.row))
        self.assertIn("Support:  Medium 8/47 (17%)", text)
        self.assertIn("Motif similarity:  High HOMER 0.83, p=0.018", text)
        self.assertIn("IC recovery:  Medium 60%", text)

    def test_small_positive_values_are_preserved(self):
        for p, expected in [(0.00052, "0.00052"), (0.0000012, "1.2e-06")]:
            with self.subTest(p=p):
                row = self.row.copy()
                row["p_value"] = p
                badge = search._metric_badge(row, "homer_sim")
                self.assertIn(f"p={expected}", text_content(badge))
                self.assertIn(expected, badge.children[1].children)
        row = self.row.copy()
        row["recovery"] = 0.0001
        badge = search._metric_badge(row, "recovery")
        self.assertIn("0.01%", text_content(badge))
        self.assertIn("0.0001 (0.01%)", badge.children[1].children)

    def test_zero_and_missing_values_are_distinct(self):
        row = self.row.copy()
        row["recovery"] = 0
        self.assertEqual(
            text_content(search._metric_badge(row, "recovery")), "Medium 0%"
        )
        for missing in [None, float("nan")]:
            with self.subTest(missing=missing):
                row["p_value"] = missing
                text = text_content(search._metric_badge(row, "homer_sim"))
                self.assertIn("HOMER 0.83, p=—", text)
                self.assertNotIn("p=0", text)

    def test_exported_labels_are_loaded_for_every_mode(self):
        for column in ["support_band", "homer_sim_band", "recovery_band"]:
            self.assertIn(column, catalog.MODES.columns)
            self.assertFalse(catalog.MODES[column].isna().any())
        missing = catalog.MODES[catalog.MODES.homer_sim.isna()]
        self.assertTrue((missing.homer_sim_band == "No reference").all())
        self.assertTrue((missing.recovery_band == "No reference").all())


if __name__ == "__main__":
    unittest.main()
