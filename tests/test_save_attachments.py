"""_wait_for_attachments must not scan before large E2EE files finish decrypting.

Run: uv run python -m unittest discover -s tests -t .
"""

import asyncio
import unittest
from unittest import mock

from scripts import fb_messenger


def _f(n):
    return {"href": f"blob:https://www.messenger.com/{n}", "name": f"{n}.pptx"}


class FakePage:
    """Returns one scripted scan per poll; repeats the last one afterwards."""

    def __init__(self, scans):
        self.scans = list(scans)
        self.polls = 0

    async def evaluate(self, _js):
        i = min(self.polls, len(self.scans) - 1)
        self.polls += 1
        return self.scans[i]

    async def wait_for_timeout(self, _ms):
        pass


def run(page, **kw):
    with mock.patch("builtins.print"):
        return asyncio.run(fb_messenger._wait_for_attachments(page, **kw))


class WaitForAttachments(unittest.TestCase):
    def test_waits_for_pending_large_file(self):
        # small file ready at once; big file pending for 3 polls, then ready
        page = FakePage([
            {"ready": [_f("a")], "pending": 1},
            {"ready": [_f("a")], "pending": 1},
            {"ready": [_f("a")], "pending": 1},
            {"ready": [_f("a"), _f("big")], "pending": 0},
        ])
        files = run(page, settle=3)
        self.assertEqual([f["name"] for f in files], ["a.pptx", "big.pptx"])

    def test_waits_for_blob_that_appears_without_placeholder(self):
        # no pending marker at all, the big blob just shows up later
        page = FakePage([
            {"ready": [_f("a")], "pending": 0},
            {"ready": [_f("a"), _f("big")], "pending": 0},
        ])
        files = run(page, settle=3)
        self.assertEqual(len(files), 2)
        self.assertGreaterEqual(page.polls, 4)  # 2 changes + 2 stable repeats

    def test_stable_settles_after_settle_polls(self):
        page = FakePage([{"ready": [_f("a")], "pending": 0}])
        run(page, settle=3)
        self.assertEqual(page.polls, 3)

    def test_timeout_returns_ready_and_warns(self):
        page = FakePage([{"ready": [_f("a")], "pending": 1}])
        fake_time = mock.Mock(monotonic=mock.Mock(side_effect=[0, 0, 0, 999]))
        with mock.patch.object(fb_messenger, "time", fake_time):
            files = run(page, timeout_s=10)
        self.assertEqual(len(files), 1)

    def test_no_attachments(self):
        page = FakePage([{"ready": [], "pending": 0}])
        self.assertEqual(run(page, settle=2), [])


if __name__ == "__main__":
    unittest.main()
