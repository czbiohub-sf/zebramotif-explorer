import unittest
from unittest.mock import patch

import numpy as np

from zebramotif import data as catalog
from zebramotif.pages import search
from zebramotif.plot_logo import plot_logo
from zebramotif.utils import BASES, nucleotide_color_dict

DBID = "ENSDARG00000056438"  # her9


def ppm(sequence):
    return np.eye(4)[[BASES.index(base) for base in sequence]]


def figures(result):
    return [result["primary_logo"]] + [
        card.children[-1].children[-1].figure
        for card in result["alternate_content"] or []
    ]


class MotifAlignmentTests(unittest.TestCase):
    def setUp(self):
        # Include both overhang directions, unequal lengths, a reverse-complemented
        # alternate, and an unshifted alternate in the same comparison.
        self.modes = catalog.MODES_BY_DBID[DBID].copy(deep=True)
        for index, sequence, offset, rc in zip(
            self.modes.index,
            ["ACGTAC", "GATT", "GGTA", "TGC"],
            [None, -2, 4, 0],
            [None, True, False, False],
        ):
            self.modes.at[index, "pwm"] = ppm(sequence)
            self.modes.at[index, "pwm_length"] = len(sequence)
            self.modes.at[index, "offset_to_primary"] = offset
            self.modes.at[index, "rc_to_primary"] = rc
        self.addCleanup(patch.stopall)
        patch.dict(catalog.MODES_BY_DBID, {DBID: self.modes}).start()

    def assert_logo(self, figure, sequence, offset, position_range):
        self.assertEqual(tuple(figure.layout.xaxis.range), position_range)
        self.assertEqual(tuple(figure.layout.yaxis.range), (0, 2))
        self.assertEqual(len(figure.layout.updatemenus), 0)
        self.assertEqual(
            tuple(figure.layout.xaxis.ticktext),
            tuple(str(i + 1) for i in range(*position_range)),
        )
        hover = [trace for trace in figure.data if trace.type == "bar"]
        self.assertEqual(len(hover), 1)
        np.testing.assert_allclose(hover[0].x, np.arange(len(sequence)) + offset + 0.5)
        # Only actual motif columns have hover data; blank flanks are not bases.
        for i, base in enumerate(sequence):
            self.assertIn(f"<b>Position {offset + i + 1}</b>", hover[0].text[i])
            self.assertIn(f"{base}: 1", hover[0].text[i])

        # Check the drawn letters as well as the hover data.
        letters = [
            trace
            for trace in figure.data
            if trace.type == "scatter" and trace.fillcolor != "white"
        ]
        self.assertEqual(len(letters), len(sequence))
        for i, (base, trace) in enumerate(zip(sequence, letters)):
            self.assertEqual(trace.fillcolor, nucleotide_color_dict()[base])
            np.testing.assert_allclose(
                [min(trace.x), max(trace.x)], [offset + i + 0.08, offset + i + 0.92]
            )

    def test_alternates_use_the_primary_orientation_and_signed_offsets(self):
        result = search.update_tf(DBID)
        self.assertEqual(result["alternate_section_style"], {})
        for figure, sequence, offset in zip(
            figures(result), ["ACGTAC", "AATC", "GGTA", "TGC"], [0, -2, 4, 0]
        ):
            self.assert_logo(figure, sequence, offset, (-2, 8))

    def test_reverse_control_reflects_the_whole_aligned_group(self):
        for figure, sequence, offset in zip(
            figures(search.update_tf(DBID, reverse=True)),
            ["GTACGT", "GATT", "TACC", "GCA"],
            [0, 4, -2, 3],
        ):
            self.assert_logo(figure, sequence, offset, (-2, 8))

    def test_reversing_asymmetric_flanks_preserves_every_base(self):
        patch.dict(catalog.MODES_BY_DBID, {DBID: self.modes.iloc[:2]}).start()
        primary, alternate = figures(search.update_tf(DBID, reverse=True))
        self.assert_logo(primary, "GTACGT", 0, (0, 8))
        self.assert_logo(alternate, "GATT", 4, (0, 8))

    def test_primary_without_alternates_still_supports_both_orientations(self):
        patch.dict(catalog.MODES_BY_DBID, {DBID: self.modes.iloc[:1]}).start()
        for reverse, sequence in [(False, "ACGTAC"), (True, "GTACGT")]:
            with self.subTest(reverse=reverse):
                result = search.update_tf(DBID, reverse=reverse)
                self.assertEqual(result["alternate_section_style"], {"display": "none"})
                self.assertIsNone(result["alternate_content"])
                self.assert_logo(result["primary_logo"], sequence, 0, (0, 6))

    def test_display_does_not_modify_stored_or_downloaded_matrices(self):
        before = [np.array(value, copy=True) for value in self.modes.pwm]
        for scale in ["ic", "log_odds"]:
            for reverse in [False, True]:
                search.update_tf(DBID, reverse=reverse, scale=scale)
        for expected, actual in zip(before, self.modes.pwm):
            np.testing.assert_array_equal(actual, expected)

    def test_changing_scale_preserves_alignment_and_reverse_complement(self):
        for scale in ["ic", "log_odds"]:
            for reverse, sequences, offsets in [
                (False, ["ACGTAC", "AATC", "GGTA", "TGC"], [0, -2, 4, 0]),
                (True, ["GTACGT", "GATT", "TACC", "GCA"], [0, 4, -2, 3]),
            ]:
                with self.subTest(scale=scale, reverse=reverse):
                    for figure, sequence, offset in zip(
                        figures(search.update_tf(DBID, reverse=reverse, scale=scale)),
                        sequences,
                        offsets,
                    ):
                        self.assert_logo(figure, sequence, offset, (-2, 8))

    def test_clearing_a_selection_hides_the_group_in_either_orientation(self):
        for reverse in [False, True]:
            result = search.update_tf(None, reverse=reverse)
            self.assertEqual(result["primary_section_style"], {"display": "none"})
            self.assertEqual(result["primary_logo"], {})
            self.assertEqual(result["alternate_section_style"], {"display": "none"})


