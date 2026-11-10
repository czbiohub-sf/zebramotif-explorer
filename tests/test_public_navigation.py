import json
import unittest

from plotly.utils import PlotlyJSONEncoder

import zebramotif.app as dashboard
from zebramotif import data as catalog


class PublicNavigationTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()

    def test_health_check_reports_loaded_application(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_unknown_page_returns_404_and_useful_navigation(self):
        response = self.client.get("/a-page-that-does-not-exist")
        self.assertEqual(response.status_code, 404)
        page, route = dashboard.render_page("/a-page-that-does-not-exist", "/")
        self.assertEqual(route, "/a-page-that-does-not-exist")
        content = json.dumps(page, cls=PlotlyJSONEncoder)
        self.assertIn("Page not found", content)
        self.assertIn('"href": "/search"', content)

    def test_framework_routes_and_known_pages_still_load(self):
        for path in [
            "/",
            "/search",
            "/downloads",
            "/methods",
            "/_dash-layout",
            "/_dash-dependencies",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_release_documents_are_available_without_exposing_other_files(self):
        with self.client.get("/documents/CITATION.cff") as citation:
            self.assertEqual(citation.status_code, 200)
            self.assertIn("cff-version:", citation.get_data(as_text=True))
        with self.client.get("/documents/release_metadata.json") as metadata:
            self.assertEqual(metadata.status_code, 200)
            self.assertEqual(
                json.loads(metadata.get_data())["version"],
                catalog.RELEASE_METADATA["version"],
            )
        with self.client.get("/documents/SCHEMA.md") as schema:
            self.assertEqual(schema.status_code, 200)
            self.assertIn("PPM database schema", schema.get_data(as_text=True))
        with self.client.get("/documents/PROVENANCE.json") as provenance:
            self.assertEqual(provenance.status_code, 200)
            self.assertEqual(provenance.get_json()["schema_version"], 2)
        for filename in ["tf_to_rep.parquet", "app.py", "missing.txt"]:
            with self.subTest(filename=filename):
                self.assertEqual(
                    self.client.get(f"/documents/{filename}").status_code, 404
                )


if __name__ == "__main__":
    unittest.main()
