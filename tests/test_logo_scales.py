import unittest

import numpy as np

from zebramotif.plot_logo import (
    information_content_weights,
    log_odds_weights,
    plot_logo,
)


class LogoScaleTests(unittest.TestCase):
    def setUp(self):
        self.ppm = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.5, 0.0, 0.5, 0.0],
                [0.25, 0.25, 0.25, 0.25],
                [0.75, 0.25, 0.0, 0.0],
            ]
        )

    def test_information_content_uses_probability_weighted_entropy(self):
        before = self.ppm.copy()
        with np.errstate(all="raise"):
            weights = information_content_weights(self.ppm)
        np.testing.assert_allclose(
            weights,
            [
                [2.0, 0.0, 0.0, 0.0],
                [0.5, 0.0, 0.5, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [0.8915414066556504, 0.2971804688852168, 0.0, 0.0],
            ],
        )
        np.testing.assert_array_equal(self.ppm, before)

    def test_log_odds_keeps_the_existing_enrichment_heights(self):
        np.testing.assert_allclose(
            log_odds_weights(self.ppm),
            [
                [2.0, 0.0, 0.0, 0.0],
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 0.0],
                [np.log2(3), 0.0, 0.0, 0.0],
            ],
        )

    def test_mixed_column_renders_one_bit_in_ic_and_two_in_log_odds(self):
        for scale, height, label, title in [
            ("ic", 1, "Information content", "Information content (bits)"),
            ("log_odds", 2, "Stacked log-odds", "Enrichment, log₂(p/0.25)"),
        ]:
            with self.subTest(scale=scale):
                figure = plot_logo(
                    self.ppm[1:2], scale=scale, show_reverse_complement=False
                )
                letters = [trace for trace in figure.data if trace.type == "scatter"]
                self.assertAlmostEqual(max(max(trace.y) for trace in letters), height)
                hover = next(trace for trace in figure.data if trace.type == "bar")
                self.assertIn(f"{label}: {height} bits", hover.text[0])
                self.assertIn("A: 0.5", hover.text[0])
                self.assertIn("G: 0.5", hover.text[0])
                self.assertEqual(figure.layout.yaxis.title.text, title)
                self.assertEqual(tuple(figure.layout.yaxis.range), (0, 2))

    def test_standalone_reverse_complement_uses_the_selected_scale(self):
        for scale, label in [
            ("ic", "Information content"),
            ("log_odds", "Stacked log-odds"),
        ]:
            with self.subTest(scale=scale):
                figure = plot_logo(self.ppm[:2], scale=scale)
                forward, reverse = [
                    trace for trace in figure.data if trace.type == "bar"
                ]
                self.assertTrue(forward.visible)
                self.assertFalse(reverse.visible)
                self.assertIn(f"{label}:", forward.text[0])
                self.assertIn(f"{label}:", reverse.text[0])
                self.assertIn("T: 0.5", reverse.text[0])
                self.assertIn("C: 0.5", reverse.text[0])

    def test_unknown_scale_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown logo scale"):
            plot_logo(self.ppm, scale="unknown")


if __name__ == "__main__":
    unittest.main()
