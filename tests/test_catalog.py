import unittest
from unittest.mock import patch

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif import structure_viewer
from zebramotif.pages import search


def text_content(value):
    if isinstance(value, (list, tuple)):
        return " ".join(text_content(child) for child in value)
    if hasattr(value, "children"):
        return text_content(value.children)
    return "" if value is None else str(value)


class CatalogTests(unittest.TestCase):
    def test_exported_predictions_resolve_to_their_own_dbid(self):
        for primary in catalog.PRIMARY_MODES.itertuples():
            with self.subTest(dbid=primary.DBID):
                selected = catalog.TF2REP_BY_DBID.loc[primary.DBID]
                self.assertEqual(selected["Rep_DBID"], primary.DBID)
                self.assertTrue(selected["is_representative"])
                self.assertEqual(selected["resolution"], "self")

    def test_znf76_search_uses_its_own_structure_and_confidence(self):
        dbid = "ENSDARG00000013279"
        with patch.object(structure_viewer, "structure_data", return_value={}) as load:
            result = search.update_structure(dbid, [], [])
        self.assertEqual(result["structure_section_style"], {})
        load.assert_called_once_with(
            "structures/ZM00000013279.1.cif.gz", dbd=None, contacts=None
        )
        with patch.object(search, "_confidence_summary", return_value=None) as summary:
            self.assertEqual(
                search.update_confidence(dbid),
                {"confidence_section_style": {}, "confidence_content": None},
            )
        summary.assert_called_once_with(dbid, "znf76")

    def test_homepage_counts_genes_without_counting_their_domain_entries(self):
        self.assertEqual(catalog.N_TFS, 2543)
        self.assertEqual(len(catalog.TF2REP), 2551)
        self.assertEqual(catalog.TF2REP["sequence_type"].eq("domain").sum(), 7)
        self.assertEqual(catalog.TF2REP["in_original_catalog"].sum(), 2543)
        domains = catalog.TF2REP.loc[catalog.TF2REP["sequence_type"].eq("domain")]
        self.assertFalse(domains["in_original_catalog"].any())

    def test_zfin_links_come_from_the_consolidated_lookup(self):
        mapped = catalog.TF2REP.dropna(subset=["zfin_id"])
        self.assertEqual(len(mapped), 2079)
        self.assertEqual(
            catalog.ZFIN_BY_DBID,
            mapped.set_index("DBID")["zfin_id"].to_dict(),
        )
        self.assertTrue(
            catalog.TF2REP.loc[catalog.TF2REP["sequence_type"].eq("domain"), "zfin_id"]
            .isna()
            .all()
        )

    def test_pogza_has_searchable_predictions_and_annotations(self):
        dbid = "ENSDARG00000054778"
        selected = catalog.TF2REP_BY_DBID.loc[dbid]
        self.assertEqual(selected["Rep_DBID"], dbid)
        self.assertEqual(selected["resolution"], "self")
        self.assertEqual(selected["sequence_type"], "full_length")
        self.assertTrue(selected["is_representative"])
        self.assertFalse(selected["in_original_catalog"])
        self.assertIn(dbid, catalog.MODES_BY_DBID)
        self.assertIn(dbid, catalog.DBD_BY_DBID)
        self.assertIn(dbid, catalog.CONTACTS_BY_DBID)
        self.assertIn(dbid, catalog.CONFIDENCE_BY_DBID)
        self.assertIn(
            "pogza",
            text_content(search.update_result_header(dbid)["tf_result_identity"]),
        )
        response = dashboard.server.test_client().get("/motifs/ZM00000054778.1.txt")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"MOTIF ZM00000054778.1 pogza", response.data)

    def test_profiles_omit_sequence_type(self):
        for kind in ("full_length", "domain"):
            with self.subTest(sequence_type=kind):
                primary = catalog.PRIMARY_MODES[
                    catalog.PRIMARY_MODES["sequence_type"].eq(kind)
                ].iloc[0]
                profile = search._primary_profile(primary)
                self.assertNotIn("Sequence type", text_content(profile))


if __name__ == "__main__":
    unittest.main()
