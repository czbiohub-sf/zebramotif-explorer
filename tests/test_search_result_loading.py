import json
import unittest
from unittest.mock import patch

from search_callbacks import result_payload

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif import structure_viewer
from zebramotif.pages import search

IRF2 = "ENSDARG00000040465"


class SearchResultLoadingTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()

    def render(self, payload):
        response = self.client.post("/_dash-update-component", json=payload)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertNotIn("sideUpdate", result)
        return result["response"]

    def assert_complete_result(self, result):
        self.assertEqual(result["tf-result-panel"]["style"], {})
        self.assertIn("irf2", json.dumps(result["tf-result-identity"]["children"]))
        self.assertEqual(result["primary-section"]["style"], {})
        self.assertTrue(result["primary-logo"]["figure"]["data"])
        self.assertEqual(len(result["alternate-content"]["children"]), 3)
        self.assertEqual(result["structure-section"]["style"], {})
        self.assertEqual(
            result["structure-content"]["children"]["type"], "MolstarViewer"
        )
        self.assertEqual(result["confidence-section"]["style"], {})
        self.assertIsNotNone(result["confidence-content"]["children"])
        self.assertEqual(result["search-empty-state"]["style"], {"display": "none"})
        self.assertEqual(result["search-result-selection"]["data"], IRF2)
        self.assertEqual(result["plddt-legend"]["style"], {})

    def test_selection_replaces_the_guide_with_all_matching_tiles_in_one_response(self):
        with patch.object(structure_viewer, "structure_data", return_value={}):
            self.assert_complete_result(self.render(result_payload(IRF2)))

    def test_initial_shared_link_also_returns_the_complete_result(self):
        with patch.object(structure_viewer, "structure_data", return_value={}):
            self.assert_complete_result(self.render(result_payload(IRF2, changed=None)))

    def test_clearing_or_invalid_selection_restores_guide_and_removes_every_tile(self):
        for dbid in [None, "unknown"]:
            with self.subTest(dbid=dbid):
                result = self.render(result_payload(dbid))
                self.assertEqual(result["search-empty-state"]["style"], {})
                for section in [
                    "tf-result-panel",
                    "primary-section",
                    "alternate-section",
                    "structure-section",
                    "confidence-section",
                ]:
                    self.assertEqual(result[section]["style"], {"display": "none"})
                self.assertIsNone(result["structure-content"]["children"])
                self.assertEqual(result["plddt-legend"]["style"], {"display": "none"})

    def test_unavailable_structure_does_not_block_the_other_tiles(self):
        with patch.object(structure_viewer, "structure_data", return_value=None):
            result = self.render(result_payload(IRF2))
        self.assertEqual(result["tf-result-panel"]["style"], {})
        self.assertEqual(result["primary-section"]["style"], {})
        self.assertEqual(result["confidence-section"]["style"], {})
        self.assertEqual(result["structure-section"]["style"], {"display": "none"})
        self.assertEqual(result["plddt-legend"]["style"], {"display": "none"})
        self.assertEqual(result["search-empty-state"]["style"], {"display": "none"})

    def test_unresolved_query_shows_its_identity_without_waiting_for_missing_motifs(
        self,
    ):
        dbid = catalog.TF2REP.query("resolution == 'unresolved'").iloc[0]["DBID"]
        result = self.render(result_payload(dbid))
        self.assertEqual(result["tf-result-panel"]["style"], {})
        self.assertIn("No predicted PPM", json.dumps(result["overview-content"]))
        self.assertEqual(result["primary-section"]["style"], {"display": "none"})
        self.assertEqual(result["structure-section"]["style"], {"display": "none"})
        self.assertEqual(result["search-empty-state"]["style"], {"display": "none"})

    def test_logo_switches_leave_the_viewer_camera_and_other_content_untouched(self):
        for control, options in [
            ("motif-logo-scale.value", {"scale": "log_odds"}),
            ("motif-reverse-complement.value", {"reverse": True}),
        ]:
            with (
                self.subTest(control=control),
                patch.object(
                    search,
                    "update_structure",
                    side_effect=AssertionError("Viewer rebuilt"),
                ),
                patch.object(
                    search,
                    "update_result_header",
                    side_effect=AssertionError("Header rebuilt"),
                ),
                patch.object(
                    search,
                    "update_confidence",
                    side_effect=AssertionError("Confidence rebuilt"),
                ),
            ):
                result = self.render(
                    result_payload(IRF2, changed=control, rendered_dbid=IRF2, **options)
                )
                self.assertIn("primary-logo", result)
                self.assertNotIn("structure-content", result)
                self.assertNotIn("tf-result-identity", result)
                self.assertNotIn("confidence-content", result)

    def test_contacts_view_replaces_the_confidence_key_in_both_domain_views(self):
        for dbd, contacts in [
            ([], []),
            (["on"], []),
            ([], ["on"]),
            (["on"], ["on"]),
        ]:
            with (
                self.subTest(dbd=bool(dbd), contacts=bool(contacts)),
                patch.object(structure_viewer, "structure_data", return_value={}),
            ):
                result = self.render(
                    result_payload(
                        IRF2,
                        dbd=dbd,
                        contacts=contacts,
                        changed="dbd-toggle.value",
                        rendered_dbid=IRF2,
                    )
                )
                legend = result["plddt-legend"]
                self.assertEqual(
                    legend["style"], {"display": "none"} if contacts else {}
                )
                if contacts:
                    self.assertIsNone(legend["children"])
                    self.assertIn(
                        "Non-contact residue",
                        json.dumps(result["contacts-legend"]["children"]),
                    )
                else:
                    self.assertIn("Very high (>90)", json.dumps(legend["children"]))

    def test_domain_only_filters_contacts_and_their_color_key(self):
        with (
            patch.dict(catalog.CONTACTS_BY_DBID, {IRF2: {2: "base", 10: "backbone"}}),
            patch.object(structure_viewer, "structure_data", return_value={}) as load,
        ):
            result = self.render(
                result_payload(
                    IRF2,
                    dbd=["on"],
                    contacts=["on"],
                    changed="dbd-toggle.value",
                    rendered_dbid=IRF2,
                )
            )
        self.assertEqual(load.call_args.kwargs["contacts"], {10: "backbone"})
        text = json.dumps(result["contacts-legend"]["children"])
        self.assertIn("Backbone contact", text)
        self.assertNotIn("Base contact", text)
        self.assertEqual(result["plddt-legend"]["style"], {"display": "none"})

    def test_contacts_view_stays_active_when_the_domain_has_no_contacts(self):
        with (
            patch.dict(catalog.CONTACTS_BY_DBID, {IRF2: {2: "base"}}),
            patch.object(structure_viewer, "structure_data", return_value={}) as load,
        ):
            result = self.render(
                result_payload(
                    IRF2,
                    dbd=["on"],
                    contacts=["on"],
                    changed="dbd-toggle.value",
                    rendered_dbid=IRF2,
                )
            )
        self.assertEqual(load.call_args.kwargs["contacts"], {})
        self.assertEqual(result["plddt-legend"]["style"], {"display": "none"})
        self.assertEqual(result["contacts-legend"]["style"]["display"], "flex")
        self.assertIn(
            "Non-contact residue", json.dumps(result["contacts-legend"]["children"])
        )

    def test_structure_switches_leave_the_motifs_and_identity_untouched(self):
        for control, options in [
            ("dbd-toggle.value", {"dbd": ["on"]}),
            ("contacts-toggle.value", {"contacts": ["on"]}),
        ]:
            with (
                self.subTest(control=control),
                patch.object(structure_viewer, "structure_data", return_value={}),
                patch.object(
                    search, "update_tf", side_effect=AssertionError("Motifs rebuilt")
                ),
                patch.object(
                    search,
                    "update_result_header",
                    side_effect=AssertionError("Header rebuilt"),
                ),
                patch.object(
                    search,
                    "update_confidence",
                    side_effect=AssertionError("Confidence rebuilt"),
                ),
            ):
                result = self.render(
                    result_payload(IRF2, changed=control, rendered_dbid=IRF2, **options)
                )
                self.assertIn("structure-content", result)
                self.assertNotIn("primary-logo", result)
                self.assertNotIn("tf-result-identity", result)
                self.assertNotIn("confidence-content", result)

    def test_selection_with_a_simultaneous_switch_change_still_updates_every_tile(self):
        payload = result_payload(IRF2, reverse=True)
        payload["changedPropIds"].append("motif-reverse-complement.value")
        with patch.object(structure_viewer, "structure_data", return_value={}):
            self.assert_complete_result(self.render(payload))

    def test_switch_during_pending_selection_still_returns_the_complete_new_result(
        self,
    ):
        for rendered_dbid in [None, "ENSDARG00000076763"]:
            for changed in [
                "motif-logo-scale.value",
                "dbd-toggle.value",
                "contacts-toggle.value",
            ]:
                with (
                    self.subTest(rendered_dbid=rendered_dbid, changed=changed),
                    patch.object(structure_viewer, "structure_data", return_value={}),
                ):
                    self.assert_complete_result(
                        self.render(
                            result_payload(
                                IRF2, changed=changed, rendered_dbid=rendered_dbid
                            )
                        )
                    )


if __name__ == "__main__":
    unittest.main()
