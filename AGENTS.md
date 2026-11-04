# Working on Taskwell

See `CLAUDE.md`. The Mac app in `Taskwell mac app/` is a window around the web
page at jessieebie.github.io/taskwell, built with py2app, so it carries its own
Python and needs none installed.

## Moving between Macs

Jessie works on more than one Mac. `~/Documents` syncs through iCloud, so
projects and anything saved in Documents move on their own; `~/Library`,
`/Applications`, and the Keychain do not. The account name differs between Macs
(`jessieebie` and `jessicaebie`), so never save or hardcode a full home path.
Every app has exactly one installed copy, in `/Applications/Jessie Apps`.

Tasks sync through Supabase once you sign in, so nothing needs copying. The app's
web storage in `~/Library/Application Support/Taskwell` stays on each Mac; keep
anything that must follow Jessie in Supabase, not `localStorage`. `dist/` is build
output; install the finished app to `/Applications/Jessie Apps` and don't leave a
second copy.
