import json
import os
import subprocess
import sys
import unittest

# Runs in a fresh interpreter because the setting is read when the app is imported.
PROBE = """
import json
from plotly.utils import PlotlyJSONEncoder
import zebramotif.app as dashboard
from zebramotif import data as catalog
from zebramotif.pages import search

client = dashboard.server.test_client()
motif_id = catalog.PRIMARY_MODES.iloc[0]["motif_id"]
dbid = catalog.PRIMARY_MODES.iloc[0]["DBID"]
version = catalog.DOWNLOADS.version
paths = [
    "/",
    "/search",
    "/methods",
    "/healthz",
    "/documents/CITATION.cff",
    "/downloads",
    f"/downloads/{version}/zebramotif_primary_modes.zip",
    f"/downloads/{version}/release_metadata.json",
    f"/motifs/{motif_id}.txt",
    f"/motifs/tf/{dbid}.meme",
]
print(json.dumps({
    "status": {path: client.get(path).status_code for path in paths},
    "pages": list(dashboard.PAGES),
    "callbacks": "\\n".join(dashboard.app.callback_map),
    "rendered": json.dumps(
        [dashboard.render_page(path, None)[0] for path in ["/", "/search", "/methods"]]
        + [
            dashboard.sidebar,
            search._primary_profile(catalog.PRIMARY_MODES.iloc[0]),
            search.update_result_header(dbid),
        ],
        cls=PlotlyJSONEncoder,
    ),
}))
"""


class DownloadsDisabledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            [sys.executable, "-c", PROBE],
            env={**os.environ, "ZEBRAMOTIF_DOWNLOADS": "off"},
            capture_output=True,
            text=True,
            check=True,
        )
        cls.probe = json.loads(result.stdout.strip().splitlines()[-1])

    def test_download_routes_return_404(self):
        for path, status in self.probe["status"].items():
            if path.startswith(("/downloads", "/motifs")):
                with self.subTest(path=path):
                    self.assertEqual(status, 404)

    def test_other_pages_and_documents_still_load(self):
        for path, status in self.probe["status"].items():
            if not path.startswith(("/downloads", "/motifs")):
                with self.subTest(path=path):
                    self.assertEqual(status, 200)

    def test_pages_render_without_download_links(self):
        self.assertNotIn('"/downloads"', self.probe["rendered"])
        self.assertNotIn("/motifs/", self.probe["rendered"])

    def test_downloads_page_and_callbacks_are_not_registered(self):
        self.assertNotIn("/downloads", self.probe["pages"])
        self.assertNotIn("dl-primary-zip", self.probe["callbacks"])


if __name__ == "__main__":
    unittest.main()
