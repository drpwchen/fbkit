"""Which date range each Content Library tab is read with (v0.12.4).

Since 2026-11 Facebook applies `routeDateRange` to the Scheduled tab too; a
scheduled post is in the future, so "last N days" returned an empty table and
`post-list-scheduled` said `No scheduled posts.`. These tests pin the request
variables without touching Facebook: the GraphQL call is mocked.

    uv run python -m unittest discover -s tests -t . -v
"""
import base64
import unittest
from unittest import mock

from scripts import fb_session


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def table_chunk(post_ids, has_next=False, cursor=None):
    """The deferred chunk that carries the table, only the fields we read."""
    edges = [{"node": {
        "title": f"post {pid}", "timestamp_text": "",
        "story": {"id": b64(f"S:_I100:{pid}"), "scheduled_publish_time": 1795388400,
                  "unpublished_content_type": "SCHEDULED"},
    }} for pid in post_ids]
    return {"data": {"id": "PAGE1", "prodash_content_library": {
        "edges": edges, "page_info": {"has_next_page": has_next, "end_cursor": cursor}}}}


class DateRangeTests(unittest.TestCase):
    def fetch(self, filtering, responses, **kwargs):
        with mock.patch.object(fb_session, "graphql_chunks", side_effect=responses) as gql:
            rows = fb_session.fetch_content_library(
                object(), {}, "100", filtering, **kwargs)
        return rows, [call.args[5] for call in gql.call_args_list]

    def test_scheduled_is_read_without_a_date_range(self):
        rows, sent = self.fetch("SCHEDULED", [[{"data": {}}, table_chunk(["111"])]])
        self.assertEqual([r["post_id"] for r in rows], ["111"])
        self.assertEqual(sent[0]["routeFilter"], "SCHEDULED")
        self.assertIsNone(sent[0]["routeDateRange"])

    def test_scheduled_ignores_an_explicit_date_range(self):
        _, sent = self.fetch("SCHEDULED", [[table_chunk([])]], date_range="LAST_90D")
        self.assertIsNone(sent[0]["routeDateRange"])

    def test_scheduled_pagination_has_no_date_range_either(self):
        rows, sent = self.fetch(
            "SCHEDULED",
            [[table_chunk(["1"], has_next=True, cursor="CUR")], [table_chunk(["2"])]],
            limit=5)
        self.assertEqual([r["post_id"] for r in rows], ["1", "2"])
        self.assertEqual(sent[1]["filteringOption"], "SCHEDULED")
        self.assertIsNone(sent[1]["dateRange"])
        self.assertEqual(sent[1]["id"], "PAGE1")

    def test_published_keeps_its_date_range(self):
        _, sent = self.fetch("PUBLISHED", [[table_chunk(["9"])]], date_range="LAST_7D")
        self.assertEqual(sent[0]["routeDateRange"], "LAST_7D")
        _, sent = self.fetch("PUBLISHED", [[table_chunk(["9"])]])
        self.assertEqual(sent[0]["routeDateRange"], "LAST_28D")


if __name__ == "__main__":
    unittest.main()
