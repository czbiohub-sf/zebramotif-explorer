import unittest
from unittest.mock import patch

import pandas as pd
from search_callbacks import result_payload

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif import structure_viewer
from zebramotif.pages import search

NO_ANNOTATION = "ENSDARG00000028335"  # hmga1a
PLACED = "ENSDARG00000116327"  # arntl2


def text_content(component):
    if component is None:
        return ""
    if isinstance(component, (list, tuple)):
        return " ".join(filter(None, (text_content(child) for child in component)))
    if hasattr(component, "children"):
        return text_content(component.children)
    return str(component)


class DomainDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unplaced = catalog.PRIMARY_MODES.query("TF_Name == 'hopx'").iloc[0]["DBID"]

    def test_distinguishes_absent_annotations_from_unplaced_domains(self):
        self.assertEqual(
            catalog.DOMAIN_STATUS_BY_DBID[NO_ANNOTATION], "No domains annotated"
        )
        self.assertEqual(
            catalog.DOMAIN_STATUS_BY_DBID[self.unplaced],
            "No domains confidently placed with DNA",
        )
        self.assertIsNone(catalog.DOMAIN_STATUS_BY_DBID[PLACED])

    def test_highlights_come_from_the_current_flagged_annotations(self):
        for dbid, domains in catalog._DOMAINS.groupby("DBID"):
            with self.subTest(dbid=dbid):
                flagged = domains.loc[domains["DNA-Binding"]]
                highlights = catalog.DBD_BY_DBID.get(dbid, [])
                self.assertEqual(
                    highlights,
                    [
                        (int(r.start), int(r.end), r.description)
                        for r in flagged.itertuples()
                    ],
                )

    def test_current_annotations_override_stale_domain_confidence(self):
        metrics = {
            "dom_pLDDT": {"p50": 95, "p10": 93, "p90": 98, "n": 47},
            "ipTM": {"p50": 0.7, "p10": 0.65, "p90": 0.75, "n": 47},
        }
        for dbid, message in [
            (NO_ANNOTATION, "No domains annotated"),
            (self.unplaced, "No domains confidently placed with DNA"),
        ]:
            with (
                self.subTest(dbid=dbid),
                patch.dict(catalog.CONFIDENCE_BY_DBID, {dbid: metrics}),
            ):
                text = text_content(search._confidence_summary(dbid, "test_tf"))
                self.assertIn(message, text)
                self.assertIn("Unavailable", text)
                self.assertNotIn("95", text)
                self.assertNotIn("very high for the DNA-binding domain", text)

    def test_reason_is_shown_even_when_domain_confidence_row_is_missing(self):
        with patch.dict(
            catalog.CONFIDENCE_BY_DBID,
            {self.unplaced: {"ipTM": {"p50": 0.2, "p10": 0.1, "p90": 0.3, "n": 47}}},
        ):
            text = text_content(search._confidence_summary(self.unplaced, "hopx"))
        self.assertIn("No domains confidently placed with DNA", text)

    def test_structure_message_describes_representative_for_clustered_query(self):
        selected = pd.DataFrame({"Rep_DBID": [self.unplaced]}, index=["cluster_member"])
        with (
            patch.object(catalog, "TF2REP_BY_DBID", selected),
            patch.object(structure_viewer, "structure_data", return_value={}),
        ):
            result = search.update_structure("cluster_member", ["on"], [])
        self.assertEqual(result["dbd_toggle_row_style"]["display"], "none")
        self.assertEqual(
            result["domain_status"], "No domains confidently placed with DNA"
        )
        self.assertEqual(result["domain_status_style"], {})

    def test_clearing_or_unresolved_selection_clears_domain_message(self):
        selected = pd.DataFrame({"Rep_DBID": [None]}, index=["unresolved"])
        with patch.object(catalog, "TF2REP_BY_DBID", selected):
            for dbid in (None, "unresolved"):
                with self.subTest(dbid=dbid):
                    result = search.update_structure(dbid, [], [])
                    self.assertIsNone(result["domain_status"])
                    self.assertEqual(result["domain_status_style"], {"display": "none"})

    def test_missing_structure_clears_domain_message(self):
        with patch.object(structure_viewer, "structure_data", return_value=None):
            result = search.update_structure(NO_ANNOTATION, [], [])
        self.assertIsNone(result["domain_status"])
        self.assertEqual(result["domain_status_style"], {"display": "none"})

    def test_dash_callback_serializes_messages_and_clears_them_for_placed_domain(self):
        client = dashboard.server.test_client()
        with patch.object(structure_viewer, "structure_data", return_value={}):
            for dbid, expected in [
                (NO_ANNOTATION, "No domains annotated"),
                (self.unplaced, "No domains confidently placed with DNA"),
                (PLACED, None),
                (None, None),
            ]:
                with self.subTest(dbid=dbid):
                    response = client.post(
                        "/_dash-update-component",
                        json=result_payload(dbid, dbd=["on"]),
                    )
                    self.assertEqual(response.status_code, 200)
                    result = response.get_json()["response"]
                    self.assertEqual(result["domain-status"]["children"], expected)
                    self.assertEqual(
                        result["domain-status"]["style"],
                        {} if expected else {"display": "none"},
                    )
                    self.assertEqual(
                        result["dbd-toggle-row"]["style"].get("display") == "none",
                        dbid != PLACED,
                    )


if __name__ == "__main__":
    unittest.main()
