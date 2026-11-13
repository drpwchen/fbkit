"""Which feedback object a top-level comment goes to (v0.12.1).

Facebook stopped accepting `feedback:<post_id>` (2026-10-31 … 11-13); a post's
story now reports its own feedback as `feedback:pfbid…`. These tests pin the
resolution order without touching Facebook: every network call is mocked.

    uv run python -m unittest discover -s tests -v
"""
import argparse
import base64
import unittest
from unittest import mock

from scripts import fb, fb_session


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


PFBID = "pfbid0AbCdEfGhIjKlMnOpQrStUvWxYz123456789"
POST_FB = b64(f"feedback:{PFBID}")              # the post's own feedback
COMMENT_FB = b64("feedback:pfbid0ZzzOtherOneForTheComment")  # a comment's feedback
LEGACY = b64("feedback:111222333")
STORY_ID = b64("S:_I100:111222333")


def story_response(post_fb=POST_FB, comment_fb=COMMENT_FB):
    """Shape of CometFocusedStoryViewStoryQuery, only the id fields kept."""
    return {"data": {"node": {
        "id": STORY_ID,
        "feedback": {"id": post_fb} if post_fb else None,
        "comet_sections": {"feedback": {"story": {"feedback_context": {
            "interesting_top_level_comments": [
                {"comment": {"feedback": {"id": comment_fb}}},
            ],
        }}}},
    }}}


def ok_response(text):
    return {"data": {"comment_create": {"feedback_comment_edge": {
        "node": {"id": "c1", "preferred_body": {"text": text}}}}}}


class DecodeTests(unittest.TestCase):
    def test_post_feedback_formats(self):
        self.assertEqual(fb_session.decode_post_feedback_id(POST_FB), f"feedback:{PFBID}")
        self.assertEqual(fb_session.decode_post_feedback_id(LEGACY), "feedback:111222333")

    def test_rejects_comment_feedback_and_junk(self):
        self.assertEqual(fb_session.decode_post_feedback_id(b64("feedback:111_222")), "")
        self.assertEqual(fb_session.decode_post_feedback_id(STORY_ID), "")
        self.assertEqual(fb_session.decode_post_feedback_id("not base64 !!"), "")
        self.assertEqual(fb_session.decode_post_feedback_id(None), "")

    def test_story_node_feedback_is_the_post_not_a_comment(self):
        self.assertEqual(fb_session.story_node_feedback_id(story_response()), POST_FB)

    def test_story_without_node_feedback(self):
        self.assertIsNone(fb_session.story_node_feedback_id(story_response(post_fb=None)))
        self.assertIsNone(fb_session.story_node_feedback_id({"data": {"node": None}}))
        self.assertIsNone(fb_session.story_node_feedback_id({"errors": [{}]}))

    def test_story_with_comment_style_node_feedback_is_refused(self):
        bad = story_response(post_fb=b64("feedback:111_222"))
        self.assertIsNone(fb_session.story_node_feedback_id(bad))

    def test_fetch_story_feedback_id(self):
        with mock.patch.object(fb_session, "graphql_request", return_value=story_response()) as gq:
            self.assertEqual(fb_session.fetch_story_feedback_id("s", {}, "100", STORY_ID), POST_FB)
        self.assertEqual(gq.call_args.args[5]["storyID"], STORY_ID)

    def test_fetch_story_feedback_id_survives_failures(self):
        with mock.patch.object(fb_session, "graphql_request", side_effect=SystemExit(1)):
            self.assertIsNone(fb_session.fetch_story_feedback_id("s", {}, "100", STORY_ID))
        with mock.patch.object(fb_session, "graphql_request", side_effect=ConnectionError()):
            self.assertIsNone(fb_session.fetch_story_feedback_id("s", {}, "100", STORY_ID))
        self.assertIsNone(fb_session.fetch_story_feedback_id("s", {}, "100", ""))


class AsFeedbackIdTests(unittest.TestCase):
    def test_inputs(self):
        self.assertEqual(fb._as_feedback_id(POST_FB), POST_FB)
        self.assertEqual(fb._as_feedback_id(PFBID), POST_FB)
        self.assertEqual(fb._as_feedback_id("111222333"), LEGACY)
        self.assertEqual(fb._as_feedback_id(STORY_ID), "")
        self.assertEqual(fb._as_feedback_id(b64("feedback:111_222")), "")
        self.assertEqual(fb._as_feedback_id(""), "")


