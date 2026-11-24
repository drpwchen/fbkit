"""`fb post --video` (v0.13.0): flag checks, the three-step upload, the
processing wait, and the mutation payload. Every network call is mocked.

    uv run python -m unittest discover -s tests -t .
"""
import argparse
import json
import os
import tempfile
import unittest
from unittest import mock

from scripts import fb, fb_session


def post_args(**kw):
    base = dict(
        text="hello", privacy="SELF", image=None, video=None, schedule=None,
        comment=None, group=None, composer=False, headless=False,
        profile="default",
    )
    base.update(kw)
    return argparse.Namespace(**base)


class TempVideo:
    """A real file on disk with a video extension (content is irrelevant)."""

    def __init__(self, ext=".mp4", size=3000):
        self.ext, self.size = ext, size

    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=self.ext)
        with os.fdopen(fd, "wb") as fh:
            fh.write(b"\0" * self.size)
        return self.path

    def __exit__(self, *exc):
        os.remove(self.path)


class VideoFlagTests(unittest.TestCase):
    def test_no_video_is_fine(self):
        self.assertIsNone(fb.video_flag_error(post_args()))

    def test_plain_video_is_fine(self):
        with TempVideo() as path:
            self.assertIsNone(fb.video_flag_error(post_args(video=path)))

    def test_video_with_schedule_is_fine(self):
        with TempVideo() as path:
            self.assertIsNone(fb.video_flag_error(
                post_args(video=path, schedule="2030-01-01 09:00")))

    def test_refused_combinations(self):
        with TempVideo() as path:
            for kw in ({"image": ["a.jpg"]}, {"group": "123"}, {"composer": True}):
                with self.subTest(kw=kw):
                    self.assertIsNotNone(fb.video_flag_error(post_args(video=path, **kw)))

    def test_missing_file(self):
        self.assertIn("not found", fb.video_flag_error(post_args(video="nope.mp4")))

    def test_unsupported_extension(self):
        with TempVideo(ext=".avi") as path:
            self.assertIn("unsupported", fb.video_flag_error(post_args(video=path)))


def story_with_video(status, duration):
    """Shape of CometFocusedStoryViewStoryQuery, only the video fields kept."""
    return {"data": {"node": {"attachments": [{
        "media": {"__typename": "Video"},
        "styles": {"attachment": {"media": {
            "video_status_type": status,
            "playable_duration_in_ms": duration,
        }}},
    }]}}}


class VideoStatusTests(unittest.TestCase):
    def test_reads_status_and_duration(self):
        self.assertEqual(
            fb_session.story_video_status(story_with_video("OK", 30000)), ("OK", 30000))

    def test_no_video_attachment(self):
        self.assertEqual(fb_session.story_video_status({"data": {"node": {}}}), (None, None))
        self.assertEqual(fb_session.story_video_status(None), (None, None))

    def test_ready_rules(self):
        ready = fb_session.video_ready
        self.assertTrue(ready("OK", 30000))
        self.assertFalse(ready("UNDISCOVERABLE", 30000))           # published: not yet
        self.assertTrue(ready("UNDISCOVERABLE", 30000, scheduled=True))
        self.assertFalse(ready("UNDISCOVERABLE", None, scheduled=True))
        self.assertFalse(ready(None, None, scheduled=True))

    def test_wait_polls_until_ok(self):
        answers = iter([None, story_with_video("PROCESSING", None), story_with_video("OK", 5000)])
        with mock.patch.object(fb_session, "fetch_story", side_effect=lambda *a: next(answers)), \
             mock.patch.object(fb_session.time, "sleep"):
            result = fb_session.wait_for_story_video(None, {}, "1", "S", timeout=300, interval=1)
        self.assertEqual(result, (True, "OK", 5000))

    def test_wait_gives_up(self):
        clock = iter(range(0, 10_000, 100))
        with mock.patch.object(fb_session, "fetch_story", return_value=None), \
             mock.patch.object(fb_session.time, "sleep"), \
             mock.patch.object(fb_session.time, "time", side_effect=lambda: next(clock)):
            ready, status, _ = fb_session.wait_for_story_video(
                None, {}, "1", "S", timeout=300, interval=10)
        self.assertFalse(ready)
        self.assertIsNone(status)


class FakeResp:
    def __init__(self, payload, status=200, prefix=True):
        self.status_code = status
        body = json.dumps(payload)
        self.text = ("for (;;);" + body) if prefix else body


