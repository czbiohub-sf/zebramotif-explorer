import unittest
from concurrent.futures import ThreadPoolExecutor

from dash import html

import zebramotif.app as dashboard


# Capture the available scripts at import, before any test requests the index.
SCRIPT_PATHS = tuple(
    f"/_dash-component-suites/{library}/{path}"
    for library, paths in dashboard.app.registered_paths.items()
    for path in paths
    if path.endswith(".js")
    and (
        library == "dash_bootstrap_components"
        or (library == "dash" and "react-dom@" in path)
    )
)


class AssetStartupTests(unittest.TestCase):
    def test_workflow_images_are_available(self):
        page, _ = dashboard.render_page("/methods", "/")
        pending = [page]
        images = []
        while pending:
            component = pending.pop()
            if (
                isinstance(component, html.Img)
                and "methods-workflow-graphic"
                in (getattr(component, "className", "") or "").split()
            ):
                images.append(component)
            children = getattr(component, "children", None)
            if children is not None:
                pending.extend(
                    children if isinstance(children, (list, tuple)) else [children]
                )

        self.assertEqual(len(images), 4)
        with dashboard.server.test_client() as client:
            for image in images:
                with self.subTest(path=image.src), client.get(image.src) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.content_type.startswith("image/"))

    def test_parallel_script_requests_work_without_an_initial_index_request(self):
        self.assertGreaterEqual(len(SCRIPT_PATHS), 2)

        def fetch(path):
            with dashboard.server.test_client() as client:
                response = client.get(path)
                return response.status_code, response.content_type

        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(fetch, SCRIPT_PATHS * 2))
        for status, content_type in responses:
            self.assertEqual(status, 200)
            self.assertIn("javascript", content_type)


if __name__ == "__main__":
    unittest.main()
