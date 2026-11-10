import unittest
from urllib.parse import urlparse

from zebramotif import data as catalog
from zebramotif.pages import search
from zebramotif.utils import base_gene_dbid


def components(value):
    if isinstance(value, (list, tuple)):
        for child in value:
            yield from components(child)
    elif hasattr(value, "children"):
        yield value
        yield from components(value.children)


def is_ensembl_link(component):
    host = urlparse(getattr(component, "href", None) or "").hostname or ""
    return host == "ensembl.org" or host.endswith(".ensembl.org")


class GeneLinkTests(unittest.TestCase):
    def test_domain_headers_link_and_label_the_parent_ensembl_gene(self):
        domains = catalog.TF2REP.loc[catalog.TF2REP["sequence_type"].eq("domain")]
        self.assertGreater(len(domains), 0)
        for _, selected in domains.iterrows():
            dbid = selected["DBID"]
            with self.subTest(dbid=dbid):
                header = search._tf_identity(selected, dbid)
                ensembl_links = [
                    component
                    for component in components(header)
                    if is_ensembl_link(component)
                ]
                self.assertEqual(len(ensembl_links), 1)
                link = ensembl_links[0]
                parent_gene = dbid.rsplit("_", 1)[0]
                self.assertEqual(link.children, parent_gene)
                self.assertEqual(
                    link.href,
                    "https://useast.ensembl.org/Danio_rerio/Gene/Summary?"
                    f"db=core;g={parent_gene}",
                )
                self.assertIn(dbid, catalog.TF2REP_BY_DBID.index)
                self.assertNotIn(dbid, catalog.ZFIN_BY_DBID)

    def test_plain_gene_header_retains_its_ensembl_id(self):
        dbid = "ENSDARG00000013279"
        selected = catalog.TF2REP_BY_DBID.loc[dbid]
        header = search._tf_identity(selected, dbid)
        link = next(
            component for component in components(header) if is_ensembl_link(component)
        )
        self.assertEqual(link.children, dbid)
        self.assertTrue(link.href.endswith(f"g={dbid}"))

    def test_non_numeric_suffix_is_preserved(self):
        self.assertEqual(
            base_gene_dbid("ENSDARG00000010132_domain"),
            "ENSDARG00000010132_domain",
        )
        self.assertEqual(
            base_gene_dbid("ENSDARG00000010132_1_extra"),
            "ENSDARG00000010132_1_extra",
        )


if __name__ == "__main__":
    unittest.main()
