import unittest
from unittest.mock import patch

import dash_bootstrap_components as dbc
import pandas as pd
from search_callbacks import result_payload

import zebramotif.app as dashboard
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


def metric_row(median, low, high, n=47):
    return {"p50": median, "p10": low, "p90": high, "n": n}


class ConfidenceDisplayTests(unittest.TestCase):
    def test_primary_support_shows_band_and_counts_with_tooltip_details(self):
        primary = catalog.PRIMARY_MODES.iloc[0].copy()
        primary["n_members"] = 7
        primary["num_specs"] = 47
        primary["support_band"] = "Medium"
        profile = search._primary_profile(primary)
        text = text_content(profile)
        self.assertIn("Support Medium 7/47 (15%)", text)
        self.assertNotIn("7 predictions", text)
        badge = search._metric_badge(primary, "support")
        tooltip = badge.children[1]
        self.assertIn("7 of 47 predictions", tooltip.children)
        self.assertIn("14.9%", tooltip.children)

    def test_score_bands_at_boundaries(self):
        for score, expected in [
            (49.9, "Very low"),
            (50, "Low"),
            (70, "High"),
            (90, "Very high"),
        ]:
            with self.subTest(metric="dom_pLDDT", score=score):
                self.assertEqual(
                    search._confidence_level("dom_pLDDT", score)[0], expected
                )
        for score, expected in [
            (0.599, "Low"),
            (0.6, "Uncertain"),
            (0.8, "Uncertain"),
            (0.801, "High"),
        ]:
            with self.subTest(metric="ipTM", score=score):
                self.assertEqual(search._confidence_level("ipTM", score)[0], expected)

    def test_zero_domain_sentinel_is_unavailable(self):
        metrics = {
            "dom_pLDDT": metric_row(0, 0, 0),
            "ipTM": metric_row(0.92, 0.9, 0.94),
        }
        with patch.dict(catalog.CONFIDENCE_BY_DBID, {"test": metrics}):
            text = text_content(search._confidence_summary("test", "test_tf"))
        self.assertIn("Unavailable", text)
        self.assertIn("No domain confidence estimate was computed", text)
        self.assertIn("Protein–DNA interface High", text)
        self.assertNotIn("Very low", text)

    def test_interface_variation_is_not_hidden_by_median(self):
        metrics = {
            "dom_pLDDT": metric_row(92, 91, 93),
            "ipTM": metric_row(0.7, 0.1, 0.9),
        }
        with patch.dict(catalog.CONFIDENCE_BY_DBID, {"test": metrics}):
            text = text_content(search._confidence_summary("test", "test_tf"))
        self.assertIn("Protein–DNA interface Uncertain", text)
        self.assertIn("varies from low to high", text)
        self.assertIn("Middle 80%: 0.1–0.9", text)

    def test_smaller_subset_uses_actual_prediction_count(self):
        metrics = {
            "dom_pLDDT": metric_row(92, 91, 93, n=25),
            "ipTM": metric_row(0.92, 0.9, 0.94, n=25),
        }
        with patch.dict(catalog.CONFIDENCE_BY_DBID, {"test": metrics}):
            text = text_content(search._confidence_summary("test", "test_tf"))
        self.assertIn("25 predictions", text)
        self.assertNotIn("47 predictions", text)

    def test_small_boundary_crossing_does_not_add_variation_note(self):
        metrics = {
            "dom_pLDDT": metric_row(89.7, 89.5, 90.05),
            "ipTM": metric_row(0.801, 0.799, 0.803),
        }
        with patch.dict(catalog.CONFIDENCE_BY_DBID, {"test": metrics}):
            text = text_content(search._confidence_summary("test", "test_tf"))
        self.assertIn("DNA-binding domain", text)
        self.assertIn("Protein–DNA interface", text)
        self.assertIn("Middle 80%", text)
        self.assertNotIn("varies from", text)

    def test_missing_summary_is_explicit(self):
        with patch.dict(catalog.CONFIDENCE_BY_DBID, {}, clear=True):
            text = text_content(search._confidence_summary("test", "test_tf"))
        self.assertEqual(text, "A confidence summary is not available for test_tf.")

    def test_missing_median_is_unavailable(self):
        for value in (None, float("nan")):
            with self.subTest(value=value):
                component = search._confidence_metric(
                    "ipTM", "Protein–DNA interface", metric_row(value, 0.1, 0.9)
                )
                self.assertIn("Unavailable", text_content(component))

    def test_uses_top_ranked_subset(self):
        query = catalog.TF2REP.query("resolution == 'self'").iloc[0]
        rep = query["Rep_DBID"]
        expected = catalog._CONFIDENCE.query(
            "DBID == @rep and subset == 'top47' and metric == 'ipTM'"
        ).iloc[0]
        row = catalog.CONFIDENCE_BY_DBID[rep]["ipTM"]
        self.assertEqual(row["p50"], expected["p50"])
        self.assertEqual(row["p10"], expected["p10"])
        self.assertEqual(row["p90"], expected["p90"])

    def test_clustered_query_uses_representative_confidence(self):
        query = catalog.TF2REP.query("resolution == 'cluster'").iloc[0]
        rep = query["Rep_DBID"]
        primary = catalog.PRIMARY_MODES.query("DBID == @rep").iloc[0]
        result = search.update_confidence(query["DBID"])
        self.assertEqual(result["confidence_section_style"], {})
        expected = search._confidence_summary(rep, primary["TF_Name"])
        self.assertEqual(
            text_content(result["confidence_content"]), text_content(expected)
        )

    def test_clearing_or_unresolved_query_hides_previous_summary(self):
        selected = pd.DataFrame({"Rep_DBID": [None]}, index=["unresolved"])
        with patch.object(catalog, "TF2REP_BY_DBID", selected):
            for query in (None, "unresolved"):
                with self.subTest(query=query):
                    self.assertEqual(
                        search.update_confidence(query),
                        {
                            "confidence_section_style": {"display": "none"},
                            "confidence_content": None,
                        },
                    )

    def test_dash_callback_serializes_confidence_content(self):
        query = catalog.TF2REP.query("resolution == 'self'").iloc[0]["DBID"]
        client = dashboard.server.test_client()
        for value in (query, None):
            with self.subTest(query=value):
                response = client.post(
                    "/_dash-update-component",
                    json=result_payload(value),
                )
                self.assertEqual(response.status_code, 200)
                content = response.get_json()["response"]["confidence-content"][
                    "children"
                ]
                self.assertEqual(content is None, value is None)


if __name__ == "__main__":
    unittest.main()
