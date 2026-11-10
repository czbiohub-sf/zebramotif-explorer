import gzip
import json
import unittest
from xml.etree import ElementTree

from plotly.utils import PlotlyJSONEncoder

import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif.pages import home


class HomePerformanceTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()

    def test_home_uses_static_logos_without_mounting_plotly(self):
        page, _ = dashboard.render_page("/", None)
        content = json.dumps(page, cls=PlotlyJSONEncoder)
        self.assertNotIn('"type": "Graph"', content)
        self.assertIn("home-irf2-logo.svg", content)
        self.assertIn("home-irf2-logo-narrow.svg", content)
        self.assertIn('"id": "home-tf-dropdown"', content)
        for value, label in home.HOME_STATS:
            self.assertIn(value, content)
            self.assertIn(label, content)

    def test_both_svg_sizes_show_the_current_home_example_in_information_content(self):
        primary = catalog.PRIMARY_MODES.loc[
            catalog.PRIMARY_MODES.DBID.eq(home.HOME_EXAMPLE_DBID)
        ].iloc[0]
        for filename in ["home-irf2-logo.svg", "home-irf2-logo-narrow.svg"]:
            with self.subTest(filename=filename):
                with self.client.get(f"/assets/{filename}") as response:
                    self.assertEqual(response.status_code, 200)
                    svg = ElementTree.fromstring(response.get_data())
                self.assertEqual(svg.attrib["data-motif-id"], primary.motif_id)
                self.assertEqual(
                    svg.attrib["data-dataset-version"],
                    catalog.RELEASE_METADATA["version"],
                )
                self.assertEqual(svg.attrib["data-logo-scale"], "ic")
                self.assertIn("Information content (bits)", " ".join(svg.itertext()))

    def test_large_viewer_script_is_compressed_and_still_contains_the_original_code(
        self,
    ):
        resource = next(
            path
            for path in dashboard.app.registered_paths["dash_molstar"]
            if path == "rcsb-molstar.js"
        )
        path = f"/_dash-component-suites/dash_molstar/{resource}"
        original = self.client.get(path)
        compressed = self.client.get(path, headers={"Accept-Encoding": "gzip"})
        self.assertEqual(compressed.status_code, 200)
        self.assertEqual(compressed.headers["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", compressed.headers["Vary"])
        self.assertLess(len(compressed.data), len(original.data) / 3)
        self.assertEqual(gzip.decompress(compressed.data), original.data)

    def test_page_data_is_compressed_without_changing_the_json(self):
        original = self.client.get("/_dash-layout")
        compressed = self.client.get(
            "/_dash-layout", headers={"Accept-Encoding": "gzip"}
        )
        self.assertEqual(compressed.headers["Content-Encoding"], "gzip")
        self.assertEqual(
            json.loads(gzip.decompress(compressed.data)), original.get_json()
        )


if __name__ == "__main__":
    unittest.main()
