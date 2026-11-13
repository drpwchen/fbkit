# fbkit reference: profiles, files, how it works

Back to the [README](../README.md).

## Cookie Profiles

```
profiles/
├── default/
│   ├── cookies.json        # personal profile (cookie extension export)
│   ├── config.json         # pincode, self_name
│   ├── contacts.json       # cached Messenger contacts (auto-generated)
│   └── storage_state.json  # auto-saved by Playwright
└── fanpage/
    └── cookies.json        # exported while in "Switch to Page" mode
```

## Files

| File | Purpose |
|------|---------|
| `scripts/fb.py` | Main CLI — all subcommands |
| `scripts/fb_session.py` | Session management, cookies, tokens, GraphQL helpers |
| `scripts/fb_config.py` | GraphQL doc IDs (update when Facebook changes them) |
| `scripts/fb_browser.py` | Playwright browser context, cookie injection, stealth, PIN handling |
| `scripts/fb_messenger.py` | Messenger operations — send, read, search, contacts, history |
| `scripts/post.py` | Standalone post script (legacy) |

## How It Works

### GraphQL API (post, photos, listing, deleting, comments, reply)

- Loads cookies from `profiles/<name>/cookies.json`
- Uses `i_user` cookie as actor ID for fan page profiles, `c_user` for personal
- Fetches CSRF tokens (`fb_dtsg`, `lsd`, etc.) from Facebook homepage
- Auto-detects `pageID` from the Professional Dashboard page
- Uses Facebook's internal GraphQL API (`/api/graphql/`) with Relay doc IDs
- Reads deferred responses in full: the Content Library streams its table as
  later chunks of one response, so those queries collect every chunk instead of
  the first one

### Playwright Browser Automation (login, messenger)

- Injects cookies into a Chromium browser context
- Applies stealth settings to avoid detection
- Auto-enters E2E encryption PIN from `config.json`
- Pre-send verification: confirms text is in input box before pressing Enter
- Handles Messenger's virtualized DOM by scrolling and collecting incrementally
- Saves browser state (`storage_state.json`) for faster subsequent runs
