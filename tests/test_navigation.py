import unittest

import zebramotif.app as dashboard


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()
        self.callback = next(
            key for key in dashboard.app.callback_map if "page-content.children" in key
        )

    def navigate(self, pathname, rendered_route=None):
        return self.client.post(
            "/_dash-update-component",
            json={
                "output": self.callback,
                "outputs": [
                    {"id": "page-content", "property": "children"},
                    {"id": "rendered-route", "property": "data"},
                ],
                "inputs": [{"id": "url", "property": "pathname", "value": pathname}],
                "state": [
                    {
                        "id": "rendered-route",
                        "property": "data",
                        "value": rendered_route,
                    }
                ],
                "changedPropIds": ["url.pathname"],
            },
        )

    def test_initial_routes_render(self):
        for pathname in ["/", "/search", "/downloads", "/methods"]:
            with self.subTest(pathname=pathname):
                response = self.navigate(pathname)
                self.assertEqual(response.status_code, 200)
                result = response.get_json()["response"]
                self.assertEqual(result["rendered-route"]["data"], pathname)
                self.assertIsNotNone(result["page-content"]["children"])

    def test_repeated_route_leaves_existing_controls_untouched(self):
        for pathname in ["/", "/search", "/downloads", "/methods"]:
            with self.subTest(pathname=pathname):
                response = self.navigate(pathname, pathname)
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response.get_data(), b"")

    def test_uninitialized_location_leaves_the_page_untouched(self):
        for rendered_route in [None, "/search"]:
            with self.subTest(rendered_route=rendered_route):
                response = self.navigate(None, rendered_route)
                self.assertEqual(response.status_code, 204)

    def test_navigation_back_to_home_still_renders(self):
        response = self.navigate("/", "/search")
        self.assertEqual(response.status_code, 200)
        self.assertIn("home-hero", response.get_data(as_text=True))
        self.assertIn("home-tf-dropdown", response.get_data(as_text=True))
        self.assertNotRegex(
            response.get_data(as_text=True), r'"id"\s*:\s*"tf-dropdown"'
        )


if __name__ == "__main__":
    unittest.main()
