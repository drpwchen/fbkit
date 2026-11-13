# Security policy

fbkit acts as your own Facebook account. Its profile folders hold session cookies, an optional
Messenger E2EE PIN and subscriber snapshots, so a leak is serious.

## Reporting a vulnerability

Please report it privately through GitHub: the repository's **Security** tab, then **Report a
vulnerability**. Do not open a public issue for it.

Useful in a report: the version, the command you ran, and what happened. Never attach cookies,
the contents of `profiles/`, or real names from a subscriber snapshot; use invented data.

## What counts

- Any path where cookies, the PIN, tokens or subscriber names are printed, logged, committed or
  sent anywhere other than facebook.com.
- A command that acts on a wider audience than the one requested, or deletes something the
  `--match` guard should have refused.

## Handling your own data

`profiles/<name>/` is gitignored. Keep it that way, and do not paste its contents into chats,
issues or logs.

## Supported versions

Only the latest release receives fixes.