class CreateCommentTests(unittest.TestCase):
    def setUp(self):
        patches = [mock.patch.object(fb.time, "sleep")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_create(self, story_side_effect, try_results, **kw):
        """Returns the feedback ids _try_comment was called with."""
        with mock.patch.object(fb, "fetch_story_feedback_id", side_effect=story_side_effect) as story, \
             mock.patch.object(fb, "_try_comment", side_effect=try_results) as tc:
            fb._create_comment("s", {}, "100", kw.pop("post_id", "111222333"), "hi", **kw)
        self.story_calls = story.call_count
        return [c.args[3] for c in tc.call_args_list]

    def test_story_feedback_is_used(self):
        used = self.run_create([POST_FB], [(True, {})], story_id=STORY_ID)
        self.assertEqual(used, [POST_FB])

    def test_story_not_readable_yet_then_readable(self):
        used = self.run_create([None, POST_FB], [(False, {}), (True, {})], story_id=STORY_ID)
        self.assertEqual(used, [LEGACY, POST_FB])

    def test_story_resolved_once_is_reused(self):
        used = self.run_create([POST_FB], [(False, {}), (True, {})], story_id=STORY_ID)
        self.assertEqual(used, [POST_FB, POST_FB])
        self.assertEqual(self.story_calls, 1)

    def test_no_story_falls_back_to_legacy(self):
        used = self.run_create([], [(True, {})])
        self.assertEqual(used, [LEGACY])
        self.assertEqual(self.story_calls, 0)

    def test_explicit_feedback_id_skips_story(self):
        used = self.run_create([], [(True, {})], feedback_id=POST_FB, story_id=STORY_ID)
        self.assertEqual(used, [POST_FB])
        self.assertEqual(self.story_calls, 0)

    def test_pfbid_as_post_id(self):
        # ~/.claude fb_comment_feedback.py passes the decoded pfbid as post_id.
        used = self.run_create([], [(True, {})], post_id=PFBID)
        self.assertEqual(used, [POST_FB])

    def test_base64_feedback_as_post_id(self):
        used = self.run_create([], [(True, {})], post_id=POST_FB)
        self.assertEqual(used, [POST_FB])

    def test_invalid_target_exits_before_commenting(self):
        with self.assertRaises(SystemExit):
            self.run_create([], [], post_id=b64("feedback:111_222"))

    def test_all_attempts_fail_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_create([POST_FB], [(False, {})] * 3, story_id=STORY_ID)
        self.assertEqual(cm.exception.code, 1)


class TryCommentTests(unittest.TestCase):
    def test_feedback_id_sent_verbatim(self):
        with mock.patch.object(fb, "graphql_request", return_value=ok_response("hi")) as gq:
            ok, _ = fb._try_comment("s", {}, "100", POST_FB, "hi")
        self.assertTrue(ok)
        self.assertEqual(gq.call_args.args[5]["input"]["feedback_id"], POST_FB)

    def test_no_blind_success(self):
        with mock.patch.object(fb, "graphql_request", return_value={"data": {}}):
            ok, _ = fb._try_comment("s", {}, "100", POST_FB, "hi")
        self.assertFalse(ok)


class CmdCommentTests(unittest.TestCase):
    def run_cmd(self, arg, story_lookup=""):
        args = argparse.Namespace(post_id=arg, text="hi", profile="default")
        with mock.patch.object(fb, "load_cookies", return_value={"actor_id": "100"}), \
             mock.patch.object(fb, "create_session", return_value="s"), \
             mock.patch.object(fb, "fetch_tokens", return_value={}), \
             mock.patch.object(fb, "_story_id_for_post", return_value=story_lookup) as look, \
             mock.patch.object(fb, "_create_comment") as cc:
            fb.cmd_comment(args)
        return look, cc.call_args

    def test_pfbid(self):
        look, call = self.run_cmd(PFBID)
        look.assert_not_called()
        self.assertEqual(call.kwargs["feedback_id"], POST_FB)

    def test_base64_feedback_id(self):
        look, call = self.run_cmd(POST_FB)
        look.assert_not_called()
        self.assertEqual(call.kwargs["feedback_id"], POST_FB)

    def test_numeric_post_id_reads_story_from_library(self):
        look, call = self.run_cmd("111222333", story_lookup=STORY_ID)
        look.assert_called_once()
        self.assertEqual(call.args[3], "111222333")
        self.assertEqual(call.kwargs["story_id"], STORY_ID)
        self.assertEqual(call.kwargs["feedback_id"], "")

    def test_story_id_is_read_directly(self):
        look, call = self.run_cmd(STORY_ID)
        look.assert_not_called()
        self.assertEqual(call.args[3], "111222333")
        self.assertEqual(call.kwargs["story_id"], STORY_ID)

    def test_comment_feedback_is_not_accepted_as_target(self):
        with self.assertRaises(SystemExit):
            self.run_cmd(b64("feedback:111_222"))


class CallSiteTests(unittest.TestCase):
    def test_comment_on_scheduled_passes_row_story_id(self):
        row = {"post_id": "111222333", "story_id": STORY_ID, "scheduled": 0, "when_text": "x"}
        with mock.patch.object(fb, "_find_scheduled_row", return_value=row), \
             mock.patch.object(fb, "_create_comment") as cc:
            fb._comment_on_scheduled("s", {}, "100", "hi", "2026-11-20 07:00")
        self.assertEqual(cc.call_args.kwargs["story_id"], STORY_ID)

    def test_comment_scheduled_passes_row_story_id(self):
        row = {"post_id": "111222333", "story_id": STORY_ID, "scheduled": 0,
               "when_text": "x", "text": "post"}
        args = argparse.Namespace(browser=False, index=1, match="post", text="hi")
        with mock.patch.object(fb, "_fetch_rows", return_value=("s", {}, "100", [row])), \
             mock.patch.object(fb, "_pick_row", return_value=row), \
             mock.patch.object(fb, "_create_comment") as cc:
            fb.cmd_comment_scheduled(args)
        self.assertEqual(cc.call_args.kwargs["story_id"], STORY_ID)

    def test_story_id_for_post(self):
        rows = {"PUBLISHED": [{"post_id": "9", "story_id": "x"}],
                "SCHEDULED": [{"post_id": "111222333", "story_id": STORY_ID}]}
        with mock.patch.object(fb, "fetch_content_library",
                               side_effect=lambda s, t, a, f, limit: rows[f]):
            self.assertEqual(fb._story_id_for_post("s", {}, "100", "111222333"), STORY_ID)
            self.assertEqual(fb._story_id_for_post("s", {}, "100", "404"), "")


if __name__ == "__main__":
    unittest.main()
