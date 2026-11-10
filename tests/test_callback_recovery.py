import unittest

import zebramotif.app as dashboard
from search_callbacks import result_payload


ZNF76 = "ENSDARG00000013279"
IRF2 = "ENSDARG00000040465"
DOMAIN = "ENSDARG00000010132_1"
MOTIF_OUTPUTS = [
    ("overview-content", "children"),
    ("overview-section", "style"),
    ("primary-section", "style"),
    ("primary-validation", "children"),
    ("primary-logo", "figure"),
    ("alternate-section", "style"),
    ("alternate-content", "children"),
]


class CallbackRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()

    def motif_payload(self, *, current=False):
        if current:
            return result_payload(IRF2)
        outputs = MOTIF_OUTPUTS
        key = ".." + "...".join(f"{name}.{prop}" for name, prop in outputs) + ".."
        return {
            "output": key,
            "outputs": [{"id": name, "property": prop} for name, prop in outputs],
            "inputs": [
                {"id": "tf-dropdown", "property": "value", "value": IRF2},
                {
                    "id": "motif-reverse-complement",
                    "property": "value",
                    "value": False,
                },
            ],
            "state": [],
            "changedPropIds": ["tf-dropdown.value"],
        }

    def post(self, payload, referrer="http://localhost:8568/search"):
        return self.client.post(
            "/_dash-update-component", json=payload, headers={"Referer": referrer}
        )

    def assert_reload(self, response, target):
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["response"], {})
        self.assertEqual(result["sideUpdate"]["url"], {"refresh": True, "href": target})

    def test_open_tab_with_old_motif_outputs_reloads_and_retains_dropdown_selection(
        self,
    ):
        payload = self.motif_payload()
        self.assertNotIn(payload["output"], dashboard.app.callback_map)
        self.assert_reload(self.post(payload), f"/search?tf={IRF2}")

    def test_old_input_property_is_detected_even_if_callback_output_is_unchanged(self):
        payload = self.motif_payload(current=True)
        payload["inputs"][1]["property"] = "data"
        self.assertIn(payload["output"], dashboard.app.callback_map)
        self.assert_reload(self.post(payload), f"/search?tf={IRF2}")

    def test_tab_without_logo_scale_input_reloads_and_retains_selection(self):
        payload = self.motif_payload(current=True)
        payload["inputs"] = [
            field for field in payload["inputs"] if field["id"] != "motif-logo-scale"
        ]
        self.assert_reload(self.post(payload), f"/search?tf={IRF2}")

    def test_tab_with_removed_plddt_toggle_reloads_and_retains_selection(self):
        payload = self.motif_payload(current=True)
        payload["inputs"].append(
            {"id": "plddt-toggle", "property": "value", "value": ["on"]}
        )
        self.assert_reload(self.post(payload), f"/search?tf={IRF2}")

    def test_tab_with_independent_motif_callback_reloads_and_retains_selection(self):
        outputs = MOTIF_OUTPUTS + [("search-empty-state", "style")]
        payload = self.motif_payload(current=True)
        payload["output"] = (
            ".." + "...".join(f"{name}.{prop}" for name, prop in outputs) + ".."
        )
        payload["outputs"] = [{"id": name, "property": prop} for name, prop in outputs]
        payload["inputs"] = payload["inputs"][:3]
        self.assert_reload(self.post(payload), f"/search?tf={IRF2}")

    def test_initial_stale_callback_retains_the_tf_from_the_shared_url(self):
        payload = self.motif_payload()
        payload["inputs"][0]["value"] = None
        payload["changedPropIds"] = []
        self.assert_reload(
            self.post(payload, referrer=f"http://localhost:8568/search?tf={DOMAIN}"),
            f"/search?tf={DOMAIN}",
        )

    def test_old_url_callback_recovers_the_clicked_example_instead_of_previous_tf(self):
        callback = next(
            key
            for key in dashboard.app.callback_map
            if "tf-dropdown.value" in key and "url.search" in key
        )
        payload = {
            "output": callback,
            "outputs": [
                {"id": name, "property": prop}
                for name, prop in [
                    ("tf-dropdown", "value"),
                    ("url", "search"),
                    ("search-link-state", "data"),
                    ("search-link-message", "children"),
                ]
            ],
            "inputs": [
                {"id": "tf-dropdown", "property": "value", "value": ZNF76},
                {"id": "url", "property": "search", "value": f"?tf={DOMAIN}"},
            ],
            "state": [
                {"id": "url", "property": "pathname", "value": "/search"},
                {"id": "search-link-state", "property": "data", "value": True},
            ],
            "changedPropIds": ["url.search"],
        }
        self.assert_reload(self.post(payload), f"/search?tf={DOMAIN}")

    def test_current_callback_renders_motifs_without_requesting_a_reload(self):
        response = self.post(self.motif_payload(current=True))
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertNotIn("sideUpdate", result)
        self.assertEqual(result["response"]["primary-section"]["style"], {})
        self.assertEqual(len(result["response"]["alternate-content"]["children"]), 3)
        self.assertIn("ZM00000040465.1", response.get_data(as_text=True))

    def test_scale_change_renders_information_content_for_the_whole_group(self):
        payload = self.motif_payload(current=True)
        payload["inputs"][2]["value"] = "ic"
        payload["changedPropIds"] = ["motif-logo-scale.value"]
        response = self.post(payload)
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertNotIn("sideUpdate", result)
        figure = result["response"]["primary-logo"]["figure"]
        self.assertEqual(
            figure["layout"]["yaxis"]["title"]["text"], "Information content (bits)"
        )
        self.assertNotIn("Stacked log-odds", response.get_data(as_text=True))
        for card in result["response"]["alternate-content"]["children"]:
            figure = card["props"]["children"][-1]["props"]["children"][0]["props"][
                "figure"
            ]
            self.assertEqual(figure["layout"]["yaxis"]["title"]["text"], "IC (bits)")

    def test_recovery_stays_on_known_local_pages(self):
        self.assert_reload(
            self.post(self.motif_payload(), referrer="http://localhost:8568/methods"),
            "/methods",
        )
        self.assert_reload(
            self.post(self.motif_payload(), referrer="https://example.com//outside"),
            f"/search?tf={IRF2}",
        )


if __name__ == "__main__":
    unittest.main()
