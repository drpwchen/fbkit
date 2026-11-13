![Last commit](https://img.shields.io/github/last-commit/drpwchen/fbkit?style=flat-square)
![License](https://img.shields.io/github/license/drpwchen/fbkit?style=flat-square)

# fbkit

Facebook CLI toolkit — posting, scheduling, comments, Messenger, profile
insights, and subscriber tracking, all via GraphQL API + Playwright.
Formerly known as `fbpost`; renamed when it grew past posting
(origin and credits at the [bottom](#credits--origin)).

## Requirements & cost

Python 3.12+ and [uv](https://docs.astral.sh/uv/), on any OS Playwright supports. Free (MIT): no API keys,
no paid services. It acts as **your own Facebook account** using cookies you export from your browser,
so it needs nothing else, and Facebook's own terms apply to what you do with it. See
[SECURITY.md](SECURITY.md) for how the cookies are handled.

## Setup

### 1. Install dependencies and the Playwright browser

```bash
uv sync
uv run playwright install chromium
```

### 2. Export cookies from Chrome

Install a cookie export extension (e.g., [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)):

1. Log in to [facebook.com](https://www.facebook.com) in Chrome
2. Click the cookie extension icon
3. Export cookies as **JSON**
4. Save as `profiles/default/cookies.json`

For fan page profiles, switch to the Page first ("Switch to Page" in Facebook), then export.

### 3. Set up profile config

Create `profiles/default/config.json`:

```json
{
  "pincode": "123456",
  "self_name": "Your Name"
}
```

- `pincode`: Your Messenger E2E encryption PIN (auto-entered during browser automation)
- `self_name`: Your Facebook display name (filters out your own comments)

## Quick Start

```bash
# Post to Facebook
uv run fb post "Hello world"

# List unreplied comments
uv run fb comments

# Reply to a comment
uv run fb reply 0 "Thanks!"

# Send a Messenger message (by name)
uv run fb send Alice "你好"

# Send a Messenger message (by thread ID)
uv run fb send 1234567890123456 "你好"
```

Each command prints its raw result. `fb post` defaults to `--privacy SELF` (only you), so the first
post is a safe rehearsal; it prints the new post's id once Facebook confirms it.

> 🧋 Saved you some time? [Buy me a drink](https://drpwchen.com/en/support/).


## What this version is like to use

**API first, browser only when there is no API.** Posting, photos, scheduling,
audiences, listing your own posts, deleting them, and commenting all go through
Facebook's own GraphQL endpoints — seconds per command, no window opening.
Playwright is still there for what genuinely needs a real browser (login,
Messenger), and every converted command keeps its old browser implementation
behind `--browser` for the day Facebook changes a query.

**It refuses to claim success it did not verify.** A photo post reads back the
id, an audience is re-read from the story Facebook stored, a schedule is
compared against the epoch it kept, a deletion is confirmed by the post being
gone from the library. The recurring bug in this space is a command that
reports success while nothing happened; several of those are fixed here, and
new features are built so the same failure cannot come back quietly.

**Destructive things ask you to prove you mean them.** Deletes resolve the
index in the same run, print what they are about to remove, and abort unless
`--match` text is really in that row — deleting a published post by index
without `--match` is refused outright. During testing that guard caught a
genuinely wrong row.

**Audiences are never guessed.** Subscriber-only sharing is not a privacy
state: it is an account-specific list id, looked up at post time from your own
audience list and keyed on a stable icon rather than a translated label. An
unknown `--privacy` fails instead of falling back to a wider audience.

**It says how it knows.** Every non-obvious payload in the code carries a note
on how it was captured and what breaks if Facebook changes it, and the
CHANGELOG records the real bug behind each fix rather than a version bump.

## Commands

The full reference, with every option and example, is in [docs/commands.md](docs/commands.md).

| Area | Commands |
|---|---|
| Post | `fb post` (text, photos, scheduling, audiences, link-in-comments) |
| Your posts | list, comment on, and delete your own published or scheduled posts |
| Reports | content data report (CSV), profile insights, subscriber snapshots |
| Comments | `fb comments`, `fb reply` |
| Messenger | `fb send`, inbox, read, search, history, contacts, `fb daemon` |
| Login | `fb login` (headed browser) |

How profiles, files and the two engines (GraphQL and Playwright) work:
[docs/reference.md](docs/reference.md).

## Limitations

- No sandbox: every command acts on a real, live account. Rehearse with `--privacy SELF` first.
- There is no official API behind it. It uses Facebook's internal GraphQL endpoints and a browser
  for login and Messenger, so a Facebook change can break a command until the doc IDs or selectors
  are updated.
- The browser-driven flows target the Traditional Chinese (zh-TW) Facebook UI (see Notes).
- Cookies expire; re-export them (or run `fb login`) when Facebook logs the session out.
- Published posts cannot be recovered after `post-delete`.

## Related tools

[openevidence-tools](https://github.com/drpwchen/openevidence-tools) and
[deja-browser](https://github.com/drpwchen/deja-browser) are other browser-driving tools from the same author;
[claude-pacer](https://github.com/drpwchen/claude-pacer) keeps long agent runs inside usage limits.

## Notes

- **The browser-driven flows (`--image` posts, scheduled-post list/comment/delete, `fb report`) target Facebook's Traditional Chinese (zh-TW) UI** — their selectors are zh-TW labels. If your Facebook display language isn't 繁體中文, those flows will fail at the first zh-TW-labeled step. `fb post` (including `--schedule` and `--comment`), `fb comment`, `fb comments`, and `fb reply` are pure GraphQL and language-independent.
- GraphQL doc IDs in `fb_config.py` may change when Facebook deploys new frontend code. Update them when requests start returning errors.
- E2E threads use the URL path `/messages/e2ee/t/<id>/` automatically for numeric thread IDs > 15 digits.
- Send defaults to headed mode. Use `--headless` only after verifying your E2E PIN session is active.
- Contact names support fuzzy matching — partial names work if they match exactly one contact.

---

## 🌱 Start here if you're new to AI agents ／ AI agent 新手起點

This tool is one piece of my personal AI workflow. If you want to learn how to use AI agents like Claude Code from zero (no programming background needed), I wrote a beginner series (in Traditional Chinese):

這個工具是我個人 AI 工作流的一部分。想從零開始學怎麼用 Claude Code 這類 AI agent（不需要程式背景），可以從我的入門系列開始：

1. [從零開始：安裝、看懂 GitHub、跑起你的第一個工具](https://drpwchen.com/posts/getting-started/)
2. [怎麼跟 AI agent 講話：心法、元技能與規則檔](https://drpwchen.com/posts/talking-to-agents/)
3. [自動化流程不是設計出來的，是長出來的](https://drpwchen.com/posts/growing-your-workflow/)

Full map of my tools and posts ／ 所有工具與文章的全貌 → [drpwchen.com/map](https://drpwchen.com/map/)

---

## Support 支持

If this tool helped you, you can [buy me a drink](https://drpwchen.com/en/support/) 🧋
覺得這個工具有幫助嗎？歡迎[請我喝飲料](https://drpwchen.com/support/)。

---

## Credits & origin

**Originally forked from [htlin222/fbpost](https://github.com/htlin222/fbpost)** —
all credit for the original design and the GraphQL groundwork goes to
[@htlin222](https://github.com/htlin222), and this project stays MIT-licensed
with their copyright intact. It has been maintained here as a standalone
project since July 2026 (upstream inactive since March 2026), and renamed
`fbkit` in August 2026 once it covered far more than posting. On top of the
original it added photo/scheduled posts via pure GraphQL, link-in-comments,
Content Library post management, the CSV report exporter, profile insights,
subscriber tracking, and a reliability sweep (honest send verification,
wrong-contact guards, daemon-safe teardown). The early fixes were offered
upstream as [PR #1](https://github.com/htlin222/fbpost/pull/1) and
[PR #2](https://github.com/htlin222/fbpost/pull/2); they were closed unmerged
in July 2026 — anyone is welcome to take them from here.
