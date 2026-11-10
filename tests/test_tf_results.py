import json
import re
import unittest

import numpy as np
from search_callbacks import result_payload

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif.utils import as_pwm


def text_content(component):
    if isinstance(component, dict):
        return text_content(component.get("props", {}).get("children"))
    if isinstance(component, (list, tuple)):
        return "".join(text_content(child) for child in component)
    return "" if component is None else str(component)


class TFResultTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()
        self.cluster = catalog.TF2REP.query("TF_Name == 'nfatc4'").iloc[0]
        self.redirect = catalog.TF2REP.query("resolution == 'symbol_redirect'").iloc[0]
        self.unresolved = catalog.TF2REP.query("resolution == 'unresolved'").iloc[0]

    def header(self, dbid):
        response = self.client.post(
            "/_dash-update-component",
            json=result_payload(dbid),
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["response"]

    def assert_download(self, dbid):
        selected = catalog.TF2REP_BY_DBID.loc[dbid]
        expected = catalog.ALL_MODES.loc[
            catalog.ALL_MODES["DBID"].eq(selected["Rep_DBID"])
        ]
        response = self.client.get(f"/motifs/tf/{dbid}.meme")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")
        self.assertEqual(
            response.headers["Content-Disposition"],
            f'attachment; filename="zebramotif_{dbid}.meme"',
        )
        document = response.get_data(as_text=True)
        self.assertEqual(document.count("MEME version 4"), 1)
        self.assertIn("ALPHABET= ACGT", document)
        blocks = re.split(r"(?m)^MOTIF ", document)[1:]
        self.assertEqual(len(blocks), len(expected))
        self.assertEqual(expected.iloc[0]["tier"], "primary")
        for block, (_, mode) in zip(blocks, expected.iterrows()):
            lines = block.splitlines()
            motif_id, names = lines[0].split()
            self.assertEqual(motif_id, mode["motif_id"])
            self.assertEqual(names, catalog.ALT_NAMES[motif_id])
            index = next(
                i
                for i, line in enumerate(lines)
                if line.startswith("letter-probability matrix:")
            )
            fields = dict(re.findall(r"(\w+)=\s*(\S+)", lines[index]))
            self.assertEqual(int(fields["alength"]), 4)
            self.assertEqual(int(fields["w"]), mode["pwm_length"])
            self.assertEqual(int(fields["nsites"]), mode["n_members"])
            matrix = np.array(
                [
                    [float(value) for value in line.split()]
                    for line in lines[index + 1 :]
                    if line.strip()
                ]
            )
            np.testing.assert_allclose(matrix, as_pwm(mode["pwm"]), atol=5e-7, rtol=0)
        return len(blocks)

    def test_downloads_include_all_modes_for_genes_domains_and_representatives(self):
        for dbid in [
            "ENSDARG00000013279",  # znf76: primary plus three alternates
            "ENSDARG00000010132_1",  # separately modeled dacha domain
            self.cluster["DBID"],
            self.redirect["DBID"],
        ]:
            with self.subTest(dbid=dbid):
                count = self.assert_download(dbid)
                if dbid == "ENSDARG00000013279":
                    self.assertEqual(count, 4)

    def test_primary_only_result_downloads_a_valid_single_motif_document(self):
        counts = catalog.ALL_MODES.groupby("DBID").size()
        dbid = counts[counts.eq(1)].index[0]
        self.assertEqual(self.assert_download(dbid), 1)

    def test_unknown_and_unresolved_downloads_do_not_return_empty_documents(self):
        for dbid in ["unknown", "ENSDARG00000010132_99", self.unresolved["DBID"]]:
            with self.subTest(dbid=dbid):
                response = self.client.get(f"/motifs/tf/{dbid}.meme")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Content-Disposition", response.headers)

    def test_header_keeps_selected_identity_and_identifies_the_modeled_representative(
        self,
    ):
        for selected in [
            catalog.TF2REP.query("DBID == 'ENSDARG00000013279'").iloc[0],
            self.cluster,
            self.redirect,
        ]:
            dbid = selected["DBID"]
            with self.subTest(dbid=dbid):
                result = self.header(dbid)
                identity = json.dumps(result["tf-result-identity"]["children"])
                self.assertIn(selected["TF_Name"], identity)
                self.assertIn(selected["Family"], identity)
                self.assertIn(dbid, identity)
                self.assertEqual(result["tf-result-panel"]["style"], {})
                self.assertFalse(result["copy-tf-link"]["disabled"])
                self.assertEqual(
                    result["download-tf-motifs"],
                    {
                        "href": f"/motifs/tf/{dbid}.meme",
                        "disabled": False,
                    },
                )
                if selected["Rep_DBID"] != dbid:
                    note = result["tf-result-note"]["children"]
                    primary = catalog.modes_for_query(dbid).iloc[0]
                    self.assertEqual(note["props"]["role"], "note")
                    self.assertIn(
                        "Selected TF",
                        text_content(result["tf-result-identity"]["children"]),
                    )
                    self.assertIn(
                        f"Showing predictions for {primary['TF_Name']}",
                        text_content(note),
                    )
                    self.assertIn(
                        f"You selected {selected['TF_Name']}", text_content(note)
                    )
                    self.assertIn(
                        f"Modeled entry: {selected['Rep_DBID']}", text_content(note)
                    )
                    self.assertIn(
                        "motifs, JASPAR comparisons, structure, and confidence",
                        text_content(note),
                    )
                    self.assertIn(
                        f"/search?tf={selected['Rep_DBID']}", json.dumps(note)
                    )
                else:
                    self.assertIsNone(result["tf-result-note"]["children"])

    def test_shared_result_explains_the_recorded_resolution_without_claiming_identical_symbols(
        self,
    ):
        for selected, label in [
            (self.cluster, "Sequence-cluster representative"),
            (self.redirect, "Gene-symbol redirect"),
        ]:
            with self.subTest(resolution=selected["resolution"]):
                result = self.header(selected["DBID"])
                note = text_content(result["tf-result-note"]["children"])
                self.assertIn(label, note)
                self.assertNotIn("sharing this gene symbol", note)
                self.assertNotIn("same gene symbol", note)

    def test_changing_from_a_shared_result_to_a_modeled_domain_clears_the_banner(self):
        self.header(self.cluster["DBID"])
        result = self.header("ENSDARG00000010132_1")
        self.assertIsNone(result["tf-result-note"]["children"])
        identity = text_content(result["tf-result-identity"]["children"])
        self.assertIn("dacha (domain 1)", identity)
        self.assertIn("ENSDARG00000010132_1", identity)
        self.assertNotIn("Selected TF", identity)

    def test_clearing_or_invalid_selection_removes_identity_and_disables_actions(self):
        for dbid in [None, "unknown"]:
            with self.subTest(dbid=dbid):
                result = self.header(dbid)
                self.assertEqual(
                    result["tf-result-panel"]["style"], {"display": "none"}
                )
                self.assertIsNone(result["tf-result-identity"]["children"])
                self.assertIsNone(result["tf-result-note"]["children"])
                self.assertTrue(result["copy-tf-link"]["disabled"])
                self.assertEqual(
                    result["download-tf-motifs"],
                    {
                        "href": None,
                        "disabled": True,
                    },
                )

    def test_unresolved_query_retains_identity_and_sharing_without_a_download(self):
        result = self.header(self.unresolved["DBID"])
        self.assertEqual(result["tf-result-panel"]["style"], {})
        self.assertIn(
            self.unresolved["TF_Name"],
            json.dumps(result["tf-result-identity"]["children"]),
        )
        self.assertFalse(result["copy-tf-link"]["disabled"])
        self.assertIsNone(result["tf-result-note"]["children"])
        self.assertEqual(result["download-tf-motifs"], {"href": None, "disabled": True})


if __name__ == "__main__":
    unittest.main()
