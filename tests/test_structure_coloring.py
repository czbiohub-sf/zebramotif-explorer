import itertools
import unittest

from zebramotif import data as catalog
from zebramotif import structure_viewer

IRF2 = "ENSDARG00000040465"


def residues(component):
    return {
        residue["number"]
        for target in component["targets"]
        for chain in target["chains"]
        for residue in chain["residues"]
    }


class StructureColoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        primary = catalog.PRIMARY_MODES.loc[catalog.PRIMARY_MODES.DBID.eq(IRF2)]
        cls.path = primary.iloc[0]["structure_path"]

    def test_plddt_uses_model_scores_and_preserves_dna_base_visuals(self):
        colored = structure_viewer.structure_data(self.path)
        self.assertEqual(colored["data"], structure_viewer._read_cif(self.path))
        self.assertIn("_atom_site.B_iso_or_equiv", colored["data"])
        self.assertEqual(colored["preset"], {"kind": "empty"})
        components = {item["label"]: item for item in colored["component"]}
        protein = components["Protein"]
        self.assertEqual(
            protein["representation"],
            [{"type": "cartoon", "color": "plddt-confidence"}],
        )
        dna = components["DNA"]
        self.assertEqual(
            {chain["auth_name"] for t in dna["targets"] for chain in t["chains"]},
            {"B", "C"},
        )
        representation = dna["representation"][0]
        self.assertEqual(representation["color"], "polymer-id")
        self.assertIn("nucleotide-ring", representation["typeParams"]["visuals"])
        self.assertIn("nucleotide-atomic-bond", representation["typeParams"]["visuals"])

    def test_domain_filter_and_contacts_cover_only_the_visible_protein_once(self):
        protein = set(
            structure_viewer._chain_residues(self.path)[structure_viewer.PROTEIN_CHAIN]
        )
        domains = catalog.DBD_BY_DBID[IRF2]
        contacts = catalog.CONTACTS_BY_DBID[IRF2]
        for dbd_on, contacts_on in itertools.product([False, True], repeat=2):
            with self.subTest(dbd=dbd_on, contacts=contacts_on):
                visible = (
                    {r for r in protein if any(a <= r <= b for a, b, _ in domains)}
                    if dbd_on
                    else protein
                )
                data = structure_viewer.structure_data(
                    self.path,
                    dbd=domains if dbd_on else None,
                    contacts=contacts if contacts_on else None,
                )
                seen = set()
                for component in data["component"]:
                    if component["label"] == "DNA":
                        continue
                    selected = residues(component)
                    self.assertTrue(seen.isdisjoint(selected))
                    seen.update(selected)
                    representation = component["representation"][0]
                    for residue in selected:
                        if contacts_on and residue in contacts:
                            self.assertEqual(
                                representation["colorParams"]["value"],
                                structure_viewer.CONTACT_COLORS[contacts[residue]],
                            )
                        elif contacts_on:
                            self.assertEqual(representation["color"], "uniform")
                            self.assertEqual(
                                representation["colorParams"]["value"],
                                structure_viewer.NON_CONTACT_COLOR,
                            )
                        else:
                            self.assertEqual(
                                representation["color"], "plddt-confidence"
                            )
                self.assertEqual(seen, visible)
                self.assertTrue(any(c["label"] == "DNA" for c in data["component"]))

    def test_empty_contact_selection_still_greys_out_the_visible_domain(self):
        data = structure_viewer.structure_data(
            self.path, dbd=catalog.DBD_BY_DBID[IRF2], contacts={}
        )
        for component in data["component"]:
            if component["label"] != "DNA":
                self.assertEqual(
                    component["representation"],
                    [
                        {
                            "type": "cartoon",
                            "color": "uniform",
                            "colorParams": {
                                "value": structure_viewer.NON_CONTACT_COLOR
                            },
                        }
                    ],
                )

    def test_plddt_handles_unavailable_structures(self):
        for path in [None, float("nan"), "structures/missing.cif.gz"]:
            with self.subTest(path=path):
                self.assertIsNone(structure_viewer.structure_data(path))


if __name__ == "__main__":
    unittest.main()
