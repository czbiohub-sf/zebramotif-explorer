import unittest

import zebramotif.app as dashboard
from zebramotif.navigation import (
    format_tf_search,
    parse_tf_search,
    synchronize_tf_search,
)

ZNF76 = "ENSDARG00000013279"
DOMAIN = "ENSDARG00000010132_1"


class SearchQueryTests(unittest.TestCase):
    def test_shared_links_use_the_queried_id_including_domain_entries(self):
        for dbid in [ZNF76, DOMAIN]:
            with self.subTest(dbid=dbid):
                result = parse_tf_search(f"?tf={dbid}", {ZNF76, DOMAIN})
                self.assertEqual(result.dbid, dbid)
                self.assertEqual(result.message, "")

    def test_invalid_links_do_not_select_an_arbitrary_tf(self):
        for query in [
            "?tf=znf76",
            "?tf=",
            "?tf=ENSDARG99999999999",
            f"?tf={ZNF76}&tf={DOMAIN}",
            f"?tf={ZNF76}&tf={ZNF76}",
            "?tf=%FF",
            "?" + "&".join(["ref=x"] * 101),
        ]:
            with self.subTest(query=query):
                result = parse_tf_search(query, {ZNF76, DOMAIN})
                self.assertIsNone(result.dbid)
                self.assertTrue(result.message)
                self.assertEqual(result.search, query)

    def test_query_without_a_tf_is_an_empty_search(self):
        for query in [None, "", "?ref=publication"]:
            with self.subTest(query=query):
                result = parse_tf_search(query, {ZNF76})
                self.assertIsNone(result.dbid)
                self.assertEqual(result.message, "")

    def test_selection_and_clearing_preserve_unrelated_query_parameters(self):
        self.assertEqual(
            format_tf_search(DOMAIN, f"?ref=paper+one&tf={ZNF76}&ref=paper+two"),
            f"?ref=paper+one&ref=paper+two&tf={DOMAIN}",
        )
        self.assertEqual(format_tf_search(None, f"?tf={ZNF76}"), "")
        self.assertEqual(format_tf_search(None, "?ref=paper&tf=bad"), "?ref=paper")

    def test_a_new_selection_replaces_a_previous_or_invalid_url(self):
        for query in [f"?tf={DOMAIN}", "?tf=%FF"]:
            with self.subTest(query=query):
                result = synchronize_tf_search(
                    ZNF76, query, {ZNF76, DOMAIN}, from_url=False
                )
                self.assertEqual(result.dbid, ZNF76)
                self.assertEqual(result.search, f"?tf={ZNF76}")
                self.assertEqual(result.message, "")


class SearchLinkCallbackTests(unittest.TestCase):
    def setUp(self):
        self.client = dashboard.server.test_client()
        self.callback = next(
            key
            for key in dashboard.app.callback_map
            if "tf-dropdown.value" in key and "url.search" in key
        )

    def sync(
        self,
        dbid,
        search,
        *,
        initialized=True,
        trigger="tf-dropdown.value",
        pathname="/search",
    ):
        return self.client.post(
            "/_dash-update-component",
            json={
                "output": self.callback,
                "outputs": [
                    {"id": "tf-dropdown", "property": "value"},
                    {"id": "url", "property": "search"},
                    {"id": "search-link-state", "property": "data"},
                    {"id": "search-link-message", "property": "children"},
                ],
                "inputs": [
                    {"id": "tf-dropdown", "property": "value", "value": dbid},
                    {"id": "search-url", "property": "search", "value": search},
                ],
                "state": [
                    {"id": "url", "property": "pathname", "value": pathname},
                    {
                        "id": "search-link-state",
                        "property": "data",
                        "value": initialized,
                    },
                ],
                "changedPropIds": [trigger],
            },
        )

    def test_direct_load_and_refresh_restore_the_shared_tf(self):
        for initialized in [None, False]:
            with self.subTest(initialized=initialized):
                response = self.sync(None, f"?tf={ZNF76}", initialized=initialized)
                self.assertEqual(response.status_code, 200)
                result = response.get_json()["response"]
                self.assertEqual(result["tf-dropdown"]["value"], ZNF76)
                self.assertNotIn("url", result)
                self.assertTrue(result["search-link-state"]["data"])

    def test_fresh_selection_wins_over_the_old_url(self):
        response = self.sync(DOMAIN, f"?tf={ZNF76}")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["response"]
        self.assertEqual(result["url"]["search"], f"?tf={DOMAIN}")
        self.assertNotIn("tf-dropdown", result)

    def test_history_navigation_restores_the_previous_tf_without_writing_the_url(self):
        response = self.sync(DOMAIN, f"?tf={ZNF76}", trigger="search-url.search")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["response"]
        self.assertEqual(result["tf-dropdown"]["value"], ZNF76)
        self.assertNotIn("url", result)

    def test_synchronized_echo_does_not_write_either_input_again(self):
        response = self.sync(ZNF76, f"?tf={ZNF76}", trigger="search-url.search")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["response"]
        self.assertNotIn("url", result)
        self.assertNotIn("tf-dropdown", result)

    def test_clearing_selection_removes_the_tf_from_the_link(self):
        response = self.sync(None, f"?tf={ZNF76}")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["response"]
        self.assertEqual(result["url"]["search"], "")
        self.assertNotIn("tf-dropdown", result)

    def test_invalid_navigation_clears_previous_results_and_explains_the_link(self):
        response = self.sync(ZNF76, "?tf=unknown", trigger="search-url.search")
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["response"]
        self.assertIsNone(result["tf-dropdown"]["value"])
        self.assertTrue(result["search-link-message"]["children"])
        self.assertNotIn("url", result)

    def test_leaving_search_cannot_rewrite_navigation(self):
        response = self.sync(
            None, "", trigger="search-url.search", pathname="/downloads"
        )
        self.assertEqual(response.status_code, 204)


if __name__ == "__main__":
    unittest.main()