class StandaloneLogoTests(unittest.TestCase):
    def test_long_shared_windows_thin_tick_labels_without_dropping_bases(self):
        figure = plot_logo(
            ppm("ACGT" * 6), position_range=(-5, 24), show_reverse_complement=False
        )
        self.assertLessEqual(len(figure.layout.xaxis.tickvals), 16)
        self.assertIn("1", figure.layout.xaxis.ticktext)
        hover = next(trace for trace in figure.data if trace.type == "bar")
        np.testing.assert_allclose(hover.x, np.arange(24) + 0.5)

    def test_default_reverse_complement_toggle_is_preserved(self):
        figure = plot_logo(ppm("ACG"))
        forward, reverse = [trace for trace in figure.data if trace.type == "bar"]
        self.assertTrue(forward.visible)
        self.assertFalse(reverse.visible)
        np.testing.assert_allclose(forward.x, [0.5, 1.5, 2.5])
        np.testing.assert_allclose(reverse.x, [0.5, 1.5, 2.5])
        self.assertEqual(len(figure.layout.updatemenus), 1)
        button = figure.layout.updatemenus[0].buttons[0]
        self.assertEqual(len(button.args[0]["visible"]), len(figure.data))
        self.assertEqual(len(button.args2[0]["visible"]), len(figure.data))

    def test_standalone_toggle_reflects_occupied_columns_within_shared_window(self):
        figure = plot_logo(ppm("ACG"), position_offset=-2, position_range=(-3, 6))
        forward, reverse = [trace for trace in figure.data if trace.type == "bar"]
        np.testing.assert_allclose(forward.x, [-1.5, -0.5, 0.5])
        np.testing.assert_allclose(reverse.x, [2.5, 3.5, 4.5])
        self.assertIn("C: 1", reverse.text[0])


if __name__ == "__main__":
    unittest.main()
