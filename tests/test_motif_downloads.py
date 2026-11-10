import unittest
from pathlib import Path

import numpy as np

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif.pages import search
from zebramotif.utils import as_pwm


def components(value):
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from components(child)
    else:
        yield value
        if hasattr(value, "children"):
            yield from components(value.children)


class MotifTextTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()

    def assert_motif_document(self, mode):
        motif_id = mode["motif_id"]
        response = self.client.get(f"/motifs/{motif_id}.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/plain")
        self.assertEqual(
            response.headers["Content-Disposition"],
            f'inline; filename="{motif_id}.txt"',
        )
        text = response.get_data(as_text=True)
        self.assertTrue(text.startswith("MEME version 4\n"))
        self.assertIn("ALPHABET= ACGT", text)
        self.assertEqual(text.count("\nMOTIF "), 1)
        self.assertIn(f"MOTIF {motif_id} {catalog.ALT_NAMES[motif_id]}\n", text)
        lines = text.splitlines()
        header = next(
            i
            for i, line in enumerate(lines)
            if line.startswith("letter-probability matrix:")
        )
        self.assertIn(f"w= {mode['pwm_length']}", lines[header])
        self.assertIn(f"nsites= {mode['n_members']}", lines[header])
        matrix = np.loadtxt(lines[header + 1 :], ndmin=2)
        np.testing.assert_allclose(matrix, as_pwm(mode["pwm"]), atol=5e-7, rtol=0)
        return text

    def test_primary_matrix_is_a_complete_meme_document(self):
        self.assert_motif_document(catalog.PRIMARY_MODES.iloc[0])

    def test_domain_primary_matrix_is_available(self):
        primary = catalog.PRIMARY_MODES[
            catalog.PRIMARY_MODES["DBID"] == "ENSDARG00000054304_2"
        ].iloc[0]
        self.assert_motif_document(primary)

    def test_every_alternate_matrix_is_a_complete_meme_document(self):
        alternates = catalog.ALL_MODES[catalog.ALL_MODES["tier"] == "alternate"]
        self.assertGreater(len(alternates), 0)
        for _, alternate in alternates.iterrows():
            with self.subTest(motif_id=alternate["motif_id"]):
                self.assert_motif_document(alternate)

    def test_unknown_ids_return_not_found(self):
        for motif_id in ["missing", "ZM00000013279.99"]:
            with self.subTest(motif_id=motif_id):
                response = self.client.get(f"/motifs/{motif_id}.txt")
                self.assertEqual(response.status_code, 404)

    def test_clustered_tf_links_to_its_representative_primary(self):
        selected = catalog.TF2REP[catalog.TF2REP["resolution"] == "cluster"].iloc[0]
        primary = catalog.MODES_BY_DBID[selected["Rep_DBID"]]
        primary = primary[primary["tier"] == "primary"].iloc[0]
        profile = search._primary_profile(primary)
        links = [
            component
            for component in components(profile)
            if str(getattr(component, "href", "")).startswith("/motifs/")
        ]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].href, f"/motifs/{primary['motif_id']}.txt")
        self.assert_motif_document(primary)

    def test_znf76_search_exposes_its_primary_and_three_alternates(self):
        result = search.update_tf("ENSDARG00000013279")
        self.assertEqual(result["primary_section_style"], {})
        links = [
            component
            for component in components(result["primary_validation"])
            if str(getattr(component, "href", "")).startswith("/motifs/")
        ]
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].href, "/motifs/ZM00000013279.1.txt")
        self.assertEqual(result["alternate_section_style"], {})
        self.assertEqual(len(result["alternate_content"]), 3)
        alternate_links = [
            component
            for component in components(result["alternate_content"])
            if str(getattr(component, "href", "")).startswith("/motifs/")
        ]
        self.assertEqual(len(alternate_links), 3)
        self.assertEqual(
            {link.href for link in alternate_links},
            {f"/motifs/ZM00000013279.{rank}.txt" for rank in [2, 3, 4]},
        )
        for link in alternate_links:
            self.assertEqual(
                link.children, link.href.split("/")[-1].removesuffix(".txt")
            )
            self.assertEqual(link.title, "Open MEME motif file")
            alternate = catalog.MODES_BY_MOTIF_ID.loc[link.children]
            self.assert_motif_document(alternate)
        primary = catalog.PRIMARY_BY_MOTIF_ID.loc["ZM00000013279.1"]
        text = self.assert_motif_document(primary)
        self.assertIn("MOTIF ZM00000013279.1 znf76\n", text)

    def test_bundled_meme_names_match_collection_downloads(self):
        for filename, modes in [
            ("zebramotif_primary_modes.meme", catalog.PRIMARY_MODES),
            ("zebramotif_all_modes.meme", catalog.ALL_MODES),
        ]:
            with self.subTest(filename=filename):
                document = (Path(catalog.DATA_DIR) / filename).read_text()
                motifs = [
                    line.split(maxsplit=2)[1:]
                    for line in document.splitlines()
                    if line.startswith("MOTIF ")
                ]
                expected = {
                    motif_id: catalog.ALT_NAMES[motif_id]
                    for motif_id in modes["motif_id"]
                }
                self.assertEqual(len(motifs), len(expected))
                self.assertEqual(dict(motifs), expected)


if __name__ == "__main__":
    unittest.main()