class FakeSession:
    """Records each POST; answers start/rupload/receive from a script."""

    def __init__(self, receive_offsets, size):
        self.headers = {"Content-Type": "application/x-www-form-urlencoded",
                        "X-FB-Friendly-Name": "Leftover"}
        self.calls = []
        self.receive_offsets = list(receive_offsets)
        self.size = size

    def post(self, url, params=None, data=None, headers=None, **kw):
        # The GraphQL leftovers must not ride along on any upload request.
        assert "Content-Type" not in self.headers, url
        assert "X-FB-Friendly-Name" not in self.headers, url
        body_len = None
        if hasattr(data, "read"):
            body_len = len(data.read())
        self.calls.append({"url": url, "params": params, "data": data,
                           "headers": headers, "body_len": body_len})
        if url.endswith("/start/"):
            return FakeResp({"payload": {"video_id": "V1", "upload_session_id": "U1",
                                         "start_offset": 0, "end_offset": 1048576,
                                         "skip_upload": False}})
        if "rupload" in url:
            return FakeResp({"h": "1:handle"}, prefix=False)
        offset = self.receive_offsets.pop(0)
        return FakeResp({"payload": {"start_offset": offset, "end_offset": self.size}})


TOKENS = {"fb_dtsg": "DTSG", "jazoest": "J", "lsd": "L"}


class UploadVideoTests(unittest.TestCase):
    def test_three_steps_and_headers_restored(self):
        with TempVideo(size=3000) as path:
            s = FakeSession([3000], 3000)
            vid = fb_session.upload_video(s, TOKENS, "42", path)
        self.assertEqual(vid, "V1")
        kinds = [("start" if c["url"].endswith("/start/") else
                  "rupload" if "rupload" in c["url"] else "receive") for c in s.calls]
        self.assertEqual(kinds, ["start", "rupload", "receive"])
        start, rup, recv = s.calls
        self.assertEqual(start["data"]["file_size"], "3000")
        self.assertEqual(start["data"]["file_extension"], "mp4")
        self.assertEqual(rup["params"]["fb_dtsg"], "DTSG")      # auth lives in the query
        self.assertEqual(rup["headers"]["Offset"], "0")
        self.assertEqual(rup["headers"]["product_media_id"], "V1")
        self.assertEqual(rup["headers"]["id"], "U1")
        self.assertEqual(rup["body_len"], 3000)
        self.assertEqual(recv["data"]["fbuploader_video_file_chunk"], "1:handle")
        self.assertEqual(recv["data"]["video_id"], "V1")
        # restored for the GraphQL calls that follow
        self.assertEqual(s.headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertEqual(s.headers["X-FB-Friendly-Name"], "Leftover")

    def test_resumes_from_reported_offset(self):
        with TempVideo(size=3000) as path:
            s = FakeSession([1000, 3000], 3000)
            fb_session.upload_video(s, TOKENS, "42", path)
        ruploads = [c for c in s.calls if "rupload" in c["url"]]
        self.assertEqual([c["headers"]["Offset"] for c in ruploads], ["0", "1000"])
        self.assertEqual([c["body_len"] for c in ruploads], [3000, 2000])

    def test_no_progress_exits(self):
        with TempVideo(size=3000) as path:
            s = FakeSession([0], 3000)
            with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
                fb_session.upload_video(s, TOKENS, "42", path)


class CmdPostVideoTests(unittest.TestCase):
    """cmd_post wiring: attachment shape, schedule fields, the processing gate."""

    def run_post(self, wait_result, **kw):
        sent = {}

        def fake_graphql(session, tokens, actor_id, doc_id, name, variables):
            sent["variables"] = variables
            return {"data": {"story_create": {"post_id": "P1", "story_id": "S1"}}}

        with TempVideo() as path, \
             mock.patch.object(fb, "load_cookies", return_value={"actor_id": "42"}), \
             mock.patch.object(fb, "create_session", return_value=mock.Mock()), \
             mock.patch.object(fb, "fetch_tokens", return_value=dict(TOKENS)), \
             mock.patch.object(fb, "resolve_privacy_row", return_value={"base_state": "SELF", "allow": []}), \
             mock.patch.object(fb, "upload_video", return_value="V9") as up, \
             mock.patch.object(fb, "wait_for_story_video", return_value=wait_result) as wait, \
             mock.patch.object(fb, "graphql_request", side_effect=fake_graphql), \
             mock.patch.object(fb, "_parse_schedule", return_value=1_900_000_000), \
             mock.patch("builtins.print"):
            fb.cmd_post(post_args(video=path, **kw))
        return sent["variables"], up, wait

    def test_immediate_video_post(self):
        variables, up, wait = self.run_post((True, "OK", 30000))
        self.assertEqual(variables["input"]["attachments"],
                         [{"video": {"id": "V9", "notify_when_processed": True}}])
        self.assertNotIn("unpublished_content_data", variables["input"])
        up.assert_called_once()
        self.assertFalse(wait.call_args.kwargs["scheduled"])

    def test_scheduled_video_post(self):
        variables, _, wait = self.run_post(
            (True, "UNDISCOVERABLE", 30000), schedule="2030-01-01 09:00")
        self.assertEqual(variables["input"]["unpublished_content_data"]["unpublished_content_type"],
                         "SCHEDULED")
        self.assertTrue(wait.call_args.kwargs["scheduled"])

    def test_unprocessed_video_exits_nonzero(self):
        with self.assertRaises(SystemExit) as cm, mock.patch("sys.stderr"):
            self.run_post((False, None, None))
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
